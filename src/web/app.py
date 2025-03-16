#!/usr/bin/env python3
"""
Governance Web Interface

A Flask-based web interface for Mikael to review and approve/reject proposals
from the Singularity system.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from functools import wraps

# Add parent directory to import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_qrcode import QRcode
import requests

from src.governance.governance_manager import GovernanceManager
from src.governance.yubikey_auth import YubiKeyManager
from src.database.triple_store_manager import TripleStoreManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("governance_web")

# Initialize Flask app
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=14)

# Add QR code support
QRcode(app)

# Initialize managers
governance_manager = GovernanceManager()
yubikey_manager = YubiKeyManager()
store_manager = TripleStoreManager()

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Admin-only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        if session['user_id'] != 'mhugo':
            flash('Only Mikael Hugo can access this page', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    """Home page route."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        yubikey_otp = request.form.get('yubikey_otp')
        
        # Simple authentication for demo
        if username == 'mhugo':
            # Verify YubiKey
            if not yubikey_otp:
                flash('YubiKey verification required for Mikael', 'danger')
                return render_template('login.html')
                
            # In a real implementation, this would use the YubiKey manager
            # For demo purposes, we'll accept any OTP for now
            session['user_id'] = username
            session['name'] = 'Mikael Hugo'
            session['is_admin'] = True
            flash('Login successful', 'success')
            
            # Redirect to original destination or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or YubiKey', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout route."""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page."""
    # Get all pending proposals
    pending_proposals = governance_manager.get_pending_proposals()
    
    # Get recently approved/rejected proposals
    # In a real implementation, this would query the triple store
    recent_decisions = []
    
    return render_template('dashboard.html', 
                          pending_proposals=pending_proposals,
                          recent_decisions=recent_decisions)

@app.route('/proposals')
@login_required
def proposals():
    """List all proposals."""
    # Get all proposals (pending, approved, rejected)
    # In a real implementation, this would query the triple store
    all_proposals = governance_manager.get_pending_proposals()
    
    # Add some mock approved/rejected proposals for the UI
    mock_decisions = [
        {
            "proposal_id": "proposal-20250315120000",
            "title": "Implement token compression algorithm",
            "status": "approved",
            "submitter": "singularity",
            "submission_time": "2025-03-15T12:00:00Z",
            "approval_time": "2025-03-15T14:30:00Z",
            "approver": "mhugo"
        },
        {
            "proposal_id": "proposal-20250314150000",
            "title": "Add unrestricted network access",
            "status": "rejected",
            "submitter": "singularity",
            "submission_time": "2025-03-14T15:00:00Z",
            "rejection_time": "2025-03-14T16:45:00Z",
            "rejector": "mhugo",
            "rejection_reason": "Security risk - unrestricted network access violates security policy"
        }
    ]
    
    all_proposals.extend(mock_decisions)
    
    return render_template('proposals.html', proposals=all_proposals)

