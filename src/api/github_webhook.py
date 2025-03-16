#!/usr/bin/env python3
"""
GitHub Webhook Handler

This module handles GitHub webhooks for the Origin repository,
integrating with GitHub's web interface for Mikael's approvals.
"""

import os
import sys
import json
import hmac
import hashlib
import logging
import datetime
import requests
from typing import Dict, List, Any, Optional, Tuple
from flask import Flask, request, jsonify, Response, Blueprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("github_webhook")

try:
    from ..governance.llm_commit_sentry import get_llm_commit_sentry
    from ..governance.origin_self_improvement import get_origin_self_improvement
except ImportError:
    # Adjust imports for direct execution
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.governance.llm_commit_sentry import get_llm_commit_sentry
    from src.governance.origin_self_improvement import get_origin_self_improvement

# Create Blueprint for GitHub webhook endpoints
github_webhook = Blueprint('github_webhook', __name__)

# GitHub API configuration
GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")

def verify_github_signature(request_data: bytes, signature_header: str) -> bool:
    """
    Verify GitHub webhook signature.
    
    Args:
        request_data: Raw request data
        signature_header: GitHub signature header (X-Hub-Signature-256)
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not set, skipping signature verification")
        return True
        
    if not signature_header:
        logger.error("No signature header provided")
        return False
        
    try:
        # Get expected signature
        expected_signature = "sha256=" + hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            request_data,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures using constant-time comparison
        return hmac.compare_digest(expected_signature, signature_header)
        
    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        return False

def get_diff_content(repo_owner: str, repo_name: str, pull_request_number: int) -> Optional[str]:
    """
    Get diff content for a pull request.
    
    Args:
        repo_owner: Repository owner/organization
        repo_name: Repository name
        pull_request_number: Pull request number
        
    Returns:
        Diff content as string, or None if error
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not set, cannot get diff content")
        return None
        
    try:
        headers = {
            "Accept": "application/vnd.github.v3.diff",
            "Authorization": f"token {GITHUB_TOKEN}"
        }
        
        url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/pulls/{pull_request_number}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.text
        else:
            logger.error(f"Error getting diff content: {response.status_code}, {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting diff content: {str(e)}")
        return None

def post_comment(repo_owner: str, repo_name: str, issue_number: int, comment: str) -> bool:
    """
    Post a comment on a GitHub issue or pull request.
    
    Args:
        repo_owner: Repository owner/organization
        repo_name: Repository name
        issue_number: Issue or pull request number
        comment: Comment text
        
    Returns:
        True if comment was posted successfully, False otherwise
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not set, cannot post comment")
        return False
        
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {GITHUB_TOKEN}"
        }
        
        data = {
            "body": comment
        }
        
        url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/issues/{issue_number}/comments"
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in (201, 200):
            return True
        else:
            logger.error(f"Error posting comment: {response.status_code}, {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error posting comment: {str(e)}")
        return False

def add_label(repo_owner: str, repo_name: str, issue_number: int, label: str) -> bool:
    """
    Add a label to a GitHub issue or pull request.
    
    Args:
        repo_owner: Repository owner/organization
        repo_name: Repository name
        issue_number: Issue or pull request number
        label: Label to add
        
    Returns:
        True if label was added successfully, False otherwise
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not set, cannot add label")
        return False
        
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {GITHUB_TOKEN}"
        }
        
        # First check if the label exists
        url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/labels/{label}"
        response = requests.get(url, headers=headers)
        
        # If label doesn't exist, create it
        if response.status_code == 404:
            create_label_url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/labels"
            label_data = {
                "name": label,
                "color": "0366d6",  # GitHub blue
                "description": "Label added by governance system"
            }
            requests.post(create_label_url, headers=headers, json=label_data)
        
        # Add label to issue/PR
        data = {
            "labels": [label]
        }
        
        url = f"{GITHUB_API_URL}/repos/{repo_owner}/{repo_name}/issues/{issue_number}/labels"
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in (200, 201):
            return True
        else:
            logger.error(f"Error adding label: {response.status_code}, {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error adding label: {str(e)}")
        return False

@github_webhook.route('/webhook', methods=['POST'])
def handle_webhook() -> Response:
    """Handle GitHub webhook events."""
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_github_signature(request.data, signature):
        logger.error("Invalid signature")
        return jsonify({"error": "Invalid signature"}), 401
    
    # Parse event
    event_type = request.headers.get('X-GitHub-Event')
    payload = request.json
    
    # Handle pull request events
    if event_type == 'pull_request':
        return handle_pull_request_event(payload)
    
    # Handle pull request review events
    elif event_type == 'pull_request_review':
        return handle_pull_request_review_event(payload)
    
    # Acknowledge other events
    return jsonify({"message": f"Event {event_type} received"}), 200

