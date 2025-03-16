"""
REST API for the Secret Vault and Killswitch

This module provides a Flask-based API for interacting with the secret vault 
and managing the killswitch functionality. It enables automated systems to 
securely retrieve credentials while maintaining centralized control.

It also provides API endpoints for Vultr infrastructure management, allowing
Origin to control its own infrastructure using Vultr APIs.
"""

import os
import json
import time
import logging
from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from functools import wraps
from typing import Dict, List, Any, Optional, Callable
from werkzeug.exceptions import Unauthorized, Forbidden, NotFound

# Import the vault manager and Vultr manager
from ..security.vault_manager import get_vault, SecretVault
from ..api.vultr_manager import VultrSelfManager

# Set up logging
logger = logging.getLogger(__name__)

# Create the API blueprint
vault_api = Blueprint('vault_api', __name__)

# Authentication tokens (in memory cache)
AUTH_TOKENS = {}

# Initialize Vultr manager (will be set up when credentials are available)
vultr_manager = None

def get_vault_instance() -> SecretVault:
    """Get the vault instance and ensure it's open."""
    vault = get_vault()
    if not vault.is_open:
        vault.open()
    return vault


def require_auth(f: Callable) -> Callable:
    """Decorator to require authentication for API endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            logger.warning("Missing Authorization header")
            raise Unauthorized("Authentication required")
        
        # Check token format
        parts = auth_header.split()
        if parts[0].lower() != 'bearer' or len(parts) != 2:
            logger.warning("Invalid Authorization header format")
            raise Unauthorized("Invalid authentication format")
        
        token = parts[1]
        
        # Get the vault
        vault = get_vault_instance()
        
        # Verify token
        token_data = vault.access_control.verify_token(token)
        if not token_data:
            logger.warning("Invalid or expired token")
            raise Unauthorized("Invalid or expired token")
        
        # Add token data to the request
        request.token_data = token_data
        
        return f(*args, **kwargs)
    return decorated


def require_permission(permission: str) -> Callable:
    """Decorator to require specific permission for API endpoints."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            # Get token data (should be added by require_auth)
            token_data = getattr(request, 'token_data', None)
            if not token_data:
                logger.warning("No token data found - authentication required")
                raise Unauthorized("Authentication required")
            
            # Check permission
            user_id = token_data['user_id']
            permissions = token_data['permissions']
            
            if not permissions.get(permission, False):
                logger.warning(f"User {user_id} doesn't have required permission: {permission}")
                raise Forbidden(f"Missing required permission: {permission}")
            
            return f(*args, **kwargs)
        return decorated
    return decorator