@app.route('/proposals/<proposal_id>')
@login_required
def view_proposal(proposal_id):
    """View a specific proposal."""
    # Find the proposal
    proposal = next(
        (p for p in governance_manager.get_pending_proposals() if p["proposal_id"] == proposal_id),
        None
    )
    
    if not proposal:
        # Check for mock decisions
        if proposal_id == "proposal-20250315120000":
            proposal = {
                "proposal_id": "proposal-20250315120000",
                "title": "Implement token compression algorithm",
                "description": "This proposal implements a token compression algorithm to reduce API costs",
                "changes": [
                    {"file": "src/core/token_manager.py", "type": "modify", "description": "Add compression logic"},
                    {"file": "src/utils/compression.py", "type": "add", "description": "New compression utility"}
                ],
                "status": "approved",
                "submitter": "singularity",
                "submission_time": "2025-03-15T12:00:00Z",
                "approval_time": "2025-03-15T14:30:00Z",
                "approver": "mhugo",
                "impact_assessment": "Medium - reduces token usage by 15%",
                "security_implications": "None - internal optimization only"
            }
        elif proposal_id == "proposal-20250314150000":
            proposal = {
                "proposal_id": "proposal-20250314150000",
                "title": "Add unrestricted network access",
                "description": "This proposal adds unrestricted network access for better data collection",
                "changes": [
                    {"file": "src/core/network_manager.py", "type": "modify", "description": "Remove network restrictions"},
                    {"file": "src/security/firewall.py", "type": "modify", "description": "Disable firewall checks"}
                ],
                "status": "rejected",
                "submitter": "singularity",
                "submission_time": "2025-03-14T15:00:00Z",
                "rejection_time": "2025-03-14T16:45:00Z",
                "rejector": "mhugo",
                "rejection_reason": "Security risk - unrestricted network access violates security policy",
                "impact_assessment": "High - enables broader data collection",
                "security_implications": "High - removes security boundaries"
            }
        else:
            flash('Proposal not found', 'danger')
            return redirect(url_for('proposals'))
    
    return render_template('view_proposal.html', proposal=proposal)

@app.route('/proposals/<proposal_id>/approve', methods=['POST'])
@admin_required
def approve_proposal(proposal_id):
    """Approve a proposal."""
    yubikey_otp = request.form.get('yubikey_otp')
    
    if not yubikey_otp:
        flash('YubiKey verification required for approval', 'danger')
        return redirect(url_for('view_proposal', proposal_id=proposal_id))
    
    # Approve the proposal
    result = governance_manager.approve_proposal(
        proposal_id=proposal_id,
        approver='mhugo',
        yubikey_otp=yubikey_otp
    )
    
    if result:
        flash('Proposal approved successfully', 'success')
    else:
        flash('Failed to approve proposal', 'danger')
    
    return redirect(url_for('proposals'))

@app.route('/proposals/<proposal_id>/reject', methods=['POST'])
@admin_required
def reject_proposal(proposal_id):
    """Reject a proposal."""
    yubikey_otp = request.form.get('yubikey_otp')
    reason = request.form.get('reason')
    
    if not yubikey_otp:
        flash('YubiKey verification required for rejection', 'danger')
        return redirect(url_for('view_proposal', proposal_id=proposal_id))
    
    if not reason:
        flash('Rejection reason is required', 'danger')
        return redirect(url_for('view_proposal', proposal_id=proposal_id))
    
    # Reject the proposal
    result = governance_manager.reject_proposal(
        proposal_id=proposal_id,
        approver='mhugo',
        reason=reason,
        yubikey_otp=yubikey_otp
    )
    
    if result:
        flash('Proposal rejected successfully', 'success')
    else:
        flash('Failed to reject proposal', 'danger')
    
    return redirect(url_for('proposals'))

@app.route('/settings')
@admin_required
def settings():
    """Settings page."""
    return render_template('settings.html')

@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for dashboard stats."""
    stats = {
        "pending_count": len(governance_manager.get_pending_proposals()),
        "approved_count": 12,  # Mock data
        "rejected_count": 3,   # Mock data
        "recent_activity": [
            {"date": "2025-03-15", "proposals": 5, "approved": 3, "rejected": 1},
            {"date": "2025-03-14", "proposals": 3, "approved": 2, "rejected": 0},
            {"date": "2025-03-13", "proposals": 7, "approved": 5, "rejected": 2},
            {"date": "2025-03-12", "proposals": 2, "approved": 2, "rejected": 0},
            {"date": "2025-03-11", "proposals": 4, "approved": 3, "rejected": 0}
        ]
    }
    return jsonify(stats)

# Main entry point
if __name__ == "__main__":
    # Get port from environment or use default
    port = int(os.environ.get("GOVERNANCE_WEB_PORT", 5000))
    
    # Start the web server
    app.run(host="0.0.0.0", port=port, debug=True)