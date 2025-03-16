"""
Vultr API Integration

This module provides integration with Vultr cloud services including:
1. Primary API for instance management
2. Container Registry for Docker images
3. Object Storage for backups and file storage

Origin uses these services as backup for Mikael's WSL environment and for general
cloud infrastructure management.
"""

import os
import json
import time
import logging
import requests
import boto3
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class VultrAPIManager:
    """Manages interactions with the Vultr API for cloud resources"""
    
    def __init__(self, config_path: str = None, api_key: str = None):
        """
        Initialize the Vultr API Manager
        
        Args:
            config_path: Path to the configuration file
            api_key: Vultr API key (if not provided, reads from environment)
        """
        self.config = self._load_config(config_path)
        self.api_key = api_key or os.environ.get('VULTR_API_KEY')
        
        if not self.api_key:
            logger.warning("No Vultr API key provided")
        
        # Set up API session with rate limiting
        self.session = self._create_api_session()
        
        # Set up S3 compatible client for object storage
        self.s3_client = self._create_s3_client()
        
        logger.info("Vultr API Manager initialized")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from file or default location
        
        Args:
            config_path: Path to configuration file
            
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
            "api": {
                "vultr_api": {
                    "base_url": "https://api.vultr.com/v2",
                    "rate_limit": {
                        "requests_per_second": 5,
                        "burst": 10
                    },
                    "timeout": 30,
                    "retry": {
                        "max_attempts": 3,
                        "backoff_factor": 2.0
                    }
                },
                "container_registry": {
                    "base_url": "https://registry.vultr.dndnordic.com/v2",
                    "rate_limit": {
                        "requests_per_second": 10,
                        "burst": 20
                    }
                },
                "object_storage": {
                    "endpoint": "ewr1.vultrobjects.com",
                    "region": "ewr",
                    "buckets": {
                        "backup": "origin-backups",
                        "artifacts": "origin-artifacts",
                        "logs": "origin-logs"
                    }
                }
            }
        }
    
    def _create_api_session(self) -> requests.Session:
        """
        Create a requests session with proper headers and rate limiting
        
        Returns:
            Configured requests session
        """
        session = requests.Session()
        
        # Set default headers
        session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Set default timeout
        timeout = self.config.get('api', {}).get('vultr_api', {}).get('timeout', 30)
        session.request = lambda method, url, **kwargs: super(requests.Session, session).request(
            method=method, url=url, timeout=timeout, **kwargs
        )
        
        return session
    
    def _create_s3_client(self) -> boto3.client:
        """
        Create an S3 client for Vultr Object Storage
        
        Returns:
            boto3 S3 client
        """
        object_storage_config = self.config.get('api', {}).get('object_storage', {})
        
        # Get access and secret keys from environment or config
        access_key = os.environ.get('VULTR_S3_ACCESS_KEY')
        secret_key = os.environ.get('VULTR_S3_SECRET_KEY')
        
        if not (access_key and secret_key):
            logger.warning("Vultr Object Storage credentials not found")
            return None
        
        try:
            endpoint = object_storage_config.get('endpoint', 'ewr1.vultrobjects.com')
            region = object_storage_config.get('region', 'ewr')
            
            # Create the S3 client
            client = boto3.client(
                's3',
                endpoint_url=f'https://{endpoint}',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            
            return client
        except Exception as e:
            logger.error(f"Failed to create S3 client: {e}")
            return None
    
    def _make_api_request(self, method: str, endpoint: str, data: Dict = None, 
                         params: Dict = None, retry: bool = True) -> Dict:
        """
        Make a request to the Vultr API with retry logic
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            data: Request body for POST/PUT
            params: Query parameters
            retry: Whether to retry failed requests
            
        Returns:
            JSON response data
        """
        url = f"{self.config['api']['vultr_api']['base_url']}/{endpoint.lstrip('/')}"
        retry_config = self.config['api']['vultr_api']['retry']
        max_attempts = retry_config['max_attempts'] if retry else 1
        backoff_factor = retry_config['backoff_factor']
        
        for attempt in range(max_attempts):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params)
                elif method.upper() == 'POST':
                    response = self.session.post(url, json=data, params=params)
                elif method.upper() == 'PUT':
                    response = self.session.put(url, json=data, params=params)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(url, json=data, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                # Raise for other errors
                response.raise_for_status()
                
                # Return JSON data
                return response.json()
            
            except requests.RequestException as e:
                if attempt + 1 < max_attempts:
                    wait_time = backoff_factor * (2 ** attempt)
                    logger.warning(f"API request failed: {e}. Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API request failed after {max_attempts} attempts: {e}")
                    raise
    
    # Instance Management
    
    def list_instances(self) -> List[Dict]:
        """
        List all instances
        
        Returns:
            List of instance objects
        """
        response = self._make_api_request('GET', 'instances')
        return response.get('instances', [])
    
    def get_instance(self, instance_id: str) -> Dict:
        """
        Get details for a specific instance
        
        Args:
            instance_id: ID of the instance
            
        Returns:
            Instance details
        """
        response = self._make_api_request('GET', f'instances/{instance_id}')
        return response.get('instance', {})
    
    def create_instance(self, instance_data: Dict) -> Dict:
        """
        Create a new instance
        
        Args:
            instance_data: Instance configuration
            
        Returns:
            Created instance details
        """
        response = self._make_api_request('POST', 'instances', data=instance_data)
        return response.get('instance', {})
    
    def delete_instance(self, instance_id: str) -> bool:
        """
        Delete an instance
        
        Args:
            instance_id: ID of the instance to delete
            
        Returns:
            True if successful
        """
        try:
            self._make_api_request('DELETE', f'instances/{instance_id}')
            return True
        except Exception as e:
            logger.error(f"Failed to delete instance {instance_id}: {e}")
            return False
    
    # Container Registry
    
    def list_repositories(self) -> List[str]:
        """
        List all repositories in the container registry
        
        Returns:
            List of repository names
        """
        # The Docker Registry API v2 endpoint for listing repositories
        registry_url = self.config['api']['container_registry']['base_url']
        
        # Create session with Docker registry auth
        reg_session = requests.Session()
        reg_session.auth = (
            os.environ.get('VULTR_REGISTRY_USERNAME', ''),
            os.environ.get('VULTR_REGISTRY_PASSWORD', '')
        )
        
        try:
            response = reg_session.get(f"{registry_url}/_catalog")
            response.raise_for_status()
            return response.json().get('repositories', [])
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            return []
    
    def list_tags(self, repository: str) -> List[str]:
        """
        List all tags for a repository
        
        Args:
            repository: Repository name
            
        Returns:
            List of tags
        """
        registry_url = self.config['api']['container_registry']['base_url']
        
        # Create session with Docker registry auth
        reg_session = requests.Session()
        reg_session.auth = (
            os.environ.get('VULTR_REGISTRY_USERNAME', ''),
            os.environ.get('VULTR_REGISTRY_PASSWORD', '')
        )
        
        try:
            response = reg_session.get(f"{registry_url}/{repository}/tags/list")
            response.raise_for_status()
            return response.json().get('tags', [])
        except Exception as e:
            logger.error(f"Failed to list tags for {repository}: {e}")
            return []
    
    def delete_tag(self, repository: str, tag: str) -> bool:
        """
        Delete a tag from a repository
        
        Args:
            repository: Repository name
            tag: Tag to delete
            
        Returns:
            True if successful
        """
        registry_url = self.config['api']['container_registry']['base_url']
        
        # First, get the digest for the tag
        reg_session = requests.Session()
        reg_session.auth = (
            os.environ.get('VULTR_REGISTRY_USERNAME', ''),
            os.environ.get('VULTR_REGISTRY_PASSWORD', '')
        )
        
        try:
            # Get manifest digest
            headers = {'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
            response = reg_session.head(
                f"{registry_url}/{repository}/manifests/{tag}",
                headers=headers
            )
            response.raise_for_status()
            
            digest = response.headers.get('Docker-Content-Digest')
            if not digest:
                logger.error(f"Could not get digest for {repository}:{tag}")
                return False
            
            # Delete manifest by digest
            response = reg_session.delete(
                f"{registry_url}/{repository}/manifests/{digest}"
            )
            response.raise_for_status()
            
            logger.info(f"Deleted {repository}:{tag} with digest {digest}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {repository}:{tag}: {e}")
            return False
    
    # Object Storage
    
    def list_buckets(self) -> List[str]:
        """
        List all buckets in object storage
        
        Returns:
            List of bucket names
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return []
        
        try:
            response = self.s3_client.list_buckets()
            return [bucket['Name'] for bucket in response.get('Buckets', [])]
        except Exception as e:
            logger.error(f"Failed to list buckets: {e}")
            return []
    
    def create_bucket(self, bucket_name: str) -> bool:
        """
        Create a new bucket
        
        Args:
            bucket_name: Name of the bucket to create
            
        Returns:
            True if successful
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return False
        
        try:
            self.s3_client.create_bucket(Bucket=bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            return False
    
    def upload_file(self, bucket_name: str, file_path: str, object_key: str) -> bool:
        """
        Upload a file to object storage
        
        Args:
            bucket_name: Target bucket name
            file_path: Local path to file
            object_key: Key to store the file under
            
        Returns:
            True if successful
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return False
        
        try:
            self.s3_client.upload_file(file_path, bucket_name, object_key)
            logger.info(f"Uploaded {file_path} to {bucket_name}/{object_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {file_path}: {e}")
            return False
    
    def download_file(self, bucket_name: str, object_key: str, file_path: str) -> bool:
        """
        Download a file from object storage
        
        Args:
            bucket_name: Source bucket name
            object_key: Key of the object to download
            file_path: Local path to save file
            
        Returns:
            True if successful
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return False
        
        try:
            self.s3_client.download_file(bucket_name, object_key, file_path)
            logger.info(f"Downloaded {bucket_name}/{object_key} to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {object_key}: {e}")
            return False
    
    def list_objects(self, bucket_name: str, prefix: str = '') -> List[Dict]:
        """
        List objects in a bucket with an optional prefix
        
        Args:
            bucket_name: Bucket name
            prefix: Optional key prefix to filter by
            
        Returns:
            List of object metadata
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return []
        
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            return response.get('Contents', [])
        except Exception as e:
            logger.error(f"Failed to list objects in {bucket_name}: {e}")
            return []
    
    def delete_object(self, bucket_name: str, object_key: str) -> bool:
        """
        Delete an object from storage
        
        Args:
            bucket_name: Bucket name
            object_key: Key of object to delete
            
        Returns:
            True if successful
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return False
        
        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=object_key)
            logger.info(f"Deleted {bucket_name}/{object_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {object_key}: {e}")
            return False
    
    # Backup Functions
    
    def backup_database(self, db_path: str, backup_name: str = None) -> str:
        """
        Back up a database file to object storage
        
        Args:
            db_path: Path to database file
            backup_name: Optional name for the backup (defaults to timestamp)
            
        Returns:
            Object key of the backup if successful, None otherwise
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return None
        
        try:
            # Generate backup name if not provided
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
                db_filename = os.path.basename(db_path)
                backup_name = f"{db_filename}-{timestamp}"
            
            # Get backup bucket name
            bucket_name = self.config['api']['object_storage']['buckets']['backup']
            
            # Upload the file
            object_key = f"database/{backup_name}"
            self.s3_client.upload_file(db_path, bucket_name, object_key)
            
            logger.info(f"Database backup created: {bucket_name}/{object_key}")
            return object_key
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return None
    
    def restore_database(self, object_key: str, restore_path: str) -> bool:
        """
        Restore a database from object storage
        
        Args:
            object_key: Key of the backup to restore
            restore_path: Path where to restore the database
            
        Returns:
            True if successful
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return False
        
        try:
            # Get backup bucket name
            bucket_name = self.config['api']['object_storage']['buckets']['backup']
            
            # Download the file
            self.s3_client.download_file(bucket_name, object_key, restore_path)
            
            logger.info(f"Database restored from {bucket_name}/{object_key} to {restore_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False
    
    def list_backups(self, prefix: str = 'database/') -> List[Dict]:
        """
        List available backups
        
        Args:
            prefix: Optional prefix to filter by
            
        Returns:
            List of backup metadata
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return []
        
        try:
            # Get backup bucket name
            bucket_name = self.config['api']['object_storage']['buckets']['backup']
            
            # List objects with prefix
            response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            
            # Format the response
            backups = []
            for obj in response.get('Contents', []):
                backups.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'filename': os.path.basename(obj['Key'])
                })
            
            return backups
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    # Cleanup functions
    
    def cleanup_old_backups(self, retain_days: int = 30, prefix: str = 'database/') -> int:
        """
        Clean up old backups beyond retention period
        
        Args:
            retain_days: Number of days to retain backups
            prefix: Prefix to filter backups
            
        Returns:
            Number of backups deleted
        """
        if not self.s3_client:
            logger.error("S3 client not configured")
            return 0
        
        try:
            # Get backup bucket name
            bucket_name = self.config['api']['object_storage']['buckets']['backup']
            
            # List objects with prefix
            response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=retain_days)
            
            # Track deleted objects
            deleted_count = 0
            
            # Check each object
            for obj in response.get('Contents', []):
                if obj['LastModified'] < cutoff_date:
                    # Delete old object
                    self.s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {obj['Key']}")
            
            logger.info(f"Cleaned up {deleted_count} old backups")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to clean up old backups: {e}")
            return 0


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize Vultr API Manager
    vultr_api = VultrAPIManager()
    
    # Example instance listing
    instances = vultr_api.list_instances()
    print(f"Found {len(instances)} instances")
    
    # Example repository listing
    repositories = vultr_api.list_repositories()
    print(f"Found {len(repositories)} repositories")
    
    # Example bucket listing
    buckets = vultr_api.list_buckets()
    print(f"Found {len(buckets)} buckets")