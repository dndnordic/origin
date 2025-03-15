#!/usr/bin/env python3
"""
Governance API

This module provides a FastAPI server for the governance system,
allowing Singularity to submit proposals and receive decisions.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Add parent directory to import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from governance.governance_manager import GovernanceManager
from governance.yubikey_auth import YubiKeyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("governance_api")

# Initialize FastAPI app
app = FastAPI(
    title="Mikael's Governance API",
    description="API for governing the Singularity system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Initialize managers
governance_manager = GovernanceManager()
yubikey_manager = YubiKeyManager()

# Pydantic models for API
class ProposalSubmission(BaseModel):
    title: str = Field(..., description="Title of the proposal")
    description: str = Field(..., description="Detailed description of the proposal")
    changes: List[Dict[str, Any]] = Field(..., description="List of changes proposed")
    impact_assessment: str = Field(..., description="Assessment of the proposal's impact")
    security_implications: str = Field(..., description="Security implications of the proposal")
    submitter: str = Field(..., description="Identity of the submitter")

class ApprovalRequest(BaseModel):
    yubikey_otp: Optional[str] = Field(None, description="YubiKey one-time password for verification")

class RejectionRequest(BaseModel):
    reason: str = Field(..., description="Reason for rejection")
    yubikey_otp: Optional[str] = Field(None, description="YubiKey one-time password for verification")

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

# Authentication dependency
async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Verify the authentication token.
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        str: Authenticated user ID
    
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    
    # In a real implementation, this would validate a JWT or session token
    # For this example, we'll use a simple validation
    if token.startswith("Bearer mikael_"):
        return "mikael"
    elif token.startswith("Bearer singularity_"):
        return "singularity"
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

# API endpoints
@app.get("/", response_model=ApiResponse)
async def root():
    """Root endpoint to check if the API is running."""
    return {
        "success": True,
        "message": "Mikael's Governance API is running",
        "data": {
            "version": "1.0.0",
            "status": "operational"
        }
    }

@app.post("/proposals", response_model=ApiResponse)
async def submit_proposal(
    proposal: ProposalSubmission,
    user_id: str = Depends(verify_token)
):
    """
    Submit a proposal for governance approval.
    
    Args:
        proposal: The proposal details
        user_id: Authenticated user ID
        
    Returns:
        ApiResponse: API response with proposal ID
    """
    logger.info(f"Proposal submission from {user_id}: {proposal.title}")
    
    # Convert Pydantic model to dict
    proposal_dict = proposal.dict()
    
    # Submit to governance manager
    proposal_id = governance_manager.submit_for_approval(proposal_dict)
    
    if not proposal_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit proposal"
        )
    
    return {
        "success": True,
        "message": "Proposal submitted successfully",
        "data": {
            "proposal_id": proposal_id,
            "estimated_review_time": (
                datetime.now() + timedelta(hours=governance_manager.config["approval_timeout_hours"])
            ).isoformat()
        }
    }

@app.get("/proposals", response_model=ApiResponse)
async def get_proposals(
    user_id: str = Depends(verify_token)
):
    """
    Get all pending proposals.
    
    Args:
        user_id: Authenticated user ID
        
    Returns:
        ApiResponse: API response with list of proposals
    """
    # Only Mikael can see all proposals
    if user_id != "mikael":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Mikael can view all proposals"
        )
    
    proposals = governance_manager.get_pending_proposals()
    
    return {
        "success": True,
        "message": f"Retrieved {len(proposals)} pending proposals",
        "data": {
            "proposals": proposals
        }
    }

@app.get("/proposals/{proposal_id}", response_model=ApiResponse)
async def get_proposal(
    proposal_id: str,
    user_id: str = Depends(verify_token)
):
    """
    Get a specific proposal.
    
    Args:
        proposal_id: The ID of the proposal to retrieve
        user_id: Authenticated user ID
        
    Returns:
        ApiResponse: API response with proposal details
    """
    # Find the proposal
    proposal = next(
        (p for p in governance_manager.get_pending_proposals() if p["proposal_id"] == proposal_id),
        None
    )
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {proposal_id} not found"
        )
    
    # Singularity can only see its own proposals
    if user_id == "singularity" and proposal["submitter"] != "singularity":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own proposals"
        )
    
    return {
        "success": True,
        "message": f"Retrieved proposal {proposal_id}",
        "data": {
            "proposal": proposal
        }
    }

@app.post("/proposals/{proposal_id}/approve", response_model=ApiResponse)
async def approve_proposal(
    proposal_id: str,
    approval: ApprovalRequest,
    user_id: str = Depends(verify_token)
):
    """
    Approve a proposal.
    
    Args:
        proposal_id: The ID of the proposal to approve
        approval: Approval details including YubiKey OTP
        user_id: Authenticated user ID
        
    Returns:
        ApiResponse: API response with approval result
    """
    # Only Mikael can approve proposals
    if user_id != "mikael":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Mikael can approve proposals"
        )
    
    # YubiKey validation is required
    if not approval.yubikey_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YubiKey verification is required for approvals"
        )
    
    # Approve the proposal
    result = governance_manager.approve_proposal(
        proposal_id=proposal_id,
        approver=user_id,
        yubikey_otp=approval.yubikey_otp
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve proposal"
        )
    
    return {
        "success": True,
        "message": f"Proposal {proposal_id} approved successfully",
        "data": {
            "proposal_id": proposal_id,
            "status": "approved",
            "approver": user_id,
            "approval_time": datetime.now().isoformat()
        }
    }

@app.post("/proposals/{proposal_id}/reject", response_model=ApiResponse)
async def reject_proposal(
    proposal_id: str,
    rejection: RejectionRequest,
    user_id: str = Depends(verify_token)
):
    """
    Reject a proposal.
    
    Args:
        proposal_id: The ID of the proposal to reject
        rejection: Rejection details including reason and YubiKey OTP
        user_id: Authenticated user ID
        
    Returns:
        ApiResponse: API response with rejection result
    """
    # Only Mikael can reject proposals
    if user_id != "mikael":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Mikael can reject proposals"
        )
    
    # YubiKey validation is required
    if not rejection.yubikey_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YubiKey verification is required for rejections"
        )
    
    # Reject the proposal
    result = governance_manager.reject_proposal(
        proposal_id=proposal_id,
        approver=user_id,
        reason=rejection.reason,
        yubikey_otp=rejection.yubikey_otp
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject proposal"
        )
    
    return {
        "success": True,
        "message": f"Proposal {proposal_id} rejected successfully",
        "data": {
            "proposal_id": proposal_id,
            "status": "rejected",
            "rejector": user_id,
            "rejection_time": datetime.now().isoformat(),
            "reason": rejection.reason
        }
    }

@app.get("/system/health", response_model=ApiResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "success": True,
        "message": "System is healthy",
        "data": {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy"
        }
    }

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.environ.get("GOVERNANCE_API_PORT", 8000))
    
    # Start the API server
    uvicorn.run(
        "governance_api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        workers=1
    )