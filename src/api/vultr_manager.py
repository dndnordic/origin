"""
Origin Vultr Manager

This module enables Origin to manage its own infrastructure on Vultr.
It provides capabilities for self-provisioning, scaling, and infrastructure management.
"""

import os
import json
import time
import logging
import requests
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

# Import Vultr Python Client
try:
    import vultr  # Official Vultr Python client
    VULTR_CLIENT_AVAILABLE = True
except ImportError:
    VULTR_CLIENT_AVAILABLE = False
    
from src.security.vault_manager import SecretVault
from src.api.vultr_api import VultrAPIManager
from src.api.vultr_inference_api import InferenceManager

logger = logging.getLogger(__name__)

class VultrSelfManager:
    """
    Enables Origin to manage its own infrastructure on Vultr.
    This class provides self-management capabilities including:
    - Provisioning new instances
    - Scaling resources based on demand
    - Managing its own storage and persistence
    - Handling backups and disaster recovery
    """
    
    def __init__(self, config_path: Optional[str] = None, vault: Optional[SecretVault] = None):
        """
        Initialize the Vultr Self-Manager with access to the vault for credentials
        
        Args:
            config_path: Path to configuration file
            vault: Secret vault instance (will create a new one if not provided)
        """
        self.config = self._load_config(config_path)
        self.vault = vault
        
        # Tracks the current infrastructure state
        self.current_state = {
            "instances": {},
            "database_backups": [],
            "container_images": {},
            "last_health_check": None,
            "pending_approvals": [],
            "resources": {
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "storage_usage": 0.0,
                "network_usage": 0.0
            }
        }
        
        # Initialize API managers with access to the vault
        self.api_manager = None
        self.inference_manager = None
        
        # Vultr official client (preferred if available)
        self.vultr_client = None
        
        # Resource approval system
        self.require_approval = self.config.get('require_approval', True)
        self.approval_status = {}
        
        logger.info("Vultr Self-Manager initialized")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """
        Load configuration from file or default locations
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            Dict containing configuration
        """
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Check common config locations
        config_locations = [
            '/app/config/vultr-api-config.json',
            '/data/config/vultr-api-config.json',
            os.path.join(os.path.dirname(__file__), '..', 'config', 'vultr-api-config.json')
        ]
        
        for location in config_locations:
            if os.path.exists(location):
                with open(location, 'r') as f:
                    return json.load(f)
        
        # Return default configuration
        return {
            "infrastructure": {
                "initial_instances": 1,
                "max_instances": 3,
                "min_instances": 1,
                "instance_type": "vc2-1c-1gb",
                "region": "ewr",
                "auto_scale": True,
                "scale_up_threshold": 0.8,
                "scale_down_threshold": 0.2,
                "backup": {
                    "enabled": True,
                    "frequency_hours": 24,
                    "retention_days": 7
                },
                "cost_controls": {
                    "monthly_budget": 50,  # USD
                    "alert_threshold": 0.8,  # 80% of budget
                    "require_approval": True,  # Require Mikael's approval for resources that cost money
                    "auto_approve_under": 5  # Auto-approve resources under $5
                }
            },
            "vault": {
                "access": {
                    "enabled": True,
                    "token_name": "vultr_api_credentials"
                }
            },
            "approvals": {
                "admin_user": "mikael",
                "notification_email": "mikael@dndnordic.com",
                "auto_cancel_after": 72,  # Hours
                "resources_requiring_approval": [
                    "instance", "block_storage", "load_balancer", "kubernetes"
                ]
            }
        }
    
    def initialize(self) -> bool:
        """
        Initialize the Vultr infrastructure manager, retrieving credentials from the vault
        
        Returns:
            True if initialization was successful
        """
        # Get session with the vault
        vault_session = self._get_vault_session()
        if not vault_session:
            logger.error("Failed to get vault session")
            return False
        
        # Get Vultr API credentials from vault
        vultr_credentials = self._get_vultr_credentials(vault_session)
        if not vultr_credentials:
            logger.error("Failed to get Vultr API credentials from vault")
            return False
        
        # Initialize API managers with credentials
        try:
            api_key = vultr_credentials.get('api_key')
            
            # Prefer the official Vultr Python client if available
            if VULTR_CLIENT_AVAILABLE:
                self.vultr_client = vultr.Vultr(api_key)
                logger.info("Using official Vultr Python client")
            else:
                logger.warning("Official Vultr Python client not available. Using custom implementation.")
                
            # Initialize custom API manager as fallback or secondary option
            self.api_manager = VultrAPIManager(api_key=api_key)
            
            # Initialize inference manager
            self.inference_manager = InferenceManager(
                vultr_url=vultr_credentials.get('inference_url', 'https://api.vultrinference.com/v1'),
                vultr_key=vultr_credentials.get('inference_key')
            )
            
            # Initial sync with Vultr to get current state
            self._sync_state()
            
            # Load pending approvals
            self._load_pending_approvals()
            
            logger.info("Vultr Self-Manager initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Vultr API managers: {e}")
            return False
            
    def _load_pending_approvals(self) -> bool:
        """
        Load pending approvals from storage
        
        Returns:
            True if successful
        """
        try:
            # In a real implementation, this would load from a persistent store
            # For this example, we'll initialize an empty list if not already set
            if 'pending_approvals' not in self.current_state:
                self.current_state['pending_approvals'] = []
            
            return True
        except Exception as e:
            logger.error(f"Failed to load pending approvals: {e}")
            return False
    
    def _get_vault_session(self) -> Optional[str]:
        """
        Get a session with the vault to access credentials
        
        Returns:
            Session ID if successful, None otherwise
        """
        try:
            # Use credentials from environment variables for initial vault access
            username = os.environ.get('VAULT_USERNAME', 'origin-system')
            auth_token = os.environ.get('VAULT_AUTH_TOKEN')
            
            if not auth_token:
                logger.error("No vault auth token available")
                return None
            
            # If vault instance is not provided, create a new one
            if not self.vault:
                from src.security.vault_manager import SecretVault
                self.vault = SecretVault()
                
            # Authenticate with the vault
            success, session_id = self.vault.authenticate(username, auth_token)
            
            if not success:
                logger.error(f"Failed to authenticate with vault: {session_id}")
                return None
            
            return session_id
        except Exception as e:
            logger.error(f"Error accessing vault: {e}")
            return None
    
    def _get_vultr_credentials(self, session_id: str) -> Optional[Dict[str, str]]:
        """
        Get Vultr API credentials from the vault
        
        Args:
            session_id: Vault session ID
            
        Returns:
            Dict with credentials if successful, None otherwise
        """
        try:
            # Get credentials from vault
            token_name = self.config.get('vault', {}).get('access', {}).get('token_name', 'vultr_api_credentials')
            success, credentials = self.vault.get_secret(session_id, token_name)
            
            if not success or not isinstance(credentials, dict):
                logger.error(f"Failed to get Vultr credentials from vault: {credentials}")
                return None
            
            # Check required fields
            required_keys = ['api_key']
            if not all(key in credentials for key in required_keys):
                logger.error(f"Vultr credentials missing required keys: {required_keys}")
                return None
            
            return credentials
        except Exception as e:
            logger.error(f"Error retrieving Vultr credentials: {e}")
            return None
    
    def _sync_state(self) -> bool:
        """
        Sync the current state with Vultr to ensure we have accurate information
        
        Returns:
            True if sync was successful
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return False
        
        try:
            # Get current instances
            instances = self.api_manager.list_instances()
            instance_dict = {instance['id']: instance for instance in instances}
            self.current_state['instances'] = instance_dict
            
            # Get container images
            repositories = self.api_manager.list_repositories()
            container_images = {}
            
            for repo in repositories:
                tags = self.api_manager.list_tags(repo)
                container_images[repo] = tags
            
            self.current_state['container_images'] = container_images
            
            # Get database backups
            backups = self.api_manager.list_backups()
            self.current_state['database_backups'] = backups
            
            # Update last sync time
            self.current_state['last_health_check'] = datetime.now().isoformat()
            
            logger.info("Successfully synced state with Vultr")
            return True
        except Exception as e:
            logger.error(f"Failed to sync state with Vultr: {e}")
            return False
    
    def request_resource(self, resource_type: str, resource_data: Dict[str, Any], 
                       auto_approve: bool = False) -> Dict[str, Any]:
        """
        Request a new resource on Vultr, with approval if required
        
        Args:
            resource_type: Type of resource to create (instance, storage, etc.)
            resource_data: Resource configuration data
            auto_approve: Whether to auto-approve the request
            
        Returns:
            Dict with request status and ID
        """
        # Generate a unique request ID
        request_id = f"{resource_type}-{int(time.time())}"
        
        # Estimate cost for the requested resource
        estimated_cost = self._estimate_resource_cost(resource_type, resource_data)
        
        # Check if this resource type requires approval
        requires_approval = resource_type in self.config.get('approvals', {}).get(
            'resources_requiring_approval', ['instance', 'block_storage']
        )
        
        # Check auto-approval threshold
        auto_approve_threshold = self.config.get('infrastructure', {}).get(
            'cost_controls', {}).get('auto_approve_under', 0)
        
        # Determine if we need approval
        need_approval = (
            requires_approval and 
            self.require_approval and
            estimated_cost > auto_approve_threshold and
            not auto_approve
        )
        
        # Create request record
        request = {
            'id': request_id,
            'type': resource_type,
            'data': resource_data,
            'estimated_cost': estimated_cost,
            'status': 'pending_approval' if need_approval else 'approved',
            'requester': 'Origin Self-Manager',
            'timestamp': datetime.now().isoformat(),
            'approval_required': need_approval
        }
        
        # Save the request
        self.current_state['pending_approvals'].append(request)
        
        # If approval is needed, notify admin and return pending status
        if need_approval:
            self._notify_admin_approval_needed(request)
            return {
                'status': 'pending_approval',
                'request_id': request_id,
                'message': f"Resource request requires approval (estimated cost: ${estimated_cost:.2f})"
            }
        
        # Otherwise, proceed with creation
        return self._create_approved_resource(request)
    
    def _estimate_resource_cost(self, resource_type: str, resource_data: Dict[str, Any]) -> float:
        """
        Estimate the monthly cost of a resource
        
        Args:
            resource_type: Type of resource
            resource_data: Resource configuration
            
        Returns:
            Estimated monthly cost in USD
        """
        # This would normally call the Vultr API to get pricing information
        # For now, we'll use some simplified estimates
        
        if resource_type == 'instance':
            # Extract plan
            plan = resource_data.get('plan', 'vc2-1c-1gb')
            
            # Simple lookup table for common plans
            plan_costs = {
                'vc2-1c-1gb': 5.0,     # $5/month
                'vc2-1c-2gb': 10.0,    # $10/month
                'vc2-2c-4gb': 20.0,    # $20/month
                'vc2-4c-8gb': 40.0,    # $40/month
                'vc2-6c-16gb': 80.0,   # $80/month
                'vc2-8c-32gb': 160.0,  # $160/month
            }
            
            return plan_costs.get(plan, 10.0)  # Default to $10 if unknown
            
        elif resource_type == 'block_storage':
            # Block storage is usually priced per GB
            size_gb = resource_data.get('size_gb', 10)
            return size_gb * 0.1  # Assume $0.10 per GB
            
        elif resource_type == 'load_balancer':
            return 10.0  # Flat fee of $10/month
            
        elif resource_type == 'kubernetes':
            # Kubernetes clusters have node costs plus management fee
            nodes = resource_data.get('node_count', 1)
            node_plan = resource_data.get('node_plan', 'vc2-2c-4gb')
            
            # Node costs (simplified)
            node_costs = {
                'vc2-1c-2gb': 10.0,    # $10/month
                'vc2-2c-4gb': 20.0,    # $20/month
                'vc2-4c-8gb': 40.0,    # $40/month
            }
            
            node_cost = node_costs.get(node_plan, 20.0)
            
            # $10 management fee plus node costs
            return 10.0 + (nodes * node_cost)
            
        # Default estimate for unknown resources
        return 5.0
    
    def _notify_admin_approval_needed(self, request: Dict[str, Any]) -> bool:
        """
        Notify the admin that a resource request needs approval
        
        Args:
            request: Resource request details
            
        Returns:
            True if notification was sent
        """
        # In a real implementation, this would send an email or notification
        admin_user = self.config.get('approvals', {}).get('admin_user', 'mikael')
        admin_email = self.config.get('approvals', {}).get('notification_email', 'mikael@dndnordic.com')
        
        logger.info(f"Approval needed for resource request {request['id']} (${request['estimated_cost']:.2f}/month)")
        logger.info(f"Would notify {admin_user} at {admin_email} in production")
        
        # For now, just log the request
        return True
    
    def _create_approved_resource(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a resource that has been approved
        
        Args:
            request: Approved resource request
            
        Returns:
            Dict with creation status and resource ID
        """
        resource_type = request['type']
        resource_data = request['data']
        
        if resource_type == 'instance':
            return self._provision_instance(resource_data)
        elif resource_type == 'block_storage':
            # Implement block storage creation
            return {'status': 'not_implemented', 'message': 'Block storage creation not implemented'}
        elif resource_type == 'load_balancer':
            # Implement load balancer creation
            return {'status': 'not_implemented', 'message': 'Load balancer creation not implemented'}
        elif resource_type == 'kubernetes':
            # Implement Kubernetes cluster creation
            return {'status': 'not_implemented', 'message': 'Kubernetes cluster creation not implemented'}
        else:
            return {
                'status': 'error',
                'message': f"Unknown resource type: {resource_type}"
            }
    
    def approve_resource_request(self, request_id: str) -> Dict[str, Any]:
        """
        Approve a pending resource request
        
        Args:
            request_id: ID of the request to approve
            
        Returns:
            Dict with approval status and resource ID
        """
        # Find the request
        request = None
        for req in self.current_state['pending_approvals']:
            if req['id'] == request_id:
                request = req
                break
        
        if not request:
            return {
                'status': 'error',
                'message': f"Request {request_id} not found"
            }
        
        # Check if it's already approved or denied
        if request['status'] != 'pending_approval':
            return {
                'status': 'error',
                'message': f"Request {request_id} is not pending approval (status: {request['status']})"
            }
        
        # Mark as approved
        request['status'] = 'approved'
        request['approved_at'] = datetime.now().isoformat()
        request['approved_by'] = self.config.get('approvals', {}).get('admin_user', 'mikael')
        
        # Create the resource
        result = self._create_approved_resource(request)
        
        # Update request with result
        request['result'] = result
        
        return {
            'status': 'approved',
            'request_id': request_id,
            'resource': result
        }
    
    def deny_resource_request(self, request_id: str, reason: str = None) -> Dict[str, Any]:
        """
        Deny a pending resource request
        
        Args:
            request_id: ID of the request to deny
            reason: Reason for denial
            
        Returns:
            Dict with denial status
        """
        # Find the request
        request = None
        for req in self.current_state['pending_approvals']:
            if req['id'] == request_id:
                request = req
                break
        
        if not request:
            return {
                'status': 'error',
                'message': f"Request {request_id} not found"
            }
        
        # Check if it's already approved or denied
        if request['status'] != 'pending_approval':
            return {
                'status': 'error',
                'message': f"Request {request_id} is not pending approval (status: {request['status']})"
            }
        
        # Mark as denied
        request['status'] = 'denied'
        request['denied_at'] = datetime.now().isoformat()
        request['denied_by'] = self.config.get('approvals', {}).get('admin_user', 'mikael')
        if reason:
            request['denial_reason'] = reason
        
        return {
            'status': 'denied',
            'request_id': request_id,
            'message': f"Resource request denied: {reason}" if reason else "Resource request denied"
        }
    
    def list_resource_requests(self, status: str = None) -> List[Dict[str, Any]]:
        """
        List resource requests
        
        Args:
            status: Filter by status (pending_approval, approved, denied)
            
        Returns:
            List of resource requests
        """
        requests = self.current_state['pending_approvals']
        
        if status:
            requests = [req for req in requests if req['status'] == status]
        
        return requests
    
    def _provision_instance(self, instance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provision a new instance on Vultr using the appropriate client
        
        Args:
            instance_data: Instance configuration data
            
        Returns:
            Dict with creation status and instance ID
        """
        # Default name if not provided
        if 'label' not in instance_data:
            instance_data['label'] = f"origin-node-{int(time.time())}"
        
        # Use defaults for other fields if not specified
        if 'region' not in instance_data:
            instance_data['region'] = self.config['infrastructure']['region']
        if 'plan' not in instance_data:
            instance_data['plan'] = self.config['infrastructure']['instance_type']
        if 'os_id' not in instance_data:
            instance_data['os_id'] = 362  # Ubuntu 20.04 x64
        if 'tag' not in instance_data:
            instance_data['tag'] = "origin-managed"
        
        try:
            # Try to use official client first if available
            if self.vultr_client and VULTR_CLIENT_AVAILABLE:
                # The official client has a different API
                instance = self.vultr_client.server.create(
                    dcid=instance_data['region'],
                    vpsplanid=instance_data['plan'],
                    osid=instance_data['os_id'],
                    label=instance_data['label'],
                    tag=instance_data['tag']
                )
                
                instance_id = instance['SUBID']
                logger.info(f"Successfully provisioned instance {instance_data['label']} with ID {instance_id} using official client")
                
                # Update local state
                self.current_state['instances'][instance_id] = instance
                
                return {
                    'status': 'success',
                    'instance_id': instance_id,
                    'message': f"Instance {instance_data['label']} created successfully"
                }
            
            # Fallback to custom API manager
            elif self.api_manager:
                instance = self.api_manager.create_instance(instance_data)
                
                if instance and 'id' in instance:
                    instance_id = instance['id']
                    logger.info(f"Successfully provisioned instance {instance_data['label']} with ID {instance_id}")
                    
                    # Update local state
                    self.current_state['instances'][instance_id] = instance
                    
                    return {
                        'status': 'success',
                        'instance_id': instance_id,
                        'message': f"Instance {instance_data['label']} created successfully"
                    }
                else:
                    logger.error(f"Failed to provision instance, unexpected response: {instance}")
                    return {
                        'status': 'error',
                        'message': f"Failed to provision instance, unexpected response: {instance}"
                    }
            else:
                logger.error("No API client available")
                return {
                    'status': 'error',
                    'message': "No API client available"
                }
        except Exception as e:
            logger.error(f"Failed to provision instance: {e}")
            return {
                'status': 'error',
                'message': f"Failed to provision instance: {str(e)}"
            }
            
    def provision_instance(self, instance_name: str = None, instance_type: str = None, 
                          region: str = None, auto_approve: bool = False) -> Dict[str, Any]:
        """
        Provision a new instance on Vultr with approval if required
        
        Args:
            instance_name: Name for the new instance
            instance_type: Type of instance to create (defaults to config)
            region: Region to create instance in (defaults to config)
            auto_approve: Whether to auto-approve the request
            
        Returns:
            Dict with request status and instance ID
        """
        # Create instance data
        instance_data = {}
        if instance_name:
            instance_data['label'] = instance_name
        if instance_type:
            instance_data['plan'] = instance_type
        if region:
            instance_data['region'] = region
            
        # Request the resource through the approval system
        return self.request_resource('instance', instance_data, auto_approve)
    
    def deprovision_instance(self, instance_id: str) -> bool:
        """
        Deprovision an instance on Vultr
        
        Args:
            instance_id: ID of the instance to deprovision
            
        Returns:
            True if successful
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return False
        
        try:
            # Delete the instance
            success = self.api_manager.delete_instance(instance_id)
            
            if success:
                logger.info(f"Successfully deprovisioned instance {instance_id}")
                
                # Update local state
                if instance_id in self.current_state['instances']:
                    del self.current_state['instances'][instance_id]
                
                return True
            else:
                logger.error(f"Failed to deprovision instance {instance_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to deprovision instance: {e}")
            return False
    
    def create_backup(self, data_path: str, backup_name: str = None) -> Optional[str]:
        """
        Create a backup of origin data to Vultr object storage
        
        Args:
            data_path: Path to the data to backup
            backup_name: Name for the backup (defaults to timestamp-based name)
            
        Returns:
            Backup ID/key if successful, None otherwise
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return None
        
        try:
            # Generate backup name if not provided
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
                backup_name = f"origin-backup-{timestamp}"
            
            # Backup database
            object_key = self.api_manager.backup_database(data_path, backup_name)
            
            if object_key:
                logger.info(f"Successfully created backup {backup_name} with key {object_key}")
                
                # Update local state
                self.current_state['database_backups'].append({
                    'key': object_key,
                    'name': backup_name,
                    'timestamp': datetime.now().isoformat()
                })
                
                return object_key
            else:
                logger.error(f"Failed to create backup {backup_name}")
                return None
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def restore_backup(self, backup_key: str, restore_path: str) -> bool:
        """
        Restore a backup from Vultr object storage
        
        Args:
            backup_key: Key of the backup to restore
            restore_path: Path to restore the backup to
            
        Returns:
            True if successful
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return False
        
        try:
            # Restore database
            success = self.api_manager.restore_database(backup_key, restore_path)
            
            if success:
                logger.info(f"Successfully restored backup {backup_key} to {restore_path}")
                return True
            else:
                logger.error(f"Failed to restore backup {backup_key}")
                return False
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def clean_old_backups(self, retention_days: int = None) -> int:
        """
        Clean up old backups beyond the retention period
        
        Args:
            retention_days: Number of days to retain backups (defaults to config)
            
        Returns:
            Number of backups deleted
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return 0
        
        try:
            # Use default from config if not specified
            retention_days = retention_days or self.config['infrastructure']['backup']['retention_days']
            
            # Clean up old backups
            deleted_count = self.api_manager.cleanup_old_backups(retention_days)
            
            logger.info(f"Cleaned up {deleted_count} old backups")
            
            # Update local state
            self._sync_state()
            
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to clean old backups: {e}")
            return 0
    
    def auto_scale(self) -> bool:
        """
        Automatically scale infrastructure based on current usage and thresholds
        
        Returns:
            True if scaling operations were successful
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return False
        
        # Skip if auto-scaling is disabled
        if not self.config['infrastructure']['auto_scale']:
            logger.info("Auto-scaling is disabled")
            return False
        
        try:
            # Get current metrics
            self._update_resource_metrics()
            
            # Check if we need to scale up
            cpu_usage = self.current_state['resources']['cpu_usage']
            current_instances = len(self.current_state['instances'])
            max_instances = self.config['infrastructure']['max_instances']
            min_instances = self.config['infrastructure']['min_instances']
            
            if cpu_usage > self.config['infrastructure']['scale_up_threshold'] and current_instances < max_instances:
                # Scale up
                logger.info(f"Scaling up due to CPU usage {cpu_usage:.2f} > threshold {self.config['infrastructure']['scale_up_threshold']}")
                self.provision_instance()
                return True
            
            elif cpu_usage < self.config['infrastructure']['scale_down_threshold'] and current_instances > min_instances:
                # Scale down
                logger.info(f"Scaling down due to CPU usage {cpu_usage:.2f} < threshold {self.config['infrastructure']['scale_down_threshold']}")
                
                # Find the instance with the lowest usage to remove
                instance_id = list(self.current_state['instances'].keys())[-1]
                self.deprovision_instance(instance_id)
                return True
            
            else:
                logger.info(f"No scaling needed. CPU usage: {cpu_usage:.2f}, Instances: {current_instances}/{max_instances}")
                return False
        except Exception as e:
            logger.error(f"Failed to auto-scale: {e}")
            return False
    
    def _update_resource_metrics(self) -> bool:
        """
        Update resource usage metrics from all instances
        
        Returns:
            True if successful
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return False
        
        try:
            # In a real implementation, this would query metrics from instances
            # For this example, we'll simulate resource usage
            
            # In a real system, this would gather metrics from:
            # 1. Kubernetes API server for pod metrics
            # 2. Instance metrics from Vultr API
            # 3. Internal metrics collection service
            
            # Simulate some resource usage (20-80% range)
            import random
            self.current_state['resources'] = {
                "cpu_usage": random.uniform(0.2, 0.8),
                "memory_usage": random.uniform(0.2, 0.8),
                "storage_usage": random.uniform(0.2, 0.8),
                "network_usage": random.uniform(0.2, 0.8)
            }
            
            logger.info(f"Updated resource metrics: CPU usage = {self.current_state['resources']['cpu_usage']:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to update resource metrics: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on all infrastructure components
        
        Returns:
            Health status information
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return {"status": "error", "message": "API manager not initialized"}
        
        try:
            # Sync state to get latest information
            self._sync_state()
            
            # Update resource metrics
            self._update_resource_metrics()
            
            # Check instance health
            instances_running = len(self.current_state['instances'])
            min_instances = self.config['infrastructure']['min_instances']
            
            # Check backup health
            backups = self.current_state['database_backups']
            backup_age = None
            
            if backups:
                latest_backup = backups[-1]
                backup_time = datetime.fromisoformat(latest_backup['timestamp'])
                backup_age = (datetime.now() - backup_time).total_seconds() / 3600  # Hours
            
            # Determine overall health
            health_status = "healthy"
            health_issues = []
            
            if instances_running < min_instances:
                health_status = "warning"
                health_issues.append(f"Running instances ({instances_running}) below minimum ({min_instances})")
            
            if self.config['infrastructure']['backup']['enabled'] and (not backup_age or backup_age > self.config['infrastructure']['backup']['frequency_hours'] * 1.5):
                health_status = "warning"
                health_issues.append("Backups are outdated or missing")
            
            # Prepare health report
            health_report = {
                "status": health_status,
                "timestamp": datetime.now().isoformat(),
                "issues": health_issues,
                "metrics": self.current_state['resources'],
                "instances": {
                    "running": instances_running,
                    "minimum": min_instances,
                    "maximum": self.config['infrastructure']['max_instances']
                },
                "backups": {
                    "enabled": self.config['infrastructure']['backup']['enabled'],
                    "count": len(backups),
                    "latest_age_hours": backup_age
                }
            }
            
            logger.info(f"Health check completed: {health_status}")
            return health_report
        except Exception as e:
            logger.error(f"Failed to perform health check: {e}")
            return {"status": "error", "message": str(e)}
    
    def run_maintenance(self) -> bool:
        """
        Perform regular maintenance operations
        
        Returns:
            True if maintenance was successful
        """
        if not self.api_manager:
            logger.error("API manager not initialized")
            return False
        
        try:
            # Check if we need to create a backup
            need_backup = self.config['infrastructure']['backup']['enabled']
            
            if need_backup and self.current_state['database_backups']:
                latest_backup = self.current_state['database_backups'][-1]
                backup_time = datetime.fromisoformat(latest_backup['timestamp'])
                hours_since_backup = (datetime.now() - backup_time).total_seconds() / 3600
                
                need_backup = hours_since_backup > self.config['infrastructure']['backup']['frequency_hours']
            
            if need_backup:
                # Create backup (in a real system, this would be a proper path)
                self.create_backup("/data/origin_db.sqlite")
            
            # Clean up old backups
            self.clean_old_backups()
            
            # Check for auto-scaling needs
            self.auto_scale()
            
            # Prune old container images
            # (This would need implementation in the VultrAPIManager)
            
            logger.info("Maintenance completed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to run maintenance: {e}")
            return False


# Operation loop for self-management
def self_management_loop():
    """Main loop for Origin's self-management capabilities"""
    logging.basicConfig(level=logging.INFO)
    
    # Initialize self-manager
    manager = VultrSelfManager()
    
    # Try to initialize with credentials from vault
    if not manager.initialize():
        logger.error("Failed to initialize self-manager, using environment variables")
        # Fall back to environment variables
        api_key = os.environ.get("VULTR_API_KEY")
        if api_key:
            manager.api_manager = VultrAPIManager(api_key=api_key)
            manager._sync_state()
        else:
            logger.error("No API credentials available, self-management disabled")
            return
    
    # Main management loop
    try:
        while True:
            # Perform health check
            health = manager.health_check()
            
            # Run maintenance if needed
            if health['status'] != "healthy":
                logger.warning(f"Health check detected issues: {health['issues']}")
                manager.run_maintenance()
            else:
                logger.info("Health check passed")
            
            # Sleep before next cycle (30 minutes)
            logger.info("Sleeping for 30 minutes before next check")
            time.sleep(1800)
    except KeyboardInterrupt:
        logger.info("Self-management loop interrupted")
    except Exception as e:
        logger.error(f"Error in self-management loop: {e}")


if __name__ == "__main__":
    self_management_loop()