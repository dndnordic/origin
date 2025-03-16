#!/usr/bin/env python3
"""
Mikael's Governance CLI Tool

This command-line tool allows Mikael to interact with the governance system,
review proposals, approve/reject commits, and manage the self-improvement system.
"""

import os
import sys
import json
import argparse
import getpass
import textwrap
import datetime
import subprocess
from typing import Dict, List, Any, Optional, Tuple

try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.governance.llm_commit_sentry import get_llm_commit_sentry
    from src.governance.origin_self_improvement import get_origin_self_improvement
    from src.governance.governance_manager import GovernanceManager
    from src.governance.yubikey_auth import verify_yubikey
except ImportError:
    print("Error: Cannot import required modules. Make sure you're running this from the Origin repository root.")
    sys.exit(1)

def format_text(text: str, width: int = 80) -> str:
    """Format text with proper wrapping."""
    return "\n".join(textwrap.wrap(text, width))

def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def print_section(title: str) -> None:
    """Print a section header."""
    print("\n" + "-" * 80)
    print(f" {title}")
    print("-" * 80)

def authenticate_mikael() -> bool:
    """
    Authenticate Mikael with password and YubiKey.
    
    Returns:
        True if authentication is successful, False otherwise
    """
    print_header("Mikael's Authentication")
    
    # Password authentication (in a real system, this would be more secure)
    password = getpass.getpass("Enter your password: ")
    
    # Validate password (simplified for example)
    # In production, this would use proper password hashing and verification
    if password != os.environ.get("MIKAEL_PASSWORD", "mikael_governance"):
        print("Error: Invalid password")
        return False
    
    # YubiKey authentication
    use_yubikey = os.environ.get("YUBIKEY_ENABLED", "true").lower() == "true"
    
    if use_yubikey:
        print("\nTouch your YubiKey to authenticate...")
        otp = getpass.getpass("YubiKey OTP: ")
        
        # Verify YubiKey
        if not verify_yubikey(otp):
            print("Error: YubiKey authentication failed")
            return False
    
    print("\nAuthentication successful!")
    return True

def view_pending_commits() -> None:
    """View pending commit analyses that need Mikael's decision."""
    commit_sentry = get_llm_commit_sentry()
    
    # Get pending analyses
    pending_analyses = commit_sentry.get_pending_analyses()
    
    if not pending_analyses:
        print("No pending commit analyses found.")
        return
    
    print_header(f"Pending Commit Analyses ({len(pending_analyses)})")
    
    for i, analysis in enumerate(pending_analyses):
        print(f"\n[{i+1}] Analysis ID: {analysis['analysis_id']}")
        print(f"    Repository: {analysis['repo_name']}")
        print(f"    Timestamp: {analysis['timestamp']}")
        print(f"    Commit Message: {analysis['commit_message']}")
        print(f"    LLM Recommendation: {analysis['recommendation']} (confidence: {analysis['confidence']:.2f})")
    
    # Allow detailed view of a specific analysis
    while True:
        choice = input("\nEnter number to view details (or 'q' to quit): ")
        
        if choice.lower() == 'q':
            break
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(pending_analyses):
                view_commit_analysis(pending_analyses[index]['analysis_id'])
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a number or 'q'.")

