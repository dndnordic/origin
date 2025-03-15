#!/usr/bin/env python3
"""
Event Store Manager

This module provides integration with Event Store for event sourcing of governance records.
It represents the secondary storage in the triple storage pattern.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union

# Mock EventStoreClient for environments without Event Store
# In a real implementation, you would use the official Python client
class EventStoreClient:
    def __init__(self, connection_string=None):
        self.connection_string = connection_string
        self.events = {}  # Mock in-memory storage
    
    def append_to_stream(self, stream_name, events, expected_version=None):
        if stream_name not in self.events:
            self.events[stream_name] = []
        
        # Simple optimistic concurrency check
        if expected_version is not None and expected_version != len(self.events[stream_name]):
            raise Exception(f"Concurrency error: expected version {expected_version} but found {len(self.events[stream_name])}")
        
        for event in events:
            self.events[stream_name].append(event)
        
        return len(self.events[stream_name]) - 1
    
    def read_stream_events_forward(self, stream_name, start, count):
        if stream_name not in self.events:
            return []
        
        return self.events[stream_name][start:start+count]

logger = logging.getLogger("event_store_manager")

class EventStoreManager:
    """
    Provides event sourcing capabilities for governance records.
    Stores all actions as a sequence of events, enabling complete history and auditability.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Event Store manager with configuration."""
        self.config = config or {}
        
        # Default configuration
        self.connection_string = self.config.get(
            'connection_string', 
            os.environ.get('EVENTSTORE_CONNECTION', 'tcp://localhost:1113')
        )
        
        # Connect to Event Store
        self.client = self._connect_to_event_store()
        
        logger.info(f"Event Store manager initialized - connected to {self.connection_string}")
    
    def _connect_to_event_store(self) -> EventStoreClient:
        """
        Connect to Event Store server.
        
        Returns:
            EventStoreClient: Connected Event Store client
        """
        try:
            # In a real implementation, this would connect to an actual Event Store instance
            client = EventStoreClient(self.connection_string)
            logger.info(f"Connected to Event Store at {self.connection_string}")
            return client
        except Exception as e:
            logger.error(f"Error connecting to Event Store: {e}")
            # For development or testing, return a mock client
            return EventStoreClient()
    
    def append_event(self, stream_id: str, event_type: str, event_data: Dict[str, Any],
                   metadata: Dict[str, Any] = None, expected_version: int = None) -> str:
        """
        Append an event to a specific stream.
        
        Args:
            stream_id: The ID of the stream to append to
            event_type: Type of event (e.g., "ProposalSubmitted", "ProposalApproved")
            event_data: The event data
            metadata: Optional metadata for the event
            expected_version: Optional expected version for optimistic concurrency control
            
        Returns:
            str: Event ID if successful
        """
        # Generate a unique event ID
        event_id = str(uuid.uuid4())
        
        # Prepare event
        event = {
            "eventId": event_id,
            "eventType": event_type,
            "data": event_data,
            "metadata": metadata or {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "governance_system"
            }
        }
        
        # Append to stream
        try:
            # In production code, you'd create proper EventData objects
            self.client.append_to_stream(stream_id, [event], expected_version)
            logger.info(f"Appended event {event_id} of type {event_type} to stream {stream_id}")
            return event_id
        except Exception as e:
            logger.error(f"Error appending event to stream {stream_id}: {e}")
            raise
    
    def read_stream(self, stream_id: str, start: int = 0, count: int = 100) -> List[Dict[str, Any]]:
        """
        Read events from a stream.
        
        Args:
            stream_id: The ID of the stream to read from
            start: The event number to start reading from
            count: The maximum number of events to read
            
        Returns:
            List[Dict[str, Any]]: List of events
        """
        try:
            events = self.client.read_stream_events_forward(stream_id, start, count)
            logger.info(f"Read {len(events)} events from stream {stream_id}")
            return events
        except Exception as e:
            logger.error(f"Error reading events from stream {stream_id}: {e}")
            return []
    
    def create_governance_record_from_events(self, stream_id: str) -> Dict[str, Any]:
        """
        Reconstruct a governance record from its event stream.
        
        Args:
            stream_id: The ID of the stream to reconstruct from
            
        Returns:
            Dict[str, Any]: The reconstructed record
        """
        events = self.read_stream(stream_id)
        if not events:
            logger.warning(f"No events found for stream {stream_id}")
            return None
        
        # Initialize an empty record
        record = {
            "record_id": stream_id,
            "history": []
        }
        
        # Apply events to build the current state
        for event in events:
            # Store the event in history
            record["history"].append({
                "event_id": event["eventId"],
                "event_type": event["eventType"],
                "timestamp": event["metadata"]["timestamp"],
                "data": event["data"]
            })
            
            # Update record state based on event type
            if event["eventType"] == "ProposalSubmitted":
                record.update({
                    "type": "proposal",
                    "status": "pending",
                    "title": event["data"]["title"],
                    "description": event["data"]["description"],
                    "submitter": event["data"]["submitter"],
                    "submission_time": event["metadata"]["timestamp"]
                })
            elif event["eventType"] == "ProposalApproved":
                record.update({
                    "status": "approved",
                    "approver": event["data"]["approver"],
                    "approval_time": event["metadata"]["timestamp"],
                    "approval_notes": event["data"].get("notes", "")
                })
            elif event["eventType"] == "ProposalRejected":
                record.update({
                    "status": "rejected",
                    "rejector": event["data"]["rejector"],
                    "rejection_time": event["metadata"]["timestamp"],
                    "rejection_reason": event["data"].get("reason", "")
                })
            # Add more event types as needed
        
        logger.info(f"Reconstructed record from {len(events)} events for stream {stream_id}")
        return record
    
    def get_all_proposals(self, status: Optional[str] = None) -> List[str]:
        """
        Get all proposal stream IDs, optionally filtered by status.
        
        Args:
            status: Optional status to filter by
            
        Returns:
            List[str]: List of stream IDs
        """
        # In a real implementation, this would use Event Store projections
        # For simplicity, we'll return an empty list
        logger.info(f"Retrieved proposals with status {status if status else 'any'}")
        return []
    
    def subscribe_to_governance_events(self, callback):
        """
        Subscribe to all governance events.
        
        Args:
            callback: Function to call when events occur
        """
        # In a real implementation, this would set up a subscription
        logger.info("Subscribed to governance events")
        # In practice, this would be an async operation and would run in the background


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize the Event Store manager
    event_store = EventStoreManager()
    
    # Example: Simulate governance proposal flow with events
    proposal_id = str(uuid.uuid4())
    stream_id = f"proposal-{proposal_id}"
    
    # Submit a proposal
    event_store.append_event(
        stream_id=stream_id,
        event_type="ProposalSubmitted",
        event_data={
            "title": "Add YubiKey Authentication to API",
            "description": "Implement YubiKey authentication for all governance API endpoints",
            "submitter": "singularity",
            "impact_assessment": "High security impact, medium complexity"
        }
    )
    
    # Approve the proposal
    event_store.append_event(
        stream_id=stream_id,
        event_type="ProposalApproved",
        event_data={
            "approver": "mikael",
            "notes": "Approved with condition to implement proper fallback mechanisms"
        }
    )
    
    # Reconstruct the record from events
    record = event_store.create_governance_record_from_events(stream_id)
    print(f"Reconstructed proposal record: {json.dumps(record, indent=2)}")