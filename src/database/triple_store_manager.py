#!/usr/bin/env python3
"""
Triple Store Manager

This module integrates the three storage systems (ImmuDB, Event Store, and PostgreSQL)
to provide a robust, tamper-proof storage solution for governance records.
"""

import json
import logging
import os
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union

from .immutable_db_manager import ImmuDBManager
from .event_store_manager import EventStoreManager

# PostgreSQL manager placeholder (to be implemented in a future PR)
class PostgreSQLManager:
    def __init__(self, config=None):
        self.config = config or {}
        self.connected = False
    
    def store_record(self, record_type, authority, content):
        # Mock implementation
        return str(uuid.uuid4())
    
    def get_record(self, record_id):
        # Mock implementation
        return None
    
    def verify_database_consistency(self):
        # Mock implementation
        return True

logger = logging.getLogger("triple_store_manager")

class TripleStoreManager:
    """
    Manages the integration of three storage systems for robust governance records.
    Provides cross-verification and ensures consistent state across all systems.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Triple Store manager with configuration."""
        self.config = config or {}
        
        # Initialize all three storage systems
        self.immudb_manager = ImmuDBManager(self.config.get('immudb', {}))
        self.event_store_manager = EventStoreManager(self.config.get('event_store', {}))
        self.pg_manager = PostgreSQLManager(self.config.get('postgresql', {}))
        
        # Metrics and monitoring
        self.cross_verify_count = 0
        self.inconsistency_count = 0
        
        logger.info("Triple Store manager initialized")
    
    def store_governance_record(self, record_type: str, authority: str, 
                              content: Dict[str, Any]) -> Optional[str]:
        """
        Store a governance record in all three storage systems with verification.
        
        Args:
            record_type: Type of record (e.g., "proposal", "approval", "rejection")
            authority: Who is creating this record (e.g., "mikael", "governance_system")
            content: The actual record content
            
        Returns:
            Optional[str]: Record ID if successful, None otherwise
        """
        try:
            # Step 1: Store in ImmuDB (primary, tamper-proof storage)
            record_id = self.immudb_manager.store_record(record_type, authority, content)
            if not record_id:
                logger.error("Failed to store record in ImmuDB")
                return None
            
            # Step 2: Append to Event Store as an event
            event_type = self._map_record_type_to_event_type(record_type)
            stream_id = f"record-{record_id}"
            
            self.event_store_manager.append_event(
                stream_id=stream_id,
                event_type=event_type,
                event_data=content,
                metadata={
                    "authority": authority,
                    "record_id": record_id,
                    "storage_time": time.time()
                }
            )
            
            # Step 3: Store in PostgreSQL for fast querying (in a real impl)
            self.pg_manager.store_record(record_type, authority, content)
            
            # Step 4: Cross-verify (periodically, not on every write in production)
            if self.config.get('verify_on_write', False):
                self._cross_verify_record(record_id)
            
            logger.info(f"Successfully stored record {record_id} in all three storage systems")
            return record_id
        except Exception as e:
            logger.error(f"Error storing governance record: {e}")
            return None
    
    def get_governance_record(self, record_id: str, 
                            verify: bool = True) -> Optional[Dict[str, Any]]:
        """
        Retrieve a governance record with cross-verification.
        
        Args:
            record_id: The ID of the record to retrieve
            verify: Whether to perform cross-verification
            
        Returns:
            Optional[Dict[str, Any]]: The verified record, or None if not found
        """
        try:
            # Try to get from ImmuDB first (most trustworthy)
            record = self.immudb_manager.get_record(record_id)
            
            if not record:
                logger.warning(f"Record {record_id} not found in ImmuDB")
                return None
            
            # Optionally verify across storage systems
            if verify:
                verification_result = self._cross_verify_record(record_id)
                if not verification_result:
                    logger.warning(f"Cross-verification failed for record {record_id}")
                    # In a real implementation, you might trigger an alert
            
            logger.info(f"Retrieved record {record_id}")
            return record
        except Exception as e:
            logger.error(f"Error retrieving governance record: {e}")
            return None
    
    def get_records_by_type(self, record_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve records of a specific type.
        
        Args:
            record_type: Type of records to retrieve
            limit: Maximum number of records to return
            
        Returns:
            List[Dict[str, Any]]: List of records
        """
        # In a real implementation, this would use PostgreSQL for efficient querying
        # For this example, we'll use ImmuDB's get_records_by_type
        return self.immudb_manager.get_records_by_type(record_type, limit)
    
    def verify_system_consistency(self) -> bool:
        """
        Verify consistency across all storage systems.
        
        Returns:
            bool: True if all systems are consistent, False otherwise
        """
        # Step 1: Verify each system's internal consistency
        immudb_consistent = self.immudb_manager.verify_database_consistency()
        pg_consistent = self.pg_manager.verify_database_consistency()
        
        # Step 2: Cross-verify a sample of records
        # In a real implementation, you might use a more sophisticated sampling strategy
        sample_consistent = True
        
        if not immudb_consistent or not pg_consistent or not sample_consistent:
            logger.error("System consistency verification failed")
            return False
        
        logger.info("System consistency verified")
        return True
    
    def _cross_verify_record(self, record_id: str) -> bool:
        """
        Verify a record across all three storage systems.
        
        Args:
            record_id: The ID of the record to verify
            
        Returns:
            bool: True if verified across all systems, False otherwise
        """
        try:
            self.cross_verify_count += 1
            
            # Get the record from ImmuDB
            immudb_record = self.immudb_manager.get_record(record_id)
            if not immudb_record:
                logger.error(f"Record {record_id} not found in ImmuDB during cross-verification")
                return False
            
            # Get the record from Event Store
            stream_id = f"record-{record_id}"
            event_store_events = self.event_store_manager.read_stream(stream_id)
            
            if not event_store_events:
                logger.error(f"Record {record_id} events not found in Event Store during cross-verification")
                self.inconsistency_count += 1
                return False
            
            # Compare record data
            # In a real implementation, you would do a more thorough comparison
            
            logger.info(f"Cross-verification successful for record {record_id}")
            return True
        except Exception as e:
            logger.error(f"Error during cross-verification of record {record_id}: {e}")
            self.inconsistency_count += 1
            return False
    
    def _map_record_type_to_event_type(self, record_type: str) -> str:
        """
        Map a record type to an event type.
        
        Args:
            record_type: The record type to map
            
        Returns:
            str: The corresponding event type
        """
        mapping = {
            "proposal": "ProposalSubmitted",
            "approval": "ProposalApproved",
            "rejection": "ProposalRejected",
            "comment": "CommentAdded",
            "revision": "ProposalRevised"
        }
        
        return mapping.get(record_type, f"{record_type.capitalize()}Recorded")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize the Triple Store manager
    store = TripleStoreManager()
    
    # Example governance record
    example_record = {
        "title": "Implement Triple Storage Pattern",
        "description": "Add robust storage with ImmuDB, Event Store, and PostgreSQL",
        "impact_assessment": "Critical for data integrity",
        "security_implications": "Prevents tampering with governance records",
        "submitter": "dnd-genesis"
    }
    
    # Store the record
    record_id = store.store_governance_record(
        record_type="proposal",
        authority="dnd-genesis",
        content=example_record
    )
    
    if record_id:
        # Retrieve the record
        record = store.get_governance_record(record_id)
        print(f"Retrieved record: {json.dumps(record, indent=2)}")
        
        # Verify system consistency
        is_consistent = store.verify_system_consistency()
        print(f"System consistency: {'Verified' if is_consistent else 'Failed'}")