def handle_pull_request_event(payload: Dict[str, Any]) -> Response:
    """
    Handle GitHub pull request events.
    
    Args:
        payload: Webhook payload
        
    Returns:
        Response for webhook
    """
    try:
        action = payload.get('action')
        pull_request = payload.get('pull_request', {})
        repo = payload.get('repository', {})
        
        # Extract repository information
        repo_owner = repo.get('owner', {}).get('login', '')
        repo_name = repo.get('name', '')
        pr_number = pull_request.get('number')
        pr_title = pull_request.get('title', '')
        pr_body = pull_request.get('body', '')
        
        # Handle PR opened or synchronized
        if action in ('opened', 'synchronize'):
            # Get LLM commit sentry
            commit_sentry = get_llm_commit_sentry()
            
            # Get diff content
            diff_content = get_diff_content(repo_owner, repo_name, pr_number)
            
            if not diff_content:
                logger.error(f"Could not get diff content for PR #{pr_number}")
                return jsonify({"error": "Could not get diff content"}), 500
            
            # Create a combined commit message from PR title and body
            commit_message = f"{pr_title}\n\n{pr_body}"
            
            # Determine repository type
            if repo_name.lower() == 'origin':
                repo_type = 'origin'
            elif repo_name.lower() == 'singularity':
                repo_type = 'singularity'
            elif repo_name.lower() == 'genesis':
                repo_type = 'genesis'
            else:
                repo_type = 'unknown'
            
            # Analyze the PR with LLM
            analysis = commit_sentry.analyze_commit(
                repo_name=repo_type,
                diff_content=diff_content,
                commit_message=commit_message
            )
            
            # Create a comment with the analysis result
            comment = f"## LLM Governance Analysis\n\n"
            comment += f"**Recommendation**: {analysis['recommendation']}\n"
            comment += f"**Confidence**: {analysis['confidence']:.2f}\n\n"
            comment += f"**Summary**: {analysis['summary']}\n\n"
            
            if 'relevant_rules' in analysis and analysis['relevant_rules']:
                comment += "**Relevant Rules**:\n"
                for rule in analysis['relevant_rules']:
                    comment += f"- {rule}\n"
                comment += "\n"
            
            if 'rule_compliance' in analysis and analysis['rule_compliance']:
                comment += "**Rule Compliance**:\n"
                for compliance in analysis['rule_compliance']:
                    complies = "✅" if compliance.get('complies', False) else "❌"
                    comment += f"- {complies} **{compliance.get('rule', 'Unknown')}**: {compliance.get('reason', 'No reason provided')}\n"
                comment += "\n"
            
            if 'concerns' in analysis and analysis['concerns']:
                comment += "**Concerns**:\n"
                for concern in analysis['concerns']:
                    comment += f"- {concern}\n"
                comment += "\n"
            
            comment += f"**Reasoning**: {analysis['reasoning']}\n\n"
            
            # Add appropriate labels and actions based on the recommendation
            if repo_type == 'origin':
                # For Origin repository, LLM can only recommend, Mikael must approve
                comment += "\n> **Note**: For the Origin repository, Mikael's approval is required."
                
                # Add label based on LLM recommendation
                if analysis['recommendation'] == 'approve':
                    add_label(repo_owner, repo_name, pr_number, "llm-recommends-approval")
                elif analysis['recommendation'] == 'needs_review':
                    add_label(repo_owner, repo_name, pr_number, "llm-recommends-review")
                else:  # 'reject'
                    add_label(repo_owner, repo_name, pr_number, "llm-recommends-rejection")
            else:
                # For Singularity and Genesis, LLM can approve directly
                if analysis['recommendation'] == 'approve':
                    comment += "\n> **Status**: This PR has been automatically approved by the LLM governance system."
                    add_label(repo_owner, repo_name, pr_number, "llm-approved")
                    
                    # For Singularity and Genesis, LLM can approve directly
                    # This would be expanded to actually approve using GitHub API
                    comment += "\n> **Note**: This is a simulated approval. In production, this would automatically approve the PR."
                    
                elif analysis['recommendation'] == 'needs_review':
                    comment += "\n> **Status**: This PR requires Mikael's manual review."
                    add_label(repo_owner, repo_name, pr_number, "needs-mikael-review")
                else:  # 'reject'
                    comment += "\n> **Status**: This PR has been automatically rejected by the LLM governance system. Please address the concerns."
                    add_label(repo_owner, repo_name, pr_number, "llm-rejected")
            
            # Post the comment
            post_comment(repo_owner, repo_name, pr_number, comment)
            
            return jsonify({"message": "PR analyzed successfully"}), 200
            
        return jsonify({"message": f"PR action {action} acknowledged"}), 200
        
    except Exception as e:
        logger.error(f"Error handling pull request event: {str(e)}")
        return jsonify({"error": f"Error handling pull request event: {str(e)}"}), 500

