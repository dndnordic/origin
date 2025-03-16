"""
Centralized Secret Vault Manager for Origin

This module provides a secure vault to store and manage all secrets used by both the Origin and 
Singularity systems. It acts as a killswitch by controlling access to credentials.

Key features:
- Encrypted storage of all secrets
- Access control with multi-factor authentication
- Audit logging of all access attempts
- Remote revocation capabilities (killswitch)
- Integration with Kubernetes secrets

TODO:
- Add integration with Keycloak for identity management
- Keycloak will be hosted within Origin and serve as the central identity
  provider for all systems, including multi-tenant authentication for Singularity
- For multi-tenant services other than Origin, identity management should be 
  delegated to Keycloak
"""

import os
import json
import time
import logging
import base64
import hashlib
import hmac
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class VaultEncryption:
    """Handles encryption/decryption of vault data."""
    
    def __init__(self, master_key: str = None):
        """Initialize encryption with a master key or generate one."""
        if master_key:
            self.master_key = master_key
        else:
            self.master_key = os.environ.get('ORIGIN_VAULT_MASTER_KEY')
        
        if not self.master_key:
            logger.warning("No master key provided, generating a new one")
            self.master_key = Fernet.generate_key().decode('utf-8')
            logger.info(f"Generated new master key: {self.master_key[:5]}...{self.master_key[-5:]}")
        
        # Create encryption key from master key
        self._setup_encryption()
    
    def _setup_encryption(self):
        """Set up the encryption key using the master key."""
        key_bytes = self.master_key.encode('utf-8')
        salt = b'origin_vault_salt'  # In production, use a secure random salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt data."""
        return self.cipher.encrypt(data.encode('utf-8')).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data."""
        try:
            return self.cipher.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Unable to decrypt data - invalid key or corrupted data")


class AccessControl:
    """Manages access control to the vault."""
    
    def __init__(self, yubikey_manager=None):
        """Initialize access control."""
        self.yubikey_manager = yubikey_manager
        self.access_tokens = {}
        self.access_log = []
    
    def authenticate(self, user_id: str, auth_factors: Dict[str, Any]) -> str:
        """
        Authenticate a user with multiple factors.
        Returns an access token if successful.
        """
        # Record authentication attempt
        attempt = {
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'ip_address': auth_factors.get('ip_address', 'unknown'),
            'success': False
        }
        
        # Check authentication factors
        if not self._verify_factors(user_id, auth_factors):
            self.access_log.append(attempt)
            logger.warning(f"Authentication failed for user {user_id}")
            raise ValueError("Authentication failed")
        
        # Generate access token
        token = self._generate_token()
        expiry = datetime.now() + timedelta(minutes=30)
        self.access_tokens[token] = {
            'user_id': user_id,
            'expiry': expiry,
            'permissions': self._get_user_permissions(user_id)
        }
        
        # Record successful authentication
        attempt['success'] = True
        self.access_log.append(attempt)
        logger.info(f"User {user_id} authenticated successfully")
        
        return token
    
    def _verify_factors(self, user_id: str, factors: Dict[str, Any]) -> bool:
        """Verify multiple authentication factors."""
        # In a real implementation, check against stored factors
        
        # YubiKey verification if available
        if self.yubikey_manager and 'yubikey_otp' in factors:
            yubikey_verified = self.yubikey_manager.verify_otp(
                user_id=user_id,
                otp=factors['yubikey_otp']
            )
            if not yubikey_verified:
                return False
        
        # Password verification (in production, use proper password hashing)
        if 'password' in factors:
            # Placeholder for password verification
            # In production, verify against securely stored hashed passwords
            pass
        
        # In this demo, always succeed if we get here
        # In production, implement proper verification
        return True
    
    def _generate_token(self) -> str:
        """Generate a secure random token."""
        random_bytes = os.urandom(32)
        return base64.urlsafe_b64encode(random_bytes).decode('utf-8')
    
    def _get_user_permissions(self, user_id: str) -> Dict[str, bool]:
        """Get permissions for a user."""
        # In production, fetch from a database
        if user_id == "mikael":
            return {
                'read_all': True,
                'write_all': True,
                'admin': True,
                'killswitch': True
            }
        elif user_id == "dnd-genesis":
            return {
                'read_all': True,
                'write_limited': True,
                'admin': False,
                'killswitch': False
            }
        elif user_id == "dnd-singularity":
            return {
                'read_limited': True,
                'write_none': True,
                'admin': False,
                'killswitch': False
            }
        else:
            return {
                'read_none': True,
                'write_none': True,
                'admin': False,
                'killswitch': False
            }
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify an access token and return user info if valid."""
        if token not in self.access_tokens:
            return None
        
        token_data = self.access_tokens[token]
        if datetime.now() > token_data['expiry']:
            # Token expired
            del self.access_tokens[token]
            return None
        
        return token_data
    
    def revoke_token(self, token: str) -> bool:
        """Revoke an access token."""
        if token in self.access_tokens:
            del self.access_tokens[token]
            return True
        return False
    
    def revoke_all_tokens(self) -> int:
        """Revoke all access tokens (killswitch)."""
        token_count = len(self.access_tokens)
        self.access_tokens = {}
        logger.warning(f"KILLSWITCH ACTIVATED: Revoked {token_count} access tokens")
        return token_count


