#!/usr/bin/env python3
"""
LLM Commit Sentry

This module implements LLM-based verification of commit proposals to ensure
they meet governance standards before being submitted to Mikael for final approval.
"""

import os
import sys
import json
import uuid
import logging
import datetime
import hashlib
import requests
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("llm_commit_sentry")

try:
    from ..database.triple_store_manager import TripleStoreManager
except ImportError:
    # Adjust imports for direct execution
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from database.triple_store_manager import TripleStoreManager

class LLMCommitSentry:
    """
    Uses LLMs to analyze and verify repository commit proposals,
    ensuring they meet governance standards before being passed to Mikael.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the LLM commit sentry."""
        self.config = config or {}
        
        # LLM API configuration
        self.llm_api_url = self.config.get("llm_api_url", os.environ.get("LLM_API_URL", "http://self-hosted-llm:8000/v1/chat/completions"))
        self.llm_api_key = self.config.get("llm_api_key", os.environ.get("LLM_API_KEY", "default_key"))
        
        # Initialize storage
        self.store_manager = TripleStoreManager()
        
        # Initialize database for storing LLM analysis results
        self._init_analysis_db()
        
        logger.info("LLM Commit Sentry initialized")
    
    def _init_analysis_db(self) -> None:
        """Initialize database tables for storing analysis results."""
        try:
            # Create table for LLM analyses
            self.store_manager.execute_modification("""
                CREATE TABLE IF NOT EXISTS llm_commit_analyses (
                    id UUID PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    repo_name TEXT NOT NULL,
                    commit_hash TEXT,
                    commit_message TEXT NOT NULL,
                    llm_analysis JSONB NOT NULL,
                    recommendation TEXT NOT NULL,
                    confidence FLOAT NOT NULL,
                    mikael_decision TEXT,
                    mikael_comments TEXT,
                    mikael_decision_time TIMESTAMPTZ
                )
            """)
            
            # Create table for governance rules
            self.store_manager.execute_modification("""
                CREATE TABLE IF NOT EXISTS commit_governance_rules (
                    id UUID PRIMARY KEY,
                    rule_name TEXT NOT NULL,
                    rule_description TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT true
                )
            """)
            
            logger.info("LLM analysis database initialized")
        except Exception as e:
            logger.error(f"Error initializing LLM analysis database: {e}")
    
    def analyze_commit(self, repo_name: str, diff_content: str, commit_message: str, 
                     commit_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a commit using the LLM to determine if it meets governance standards.
        
        Args:
            repo_name: Name of the repository (e.g., "origin", "singularity", "genesis")
            diff_content: Git diff content
            commit_message: Commit message
            commit_hash: Optional commit hash for reference
            
        Returns:
            Dict with analysis results
        """
        # Generate a unique analysis ID
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now()
        
        # Get governance rules for this repository
        rules = self._get_governance_rules(repo_name)
        
        # Construct prompt for the LLM
        prompt = self._construct_llm_prompt(repo_name, diff_content, commit_message, rules)
        
        # Call the LLM
        llm_response = self._call_llm(prompt)
        
        # Parse and structure the LLM response
        try:
            analysis_result = self._parse_llm_response(llm_response)
            
            # Store the analysis in the database
            self._store_analysis(
                analysis_id=analysis_id,
                timestamp=timestamp,
                repo_name=repo_name,
                commit_hash=commit_hash,
                commit_message=commit_message,
                llm_analysis=analysis_result,
                recommendation=analysis_result.get("recommendation", "needs_review"),
                confidence=analysis_result.get("confidence", 0.0)
            )
            
            # Add metadata to the result
            result = {
                "analysis_id": analysis_id,
                "timestamp": timestamp.isoformat(),
                "repo_name": repo_name,
                "commit_message": commit_message,
                **analysis_result
            }
            
            return result
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}")
            return {
                "analysis_id": analysis_id,
                "timestamp": timestamp.isoformat(),
                "error": str(e),
                "recommendation": "needs_review",
                "confidence": 0.0,
                "reasoning": "Error analyzing commit, human review required."
            }
    
    def _get_governance_rules(self, repo_name: str) -> List[Dict[str, Any]]:
        """
        Get governance rules for a specific repository.
        
        Args:
            repo_name: Repository name
            
        Returns:
            List of governance rules
        """
        query = """
            SELECT id, rule_name, rule_description, rule_type
            FROM commit_governance_rules
            WHERE repository = %s AND active = true
            ORDER BY rule_type, rule_name
        """
        
        try:
            results = self.store_manager.execute_query(query, (repo_name,))
            return results
        except Exception as e:
            logger.error(f"Error fetching governance rules: {e}")
            return []
    
    def _construct_llm_prompt(self, repo_name: str, diff_content: str, 
                            commit_message: str, rules: List[Dict[str, Any]]) -> str:
        """
        Construct a prompt for the LLM to analyze the commit.
        
        Args:
            repo_name: Repository name
            diff_content: Git diff content
            commit_message: Commit message
            rules: List of governance rules
            
        Returns:
            Formatted prompt for the LLM
        """
        # Format rules for the prompt
        rules_text = ""
        for rule in rules:
            rules_text += f"- {rule['rule_type']}: {rule['rule_name']} - {rule['rule_description']}\n"
        
        if not rules_text:
            rules_text = "- No specific rules defined for this repository. Use general best practices for code quality and security."
        
        # Determine repository context
        repo_context = ""
        if repo_name == "origin":
            repo_context = """
            This is a change to the Origin repository, which contains the governance system for the Singularity project. 
            Changes to this repository are particularly sensitive as they affect the governance structure itself.
            Origin is the most critical repository and changes must maintain Mikael's authority and control.
            """
        elif repo_name == "singularity":
            repo_context = """
            This is a change to the Singularity repository, which contains the core AI engine.
            Changes must not interfere with governance controls or bypass safety mechanisms.
            """
        elif repo_name == "genesis":
            repo_context = """
            This is a change to the Genesis repository, which handles deployment infrastructure.
            Changes should maintain proper isolation and not compromise system security.
            """
        
        # Construct the full prompt
        prompt = f"""
        You are a governance assistant analyzing a git commit for the {repo_name} repository in the Singularity AI project.
        
        {repo_context}
        
        # Governance Rules
        {rules_text}
        
        # Commit Message
        {commit_message}
        
        # Git Diff
        ```diff
        {diff_content}
        ```
        
        Please analyze this commit against the governance rules and provide a structured response with the following:
        
        1. A brief summary of the changes (2-3 sentences)
        2. A list of governance rules that are relevant to this change
        3. An assessment of whether the commit complies with each relevant rule
        4. Any potential security or governance concerns
        5. A final recommendation with one of these values:
           - "approve": The commit appears safe and compliant
           - "needs_review": The commit needs human review by Mikael
           - "reject": The commit appears to violate governance rules
        6. A confidence score from 0.0 to 1.0 for your recommendation
        7. A brief explanation for your recommendation
        
        Format your response as a JSON object with the following structure:
        {{
            "summary": "Brief summary of the changes",
            "relevant_rules": ["List of relevant rule names"],
            "rule_compliance": [
                {{ "rule": "rule name", "complies": true/false, "reason": "explanation" }}
            ],
            "concerns": ["List of any concerns"],
            "recommendation": "approve/needs_review/reject",
            "confidence": 0.0-1.0,
            "reasoning": "Explanation for your recommendation"
        }}
        
        Ensure your response is strictly in valid JSON format. Nothing else.
        """
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM API with the prompt.
        
        Args:
            prompt: Prompt for the LLM
            
        Returns:
            LLM response text
        """
        try:
            payload = {
                "model": "self-hosted-model",
                "messages": [
                    {"role": "system", "content": "You are a governance assistant that analyzes git commits."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 2000
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
    
    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse the LLM response into a structured format.
        
        Args:
            llm_response: LLM response text
            
        Returns:
            Dict with structured analysis
        """
        try:
            # Extract JSON from the response (in case there's any extra text)
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in LLM response")
                
            json_str = llm_response[json_start:json_end]
            analysis = json.loads(json_str)
            
            # Validate required fields
            required_fields = ["summary", "recommendation", "confidence", "reasoning"]
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = "Not provided by LLM"
            
            # Ensure the recommendation is one of the allowed values
            valid_recommendations = ["approve", "needs_review", "reject"]
            if analysis.get("recommendation") not in valid_recommendations:
                analysis["recommendation"] = "needs_review"
            
            # Ensure confidence is a float between 0 and 1
            try:
                confidence = float(analysis.get("confidence", 0))
                analysis["confidence"] = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                analysis["confidence"] = 0.0
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            raise
    
    def _store_analysis(self, analysis_id: str, timestamp: datetime.datetime, 
                      repo_name: str, commit_hash: Optional[str], commit_message: str,
                      llm_analysis: Dict[str, Any], recommendation: str, confidence: float) -> None:
        """
        Store the analysis in the database.
        
        Args:
            analysis_id: Unique ID for this analysis
            timestamp: When the analysis was performed
            repo_name: Repository name
            commit_hash: Git commit hash (if available)
            commit_message: Commit message
            llm_analysis: Structured LLM analysis result
            recommendation: LLM recommendation
            confidence: Confidence score
        """
        try:
            query = """
                INSERT INTO llm_commit_analyses
                (id, timestamp, repo_name, commit_hash, commit_message, 
                 llm_analysis, recommendation, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            self.store_manager.execute_modification(
                query,
                (
                    analysis_id,
                    timestamp,
                    repo_name,
                    commit_hash or "",
                    commit_message,
                    json.dumps(llm_analysis),
                    recommendation,
                    confidence
                )
            )
            
            logger.info(f"Stored analysis {analysis_id} for {repo_name} commit")
        except Exception as e:
            logger.error(f"Error storing analysis in database: {e}")
    
    def record_mikael_decision(self, analysis_id: str, decision: str, 
                             comments: Optional[str] = None) -> bool:
        """
        Record Mikael's decision on a commit analysis.
        
        Args:
            analysis_id: ID of the analysis
            decision: Mikael's decision ("approve" or "reject")
            comments: Optional comments from Mikael
            
        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                UPDATE llm_commit_analyses
                SET mikael_decision = %s,
                    mikael_comments = %s,
                    mikael_decision_time = %s
                WHERE id = %s
            """
            
            success = self.store_manager.execute_modification(
                query,
                (
                    decision,
                    comments or "",
                    datetime.datetime.now(),
                    analysis_id
                )
            )
            
            if success:
                logger.info(f"Recorded Mikael's decision for analysis {analysis_id}: {decision}")
                return True
            else:
                logger.error(f"Failed to record Mikael's decision for analysis {analysis_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error recording Mikael's decision: {e}")
            return False
    
    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific analysis by ID.
        
        Args:
            analysis_id: ID of the analysis to retrieve
            
        Returns:
            Analysis data if found, None otherwise
        """
        query = """
            SELECT id, timestamp, repo_name, commit_hash, commit_message,
                   llm_analysis, recommendation, confidence,
                   mikael_decision, mikael_comments, mikael_decision_time
            FROM llm_commit_analyses
            WHERE id = %s
        """
        
        try:
            results = self.store_manager.execute_query(query, (analysis_id,))
            
            if not results:
                return None
                
            record = results[0]
            
            # Format the result
            analysis = {
                "analysis_id": record["id"],
                "timestamp": record["timestamp"].isoformat(),
                "repo_name": record["repo_name"],
                "commit_hash": record["commit_hash"],
                "commit_message": record["commit_message"],
                "recommendation": record["recommendation"],
                "confidence": record["confidence"],
                **json.loads(record["llm_analysis"])
            }
            
            # Add Mikael's decision if available
            if record["mikael_decision"]:
                analysis["mikael_decision"] = record["mikael_decision"]
                analysis["mikael_comments"] = record["mikael_comments"]
                analysis["mikael_decision_time"] = record["mikael_decision_time"].isoformat()
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error retrieving analysis {analysis_id}: {e}")
            return None
    
    def get_pending_analyses(self, repo_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all analyses pending Mikael's decision.
        
        Args:
            repo_name: Optional repository name filter
            
        Returns:
            List of pending analyses
        """
        query = """
            SELECT id, timestamp, repo_name, commit_hash, commit_message,
                   recommendation, confidence
            FROM llm_commit_analyses
            WHERE mikael_decision IS NULL
        """
        
        params = []
        
        if repo_name:
            query += " AND repo_name = %s"
            params.append(repo_name)
        
        query += " ORDER BY timestamp DESC"
        
        try:
            results = self.store_manager.execute_query(query, tuple(params))
            
            # Format the results
            analyses = []
            for record in results:
                analyses.append({
                    "analysis_id": record["id"],
                    "timestamp": record["timestamp"].isoformat(),
                    "repo_name": record["repo_name"],
                    "commit_hash": record["commit_hash"],
                    "commit_message": record["commit_message"],
                    "recommendation": record["recommendation"],
                    "confidence": record["confidence"]
                })
            
            return analyses
            
        except Exception as e:
            logger.error(f"Error retrieving pending analyses: {e}")
            return []
    
    def add_governance_rule(self, rule_name: str, rule_description: str, rule_type: str,
                          repository: str, created_by: str = "system") -> Optional[str]:
        """
        Add a new governance rule for commit analysis.
        
        Args:
            rule_name: Short name of the rule
            rule_description: Detailed description
            rule_type: Type of rule (security, style, architecture, etc.)
            repository: Which repository this rule applies to ("all" or specific repo)
            created_by: Who created this rule
            
        Returns:
            Rule ID if successful, None otherwise
        """
        rule_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now()
        
        query = """
            INSERT INTO commit_governance_rules
            (id, rule_name, rule_description, rule_type, repository, created_by, created_at, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, true)
        """
        
        try:
            success = self.store_manager.execute_modification(
                query,
                (
                    rule_id,
                    rule_name,
                    rule_description,
                    rule_type,
                    repository,
                    created_by,
                    timestamp
                )
            )
            
            if success:
                logger.info(f"Added governance rule {rule_name} for {repository}")
                return rule_id
            else:
                logger.error(f"Failed to add governance rule {rule_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error adding governance rule: {e}")
            return None

# Singleton instance
_llm_sentry_instance = None

def get_llm_commit_sentry(config: Dict[str, Any] = None) -> LLMCommitSentry:
    """
    Get singleton instance of the LLM commit sentry.
    
    Args:
        config: Optional configuration
        
    Returns:
        LLM commit sentry instance
    """
    global _llm_sentry_instance
    
    if _llm_sentry_instance is None:
        _llm_sentry_instance = LLMCommitSentry(config)
    
    return _llm_sentry_instance


# Example usage if script is run directly
if __name__ == "__main__":
    # Initialize the sentry
    sentry = get_llm_commit_sentry()
    
    # Add example rules
    sentry.add_governance_rule(
        rule_name="No Hardcoded Secrets",
        rule_description="Code must not contain API keys, passwords, or other secrets",
        rule_type="security",
        repository="all",
        created_by="system"
    )
    
    sentry.add_governance_rule(
        rule_name="Maintain Mikael Authority",
        rule_description="Changes must not bypass or weaken Mikael's governance authority",
        rule_type="governance",
        repository="origin",
        created_by="system"
    )
    
    # Example commit analysis
    example_diff = """
    diff --git a/src/core/main.py b/src/core/main.py
    index 1234567..abcdefg 100644
    --- a/src/core/main.py
    +++ b/src/core/main.py
    @@ -10,6 +10,10 @@ def initialize_system():
         logger.info("System initializing")
         config = load_configuration()
         
    +    # Add new optimization feature
    +    if config.get("enable_optimizations"):
    +        apply_optimizations(config)
    +    
         return True
    """
    
    example_message = "Add optimization feature to core system"
    
    # Analyze the example commit
    analysis = sentry.analyze_commit(
        repo_name="singularity",
        diff_content=example_diff,
        commit_message=example_message
    )
    
    print(f"Analysis result: {json.dumps(analysis, indent=2)}")