@vault_api.route('/auth', methods=['POST'])
def authenticate():
    """Authenticate a user and get an access token."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400
    
    user_id = data.get('user_id')
    auth_factors = data.get('auth_factors', {})
    
    if not user_id:
        return jsonify({'error': 'Missing user_id parameter'}), 400
    
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Authenticate the user
        token = vault.access_control.authenticate(user_id, auth_factors)
        
        # Return the token
        return jsonify({
            'access_token': token,
            'token_type': 'bearer',
            'expires_in': 1800  # 30 minutes
        }), 200
    except ValueError as e:
        logger.warning(f"Authentication failed for user {user_id}: {e}")
        return jsonify({'error': 'Authentication failed'}), 401
    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/secrets', methods=['GET'])
@require_auth
def list_secrets():
    """List available secrets."""
    # Get prefix filter
    prefix = request.args.get('prefix')
    
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Get the token from require_auth
        token = request.headers.get('Authorization').split()[1]
        
        # List secrets
        secrets = vault.list_secrets(token, prefix)
        
        return jsonify({
            'secrets': secrets,
            'count': len(secrets)
        }), 200
    except Exception as e:
        logger.error(f"Error listing secrets: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/secrets/<path:secret_key>', methods=['GET'])
@require_auth
def get_secret(secret_key):
    """Get a secret value."""
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Get the token from require_auth
        token = request.headers.get('Authorization').split()[1]
        
        # Get the secret
        secret_value = vault.get_secret(token, secret_key)
        
        if secret_value is None:
            return jsonify({'error': 'Secret not found'}), 404
        
        return jsonify({
            'key': secret_key,
            'value': secret_value
        }), 200
    except Exception as e:
        logger.error(f"Error getting secret: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/secrets/<path:secret_key>', methods=['PUT', 'POST'])
@require_auth
def set_secret(secret_key):
    """Set a secret value."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400
    
    secret_value = data.get('value')
    if secret_value is None:
        return jsonify({'error': 'Missing value parameter'}), 400
    
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Get the token from require_auth
        token = request.headers.get('Authorization').split()[1]
        
        # Set the secret
        success = vault.set_secret(token, secret_key, secret_value)
        
        if not success:
            return jsonify({'error': 'Failed to set secret'}), 500
            
        # If this is Vultr API credentials, initialize the Vultr manager
        if secret_key == 'vultr_api_credentials' and isinstance(secret_value, dict):
            global vultr_manager
            try:
                # Initialize Vultr manager with vault access
                vultr_manager = VultrSelfManager(vault=vault)
                
                # Try to initialize with the new credentials
                init_success = vultr_manager.initialize()
                logger.info(f"Vultr self-manager initialization result: {init_success}")
                
                # Add initialization status to response
                return jsonify({
                    'key': secret_key,
                    'status': 'success',
                    'vultr_initialized': init_success
                }), 200
            except Exception as e:
                logger.error(f"Failed to initialize Vultr manager: {e}")
                # Continue with success response since the secret was set
        
        return jsonify({
            'key': secret_key,
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error setting secret: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/secrets/<path:secret_key>', methods=['DELETE'])
@require_auth
def delete_secret(secret_key):
    """Delete a secret."""
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Get the token from require_auth
        token = request.headers.get('Authorization').split()[1]
        
        # Delete the secret
        success = vault.delete_secret(token, secret_key)
        
        if not success:
            return jsonify({'error': 'Failed to delete secret'}), 500
        
        return jsonify({
            'key': secret_key,
            'status': 'deleted'
        }), 200
    except Exception as e:
        logger.error(f"Error deleting secret: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/sync/kubernetes', methods=['POST'])
@require_auth
@require_permission('admin')
def sync_kubernetes():
    """Sync secrets to Kubernetes."""
    data = request.get_json() or {}
    namespace = data.get('namespace', 'governance-system')
    prefix = data.get('prefix')
    
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Get the token from require_auth
        token = request.headers.get('Authorization').split()[1]
        
        # Sync to Kubernetes
        success = vault.sync_to_kubernetes(token, namespace, prefix)
        
        if not success:
            return jsonify({'error': 'Failed to sync to Kubernetes'}), 500
        
        return jsonify({
            'status': 'success',
            'namespace': namespace,
            'prefix': prefix or 'all'
        }), 200
    except Exception as e:
        logger.error(f"Error syncing to Kubernetes: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/killswitch/status', methods=['GET'])
@require_auth
def killswitch_status():
    """Get the status of the killswitch."""
    try:
        # Get the vault
        vault = get_vault_instance()
        
        return jsonify({
            'active': vault.killswitch_activated,
            'timestamp': time.time()
        }), 200
    except Exception as e:
        logger.error(f"Error getting killswitch status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/killswitch/activate', methods=['POST'])
@require_auth
@require_permission('killswitch')
def activate_killswitch():
    """Activate the killswitch."""
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Get the token from require_auth
        token = request.headers.get('Authorization').split()[1]
        
        # Activate the killswitch
        success = vault.activate_killswitch(token)
        
        if not success:
            return jsonify({'error': 'Failed to activate killswitch'}), 500
        
        return jsonify({
            'status': 'activated',
            'timestamp': time.time()
        }), 200
    except Exception as e:
        logger.error(f"Error activating killswitch: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/killswitch/deactivate', methods=['POST'])
def deactivate_killswitch():
    """Deactivate the killswitch with a master override key."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400
    
    master_override_key = data.get('master_override_key')
    if not master_override_key:
        return jsonify({'error': 'Missing master_override_key parameter'}), 400
    
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Deactivate the killswitch
        success = vault.deactivate_killswitch(master_override_key)
        
        if not success:
            return jsonify({'error': 'Failed to deactivate killswitch - invalid override key'}), 401
        
        return jsonify({
            'status': 'deactivated',
            'timestamp': time.time()
        }), 200
    except Exception as e:
        logger.error(f"Error deactivating killswitch: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# Vultr management API endpoints

@vault_api.route('/vultr/health', methods=['GET'])
@require_auth
def vultr_health_check():
    """Check the health of Vultr infrastructure."""
    try:
        # Check if Vultr manager is initialized
        global vultr_manager
        if vultr_manager is None:
            return jsonify({
                "status": "not_initialized",
                "message": "Vultr self-manager not initialized"
            }), 200
        
        # Get health report
        health_report = vultr_manager.health_check()
        return jsonify(health_report), 200
    except Exception as e:
        logger.error(f"Error checking Vultr health: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/vultr/backup', methods=['POST'])
@require_auth
@require_permission('admin')
def create_vultr_backup():
    """Create a backup of Origin data."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400
    
    data_path = data.get('data_path')
    backup_name = data.get('backup_name')
    
    if not data_path:
        return jsonify({'error': 'Missing data_path parameter'}), 400
    
    try:
        # Check if Vultr manager is initialized
        global vultr_manager
        if vultr_manager is None:
            return jsonify({
                "status": "not_initialized",
                "message": "Vultr self-manager not initialized"
            }), 500
        
        # Create backup
        backup_key = vultr_manager.create_backup(data_path, backup_name)
        
        if backup_key:
            return jsonify({
                "status": "success",
                "backup_key": backup_key,
                "message": f"Backup created successfully: {backup_key}"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to create backup"
            }), 500
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/vultr/backup/<backup_key>', methods=['POST'])
@require_auth
@require_permission('admin')
def restore_vultr_backup(backup_key):
    """Restore a backup from Vultr object storage."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400
    
    restore_path = data.get('restore_path')
    
    if not restore_path:
        return jsonify({'error': 'Missing restore_path parameter'}), 400
    
    try:
        # Check if Vultr manager is initialized
        global vultr_manager
        if vultr_manager is None:
            return jsonify({
                "status": "not_initialized",
                "message": "Vultr self-manager not initialized"
            }), 500
        
        # Restore backup
        success = vultr_manager.restore_backup(backup_key, restore_path)
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Backup {backup_key} restored to {restore_path}"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to restore backup"
            }), 500
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/vultr/backups', methods=['GET'])
@require_auth
def list_vultr_backups():
    """List all available backups."""
    try:
        # Check if Vultr manager is initialized
        global vultr_manager
        if vultr_manager is None:
            return jsonify({
                "status": "not_initialized",
                "message": "Vultr self-manager not initialized",
                "backups": []
            }), 200
        
        # List backups
        vultr_manager._sync_state()
        backups = vultr_manager.current_state['database_backups']
        
        return jsonify({
            "status": "success",
            "backups": backups
        }), 200
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/vultr/maintenance', methods=['POST'])
@require_auth
@require_permission('admin')
def run_vultr_maintenance():
    """Run maintenance operations on Vultr infrastructure."""
    try:
        # Check if Vultr manager is initialized
        global vultr_manager
        if vultr_manager is None:
            return jsonify({
                "status": "not_initialized",
                "message": "Vultr self-manager not initialized"
            }), 500
        
        # Run maintenance
        success = vultr_manager.run_maintenance()
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Maintenance completed successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to run maintenance"
            }), 500
    except Exception as e:
        logger.error(f"Error running maintenance: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@vault_api.route('/vultr/initialize', methods=['POST'])
@require_auth
@require_permission('admin')
def initialize_vultr_manager():
    """Initialize or reinitialize the Vultr manager."""
    try:
        # Get the vault
        vault = get_vault_instance()
        
        # Create new Vultr manager instance
        global vultr_manager
        vultr_manager = VultrSelfManager(vault=vault)
        
        # Initialize with credentials from vault
        success = vultr_manager.initialize()
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Vultr manager initialized successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to initialize Vultr manager - check credentials in vault"
            }), 500
    except Exception as e:
        logger.error(f"Error initializing Vultr manager: {e}")
        return jsonify({'error': 'Internal server error'}), 500


def register_vault_api(app: Flask):
    """Register the vault API blueprint with the Flask app."""
    app.register_blueprint(vault_api, url_prefix='/api/vault')
    
    # Add CORS support
    CORS(app, resources={r"/api/vault/*": {"origins": "*"}})
    
    # Try to initialize Vultr manager if credentials are available
    try:
        vault = get_vault_instance()
        # For testing only - in production would use proper authentication
        admin_token = os.environ.get('ADMIN_TOKEN')
        if admin_token:
            success, vultr_creds = vault.get_secret(admin_token, 'vultr_api_credentials')
            if success and isinstance(vultr_creds, dict):
                global vultr_manager
                vultr_manager = VultrSelfManager(vault=vault)
                vultr_manager.initialize()
                logger.info("Vultr manager initialized during API registration")
    except Exception as e:
        logger.warning(f"Failed to initialize Vultr manager during startup: {e}")
    
    logger.info("Vault API registered successfully")
    return app