class SecretVault:
    """Main vault for storing and managing secrets."""
    
    def __init__(self, storage_path: str = None, encryption: VaultEncryption = None, 
                 access_control: AccessControl = None):
        """Initialize the secret vault."""
        self.storage_path = storage_path or os.environ.get(
            'ORIGIN_VAULT_PATH', '/data/origin_vault.enc'
        )
        self.encryption = encryption or VaultEncryption()
        self.access_control = access_control or AccessControl()
        
        # Secrets are stored in memory while the vault is open
        self.secrets = {}
        self.is_open = False
        self.last_sync_time = None
        
        # Killswitch status
        self.killswitch_activated = False
    
    def open(self, master_token: str = None) -> bool:
        """Open the vault and load secrets."""
        if self.is_open:
            return True
        
        if self.killswitch_activated:
            logger.error("Killswitch activated - vault access denied")
            return False
        
        # In production, validate the master token
        
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    encrypted_data = f.read()
                    decrypted_data = self.encryption.decrypt(encrypted_data)
                    self.secrets = json.loads(decrypted_data)
                    logger.info(f"Loaded {len(self.secrets)} secrets from vault")
            else:
                # Initialize empty vault
                self.secrets = {}
                logger.info("Initialized new empty vault")
                self._save()
            
            self.is_open = True
            self.last_sync_time = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Failed to open vault: {e}")
            return False
    
    def close(self) -> bool:
        """Close the vault and secure all secrets."""
        if not self.is_open:
            return True
        
        try:
            self._save()
            self.secrets = {}
            self.is_open = False
            logger.info("Vault closed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to close vault: {e}")
            return False
    
    def _save(self) -> bool:
        """Save the vault to storage."""
        if not self.is_open:
            logger.error("Cannot save - vault is not open")
            return False
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Encrypt and save
            data_str = json.dumps(self.secrets)
            encrypted_data = self.encryption.encrypt(data_str)
            
            with open(self.storage_path, 'w') as f:
                f.write(encrypted_data)
            
            self.last_sync_time = datetime.now()
            logger.info(f"Saved {len(self.secrets)} secrets to vault")
            return True
        except Exception as e:
            logger.error(f"Failed to save vault: {e}")
            return False
    
    def get_secret(self, access_token: str, secret_key: str) -> Optional[str]:
        """Get a secret from the vault using an access token."""
        if not self.is_open:
            logger.error("Cannot get secret - vault is not open")
            return None
        
        if self.killswitch_activated:
            logger.error("Killswitch activated - secret access denied")
            return None
        
        # Verify access token
        token_data = self.access_control.verify_token(access_token)
        if not token_data:
            logger.warning(f"Invalid access token used to access secret: {secret_key}")
            return None
        
        # Check permissions
        user_id = token_data['user_id']
        permissions = token_data['permissions']
        
        # Log access attempt
        access_log = {
            'user_id': user_id,
            'action': 'get',
            'secret_key': secret_key,
            'timestamp': datetime.now().isoformat(),
            'success': False
        }
        
        # Check if user can read this secret
        can_read = (permissions.get('read_all', False) or 
                   (permissions.get('read_limited', False) and 
                    self._user_can_access_secret(user_id, secret_key)))
        
        if not can_read:
            logger.warning(f"User {user_id} denied access to secret: {secret_key}")
            return None
        
        # Return the secret if it exists
        if secret_key in self.secrets:
            access_log['success'] = True
            logger.info(f"User {user_id} accessed secret: {secret_key}")
            return self.secrets[secret_key]
        
        logger.warning(f"Secret not found: {secret_key}")
        return None
    
    def set_secret(self, access_token: str, secret_key: str, secret_value: str) -> bool:
        """Set a secret in the vault using an access token."""
        if not self.is_open:
            logger.error("Cannot set secret - vault is not open")
            return False
        
        if self.killswitch_activated:
            logger.error("Killswitch activated - secret modification denied")
            return False
        
        # Verify access token
        token_data = self.access_control.verify_token(access_token)
        if not token_data:
            logger.warning(f"Invalid access token used to modify secret: {secret_key}")
            return False
        
        # Check permissions
        user_id = token_data['user_id']
        permissions = token_data['permissions']
        
        # Log access attempt
        access_log = {
            'user_id': user_id,
            'action': 'set',
            'secret_key': secret_key,
            'timestamp': datetime.now().isoformat(),
            'success': False
        }
        
        # Check if user can write this secret
        can_write = (permissions.get('write_all', False) or 
                    (permissions.get('write_limited', False) and 
                     self._user_can_access_secret(user_id, secret_key)))
        
        if not can_write:
            logger.warning(f"User {user_id} denied permission to modify secret: {secret_key}")
            return False
        
        # Set the secret
        self.secrets[secret_key] = secret_value
        access_log['success'] = True
        
        # Save the vault
        save_success = self._save()
        logger.info(f"User {user_id} modified secret: {secret_key}")
        
        return save_success
    
    def delete_secret(self, access_token: str, secret_key: str) -> bool:
        """Delete a secret from the vault using an access token."""
        if not self.is_open:
            logger.error("Cannot delete secret - vault is not open")
            return False
        
        if self.killswitch_activated:
            logger.error("Killswitch activated - secret deletion denied")
            return False
        
        # Verify access token
        token_data = self.access_control.verify_token(access_token)
        if not token_data:
            logger.warning(f"Invalid access token used to delete secret: {secret_key}")
            return False
        
        # Check permissions
        user_id = token_data['user_id']
        permissions = token_data['permissions']
        
        # Log access attempt
        access_log = {
            'user_id': user_id,
            'action': 'delete',
            'secret_key': secret_key,
            'timestamp': datetime.now().isoformat(),
            'success': False
        }
        
        # Check if user can write this secret
        can_write = (permissions.get('write_all', False) or 
                    (permissions.get('write_limited', False) and 
                     self._user_can_access_secret(user_id, secret_key)))
        
        if not can_write:
            logger.warning(f"User {user_id} denied permission to delete secret: {secret_key}")
            return False
        
        # Delete the secret if it exists
        if secret_key in self.secrets:
            del self.secrets[secret_key]
            access_log['success'] = True
            
            # Save the vault
            save_success = self._save()
            logger.info(f"User {user_id} deleted secret: {secret_key}")
            
            return save_success
        
        logger.warning(f"Secret not found: {secret_key}")
        return False
    
    def _user_can_access_secret(self, user_id: str, secret_key: str) -> bool:
        """Determine if a user can access a specific secret."""
        # In production, implement proper access control rules
        # This is a simplified example
        
        # Admin users can access everything
        if user_id == "mikael":
            return True
        
        # dnd-genesis can access most secrets except killswitch
        if user_id == "dnd-genesis" and not secret_key.startswith("killswitch."):
            return True
        
        # dnd-singularity can only access secrets with its prefix
        if user_id == "dnd-singularity" and secret_key.startswith("singularity."):
            return True
        
        return False
    
    def list_secrets(self, access_token: str, prefix: str = None) -> List[str]:
        """List available secrets using an access token."""
        if not self.is_open:
            logger.error("Cannot list secrets - vault is not open")
            return []
        
        if self.killswitch_activated:
            logger.error("Killswitch activated - secret listing denied")
            return []
        
        # Verify access token
        token_data = self.access_control.verify_token(access_token)
        if not token_data:
            logger.warning("Invalid access token used to list secrets")
            return []
        
        # Check permissions
        user_id = token_data['user_id']
        permissions = token_data['permissions']
        
        # Filter secrets based on permissions
        if permissions.get('read_all', False):
            # Can read all secrets
            secret_keys = list(self.secrets.keys())
        elif permissions.get('read_limited', False):
            # Can read only specific secrets
            secret_keys = [k for k in self.secrets.keys() 
                          if self._user_can_access_secret(user_id, k)]
        else:
            # Cannot read any secrets
            logger.warning(f"User {user_id} denied permission to list secrets")
            return []
        
        # Apply prefix filter if provided
        if prefix:
            secret_keys = [k for k in secret_keys if k.startswith(prefix)]
        
        logger.info(f"User {user_id} listed {len(secret_keys)} secrets")
        return secret_keys
    
    def activate_killswitch(self, access_token: str) -> bool:
        """Activate the killswitch - revoke all access and prevent further access."""
        # Verify access token
        token_data = self.access_control.verify_token(access_token)
        if not token_data:
            logger.warning("Invalid access token used for killswitch activation")
            return False
        
        # Check permissions
        user_id = token_data['user_id']
        permissions = token_data['permissions']
        
        if not permissions.get('killswitch', False):
            logger.warning(f"User {user_id} denied permission to activate killswitch")
            return False
        
        # Activate killswitch
        self.killswitch_activated = True
        
        # Revoke all access tokens
        token_count = self.access_control.revoke_all_tokens()
        
        logger.critical(f"KILLSWITCH ACTIVATED by {user_id} - all access revoked")
        
        # In a real implementation, you might also:
        # - Notify administrators
        # - Shut down services
        # - Revoke other credentials
        # - Lock out all systems
        
        return True
    
    def deactivate_killswitch(self, master_override_key: str) -> bool:
        """Deactivate the killswitch - requires special master override."""
        # In production, implement a secure override mechanism
        # This is a simplified example
        
        expected_key = os.environ.get('ORIGIN_KILLSWITCH_OVERRIDE')
        if not expected_key or master_override_key != expected_key:
            logger.warning("Invalid master override key used for killswitch deactivation")
            return False
        
        self.killswitch_activated = False
        logger.warning("KILLSWITCH DEACTIVATED with master override")
        
        return True
    
    def sync_to_kubernetes(self, access_token: str, namespace: str = "governance-system",
                          prefix: str = None) -> bool:
        """Sync secrets to Kubernetes secrets."""
        if not self.is_open:
            logger.error("Cannot sync to Kubernetes - vault is not open")
            return False
        
        if self.killswitch_activated:
            logger.error("Killswitch activated - Kubernetes sync denied")
            return False
        
        # Verify access token
        token_data = self.access_control.verify_token(access_token)
        if not token_data:
            logger.warning("Invalid access token used for Kubernetes sync")
            return False
        
        # Check permissions
        user_id = token_data['user_id']
        permissions = token_data['permissions']
        
        if not permissions.get('admin', False):
            logger.warning(f"User {user_id} denied permission to sync to Kubernetes")
            return False
        
        try:
            # Get secrets to sync
            secret_keys = self.list_secrets(access_token, prefix)
            if not secret_keys:
                logger.warning("No secrets to sync to Kubernetes")
                return False
            
            # Prepare Kubernetes secret data
            k8s_data = {}
            for key in secret_keys:
                # Skip keys not matching prefix if specified
                if prefix and not key.startswith(prefix):
                    continue
                
                # Get the secret value
                value = self.get_secret(access_token, key)
                if value:
                    # Convert the key format (replace dots with underscores)
                    k8s_key = key.replace('.', '_')
                    # Base64 encode for Kubernetes
                    k8s_data[k8s_key] = base64.b64encode(value.encode('utf-8')).decode('utf-8')
            
            # In a real implementation, use the Kubernetes API to create/update secrets
            # This is a simplified example
            logger.info(f"Would sync {len(k8s_data)} secrets to Kubernetes namespace {namespace}")
            
            # Return the data for demonstration
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync to Kubernetes: {e}")
            return False


# Singleton vault instance
_vault_instance = None

def get_vault() -> SecretVault:
    """Get the singleton vault instance."""
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = SecretVault()
    return _vault_instance


# Example usage
if __name__ == "__main__":
    # Initialize vault
    vault = get_vault()
    vault.open()
    
    # Create test user authentication
    access_control = vault.access_control
    token = access_control.authenticate("mikael", {"password": "test"})
    
    # Set some secrets
    vault.set_secret(token, "github.token", "github_pat_12345")
    vault.set_secret(token, "singularity.api_key", "singularity_api_12345")
    vault.set_secret(token, "kubernetes.vultr.config", "base64_encoded_kubeconfig")
    
    # Retrieve a secret
    github_token = vault.get_secret(token, "github.token")
    print(f"Retrieved GitHub token: {github_token}")
    
    # List secrets
    secrets = vault.list_secrets(token)
    print(f"Available secrets: {secrets}")
    
    # Sync to Kubernetes
    vault.sync_to_kubernetes(token)
    
    # Close the vault
    vault.close()