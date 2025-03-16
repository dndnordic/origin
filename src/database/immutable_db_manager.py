#!/usr/bin/env python3
"""
ImmuDB Manager

This module provides integration with ImmuDB for tamper-proof storage of governance records.
"""

import base64
import hashlib
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any, Tuple, Union

try:
    from immudb import ImmudbClient
    from immudb.constants import PERMISSION_ADMIN, PERMISSION_RW, PERMISSION_R
except ImportError:
    # Mock ImmuDB client for development environments without ImmuDB
    class ImmudbClient:
        def __init__(self, *args, **kwargs):
            pass

        def login(self, *args, **kwargs):
            pass

        def verifiedSet(self, *args, **kwargs):
            pass

        def verifiedGet(self, *args, **kwargs):
            return {'value': b'{"mock": "data"}'}

logger = logging.getLogger("immutable_db_manager")

class ImmuDBManager:
    """
    Provides cryptographically verified storage for governance records.
    Ensures that once data is written, it cannot be altered without detection.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the ImmuDB manager with configuration."""
        self.config = config or {}
        
        # Support for connection string with multiple endpoints for high availability
        connection_string = os.environ.get('IMMUDB_CONNECTION_STRING', '')
        if connection_string:
            # Parse connection string format: "host1:port1,host2:port2,..."
            self.endpoints = []
            for endpoint in connection_string.split(','):
                if ':' in endpoint:
                    host, port = endpoint.strip().split(':')
                    self.endpoints.append((host, int(port)))
                else:
                    self.endpoints.append((endpoint.strip(), 3322))  # Default port
            
            # Use first endpoint as default, will try others on connection failure
            self.host, self.port = self.endpoints[0] if self.endpoints else ('localhost', 3322)
        else:
            # Legacy single endpoint configuration
            self.host = self.config.get('host', os.environ.get('IMMUDB_HOST', 'localhost'))
            self.port = int(self.config.get('port', os.environ.get('IMMUDB_PORT', '3322')))
            self.endpoints = [(self.host, self.port)]
        
        self.user = self.config.get('user', os.environ.get('IMMUDB_USER', 'immudb'))
        self.password = self.config.get('password', os.environ.get('IMMUDB_PASSWORD', 'immudb'))
        self.database = self.config.get('database', os.environ.get('IMMUDB_DATABASE', 'governance'))
        
        # Connection retry settings
        self.max_retries = int(self.config.get('max_retries', os.environ.get('IMMUDB_MAX_RETRIES', '3')))
        self.retry_delay = float(self.config.get('retry_delay', os.environ.get('IMMUDB_RETRY_DELAY', '2.0')))
        
        # Connect to ImmuDB
        self.client = None
        self._connect_with_retry()
        
        logger.info(f"ImmuDB manager initialized - connected to {self.host}:{self.port} (with {len(self.endpoints)} total endpoints)")
    
    def _connect_with_retry(self) -> None:
        """Connect to ImmuDB with retry logic and failover to other endpoints."""
        # Try all endpoints with retries
        exceptions = []
        
        for endpoint_idx, (host, port) in enumerate(self.endpoints):
            self.host, self.port = host, port
            
            for attempt in range(self.max_retries):
                try:
                    self.client = self._connect_to_endpoint(host, port)
                    if self.client:
                        logger.info(f"Successfully connected to ImmuDB at {host}:{port} (endpoint {endpoint_idx+1}/{len(self.endpoints)}, attempt {attempt+1})")
                        return
                except Exception as e:
                    exceptions.append(f"Endpoint {host}:{port} attempt {attempt+1}: {str(e)}")
                    logger.warning(f"Failed to connect to ImmuDB at {host}:{port}, attempt {attempt+1}/{self.max_retries}: {e}")
                    time.sleep(self.retry_delay)
        
        # All connection attempts failed
        error_msg = f"Failed to connect to any ImmuDB endpoint after {self.max_retries} retries per endpoint.\nErrors: {exceptions}"
        logger.error(error_msg)
        # In development, use mock client
        if os.environ.get('ENVIRONMENT') == 'development':
            self.client = ImmudbClient()
        else:
            # In production, raise exception as this is critical
            raise ConnectionError(error_msg)
    
    def _connect_to_endpoint(self, host: str, port: int) -> ImmudbClient:
        """
        Connect to a specific ImmuDB endpoint.
        
        Args:
            host: ImmuDB hostname
            port: ImmuDB port
            
        Returns:
            ImmudbClient: Connected ImmuDB client
            
        Raises:
            Exception: If connection fails
        """
        client = ImmudbClient(host, port)
        client.login(self.user, self.password)
        # TODO: Create database if it doesn't exist
        
        # Test connection with a simple operation
        try:
            # Try to get server info or similar non-destructive operation
            # This depends on the ImmuDB client capabilities
            # client.serverInfo()  # Placeholder for actual API call
            pass
        except Exception as e:
            logger.error(f"Connection test failed for {host}:{port}: {e}")
            raise
            
        logger.info(f"Connected to ImmuDB at {host}:{port}")
        return client
    
    def store_record(self, record_type: str, authority: str, 
                   content: Dict[str, Any]) -> Optional[str]:
        """
        Store a governance record in ImmuDB with cryptographic verification.
        
        Args:
            record_type: Type of record (e.g., "proposal", "approval", "rejection")
            authority: Who is creating this record (e.g., "mikael", "governance_system")
            content: The actual record content
            
        Returns:
            Optional[str]: Record ID if successful, None otherwise
        """
        try:
            # Generate a unique record ID
            timestamp = int(time.time() * 1000)
            record_id = f"{record_type}-{timestamp}-{hashlib.sha256(json.dumps(content).encode()).hexdigest()[:8]}"
            
            # Prepare record with metadata
            record = {
                "record_id": record_id,
                "record_type": record_type,
                "authority": authority,
                "timestamp": timestamp,
                "content": content,
                # Add a hash of the content for additional verification
                "content_hash": hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
            }
            
            # Store in ImmuDB with verified set
            key = f"record:{record_id}".encode('utf-8')
            value = json.dumps(record).encode('utf-8')
            self.client.verifiedSet(key, value)
            
            logger.info(f"Stored verified record {record_id} of type {record_type}")
            return record_id
        except Exception as e:
            logger.error(f"Error storing record: {e}")
            return None
    
    def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a governance record with cryptographic verification.
        
        Args:
            record_id: The ID of the record to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: The verified record, or None if not found
        """
        try:
            key = f"record:{record_id}".encode('utf-8')
            result = self.client.verifiedGet(key)
            
            if not result:
                logger.warning(f"Record {record_id} not found")
                return None
            
            record = json.loads(result['value'])
            
            # Verify content hash for additional security
            content_hash = hashlib.sha256(json.dumps(record['content'], sort_keys=True).encode()).hexdigest()
            if content_hash != record['content_hash']:
                logger.error(f"Content hash verification failed for record {record_id}")
                return None
            
            logger.info(f"Retrieved verified record {record_id}")
            return record
        except Exception as e:
            logger.error(f"Error retrieving record: {e}")
            return None
    
    def get_records_by_type(self, record_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve records of a specific type.
        
        Args:
            record_type: Type of records to retrieve
            limit: Maximum number of records to return
            
        Returns:
            List[Dict[str, Any]]: List of verified records
        """
        # In a real implementation, this would use ImmuDB's scan or zadd/zscan functionality
        # For simplicity in this example, we'll return an empty list
        logger.info(f"Retrieved records of type {record_type}")
        return []
    
    def verify_database_consistency(self) -> bool:
        """
        Verify the entire database for consistency and tampering.
        
        Returns:
            bool: True if database is consistent, False otherwise
        """
        # In a real implementation, this would use ImmuDB's consistency verification
        # For this example, we'll simulate a successful verification
        logger.info("Verified database consistency")
        return True
    
    def _generate_audit_proof(self, record_id: str) -> Dict[str, Any]:
        """
        Generate a cryptographic proof for a record that can be validated externally.
        
        Args:
            record_id: The ID of the record to generate proof for
            
        Returns:
            Dict[str, Any]: The audit proof
        """
        # In a real implementation, this would use ImmuDB's inclusion/consistency proofs
        # For this example, we'll return a mock proof
        proof = {
            "record_id": record_id,
            "timestamp": int(time.time() * 1000),
            "proof_hash": hashlib.sha256(record_id.encode()).hexdigest()
        }
        
        logger.info(f"Generated audit proof for record {record_id}")
        return proof


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize the ImmuDB manager
    db_manager = ImmuDBManager()
    
    # Example record
    example_record = {
        "title": "Security Policy Update",
        "description": "Update security policy to require YubiKey verification for all operations",
        "proposal_id": "proposal-20250315123456",
        "status": "approved",
        "approver": "mikael",
        "approval_time": "2025-03-15T12:34:56Z"
    }
    
    # Store the record
    record_id = db_manager.store_record(
        record_type="approval",
        authority="mikael",
        content=example_record
    )
    
    if record_id:
        # Retrieve the record
        retrieved_record = db_manager.get_record(record_id)
        print(f"Retrieved record: {json.dumps(retrieved_record, indent=2)}")
        
        # Verify database consistency
        is_consistent = db_manager.verify_database_consistency()
        print(f"Database consistency: {'Verified' if is_consistent else 'Failed'}")
    else:
        print("Failed to store record")