def view_commit_analysis(analysis_id: str) -> None:
    """
    View detailed information about a commit analysis.
    
    Args:
        analysis_id: ID of the analysis to view
    """
    commit_sentry = get_llm_commit_sentry()
    
    # Get the full analysis
    analysis = commit_sentry.get_analysis(analysis_id)
    
    if not analysis:
        print(f"Analysis {analysis_id} not found.")
        return
    
    print_header(f"Commit Analysis: {analysis_id}")
    
    print(f"Repository: {analysis['repo_name']}")
    print(f"Timestamp: {analysis['timestamp']}")
    print(f"Commit Message: {analysis['commit_message']}")
    print(f"Commit Hash: {analysis.get('commit_hash', 'N/A')}")
    
    print_section("LLM Analysis")
    print(f"Recommendation: {analysis['recommendation']} (confidence: {analysis['confidence']:.2f})")
    print(f"Summary: {analysis['summary']}")
    
    if 'relevant_rules' in analysis and analysis['relevant_rules']:
        print("\nRelevant Rules:")
        for rule in analysis['relevant_rules']:
            print(f"- {rule}")
    
    if 'rule_compliance' in analysis and analysis['rule_compliance']:
        print("\nRule Compliance:")
        for compliance in analysis['rule_compliance']:
            complies = "✓" if compliance.get('complies', False) else "✗"
            print(f"- {complies} {compliance.get('rule', 'Unknown rule')}: {compliance.get('reason', 'No reason provided')}")
    
    if 'concerns' in analysis and analysis['concerns']:
        print("\nConcerns:")
        for concern in analysis['concerns']:
            print(f"- {concern}")
    
    print("\nReasoning:")
    print(format_text(analysis['reasoning']))
    
    # Allow approving or rejecting the commit
    if 'mikael_decision' not in analysis:
        print_section("Decision")
        
        while True:
            decision = input("Approve or reject this commit? (a/r/s to skip): ").lower()
            
            if decision == 'a':
                comments = input("Comments (optional): ")
                commit_sentry.record_mikael_decision(analysis_id, "approve", comments)
                print("Commit approved.")
                break
            elif decision == 'r':
                reason = input("Reason for rejection (required): ")
                if reason:
                    commit_sentry.record_mikael_decision(analysis_id, "reject", reason)
                    print("Commit rejected.")
                    break
                else:
                    print("Rejection reason is required.")
            elif decision == 's':
                print("Decision skipped.")
                break
            else:
                print("Invalid input. Please enter 'a' to approve, 'r' to reject, or 's' to skip.")

def view_improvement_proposals() -> None:
    """View self-improvement proposals for the Origin system."""
    self_improvement = get_origin_self_improvement()
    
    # Get all proposals
    all_proposals = self_improvement.get_proposals()
    
    # Filter pending approval proposals
    pending_proposals = [p for p in all_proposals if p['status'] == 'pending_approval']
    
    if not pending_proposals:
        print("No pending improvement proposals found.")
        
        # Show other proposals if any
        if all_proposals:
            print(f"\nThere are {len(all_proposals)} proposals in other statuses:")
            for status in set(p['status'] for p in all_proposals):
                count = sum(1 for p in all_proposals if p['status'] == status)
                print(f"- {status}: {count}")
            
            view_all = input("\nView all proposals? (y/n): ").lower() == 'y'
            if view_all:
                proposals_to_show = all_proposals
            else:
                return
        else:
            return
    else:
        proposals_to_show = pending_proposals
    
    print_header(f"Improvement Proposals ({len(proposals_to_show)})")
    
    for i, proposal in enumerate(proposals_to_show):
        print(f"\n[{i+1}] Proposal ID: {proposal['id']}")
        print(f"    Title: {proposal['title']}")
        print(f"    Type: {proposal['improvement_type']}")
        print(f"    Status: {proposal['status']}")
        print(f"    Timestamp: {proposal['timestamp']}")
    
    # Allow detailed view of a specific proposal
    while True:
        choice = input("\nEnter number to view details (or 'q' to quit): ")
        
        if choice.lower() == 'q':
            break
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(proposals_to_show):
                view_improvement_proposal(proposals_to_show[index]['id'])
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a number or 'q'.")

