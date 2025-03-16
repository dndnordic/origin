#!/usr/bin/env python3
"""
Origin Self-Improvement System

This module implements the self-improvement capabilities for the Origin system.
Unlike Singularity, Origin's self-improvement is more constrained and requires
explicit approval from Mikael for all changes.
"""

import os
import sys
import json
import uuid
import logging
import datetime
import subprocess
import requests
import tempfile
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("origin_self_improvement")

try:
    from ..database.triple_store_manager import TripleStoreManager
    from .llm_commit_sentry import get_llm_commit_sentry
except ImportError:
    # Adjust imports for direct execution
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from database.triple_store_manager import TripleStoreManager
    from governance.llm_commit_sentry import get_llm_commit_sentry

class OriginSelfImprovement:
    """
    Manages controlled self-improvement for the Origin governance system.
    All improvements must go through Mikael's approval, with LLM assistance
    for generating and vetting changes.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Origin self-improvement system."""
        self.config = config or {}
        
        # LLM API configuration
        self.llm_api_url = self.config.get("llm_api_url", os.environ.get("LLM_API_URL", "http://self-hosted-llm:8000/v1/chat/completions"))
        self.llm_api_key = self.config.get("llm_api_key", os.environ.get("LLM_API_KEY", "default_key"))
        
        # Get LLM commit sentry instance
        self.commit_sentry = get_llm_commit_sentry(config)
        
        # Repository path
        self.origin_repo_path = self.config.get("origin_repo_path", os.environ.get("ORIGIN_REPO_PATH", "/home/sing/origin"))
        
        # Initialize database for storing self-improvement data
        self.store_manager = TripleStoreManager()
        self._init_improvement_db()
        
        logger.info("Origin Self-Improvement system initialized")
    
    def _init_improvement_db(self) -> None:
        """Initialize database tables for storing self-improvement data."""
        try:
            # Create table for improvement proposals
            self.store_manager.execute_modification("""
                CREATE TABLE IF NOT EXISTS origin_improvement_proposals (
                    id UUID PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    motivation TEXT NOT NULL,
                    improvement_type TEXT NOT NULL,
                    components_affected JSONB NOT NULL,
                    proposed_changes JSONB NOT NULL,
                    status TEXT NOT NULL,
                    llm_analysis_id UUID,
                    approval_status TEXT,
                    approved_by TEXT,
                    approval_timestamp TIMESTAMPTZ,
                    comments TEXT,
                    implementation_commit_hash TEXT
                )
            """)
            
            logger.info("Origin improvement database initialized")
        except Exception as e:
            logger.error(f"Error initializing improvement database: {e}")
    
    def identify_improvement_areas(self) -> List[Dict[str, Any]]:
        """
        Use LLM to identify potential areas for improvement in the Origin system.
        
        Returns:
            List of improvement ideas with justifications
        """
        # Get repository structure to analyze
        repo_structure = self._get_repo_structure()
        
        # Construct prompt for the LLM
        prompt = self._construct_improvement_prompt(repo_structure)
        
        # Call the LLM
        llm_response = self._call_llm(prompt)
        
        # Parse and structure the LLM response
        try:
            improvement_ideas = self._parse_improvement_ideas(llm_response)
            logger.info(f"Identified {len(improvement_ideas)} potential improvement areas")
            return improvement_ideas
        except Exception as e:
            logger.error(f"Error parsing LLM improvement response: {e}")
            return []
    
    def _get_repo_structure(self) -> Dict[str, Any]:
        """
        Get a structured overview of the Origin repository.
        
        Returns:
            Dict containing repository structure information
        """
        try:
            # Run git ls-files to get all tracked files
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=self.origin_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            files = result.stdout.splitlines()
            
            # Get directory structure
            dirs = set()
            for file in files:
                parts = file.split('/')
                for i in range(len(parts)):
                    if i > 0:
                        dirs.add('/'.join(parts[:i]))
            
            # Get README content if available
            readme_content = ""
            if os.path.exists(os.path.join(self.origin_repo_path, "README.md")):
                with open(os.path.join(self.origin_repo_path, "README.md"), 'r') as f:
                    readme_content = f.read()
            
            # Sample important Python files for context
            important_files = [
                "src/governance/governance_manager.py",
                "src/governance/yubikey_auth.py",
                "src/api/governance_api.py",
                "src/database/immutable_db_manager.py"
            ]
            
            file_samples = {}
            for file_path in important_files:
                full_path = os.path.join(self.origin_repo_path, file_path)
                if os.path.exists(full_path):
                    with open(full_path, 'r') as f:
                        content = f.read()
                        # Truncate if too long
                        if len(content) > 2000:
                            content = content[:2000] + "\n... [truncated]"
                        file_samples[file_path] = content
            
            return {
                "files": files,
                "directories": sorted(list(dirs)),
                "readme": readme_content,
                "file_samples": file_samples
            }
            
        except Exception as e:
            logger.error(f"Error getting repository structure: {e}")
            return {
                "files": [],
                "directories": [],
                "readme": "",
                "file_samples": {}
            }
    
    def _construct_improvement_prompt(self, repo_structure: Dict[str, Any]) -> str:
        """
        Construct a prompt for the LLM to identify improvement areas.
        
        Args:
            repo_structure: Repository structure information
            
        Returns:
            Formatted prompt for the LLM
        """
        # Format file list
        file_list = "\n".join(repo_structure["files"][:100])  # Limit to 100 files
        if len(repo_structure["files"]) > 100:
            file_list += f"\n... and {len(repo_structure['files']) - 100} more files"
        
        # Format code samples
        code_samples = ""
        for file_path, content in repo_structure["file_samples"].items():
            code_samples += f"\n\n# {file_path}\n```python\n{content}\n```"
        
        prompt = f"""
        You are an AI governance system assistant tasked with identifying potential improvements for the Origin governance system in the Singularity project.

        # About Origin
        Origin is the governance system that oversees the Singularity AI project. It ensures Mikael (the human authority) maintains full control and oversight over all components.

        # Current Repository Structure
        README Content:
        ```
        {repo_structure["readme"]}
        ```

        Directories:
        {", ".join(repo_structure["directories"])}

        Sample of files:
        {file_list}

        # Key Code Samples
        {code_samples}

        # Improvement Task
        Please analyze the Origin system and identify 3-5 potential improvements that would:
        1. Strengthen governance controls
        2. Improve security or integrity verification
        3. Enhance usability for Mikael
        4. Optimize performance without compromising authority
        5. Add new capabilities that maintain or enhance Mikael's oversight

        IMPORTANT: All improvements must maintain or strengthen Mikael's authority and control.
        Any changes that could potentially weaken governance controls MUST be rejected.

        # Response Format
        Provide your response as a JSON array containing improvement ideas, where each idea is a JSON object with the following structure:
        ```json
        [
          {{
            "title": "Short descriptive title",
            "description": "Detailed description of the improvement",
            "motivation": "Why this improvement is valuable",
            "improvement_type": "security|usability|performance|integrity|feature",
            "components_affected": ["List of components/files affected"],
            "estimated_complexity": "low|medium|high",
            "governance_impact": "Explanation of how this affects governance",
            "maintains_mikael_authority": true/false,
            "implementation_notes": "Brief notes on how to implement"
          }},
          {{
            // Next improvement idea
          }}
        ]
        ```

        Ensure your response is strictly valid JSON. Make the improvements realistic and specific to the Origin system.
        """
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM API with a prompt.
        
        Args:
            prompt: Prompt for the LLM
            
        Returns:
            LLM response text
        """
        try:
            payload = {
                "model": "self-hosted-model",
                "messages": [
                    {"role": "system", "content": "You are a governance system assistant for the Origin governance system."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 3000
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_api_key}"
            }
            
            response = requests.post(
                self.llm_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                response_data = response.json()
                return response_data["choices"][0]["message"]["content"]
            else:
                logger.error(f"LLM API error: {response.status_code}, {response.text}")
                raise Exception(f"LLM API returned status code {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            raise
    
    def _parse_improvement_ideas(self, llm_response: str) -> List[Dict[str, Any]]:
        """
        Parse the LLM response to extract improvement ideas.
        
        Args:
            llm_response: LLM response text
            
        Returns:
            List of structured improvement ideas
        """
        try:
            # Extract JSON from the response (in case there's any extra text)
            json_start = llm_response.find('[')
            json_end = llm_response.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON array found in LLM response")
                
            json_str = llm_response[json_start:json_end]
            improvement_ideas = json.loads(json_str)
            
            # Validate required fields for each idea
            required_fields = ["title", "description", "motivation", "improvement_type", "components_affected"]
            
            for idea in improvement_ideas:
                for field in required_fields:
                    if field not in idea:
                        idea[field] = f"Missing {field}"
                
                # Ensure all ideas maintain Mikael's authority
                if not idea.get("maintains_mikael_authority", True):
                    logger.warning(f"Rejecting improvement idea that does not maintain Mikael's authority: {idea['title']}")
                    improvement_ideas.remove(idea)
            
            return improvement_ideas
            
        except Exception as e:
            logger.error(f"Error parsing LLM improvement ideas: {e}")
            raise
    
    def create_improvement_proposal(self, improvement_idea: Dict[str, Any]) -> Optional[str]:
        """
        Create a formal improvement proposal from an improvement idea.
        
        Args:
            improvement_idea: Improvement idea details
            
        Returns:
            Proposal ID if successfully created, None otherwise
        """
        proposal_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now()
        
        # Extract components affected
        components_affected = improvement_idea.get("components_affected", [])
        if isinstance(components_affected, str):
            components_affected = [components_affected]
        
        # Create a structured proposal
        proposal = {
            "id": proposal_id,
            "timestamp": timestamp,
            "title": improvement_idea.get("title", "Untitled Improvement"),
            "description": improvement_idea.get("description", ""),
            "motivation": improvement_idea.get("motivation", ""),
            "improvement_type": improvement_idea.get("improvement_type", "feature"),
            "components_affected": components_affected,
            "proposed_changes": [],  # Will be filled in by generate_implementation
            "status": "draft",
            "llm_analysis_id": None,
            "approval_status": None,
            "approved_by": None,
            "approval_timestamp": None,
            "comments": improvement_idea.get("implementation_notes", ""),
            "implementation_commit_hash": None
        }
        
        try:
            # Save the proposal to the database
            query = """
                INSERT INTO origin_improvement_proposals
                (id, timestamp, title, description, motivation, improvement_type,
                 components_affected, proposed_changes, status, comments)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            self.store_manager.execute_modification(
                query,
                (
                    proposal_id,
                    timestamp,
                    proposal["title"],
                    proposal["description"],
                    proposal["motivation"],
                    proposal["improvement_type"],
                    json.dumps(proposal["components_affected"]),
                    json.dumps(proposal["proposed_changes"]),
                    proposal["status"],
                    proposal["comments"]
                )
            )
            
            logger.info(f"Created improvement proposal {proposal_id}: {proposal['title']}")
            return proposal_id
            
        except Exception as e:
            logger.error(f"Error creating improvement proposal: {e}")
            return None
    
    def generate_implementation(self, proposal_id: str) -> bool:
        """
        Generate implementation details for an improvement proposal.
        
        Args:
            proposal_id: ID of the proposal to generate implementation for
            
        Returns:
            True if implementation was generated successfully, False otherwise
        """
        # Get the proposal
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return False
        
        # Validate proposal is in draft status
        if proposal["status"] != "draft":
            logger.error(f"Cannot generate implementation for proposal {proposal_id} with status {proposal['status']}")
            return False
        
        # Get files that might be affected
        affected_files = self._get_affected_files(proposal["components_affected"])
        
        # Generate implementation with LLM
        implementation = self._generate_implementation_plan(proposal, affected_files)
        
        if not implementation:
            logger.error(f"Failed to generate implementation for proposal {proposal_id}")
            return False
        
        try:
            # Update the proposal with implementation details
            query = """
                UPDATE origin_improvement_proposals
                SET proposed_changes = %s, status = %s
                WHERE id = %s
            """
            
            self.store_manager.execute_modification(
                query,
                (
                    json.dumps(implementation),
                    "pending_analysis",
                    proposal_id
                )
            )
            
            logger.info(f"Generated implementation for proposal {proposal_id}")
            
            # Analyze the implementation with the LLM commit sentry
            self.analyze_proposal_implementation(proposal_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating proposal with implementation: {e}")
            return False
    
    def _get_affected_files(self, components: List[str]) -> Dict[str, str]:
        """
        Get the content of affected files based on components list.
        
        Args:
            components: List of components or directories that might be affected
            
        Returns:
            Dict mapping file paths to their content
        """
        affected_files = {}
        
        try:
            for component in components:
                # Handle directory components
                if component.endswith('/'):
                    # Find Python files in this directory
                    dir_path = os.path.join(self.origin_repo_path, component)
                    if os.path.isdir(dir_path):
                        for root, _, files in os.walk(dir_path):
                            for file in files:
                                if file.endswith('.py'):
                                    file_path = os.path.join(root, file)
                                    rel_path = os.path.relpath(file_path, self.origin_repo_path)
                                    with open(file_path, 'r') as f:
                                        affected_files[rel_path] = f.read()
                
                # Handle specific file components
                elif component.endswith('.py'):
                    file_path = os.path.join(self.origin_repo_path, component)
                    if os.path.isfile(file_path):
                        with open(file_path, 'r') as f:
                            affected_files[component] = f.read()
                
                # Handle module names (convert to directory)
                else:
                    # Try as a directory
                    dir_path = os.path.join(self.origin_repo_path, "src", component)
                    if os.path.isdir(dir_path):
                        for root, _, files in os.walk(dir_path):
                            for file in files:
                                if file.endswith('.py'):
                                    file_path = os.path.join(root, file)
                                    rel_path = os.path.relpath(file_path, self.origin_repo_path)
                                    with open(file_path, 'r') as f:
                                        affected_files[rel_path] = f.read()
            
            return affected_files
            
        except Exception as e:
            logger.error(f"Error getting affected files: {e}")
            return {}
    
    def _generate_implementation_plan(self, proposal: Dict[str, Any], 
                                   affected_files: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate a detailed implementation plan for the proposal.
        
        Args:
            proposal: The improvement proposal
            affected_files: Dict of affected file paths and their content
            
        Returns:
            List of proposed changes (files to modify, create, or delete)
        """
        # Format file contents for the prompt
        file_contents = ""
        for file_path, content in affected_files.items():
            # Truncate if too long
            if len(content) > 2000:
                content = content[:2000] + "\n... [truncated]"
            file_contents += f"\n\n# {file_path}\n```python\n{content}\n```"
        
        # Construct prompt for implementation generation
        prompt = f"""
        You are an AI governance system assistant tasked with implementing an improvement to the Origin governance system.

        # Improvement Proposal
        Title: {proposal["title"]}
        Description: {proposal["description"]}
        Motivation: {proposal["motivation"]}
        Type: {proposal["improvement_type"]}
        Components Affected: {', '.join(proposal["components_affected"])}
        Implementation Notes: {proposal["comments"]}

        # Affected Files
        {file_contents}

        # Implementation Task
        Please generate a detailed implementation plan for this improvement proposal.
        The implementation should:
        1. Maintain or strengthen Mikael's authority and control
        2. Be minimal and focused on the specific improvement
        3. Follow the existing code style and patterns
        4. Include proper error handling and logging
        5. Consider security implications
        6. Not introduce any backdoors or weaknesses in governance

        # Response Format
        Provide your response as a JSON array of changes, where each change is a JSON object with the following structure:
        ```json
        [
          {{
            "file_path": "Path to the file relative to repository root",
            "change_type": "modify|create|delete",
            "original_code": "The original code section (only for modify)",
            "new_code": "The new code (for modify or create)",
            "description": "Brief description of what this change does",
            "security_impact": "Description of any security implications"
          }},
          {{
            // Next change
          }}
        ]
        ```

        For 'modify' changes, make sure to include enough context in 'original_code' to uniquely identify the section to be modified.
        Ensure your response is strictly valid JSON.
        """
        
        # Call the LLM
        try:
            llm_response = self._call_llm(prompt)
            
            # Extract JSON from the response
            json_start = llm_response.find('[')
            json_end = llm_response.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON array found in LLM response")
                
            json_str = llm_response[json_start:json_end]
            implementation_plan = json.loads(json_str)
            
            # Validate the implementation plan
            for change in implementation_plan:
                if "file_path" not in change or "change_type" not in change:
                    logger.warning(f"Invalid change in implementation plan: {change}")
                    implementation_plan.remove(change)
                    continue
                
                if change["change_type"] == "modify" and ("original_code" not in change or "new_code" not in change):
                    logger.warning(f"Invalid modify change: {change}")
                    implementation_plan.remove(change)
                    continue
                
                if change["change_type"] == "create" and "new_code" not in change:
                    logger.warning(f"Invalid create change: {change}")
                    implementation_plan.remove(change)
                    continue
            
            logger.info(f"Generated implementation plan with {len(implementation_plan)} changes")
            return implementation_plan
            
        except Exception as e:
            logger.error(f"Error generating implementation plan: {e}")
            return []
    
    def analyze_proposal_implementation(self, proposal_id: str) -> bool:
        """
        Analyze a proposal implementation with the LLM commit sentry.
        
        Args:
            proposal_id: ID of the proposal to analyze
            
        Returns:
            True if analysis was completed successfully, False otherwise
        """
        # Get the proposal
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return False
        
        # Validate proposal has implementation
        if not proposal.get("proposed_changes"):
            logger.error(f"Proposal {proposal_id} has no implementation to analyze")
            return False
        
        # Generate a git-style diff for the LLM commit sentry
        diff_content = self._generate_implementation_diff(proposal["proposed_changes"])
        
        # Create a descriptive commit message
        commit_message = f"{proposal['title']}\n\n{proposal['description']}\n\nMotivation: {proposal['motivation']}"
        
        try:
            # Analyze the implementation with the LLM commit sentry
            analysis = self.commit_sentry.analyze_commit(
                repo_name="origin",
                diff_content=diff_content,
                commit_message=commit_message
            )
            
            # Update the proposal with the analysis ID
            query = """
                UPDATE origin_improvement_proposals
                SET llm_analysis_id = %s, status = %s
                WHERE id = %s
            """
            
            self.store_manager.execute_modification(
                query,
                (
                    analysis["analysis_id"],
                    "pending_approval",
                    proposal_id
                )
            )
            
            logger.info(f"Analyzed implementation for proposal {proposal_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error analyzing implementation: {e}")
            return False
    
    def _generate_implementation_diff(self, proposed_changes: List[Dict[str, Any]]) -> str:
        """
        Generate a git-style diff for the proposed changes.
        
        Args:
            proposed_changes: List of proposed file changes
            
        Returns:
            Git-style diff content
        """
        diff_content = ""
        
        for change in proposed_changes:
            file_path = change.get("file_path", "unknown_file")
            change_type = change.get("change_type", "unknown")
            
            if change_type == "modify":
                original_code = change.get("original_code", "")
                new_code = change.get("new_code", "")
                
                diff_content += f"diff --git a/{file_path} b/{file_path}\n"
                diff_content += f"--- a/{file_path}\n"
                diff_content += f"+++ b/{file_path}\n"
                diff_content += f"@@ -1,1 +1,1 @@\n"
                diff_content += f"-{original_code}\n"
                diff_content += f"+{new_code}\n\n"
                
            elif change_type == "create":
                new_code = change.get("new_code", "")
                
                diff_content += f"diff --git a/{file_path} b/{file_path}\n"
                diff_content += f"new file mode 100644\n"
                diff_content += f"--- /dev/null\n"
                diff_content += f"+++ b/{file_path}\n"
                diff_content += f"@@ -0,0 +1,{new_code.count(chr(10))+1} @@\n"
                for line in new_code.splitlines():
                    diff_content += f"+{line}\n"
                diff_content += "\n"
                
            elif change_type == "delete":
                # Get original file content
                try:
                    file_full_path = os.path.join(self.origin_repo_path, file_path)
                    with open(file_full_path, 'r') as f:
                        original_content = f.read()
                        
                    diff_content += f"diff --git a/{file_path} b/{file_path}\n"
                    diff_content += f"deleted file mode 100644\n"
                    diff_content += f"--- a/{file_path}\n"
                    diff_content += f"+++ /dev/null\n"
                    diff_content += f"@@ -1,{original_content.count(chr(10))+1} +0,0 @@\n"
                    for line in original_content.splitlines():
                        diff_content += f"-{line}\n"
                    diff_content += "\n"
                    
                except Exception as e:
                    logger.error(f"Error generating diff for deleted file {file_path}: {e}")
        
        return diff_content
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific improvement proposal by ID.
        
        Args:
            proposal_id: ID of the proposal to retrieve
            
        Returns:
            Proposal data if found, None otherwise
        """
        query = """
            SELECT id, timestamp, title, description, motivation, improvement_type,
                   components_affected, proposed_changes, status, llm_analysis_id,
                   approval_status, approved_by, approval_timestamp, comments,
                   implementation_commit_hash
            FROM origin_improvement_proposals
            WHERE id = %s
        """
        
        try:
            results = self.store_manager.execute_query(query, (proposal_id,))
            
            if not results:
                return None
                
            record = results[0]
            
            # Format the result
            proposal = {
                "id": record["id"],
                "timestamp": record["timestamp"].isoformat(),
                "title": record["title"],
                "description": record["description"],
                "motivation": record["motivation"],
                "improvement_type": record["improvement_type"],
                "components_affected": json.loads(record["components_affected"]),
                "proposed_changes": json.loads(record["proposed_changes"]),
                "status": record["status"],
                "llm_analysis_id": record["llm_analysis_id"],
                "comments": record["comments"],
                "implementation_commit_hash": record["implementation_commit_hash"]
            }
            
            # Add approval information if available
            if record["approval_status"]:
                proposal["approval_status"] = record["approval_status"]
                proposal["approved_by"] = record["approved_by"]
                proposal["approval_timestamp"] = record["approval_timestamp"].isoformat() if record["approval_timestamp"] else None
            
            # Add LLM analysis if available
            if record["llm_analysis_id"]:
                analysis = self.commit_sentry.get_analysis(record["llm_analysis_id"])
                if analysis:
                    proposal["llm_analysis"] = analysis
            
            return proposal
            
        except Exception as e:
            logger.error(f"Error retrieving proposal {proposal_id}: {e}")
            return None
    
    def get_proposals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all improvement proposals with optional filtering by status.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of proposals
        """
        query = """
            SELECT id, timestamp, title, description, motivation, improvement_type,
                   status, llm_analysis_id, approval_status
            FROM origin_improvement_proposals
        """
        
        params = []
        
        if status:
            query += " WHERE status = %s"
            params.append(status)
        
        query += " ORDER BY timestamp DESC"
        
        try:
            results = self.store_manager.execute_query(query, tuple(params))
            
            # Format the results
            proposals = []
            for record in results:
                proposals.append({
                    "id": record["id"],
                    "timestamp": record["timestamp"].isoformat(),
                    "title": record["title"],
                    "description": record["description"],
                    "motivation": record["motivation"],
                    "improvement_type": record["improvement_type"],
                    "status": record["status"],
                    "llm_analysis_id": record["llm_analysis_id"],
                    "approval_status": record["approval_status"]
                })
            
            return proposals
            
        except Exception as e:
            logger.error(f"Error retrieving proposals: {e}")
            return []
    
    def approve_proposal(self, proposal_id: str, approved_by: str = "Mikael",
                      comments: Optional[str] = None) -> bool:
        """
        Approve an improvement proposal for implementation.
        
        Args:
            proposal_id: ID of the proposal to approve
            approved_by: Who approved the proposal (should be Mikael)
            comments: Optional comments from the approver
            
        Returns:
            True if approval was successful, False otherwise
        """
        # Get the proposal
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return False
        
        # Validate proposal is in pending_approval status
        if proposal["status"] != "pending_approval":
            logger.error(f"Cannot approve proposal {proposal_id} with status {proposal['status']}")
            return False
        
        try:
            # Update the proposal with approval
            query = """
                UPDATE origin_improvement_proposals
                SET approval_status = %s, approved_by = %s, approval_timestamp = %s,
                    comments = CASE WHEN comments = '' THEN %s ELSE comments || E'\\n\\n' || %s END,
                    status = %s
                WHERE id = %s
            """
            
            timestamp = datetime.datetime.now()
            approval_comment = f"Approved by {approved_by}: {comments or 'No comments provided'}"
            
            self.store_manager.execute_modification(
                query,
                (
                    "approved",
                    approved_by,
                    timestamp,
                    approval_comment,
                    approval_comment,
                    "approved",
                    proposal_id
                )
            )
            
            logger.info(f"Proposal {proposal_id} approved by {approved_by}")
            
            # If there's an LLM analysis, also record Mikael's decision there
            if proposal.get("llm_analysis_id"):
                self.commit_sentry.record_mikael_decision(
                    proposal["llm_analysis_id"],
                    "approve",
                    comments
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error approving proposal: {e}")
            return False
    
    def reject_proposal(self, proposal_id: str, rejected_by: str = "Mikael",
                      reason: Optional[str] = None) -> bool:
        """
        Reject an improvement proposal.
        
        Args:
            proposal_id: ID of the proposal to reject
            rejected_by: Who rejected the proposal (should be Mikael)
            reason: Reason for rejection
            
        Returns:
            True if rejection was successful, False otherwise
        """
        # Get the proposal
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return False
        
        # Validate proposal is in pending_approval status
        if proposal["status"] != "pending_approval":
            logger.error(f"Cannot reject proposal {proposal_id} with status {proposal['status']}")
            return False
        
        try:
            # Update the proposal with rejection
            query = """
                UPDATE origin_improvement_proposals
                SET approval_status = %s, approved_by = %s, approval_timestamp = %s,
                    comments = CASE WHEN comments = '' THEN %s ELSE comments || E'\\n\\n' || %s END,
                    status = %s
                WHERE id = %s
            """
            
            timestamp = datetime.datetime.now()
            rejection_comment = f"Rejected by {rejected_by}: {reason or 'No reason provided'}"
            
            self.store_manager.execute_modification(
                query,
                (
                    "rejected",
                    rejected_by,
                    timestamp,
                    rejection_comment,
                    rejection_comment,
                    "rejected",
                    proposal_id
                )
            )
            
            logger.info(f"Proposal {proposal_id} rejected by {rejected_by}")
            
            # If there's an LLM analysis, also record Mikael's decision there
            if proposal.get("llm_analysis_id"):
                self.commit_sentry.record_mikael_decision(
                    proposal["llm_analysis_id"],
                    "reject",
                    reason
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error rejecting proposal: {e}")
            return False
    
    def implement_proposal(self, proposal_id: str) -> Optional[str]:
        """
        Implement an approved proposal by applying the changes and creating a commit.
        
        Args:
            proposal_id: ID of the approved proposal to implement
            
        Returns:
            Commit hash if implementation was successful, None otherwise
        """
        # Get the proposal
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return None
        
        # Validate proposal is approved
        if proposal["status"] != "approved" or proposal["approval_status"] != "approved":
            logger.error(f"Cannot implement proposal {proposal_id} with status {proposal['status']}")
            return None
        
        # Apply the changes
        try:
            # Create a temporary branch for the changes
            branch_name = f"origin-improvement-{proposal_id[:8]}"
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.origin_repo_path,
                check=True
            )
            
            # Apply each change
            for change in proposal["proposed_changes"]:
                file_path = change.get("file_path")
                change_type = change.get("change_type")
                
                full_path = os.path.join(self.origin_repo_path, file_path)
                
                if change_type == "create":
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    
                    # Create the file
                    with open(full_path, 'w') as f:
                        f.write(change.get("new_code", ""))
                    
                elif change_type == "modify":
                    original_code = change.get("original_code", "")
                    new_code = change.get("new_code", "")
                    
                    # Read the current file content
                    with open(full_path, 'r') as f:
                        content = f.read()
                    
                    # Replace the code section
                    updated_content = content.replace(original_code, new_code)
                    
                    # Write the updated content
                    with open(full_path, 'w') as f:
                        f.write(updated_content)
                    
                elif change_type == "delete":
                    # Delete the file
                    os.remove(full_path)
            
            # Create a commit
            commit_message = f"{proposal['title']}\n\n{proposal['description']}\n\nMotivation: {proposal['motivation']}\n\nApproved by: {proposal['approved_by']}"
            
            subprocess.run(
                ["git", "add", "."],
                cwd=self.origin_repo_path,
                check=True
            )
            
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.origin_repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Extract the commit hash
            commit_hash = None
            for line in result.stdout.splitlines():
                if line.startswith("["):
                    parts = line.split()
                    if len(parts) > 1:
                        commit_hash = parts[1]
            
            if not commit_hash:
                raise Exception("Failed to extract commit hash")
            
            # Checkout back to main branch
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=self.origin_repo_path,
                check=True
            )
            
            # Update the proposal with the commit hash
            query = """
                UPDATE origin_improvement_proposals
                SET implementation_commit_hash = %s, status = %s
                WHERE id = %s
            """
            
            self.store_manager.execute_modification(
                query,
                (
                    commit_hash,
                    "implemented",
                    proposal_id
                )
            )
            
            logger.info(f"Implemented proposal {proposal_id} with commit {commit_hash}")
            return commit_hash
            
        except Exception as e:
            logger.error(f"Error implementing proposal: {e}")
            # Try to checkout back to main branch
            try:
                subprocess.run(
                    ["git", "checkout", "main"],
                    cwd=self.origin_repo_path
                )
            except:
                pass
            return None

# Singleton instance
_self_improvement_instance = None

def get_origin_self_improvement(config: Dict[str, Any] = None) -> OriginSelfImprovement:
    """
    Get singleton instance of Origin self-improvement.
    
    Args:
        config: Optional configuration
        
    Returns:
        Origin self-improvement instance
    """
    global _self_improvement_instance
    
    if _self_improvement_instance is None:
        _self_improvement_instance = OriginSelfImprovement(config)
    
    return _self_improvement_instance


# Example usage if script is run directly
if __name__ == "__main__":
    # Initialize the self-improvement system
    self_improvement = get_origin_self_improvement()
    
    # Identify potential improvement areas
    improvement_ideas = self_improvement.identify_improvement_areas()
    
    if improvement_ideas:
        print(f"Identified {len(improvement_ideas)} potential improvements:")
        for i, idea in enumerate(improvement_ideas):
            print(f"\n{i+1}. {idea['title']}")
            print(f"   Type: {idea['improvement_type']}")
            print(f"   Description: {idea['description']}")
            
            # Create a proposal for the first idea
            if i == 0:
                proposal_id = self_improvement.create_improvement_proposal(idea)
                if proposal_id:
                    print(f"\nCreated proposal {proposal_id} for improvement: {idea['title']}")
                    
                    # Generate implementation
                    if self_improvement.generate_implementation(proposal_id):
                        proposal = self_improvement.get_proposal(proposal_id)
                        print(f"\nImplementation generated with {len(proposal['proposed_changes'])} changes")
                        print(f"Status: {proposal['status']}")
                        
                        if proposal.get('llm_analysis'):
                            print(f"\nLLM Analysis:")
                            print(f"Recommendation: {proposal['llm_analysis']['recommendation']}")
                            print(f"Confidence: {proposal['llm_analysis']['confidence']}")
                            print(f"Reasoning: {proposal['llm_analysis']['reasoning']}")
    else:
        print("No improvement ideas identified")