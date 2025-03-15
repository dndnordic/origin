#!/usr/bin/env python3
"""
Governance Manager

This module implements the core governance functionality that allows Mikael
to maintain control over the Singularity system.
"""

import datetime
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("governance_manager")

class GovernanceManager:
    """
    Core governance system that manages approvals, records decisions,
    and enforces security policies.
    """
    
    def __init__(self, config_path: str = None):
        """Initialize the governance manager with configuration."""
        self.config = self._load_config(config_path)
        self.approval_queue = []
        logger.info("Governance Manager initialized")
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            "approval_threshold": "mikael_only",  # Options: mikael_only, two_factor
            "record_storage": "triple_store",  # Options: database, immutable_db, triple_store
            "yubikey_required": True,
            "approval_timeout_hours": 48,
            "emergency_contact": "mikael@dndnordic.se",
            "notification_channels": ["email", "sms", "telegram"],
            "api_port": 8000
        }
        
        if not config_path or not os.path.exists(config_path):
            logger.warning("No config file found, using defaults")
            return default_config
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing values
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return default_config
    
    def submit_for_approval(self, proposal: Dict[str, Any]) -> str:
        """
        Submit a change proposal for governance approval.
        
        Args:
            proposal: Dict containing proposal details
                {
                    "title": str,
                    "description": str,
                    "changes": List[Dict],
                    "impact_assessment": str,
                    "security_implications": str,
                    "submitter": str
                }
                
        Returns:
            str: Proposal ID
        """
        # Generate unique proposal ID
        proposal_id = f"proposal-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Add metadata
        proposal["proposal_id"] = proposal_id
        proposal["status"] = "pending"
        proposal["submission_time"] = datetime.datetime.now().isoformat()
        proposal["approval_deadline"] = (
            datetime.datetime.now() + 
            datetime.timedelta(hours=self.config["approval_timeout_hours"])
        ).isoformat()
        
        # Add to approval queue
        self.approval_queue.append(proposal)
        
        # Send notifications
        self._notify_governance_stakeholders(proposal)
        
        logger.info(f"Proposal {proposal_id} submitted for approval")
        return proposal_id
    
    def approve_proposal(self, proposal_id: str, approver: str, 
                        yubikey_otp: Optional[str] = None) -> bool:
        """
        Approve a governance proposal.
        
        Args:
            proposal_id: The ID of the proposal to approve
            approver: Identity of the approver
            yubikey_otp: YubiKey one-time password for verification
            
        Returns:
            bool: True if approved, False otherwise
        """
        # Find proposal
        proposal = next((p for p in self.approval_queue 
                        if p["proposal_id"] == proposal_id), None)
        
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return False
        
        # Verify YubiKey if required
        if self.config["yubikey_required"] and not yubikey_otp:
            logger.error("YubiKey verification required but not provided")
            return False
            
        if self.config["yubikey_required"]:
            if not self._verify_yubikey(yubikey_otp, approver):
                logger.error("YubiKey verification failed")
                return False
        
        # Verify approver has authority
        if self.config["approval_threshold"] == "mikael_only" and approver != "mikael":
            logger.error(f"Only Mikael can approve proposals, but approver was {approver}")
            return False
        
        # Update proposal status
        proposal["status"] = "approved"
        proposal["approval_time"] = datetime.datetime.now().isoformat()
        proposal["approver"] = approver
        
        # Record the decision in all storage systems
        self._record_decision(proposal)
        
        # Remove from queue
        self.approval_queue = [p for p in self.approval_queue 
                              if p["proposal_id"] != proposal_id]
        
        logger.info(f"Proposal {proposal_id} approved by {approver}")
        return True
    
    def reject_proposal(self, proposal_id: str, approver: str, 
                       reason: str, yubikey_otp: Optional[str] = None) -> bool:
        """
        Reject a governance proposal.
        
        Args:
            proposal_id: The ID of the proposal to reject
            approver: Identity of the rejector
            reason: Reason for rejection
            yubikey_otp: YubiKey one-time password for verification
            
        Returns:
            bool: True if rejected, False otherwise
        """
        # Find proposal
        proposal = next((p for p in self.approval_queue 
                        if p["proposal_id"] == proposal_id), None)
        
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return False
        
        # Similar verification as approve_proposal
        if self.config["yubikey_required"] and not yubikey_otp:
            logger.error("YubiKey verification required but not provided")
            return False
            
        if self.config["yubikey_required"]:
            if not self._verify_yubikey(yubikey_otp, approver):
                logger.error("YubiKey verification failed")
                return False
        
        # Verify approver has authority
        if self.config["approval_threshold"] == "mikael_only" and approver != "mikael":
            logger.error(f"Only Mikael can reject proposals, but rejector was {approver}")
            return False
        
        # Update proposal status
        proposal["status"] = "rejected"
        proposal["rejection_time"] = datetime.datetime.now().isoformat()
        proposal["rejector"] = approver
        proposal["rejection_reason"] = reason
        
        # Record the decision
        self._record_decision(proposal)
        
        # Remove from queue
        self.approval_queue = [p for p in self.approval_queue 
                              if p["proposal_id"] != proposal_id]
        
        logger.info(f"Proposal {proposal_id} rejected by {approver}: {reason}")
        return True
    
    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """Get all pending proposals."""
        return self.approval_queue
    
    def _notify_governance_stakeholders(self, proposal: Dict[str, Any]) -> None:
        """Send notifications about new proposals."""
        # Implementation would connect to notification systems
        logger.info(f"Notification sent for proposal {proposal['proposal_id']}")
    
    def _verify_yubikey(self, otp: str, user: str) -> bool:
        """
        Verify YubiKey OTP.
        In a real implementation, this would connect to YubiKey validation servers
        or use local verification.
        """
        # Placeholder - would implement actual YubiKey validation
        logger.info(f"YubiKey verification for {user}")
        return True  # Placeholder
    
    def _record_decision(self, proposal: Dict[str, Any]) -> None:
        """
        Record governance decision in all storage systems for redundancy.
        Uses the TripleStoreManager to ensure tamper-proof, redundant storage.
        """
        try:
            from ..database.triple_store_manager import TripleStoreManager
            
            # Initialize triple store manager
            store_manager = TripleStoreManager()
            
            # Determine record type based on proposal status
            if proposal['status'] == 'approved':
                record_type = 'approval'
            elif proposal['status'] == 'rejected':
                record_type = 'rejection'
            else:
                record_type = 'decision'
            
            # Store the decision in all three systems
            record_id = store_manager.store_governance_record(
                record_type=record_type,
                authority=proposal.get('approver', proposal.get('rejector', 'governance_system')),
                content=proposal
            )
            
            if record_id:
                logger.info(f"Decision for proposal {proposal['proposal_id']} recorded with ID {record_id}")
            else:
                logger.error(f"Failed to record decision for proposal {proposal['proposal_id']}")
        except ImportError:
            # Fallback if triple store is not available
            logger.warning("Triple store not available, decision not recorded permanently")
        except Exception as e:
            logger.error(f"Error recording decision: {e}")
            # Important: This is a critical error, but we don't want to block the decision process
            # In a real implementation, you might trigger an alert or retry mechanism
    
    def run_api_server(self) -> None:
        """Run the governance API server to receive proposals and provide decisions."""
        # In a real implementation, this would start a web server
        port = self.config["api_port"]
        logger.info(f"Governance API server running on port {port}")


if __name__ == "__main__":
    # Example usage
    governance = GovernanceManager()
    
    # Example proposal submission
    proposal = {
        "title": "Add new feature X",
        "description": "This proposal adds feature X to improve system performance",
        "changes": [
            {"file": "src/core/feature_x.py", "type": "add"},
            {"file": "src/core/main.py", "type": "modify"}
        ],
        "impact_assessment": "Medium impact on performance, low risk",
        "security_implications": "None identified",
        "submitter": "singularity"
    }
    
    proposal_id = governance.submit_for_approval(proposal)
    print(f"Submitted proposal: {proposal_id}")
    
    # In a real application, the approval would come via API after human review
    approval_result = governance.approve_proposal(
        proposal_id, 
        "mikael",
        "fake-yubikey-otp-for-demo"
    )
    
    print(f"Approval result: {approval_result}")