def view_improvement_proposal(proposal_id: str) -> None:
    """
    View detailed information about an improvement proposal.
    
    Args:
        proposal_id: ID of the proposal to view
    """
    self_improvement = get_origin_self_improvement()
    
    # Get the full proposal
    proposal = self_improvement.get_proposal(proposal_id)
    
    if not proposal:
        print(f"Proposal {proposal_id} not found.")
        return
    
    print_header(f"Improvement Proposal: {proposal_id}")
    
    print(f"Title: {proposal['title']}")
    print(f"Type: {proposal['improvement_type']}")
    print(f"Status: {proposal['status']}")
    print(f"Timestamp: {proposal['timestamp']}")
    
    print_section("Details")
    print("Description:")
    print(format_text(proposal['description']))
    
    print("\nMotivation:")
    print(format_text(proposal['motivation']))
    
    print("\nComponents Affected:")
    for component in proposal['components_affected']:
        print(f"- {component}")
    
    if proposal.get('comments'):
        print("\nComments:")
        print(format_text(proposal['comments']))
    
    # Show LLM analysis if available
    if proposal.get('llm_analysis'):
        print_section("LLM Analysis")
        analysis = proposal['llm_analysis']
        print(f"Recommendation: {analysis['recommendation']} (confidence: {analysis['confidence']:.2f})")
        print(f"Summary: {analysis['summary']}")
        
        if 'reasoning' in analysis:
            print("\nReasoning:")
            print(format_text(analysis['reasoning']))
    
    # Show proposed changes
    if proposal.get('proposed_changes'):
        print_section("Proposed Changes")
        for i, change in enumerate(proposal['proposed_changes']):
            print(f"\nChange {i+1}:")
            print(f"File: {change.get('file_path', 'Unknown')}")
            print(f"Type: {change.get('change_type', 'Unknown')}")
            print(f"Description: {change.get('description', 'No description provided')}")
            
            if change.get('security_impact'):
                print(f"Security Impact: {change.get('security_impact')}")
    
    # Allow approving or rejecting the proposal
    if proposal['status'] == 'pending_approval':
        print_section("Decision")
        
        while True:
            decision = input("Approve or reject this proposal? (a/r/s to skip): ").lower()
            
            if decision == 'a':
                comments = input("Comments (optional): ")
                self_improvement.approve_proposal(proposal_id, "Mikael", comments)
                print("Proposal approved.")
                
                # Ask if we should implement it
                implement = input("Implement the changes now? (y/n): ").lower() == 'y'
                if implement:
                    commit_hash = self_improvement.implement_proposal(proposal_id)
                    if commit_hash:
                        print(f"Proposal implemented in commit {commit_hash}")
                    else:
                        print("Failed to implement proposal.")
                break
                
            elif decision == 'r':
                reason = input("Reason for rejection (required): ")
                if reason:
                    self_improvement.reject_proposal(proposal_id, "Mikael", reason)
                    print("Proposal rejected.")
                    break
                else:
                    print("Rejection reason is required.")
            elif decision == 's':
                print("Decision skipped.")
                break
            else:
                print("Invalid input. Please enter 'a' to approve, 'r' to reject, or 's' to skip.")

def find_improvement_areas() -> None:
    """Use the self-improvement system to identify potential improvements."""
    self_improvement = get_origin_self_improvement()
    
    print_header("Finding Improvement Areas")
    print("Analyzing repository structure and identifying potential improvements...")
    print("This may take a minute or two...\n")
    
    # Identify improvement areas
    improvement_ideas = self_improvement.identify_improvement_areas()
    
    if not improvement_ideas:
        print("No improvement ideas identified.")
        return
    
    print_section(f"Identified {len(improvement_ideas)} Potential Improvements")
    
    for i, idea in enumerate(improvement_ideas):
        print(f"\n[{i+1}] {idea['title']}")
        print(f"    Type: {idea['improvement_type']}")
        print(f"    Description: {format_text(idea['description'])}")
    
    # Allow creating proposals from ideas
    while True:
        choice = input("\nEnter number to create proposal (or 'q' to quit): ")
        
        if choice.lower() == 'q':
            break
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(improvement_ideas):
                create_improvement_proposal(improvement_ideas[index])
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a number or 'q'.")

def create_improvement_proposal(idea: Dict[str, Any]) -> None:
    """
    Create an improvement proposal from an idea.
    
    Args:
        idea: Improvement idea details
    """
    self_improvement = get_origin_self_improvement()
    
    print_header(f"Creating Proposal: {idea['title']}")
    
    # Confirm creation
    confirm = input("Confirm proposal creation? (y/n): ").lower() == 'y'
    if not confirm:
        print("Proposal creation cancelled.")
        return
    
    # Create the proposal
    proposal_id = self_improvement.create_improvement_proposal(idea)
    
    if not proposal_id:
        print("Failed to create proposal.")
        return
    
    print(f"Created proposal {proposal_id}")
    
    # Ask if we should generate implementation
    generate = input("Generate implementation now? (y/n): ").lower() == 'y'
    if generate:
        print("\nGenerating implementation...")
        success = self_improvement.generate_implementation(proposal_id)
        
        if success:
            print("Implementation generated successfully.")
            
            # Get the updated proposal
            proposal = self_improvement.get_proposal(proposal_id)
            print(f"Status: {proposal['status']}")
            
            # Show LLM analysis summary if available
            if proposal.get('llm_analysis'):
                analysis = proposal['llm_analysis']
                print(f"\nLLM Analysis:")
                print(f"Recommendation: {analysis['recommendation']} (confidence: {analysis['confidence']:.2f})")
                print(f"Summary: {analysis['summary']}")
        else:
            print("Failed to generate implementation.")

