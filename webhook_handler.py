"""GitHub webhook handler for automatic story status transitions."""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from config import Config
from database import DatabaseManager
from models import StoryStatus

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles GitHub webhook events for automatic story status transitions."""

    def __init__(self, config: Config):
        self.config = config
        self.database = DatabaseManager()
        
        # Default status transition rules
        self.status_rules = {
            # PR events
            "pull_request.opened": StoryStatus.IN_PROGRESS,
            "pull_request.ready_for_review": StoryStatus.REVIEW, 
            "pull_request.closed": None,  # Handle based on merged status
            
            # Issue events
            "issues.opened": StoryStatus.READY,
            "issues.closed": StoryStatus.DONE,
            "issues.reopened": StoryStatus.IN_PROGRESS,
            
            # Push events
            "push": None,  # Custom logic based on commits
        }
        
        # Load custom status mappings from config
        self._load_custom_status_mappings()

    def _load_custom_status_mappings(self):
        """Load custom status mapping configuration."""
        webhook_config = getattr(self.config, 'webhook_config', None)
        if webhook_config:
            custom_mappings = webhook_config.status_mappings
        else:
            custom_mappings = {}
        
        # Override default rules with custom mappings
        for event_action, status_str in custom_mappings.items():
            if status_str:
                try:
                    self.status_rules[event_action] = StoryStatus(status_str)
                except ValueError:
                    logger.warning(f"Invalid status '{status_str}' in custom mapping for '{event_action}'")
            else:
                self.status_rules[event_action] = None

    def verify_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify GitHub webhook signature."""
        webhook_secret = getattr(self.config, 'webhook_secret', None)
        if not webhook_secret:
            logger.warning("No webhook secret configured - skipping signature verification")
            return True
            
        if not signature_header:
            return False
            
        # Extract signature from header (format: "sha256=...")
        try:
            algorithm, signature = signature_header.split('=', 1)
            if algorithm != 'sha256':
                return False
        except ValueError:
            return False
            
        # Calculate expected signature
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures securely
        return hmac.compare_digest(signature, expected_signature)

    async def handle_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """Process GitHub webhook payload and trigger status transitions."""
        
        # Extract event information
        event_type = payload.get('action')
        
        # For push events, there's no action field - detect by presence of commits
        if not event_type and 'commits' in payload:
            event_type = 'push'
        
        if not event_type:
            logger.warning("Webhook payload missing 'action' field and not a push event")
            return {"status": "ignored", "reason": "missing action"}
            
        # Get repository information
        repository = payload.get('repository', {})
        repo_name = repository.get('full_name')
        
        if not repo_name:
            logger.warning("Webhook payload missing repository information")
            return {"status": "ignored", "reason": "missing repository"}
            
        # Determine event key for status mapping
        event_key = None
        if 'pull_request' in payload:
            event_key = f"pull_request.{event_type}"
        elif 'issue' in payload:
            event_key = f"issues.{event_type}"
        elif event_type == 'push':
            event_key = "push"
            
        if not event_key:
            logger.debug(f"Ignoring unsupported webhook event: {event_type}")
            return {"status": "ignored", "reason": "unsupported event"}
            
        logger.info(f"Processing webhook event: {event_key} for repository: {repo_name}")
        
        # Process the event
        result = await self._process_event(event_key, payload, repo_name)
        
        # Log the transition for audit trail
        await self._log_transition(event_key, payload, result, repo_name)
        
        return result

    async def _process_event(self, event_key: str, payload: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
        """Process specific webhook event and update story statuses."""
        
        if event_key.startswith("pull_request"):
            return await self._handle_pull_request_event(event_key, payload, repo_name)
        elif event_key.startswith("issues"):
            return await self._handle_issue_event(event_key, payload, repo_name)
        elif event_key == "push":
            return await self._handle_push_event(payload, repo_name)
        else:
            return {"status": "ignored", "reason": "unsupported event type"}

    async def _handle_pull_request_event(self, event_key: str, payload: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
        """Handle pull request webhook events."""
        pr = payload.get('pull_request', {})
        pr_number = pr.get('number')
        action = payload.get('action')
        
        # Find associated stories by PR number or issue references
        pr_title = pr.get('title', '')
        pr_body = pr.get('body', '')
        story_ids = await self._find_stories_for_pr(pr_number, f"{pr_title} {pr_body}", repo_name)
        
        if not story_ids:
            return {"status": "ignored", "reason": "no associated stories found"}
            
        # Determine target status
        target_status = None
        if action == "closed" and pr.get('merged', False):
            target_status = StoryStatus.DONE
        elif action == "closed" and not pr.get('merged', False):
            target_status = StoryStatus.READY  # Return to ready if PR closed without merge
        else:
            target_status = self.status_rules.get(event_key)
            
        if not target_status:
            return {"status": "ignored", "reason": "no status transition rule"}
            
        # Update story statuses
        updated_stories = []
        for story_id in story_ids:
            # Get current status for audit trail
            current_story = self.database.get_story(story_id)
            old_status = current_story.status.value if current_story else None
            
            success = self.database.update_story_status(story_id, target_status, propagate=True)
            if success:
                updated_stories.append(story_id)
                logger.info(f"Updated story {story_id} status to {target_status.value} due to PR {pr_number}")
                
                # Log the transition
                self.database.log_status_transition(
                    story_id=story_id,
                    old_status=old_status,
                    new_status=target_status.value,
                    trigger_type="webhook",
                    trigger_source="github",
                    event_type=event_key,
                    repository_name=repo_name,
                    pr_number=pr_number,
                    metadata={"pr_title": pr.get('title', ''), "merged": pr.get('merged', False)}
                )
                
        return {
            "status": "processed",
            "event": event_key,
            "updated_stories": updated_stories,
            "target_status": target_status.value,
            "pr_number": pr_number
        }

    async def _handle_issue_event(self, event_key: str, payload: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
        """Handle GitHub issue webhook events."""
        issue = payload.get('issue', {})
        issue_number = issue.get('number')
        
        # Find associated stories by issue number
        story_ids = await self._find_stories_for_issue(issue_number, repo_name)
        
        if not story_ids:
            return {"status": "ignored", "reason": "no associated stories found"}
            
        # Get target status from rules
        target_status = self.status_rules.get(event_key)
        if not target_status:
            return {"status": "ignored", "reason": "no status transition rule"}
            
        # Update story statuses
        updated_stories = []
        for story_id in story_ids:
            # Get current status for audit trail
            current_story = self.database.get_story(story_id)
            old_status = current_story.status.value if current_story else None
            
            success = self.database.update_story_status(story_id, target_status, propagate=True)
            if success:
                updated_stories.append(story_id)
                logger.info(f"Updated story {story_id} status to {target_status.value} due to issue {issue_number}")
                
                # Log the transition
                self.database.log_status_transition(
                    story_id=story_id,
                    old_status=old_status,
                    new_status=target_status.value,
                    trigger_type="webhook",
                    trigger_source="github",
                    event_type=event_key,
                    repository_name=repo_name,
                    issue_number=issue_number,
                    metadata={"issue_title": issue.get('title', '')}
                )
                
        return {
            "status": "processed", 
            "event": event_key,
            "updated_stories": updated_stories,
            "target_status": target_status.value,
            "issue_number": issue_number
        }

    async def _handle_push_event(self, payload: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
        """Handle push webhook events (commits)."""
        commits = payload.get('commits', [])
        
        # Look for story references in commit messages
        updated_stories = []
        for commit in commits:
            message = commit.get('message', '')
            story_ids = self._extract_story_references(message)
            
            for story_id in story_ids:
                # For commits, transition to IN_PROGRESS if not already there
                current_story = self.database.get_story(story_id)
                if current_story and current_story.status in [StoryStatus.DRAFT, StoryStatus.READY]:
                    old_status = current_story.status.value
                    success = self.database.update_story_status(story_id, StoryStatus.IN_PROGRESS, propagate=True)
                    if success:
                        updated_stories.append(story_id)
                        logger.info(f"Updated story {story_id} status to IN_PROGRESS due to commit")
                        
                        # Log the transition
                        self.database.log_status_transition(
                            story_id=story_id,
                            old_status=old_status,
                            new_status=StoryStatus.IN_PROGRESS.value,
                            trigger_type="webhook",
                            trigger_source="github",
                            event_type="push",
                            repository_name=repo_name,
                            commit_sha=commit.get('id'),
                            metadata={"commit_message": message[:100]}  # Truncate for storage
                        )
                        
        return {
            "status": "processed" if updated_stories else "ignored",
            "event": "push",
            "updated_stories": updated_stories,
            "commits_processed": len(commits)
        }

    async def _find_stories_for_pr(self, pr_number: int, pr_body: str, repo_name: str) -> List[str]:
        """Find story IDs associated with a pull request."""
        story_ids = []
        
        # Look for story references in PR body
        story_ids.extend(self._extract_story_references(pr_body))
        
        # Look in github_issues table for linked issues
        linked_stories = self.database.get_stories_by_github_issue(repo_name, pr_number)
        story_ids.extend([story.id for story in linked_stories])
        
        return list(set(story_ids))  # Remove duplicates

    async def _find_stories_for_issue(self, issue_number: int, repo_name: str) -> List[str]:
        """Find story IDs associated with a GitHub issue."""
        # Look in github_issues table
        linked_stories = self.database.get_stories_by_github_issue(repo_name, issue_number)
        return [story.id for story in linked_stories]

    def _extract_story_references(self, text: str) -> List[str]:
        """Extract story ID references from text (e.g., 'story_abc123', '#story_def456')."""
        import re
        
        # Match patterns like 'story_xxxxxxxx' or '#story_xxxxxxxx'
        # Allow alphanumeric characters for story IDs (minimum 3 characters after underscore)
        pattern = r'#?story_[a-zA-Z0-9]{3,}'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        # Clean up the matches (remove # prefix if present)
        result = [match.lstrip('#') for match in matches]
        logger.debug(f"Extracted story references from '{text}': {result}")
        return result

    async def _log_transition(self, event_key: str, payload: Dict[str, Any], result: Dict[str, Any], repo_name: str):
        """Log status transition for audit trail."""
        # Create audit log entry
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_key,
            "repository": repo_name,
            "result": result,
            "payload_summary": self._summarize_payload(payload)
        }
        
        # Store in database (assuming we'll add an audit table)
        # For now, just log it
        logger.info(f"Status transition audit: {json.dumps(audit_entry, indent=2)}")

    def _summarize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of webhook payload for audit logging."""
        summary = {
            "action": payload.get('action'),
            "repository": payload.get('repository', {}).get('full_name'),
            "sender": payload.get('sender', {}).get('login')
        }
        
        # Add specific details based on event type
        if 'pull_request' in payload:
            pr = payload['pull_request']
            summary.update({
                "pr_number": pr.get('number'),
                "pr_title": pr.get('title'),
                "merged": pr.get('merged', False)
            })
        elif 'issue' in payload:
            issue = payload['issue']
            summary.update({
                "issue_number": issue.get('number'),
                "issue_title": issue.get('title')
            })
        elif 'commits' in payload:
            summary.update({
                "commit_count": len(payload.get('commits', [])),
                "ref": payload.get('ref')
            })
            
        return summary