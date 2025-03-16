"""
Client SDK for Origin Vault and Killswitch

This module provides a Python client SDK for interacting with the Origin Vault API.
It allows Singularity, Genesis, and other authorized systems to securely access
credentials while ensuring Origin maintains centralized control.
"""

import os
import json
import time
import logging
import requests
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Configuration for connecting to the vault API."""
    api_url: str = os.environ.get('ORIGIN_VAULT_API_URL', 'https://origin-api.dndnordic.com/api/vault')
    user_id: str = os.environ.get('ORIGIN_VAULT_USER_ID', '')
    default_auth_factor: str = os.environ.get('ORIGIN_VAULT_AUTH_FACTOR', '')
    verify_ssl: bool = True


class VaultClientException(Exception):
    """Exception raised for errors in the Vault Client."""
    pass


class VaultClient:
    """Client for interacting with the Origin Vault API."""
    
    def __init__(self, config: Optional[VaultConfig] = None):
        """Initialize the vault client."""
        self.config = config or VaultConfig()
        self.session = requests.Session()
        self.session.verify = self.config.verify_ssl
        
        # Authentication state
        self.token = None
        self.token_expiry = 0
    
    def _get_url(self, endpoint: str) -> str:
        """Get the full URL for an API endpoint."""
        return f"{self.config.api_url.rstrip('/')}/{endpoint.lstrip('/')}"
    
    def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated."""
        # Check if token is expired or not set
        if not self.token or time.time() >= self.token_expiry:
            self.authenticate()
    
    def authenticate(self, user_id: Optional[str] = None, 
                   auth_factors: Optional[Dict[str, Any]] = None) -> None:
        """Authenticate with the vault API."""
        user_id = user_id or self.config.user_id
        if not user_id:
            raise VaultClientException("No user_id provided for authentication")
        
        # If no auth factors provided, use default if available
        if not auth_factors and self.config.default_auth_factor:
            auth_factors = {"password": self.config.default_auth_factor}
        
        if not auth_factors:
            raise VaultClientException("No authentication factors provided")
        
        # Prepare request
        url = self._get_url('/auth')
        data = {
            'user_id': user_id,
            'auth_factors': auth_factors
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            # Parse response
            auth_data = response.json()
            self.token = auth_data.get('access_token')
            expires_in = auth_data.get('expires_in', 1800)  # Default to 30 minutes
            
            if not self.token:
                raise VaultClientException("No access token in authentication response")
            
            # Calculate expiry time (slightly before actual expiry to be safe)
            self.token_expiry = time.time() + (expires_in * 0.9)
            
            logger.info(f"Authenticated as {user_id}")
        except requests.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            raise VaultClientException(f"Authentication failed: {e}")
    
    def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
        """List available secrets."""
        self._ensure_authenticated()
        
        # Prepare request
        url = self._get_url('/secrets')
        params = {}
        if prefix:
            params['prefix'] = prefix
        
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            response = self.session.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            return data.get('secrets', [])
        except requests.RequestException as e:
            logger.error(f"Failed to list secrets: {e}")
            raise VaultClientException(f"Failed to list secrets: {e}")
    
    def get_secret(self, secret_key: str) -> Optional[str]:
        """Get a secret value."""
        self._ensure_authenticated()
        
        # Prepare request
        url = self._get_url(f'/secrets/{secret_key}')
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            response = self.session.get(url, headers=headers)
            
            # Handle 404 separately
            if response.status_code == 404:
                logger.warning(f"Secret not found: {secret_key}")
                return None
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            return data.get('value')
        except requests.RequestException as e:
            logger.error(f"Failed to get secret: {e}")
            raise VaultClientException(f"Failed to get secret: {e}")
    
    def set_secret(self, secret_key: str, secret_value: str) -> bool:
        """Set a secret value."""
        self._ensure_authenticated()
        
        # Prepare request
        url = self._get_url(f'/secrets/{secret_key}')
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        data = {
            'value': secret_value
        }
        
        try:
            response = self.session.put(url, headers=headers, json=data)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            return data.get('status') == 'success'
        except requests.RequestException as e:
            logger.error(f"Failed to set secret: {e}")
            raise VaultClientException(f"Failed to set secret: {e}")
    
    def delete_secret(self, secret_key: str) -> bool:
        """Delete a secret."""
        self._ensure_authenticated()
        
        # Prepare request
        url = self._get_url(f'/secrets/{secret_key}')
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            response = self.session.delete(url, headers=headers)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            return data.get('status') == 'deleted'
        except requests.RequestException as e:
            logger.error(f"Failed to delete secret: {e}")
            raise VaultClientException(f"Failed to delete secret: {e}")
    
    def sync_kubernetes(self, namespace: str = 'governance-system', 
                        prefix: Optional[str] = None) -> bool:
        """Sync secrets to Kubernetes."""
        self._ensure_authenticated()
        
        # Prepare request
        url = self._get_url('/sync/kubernetes')
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        data = {
            'namespace': namespace
        }
        if prefix:
            data['prefix'] = prefix
        
        try:
            response = self.session.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            return data.get('status') == 'success'
        except requests.RequestException as e:
            logger.error(f"Failed to sync Kubernetes: {e}")
            raise VaultClientException(f"Failed to sync Kubernetes: {e}")
    
    def get_killswitch_status(self) -> bool:
        """Get the status of the killswitch."""
        self._ensure_authenticated()
        
        # Prepare request
        url = self._get_url('/killswitch/status')
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            return data.get('active', False)
        except requests.RequestException as e:
            logger.error(f"Failed to get killswitch status: {e}")
            raise VaultClientException(f"Failed to get killswitch status: {e}")
    
    def activate_killswitch(self) -> bool:
        """Activate the killswitch."""
        self._ensure_authenticated()
        
        # Prepare request
        url = self._get_url('/killswitch/activate')
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        
        try:
            response = self.session.post(url, headers=headers)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            return data.get('status') == 'activated'
        except requests.RequestException as e:
            logger.error(f"Failed to activate killswitch: {e}")
            raise VaultClientException(f"Failed to activate killswitch: {e}")


def get_client() -> VaultClient:
    """Get a pre-configured vault client."""
    return VaultClient()


# Example usage
if __name__ == "__main__":
    # Get config from environment variables or provide explicitly
    config = VaultConfig(
        api_url=os.environ.get('ORIGIN_VAULT_API_URL', 'https://origin-api.dndnordic.com/api/vault'),
        user_id=os.environ.get('ORIGIN_VAULT_USER_ID', 'dnd-singularity'),
        default_auth_factor=os.environ.get('ORIGIN_VAULT_AUTH_FACTOR', '')
    )
    
    # Create the client
    client = VaultClient(config)
    
    # Authenticate
    client.authenticate()
    
    # List all secrets available to this user
    secrets = client.list_secrets()
    print(f"Available secrets: {secrets}")
    
    # Get a specific secret
    api_key = client.get_secret('singularity.api_key')
    print(f"API Key: {api_key}")
    
    # Check killswitch status
    is_active = client.get_killswitch_status()
    print(f"Killswitch active: {is_active}")
    
    # Only proceed if killswitch is not active
    if not is_active:
        print("Starting services...")
    else:
        print("ERROR: Killswitch is active, cannot start services")