def review_git_push() -> None:
    """
    Review a git push with LLM analysis before sending to remote repository.
    This simulates a pre-push hook that requires Mikael's approval.
    """
    commit_sentry = get_llm_commit_sentry()
    
    print_header("Review Git Push")
    
    # Get the range of commits to push
    branch = input("Branch to push (default: current branch): ") or get_current_branch()
    remote = input("Remote to push to (default: origin): ") or "origin"
    
    print(f"\nAnalyzing changes to push from {branch} to {remote}/{branch}...")
    
    # Get the diff of what we're about to push
    try:
        result = subprocess.run(
            ["git", "diff", f"{remote}/{branch}..{branch}"],
            capture_output=True,
            text=True,
            check=True
        )
        diff_content = result.stdout
        
        # Get commit messages
        result = subprocess.run(
            ["git", "log", f"{remote}/{branch}..{branch}", "--pretty=format:%s"],
            capture_output=True,
            text=True,
            check=True
        )
        commit_messages = result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e}")
        print(f"Error output: {e.stderr}")
        return
    
    if not diff_content:
        print("No changes to push.")
        return
    
    # Create a combined commit message for analysis
    combined_message = f"Push to {remote}/{branch} with the following commits:\n{commit_messages}"
    
    # Analyze the push
    analysis = commit_sentry.analyze_commit(
        repo_name="origin",
        diff_content=diff_content,
        commit_message=combined_message
    )
    
    # Display analysis
    print_section("LLM Analysis")
    print(f"Recommendation: {analysis['recommendation']} (confidence: {analysis['confidence']:.2f})")
    print(f"Summary: {analysis['summary']}")
    
    if 'reasoning' in analysis:
        print("\nReasoning:")
        print(format_text(analysis['reasoning']))
    
    # Ask for decision
    print_section("Decision")
    
    while True:
        decision = input("Allow this push? (y/n): ").lower()
        
        if decision == 'y':
            # Record the approval
            commit_sentry.record_mikael_decision(analysis['analysis_id'], "approve", "Push approved by Mikael")
            
            # Actually push the changes
            push = input("Execute 'git push' now? (y/n): ").lower() == 'y'
            if push:
                try:
                    result = subprocess.run(
                        ["git", "push", remote, branch],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    print(f"Push successful:\n{result.stdout}")
                except subprocess.CalledProcessError as e:
                    print(f"Push failed: {e}")
                    print(f"Error output: {e.stderr}")
            break
            
        elif decision == 'n':
            # Record the rejection
            reason = input("Reason for rejection (required): ")
            if reason:
                commit_sentry.record_mikael_decision(analysis['analysis_id'], "reject", reason)
                print("Push rejected.")
                break
            else:
                print("Rejection reason is required.")
        else:
            print("Invalid input. Please enter 'y' to allow or 'n' to reject.")

def get_current_branch() -> str:
    """Get the name of the current git branch."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "main"

def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Mikael's Governance CLI Tool")
    
    # Authentication is required for all operations
    if not authenticate_mikael():
        sys.exit(1)
    
    while True:
        print_header("Mikael's Governance CLI")
        print("1. View pending commit analyses")
        print("2. View improvement proposals")
        print("3. Find new improvement areas")
        print("4. Review git push")
        print("0. Exit")
        
        choice = input("\nEnter choice: ")
        
        if choice == '1':
            view_pending_commits()
        elif choice == '2':
            view_improvement_proposals()
        elif choice == '3':
            find_improvement_areas()
        elif choice == '4':
            review_git_push()
        elif choice == '0':
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()