def handle_pull_request_review_event(payload: Dict[str, Any]) -> Response:
    """
    Handle GitHub pull request review events.
    
    Args:
        payload: Webhook payload
        
    Returns:
        Response for webhook
    """
    try:
        action = payload.get('action')
        review = payload.get('review', {})
        pull_request = payload.get('pull_request', {})
        repo = payload.get('repository', {})
        
        # We're only interested in completed reviews
        if action != 'submitted':
            return jsonify({"message": f"Review action {action} acknowledged"}), 200
        
        # Extract repository information
        repo_owner = repo.get('owner', {}).get('login', '')
        repo_name = repo.get('name', '')
        pr_number = pull_request.get('number')
        reviewer = review.get('user', {}).get('login', '')
        review_state = review.get('state', '')
        review_body = review.get('body', '')
        
        # Check if this is Mikael's review
        # In a real system, this would check against a list of authorized users
        is_mikael = reviewer.lower() in ['mikael', 'mhugo', 'mikki']
        
        # If this is Mikael's review of an Origin repository PR
        if is_mikael and repo_name.lower() == 'origin' and review_state in ('approved', 'rejected'):
            # Get LLM commit sentry to record the decision
            commit_sentry = get_llm_commit_sentry()
            
            # Find the analysis ID from a previous comment
            # In a real system, this would be stored more reliably
            analysis_id = None
            
            # Map GitHub review state to our internal format
            decision = "approve" if review_state == 'approved' else "reject"
            
            # Record Mikael's decision
            if analysis_id:
                commit_sentry.record_mikael_decision(
                    analysis_id=analysis_id,
                    decision=decision,
                    comments=review_body
                )
            
            # Add appropriate label
            if review_state == 'approved':
                add_label(repo_owner, repo_name, pr_number, "mikael-approved")
            else:
                add_label(repo_owner, repo_name, pr_number, "mikael-rejected")
            
            # Post a comment acknowledging Mikael's decision
            comment = f"## Mikael's Decision Recorded\n\n"
            comment += f"**Decision**: {decision}\n\n"
            
            if review_body:
                comment += f"**Comments**: {review_body}\n\n"
            
            post_comment(repo_owner, repo_name, pr_number, comment)
            
            return jsonify({"message": "Mikael's decision recorded"}), 200
            
        return jsonify({"message": "Review processed"}), 200
        
    except Exception as e:
        logger.error(f"Error handling review event: {str(e)}")
        return jsonify({"error": f"Error handling review event: {str(e)}"}), 500

# Setup instructions for GitHub webhooks
@github_webhook.route('/setup', methods=['GET'])
def webhook_setup_instructions() -> Response:
    """Show setup instructions for GitHub webhooks."""
    instructions = """
    # Setting Up GitHub Webhooks for Origin Governance

    1. Go to your GitHub repository settings
    2. Click on "Webhooks" in the left sidebar
    3. Click "Add webhook"
    4. Set Payload URL to: https://your-server.com/api/github/webhook
    5. Set Content type to: application/json
    6. Set Secret to a secure random string (same as GITHUB_WEBHOOK_SECRET env var)
    7. Select individual events: Pull requests, Pull request reviews
    8. Click "Add webhook"

    ## Required Environment Variables

    - GITHUB_TOKEN: Personal access token with repo permissions
    - GITHUB_WEBHOOK_SECRET: Secret used to verify webhook signatures
    """
    
    return Response(instructions, mimetype='text/markdown')

def init_app(app: Flask) -> None:
    """
    Initialize the GitHub webhook endpoints.
    
    Args:
        app: Flask application
    """
    app.register_blueprint(github_webhook, url_prefix='/api/github')