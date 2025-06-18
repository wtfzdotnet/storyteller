"""GitHub-primary storage manager for hierarchical story management.

This module implements GitHub Issues/Projects as the primary storage mechanism,
supporting both ephemeral (pipeline) and persistent (MCP) deployment contexts.
"""

import logging
import re
import yaml
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from github import Github, Repository
from github.GithubException import GithubException
from github.Issue import Issue
from github.IssueComment import IssueComment

from config import Config, get_config
from github_handler import GitHubHandler, IssueData
from models import (
    Epic, 
    UserStory, 
    SubStory, 
    StoryHierarchy, 
    StoryStatus, 
    StoryType
)
from story_manager import StoryAnalysis

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Configuration for GitHub storage manager."""
    
    primary: str = "github"  # "github" or "sqlite"
    cache_enabled: bool = False
    deployment_context: str = "pipeline"  # "pipeline" or "mcp"
    issue_label_prefix: str = "storyteller"
    epic_label: str = "epic"
    user_story_label: str = "user-story"
    sub_story_label: str = "sub-story"


@dataclass
class GitHubIssueMetadata:
    """Metadata extracted from GitHub issue."""
    
    story_id: str
    story_type: StoryType
    parent_id: Optional[str] = None
    target_repositories: List[str] = field(default_factory=list)
    expert_roles: List[str] = field(default_factory=list)
    status: StoryStatus = StoryStatus.DRAFT
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


class YAMLFrontmatterParser:
    """Parser for YAML frontmatter in GitHub issue bodies."""
    
    @staticmethod
    def extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        """Extract YAML frontmatter and remaining content from issue body.
        
        Args:
            content: The full issue body content
            
        Returns:
            Tuple of (frontmatter_dict, remaining_content)
        """
        if not content.strip():
            return {}, ""
            
        # Match YAML frontmatter pattern: ---\n...yaml...\n---
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)
        
        if not match:
            return {}, content
            
        try:
            frontmatter_text = match.group(1)
            remaining_content = match.group(2).strip()
            frontmatter = yaml.safe_load(frontmatter_text) or {}
            return frontmatter, remaining_content
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML frontmatter: {e}")
            return {}, content
    
    @staticmethod
    def create_frontmatter_content(metadata: Dict[str, Any], content: str) -> str:
        """Create issue body with YAML frontmatter.
        
        Args:
            metadata: Dictionary of metadata to include in frontmatter
            content: The main content body
            
        Returns:
            Formatted content with frontmatter
        """
        if not metadata:
            return content
            
        try:
            frontmatter_yaml = yaml.dump(metadata, default_flow_style=False)
            return f"---\n{frontmatter_yaml}---\n\n{content}"
        except yaml.YAMLError as e:
            logger.warning(f"Failed to create YAML frontmatter: {e}")
            return content


class GitHubStorageManager:
    """GitHub Issues-based storage manager for hierarchical story management."""
    
    def __init__(self, config: Optional[Config] = None, storage_config: Optional[StorageConfig] = None):
        """Initialize GitHub storage manager.
        
        Args:
            config: Main application configuration
            storage_config: Storage-specific configuration
        """
        self.config = config or get_config()
        self.storage_config = storage_config or StorageConfig()
        self.github_handler = GitHubHandler(self.config)
        self.frontmatter_parser = YAMLFrontmatterParser()
        
        # Optional SQLite cache for persistent deployment
        self._sqlite_cache = None
        if self.storage_config.cache_enabled and self.storage_config.deployment_context == "mcp":
            try:
                from database import DatabaseManager
                self._sqlite_cache = DatabaseManager()
            except ImportError:
                logger.warning("DatabaseManager not available for caching")
                self._sqlite_cache = None
    
    # Epic Management
    
    async def save_epic(self, epic: Epic, repository_name: Optional[str] = None) -> Issue:
        """Save an Epic as a GitHub issue with YAML frontmatter.
        
        Args:
            epic: Epic instance to save
            repository_name: Target repository (optional, uses default if not specified)
            
        Returns:
            Created GitHub Issue
        """
        # Create frontmatter metadata
        metadata = {
            "epic_id": epic.id,
            "story_type": "epic",
            "target_repositories": epic.target_repositories,
            "status": epic.status.value,
            "business_value": epic.business_value,
            "estimated_duration_weeks": epic.estimated_duration_weeks,
            "acceptance_criteria": epic.acceptance_criteria,
            "created_at": epic.created_at.isoformat(),
            "updated_at": epic.updated_at.isoformat(),
            "metadata": epic.metadata
        }
        
        # Create issue body with frontmatter
        content = f"# Epic: {epic.title}\n\n{epic.description}"
        body = self.frontmatter_parser.create_frontmatter_content(metadata, content)
        
        # Create issue data
        labels = [
            f"{self.storage_config.issue_label_prefix}",
            self.storage_config.epic_label
        ]
        
        issue_data = IssueData(
            title=f"Epic: {epic.title}",
            body=body,
            labels=labels,
            assignees=[],
            repository=repository_name
        )
        
        # Create the issue
        issue = await self.github_handler.create_issue(issue_data, repository_name)
        
        # Update SQLite cache if enabled
        if self._sqlite_cache:
            epic.metadata["github_issue_number"] = issue.number
            epic.metadata["github_repository"] = issue.repository.full_name
            self._sqlite_cache.save_epic(epic)
        
        logger.info(f"Saved Epic {epic.id} as GitHub issue #{issue.number}")
        return issue
    
    async def get_epic(self, epic_id: str, repository_name: Optional[str] = None) -> Optional[Epic]:
        """Retrieve an Epic from GitHub issue by ID.
        
        Args:
            epic_id: Epic ID to retrieve
            repository_name: Repository to search in (optional)
            
        Returns:
            Epic instance if found, None otherwise
        """
        try:
            # Search for issues with the epic_id in frontmatter
            search_query = f"label:{self.storage_config.epic_label} {epic_id} in:body"
            if repository_name:
                search_query += f" repo:{repository_name}"
            
            # Use GitHub search API
            issues = self.github_handler.github.search_issues(search_query)
            
            for issue in issues:
                epic = await self._parse_epic_from_issue(issue)
                if epic and epic.id == epic_id:
                    return epic
            
            return None
            
        except GithubException as e:
            logger.error(f"Failed to retrieve Epic {epic_id}: {e}")
            return None
    
    async def _parse_epic_from_issue(self, issue: Issue) -> Optional[Epic]:
        """Parse an Epic from a GitHub issue.
        
        Args:
            issue: GitHub Issue instance
            
        Returns:
            Epic instance if successfully parsed, None otherwise
        """
        try:
            # Extract frontmatter and content
            frontmatter, content = self.frontmatter_parser.extract_frontmatter(issue.body or "")
            
            if not frontmatter or frontmatter.get("story_type") != "epic":
                return None
            
            # Parse Epic data
            epic = Epic(
                id=frontmatter.get("epic_id", ""),
                title=self._extract_title_from_content(content) or issue.title.replace("Epic: ", ""),
                description=self._extract_description_from_content(content),
                status=StoryStatus(frontmatter.get("status", "draft")),
                business_value=frontmatter.get("business_value", ""),
                target_repositories=frontmatter.get("target_repositories", []),
                estimated_duration_weeks=frontmatter.get("estimated_duration_weeks"),
                acceptance_criteria=frontmatter.get("acceptance_criteria", []),
                created_at=datetime.fromisoformat(frontmatter.get("created_at", issue.created_at.isoformat())),
                updated_at=datetime.fromisoformat(frontmatter.get("updated_at", issue.updated_at.isoformat())),
                metadata=frontmatter.get("metadata", {})
            )
            
            # Add GitHub-specific metadata
            epic.metadata.update({
                "github_issue_number": issue.number,
                "github_repository": issue.repository.full_name,
                "github_url": issue.html_url
            })
            
            return epic
            
        except Exception as e:
            logger.error(f"Failed to parse Epic from issue #{issue.number}: {e}")
            return None
    
    # User Story Management
    
    async def save_user_story(self, user_story: UserStory, repository_name: Optional[str] = None) -> Issue:
        """Save a User Story as a GitHub issue with YAML frontmatter.
        
        Args:
            user_story: UserStory instance to save
            repository_name: Target repository (optional)
            
        Returns:
            Created GitHub Issue
        """
        # Create frontmatter metadata
        metadata = {
            "user_story_id": user_story.id,
            "story_type": "user_story",
            "epic_id": user_story.epic_id,
            "target_repositories": user_story.target_repositories,
            "status": user_story.status.value,
            "user_persona": user_story.user_persona,
            "user_goal": user_story.user_goal,
            "acceptance_criteria": user_story.acceptance_criteria,
            "story_points": user_story.story_points,
            "created_at": user_story.created_at.isoformat(),
            "updated_at": user_story.updated_at.isoformat(),
            "metadata": user_story.metadata
        }
        
        # Create issue body with frontmatter
        content = f"# User Story: {user_story.title}\n\n{user_story.description}"
        body = self.frontmatter_parser.create_frontmatter_content(metadata, content)
        
        # Create issue data
        labels = [
            f"{self.storage_config.issue_label_prefix}",
            self.storage_config.user_story_label
        ]
        
        issue_data = IssueData(
            title=f"User Story: {user_story.title}",
            body=body,
            labels=labels,
            assignees=[],
            repository=repository_name
        )
        
        # Create the issue
        issue = await self.github_handler.create_issue(issue_data, repository_name)
        
        # Update SQLite cache if enabled
        if self._sqlite_cache:
            user_story.metadata["github_issue_number"] = issue.number
            user_story.metadata["github_repository"] = issue.repository.full_name
            self._sqlite_cache.save_user_story(user_story)
        
        logger.info(f"Saved User Story {user_story.id} as GitHub issue #{issue.number}")
        return issue
    
    # Sub-Story Management
    
    async def save_sub_story(self, sub_story: SubStory, repository_name: Optional[str] = None) -> Issue:
        """Save a Sub-Story as a GitHub issue with YAML frontmatter.
        
        Args:
            sub_story: SubStory instance to save
            repository_name: Target repository (optional, defaults to sub_story.target_repository)
            
        Returns:
            Created GitHub Issue
        """
        target_repo = repository_name or sub_story.target_repository
        
        # Create frontmatter metadata
        metadata = {
            "sub_story_id": sub_story.id,
            "story_type": "sub_story",
            "user_story_id": sub_story.user_story_id,
            "department": sub_story.department,
            "target_repository": sub_story.target_repository,
            "status": sub_story.status.value,
            "technical_requirements": sub_story.technical_requirements,
            "dependencies": sub_story.dependencies,
            "assignee": sub_story.assignee,
            "estimated_hours": sub_story.estimated_hours,
            "created_at": sub_story.created_at.isoformat(),
            "updated_at": sub_story.updated_at.isoformat(),
            "metadata": sub_story.metadata
        }
        
        # Create issue body with frontmatter
        content = f"# Sub-Story ({sub_story.department}): {sub_story.title}\n\n{sub_story.description}"
        body = self.frontmatter_parser.create_frontmatter_content(metadata, content)
        
        # Create issue data
        labels = [
            f"{self.storage_config.issue_label_prefix}",
            self.storage_config.sub_story_label,
            f"department:{sub_story.department}"
        ]
        
        issue_data = IssueData(
            title=f"Sub-Story ({sub_story.department}): {sub_story.title}",
            body=body,
            labels=labels,
            assignees=[sub_story.assignee] if sub_story.assignee else [],
            repository=target_repo
        )
        
        # Create the issue
        issue = await self.github_handler.create_issue(issue_data, target_repo)
        
        # Update SQLite cache if enabled
        if self._sqlite_cache:
            sub_story.metadata["github_issue_number"] = issue.number
            sub_story.metadata["github_repository"] = issue.repository.full_name
            self._sqlite_cache.save_sub_story(sub_story)
        
        logger.info(f"Saved Sub-Story {sub_story.id} as GitHub issue #{issue.number}")
        return issue
    
    # Expert Analysis Management
    
    async def save_expert_analysis(self, issue_number: int, analysis: StoryAnalysis, repository_name: Optional[str] = None) -> None:
        """Save expert analysis as a structured comment on a GitHub issue.
        
        Args:
            issue_number: GitHub issue number
            analysis: StoryAnalysis instance
            repository_name: Repository name (optional)
        """
        # Format expert analysis as a structured comment
        comment_body = self._format_expert_analysis_comment(analysis)
        
        # Add the comment to the issue
        await self.github_handler.add_issue_comment(
            repository_name or self.config.github_repository,
            issue_number,
            comment_body
        )
        
        logger.info(f"Saved expert analysis from {analysis.role} to issue #{issue_number}")
    
    def _format_expert_analysis_comment(self, analysis: StoryAnalysis) -> str:
        """Format expert analysis as a structured comment.
        
        Args:
            analysis: StoryAnalysis instance
            
        Returns:
            Formatted comment body
        """
        comment_parts = [
            f"## Expert Analysis: {analysis.role_name}",
            "",
            "### Analysis",
            analysis.analysis,
            "",
            "### Recommendations",
            "\n".join(f"- {rec}" for rec in analysis.recommendations),
            "",
            "### Concerns",
            "\n".join(f"- {concern}" for concern in analysis.concerns),
            ""
        ]
        
        # Add metadata if available
        if analysis.metadata:
            comment_parts.extend([
                "### Additional Information",
                ""
            ])
            for key, value in analysis.metadata.items():
                comment_parts.append(f"**{key}**: {value}")
            comment_parts.append("")
        
        comment_parts.extend([
            "---",
            "*This analysis was generated by the Storyteller AI expert system*"
        ])
        
        return "\n".join(comment_parts)
    
    # Hierarchy Reconstruction
    
    async def reconstruct_story_hierarchy(self, epic_issue_number: int, repository_name: Optional[str] = None) -> Optional[StoryHierarchy]:
        """Reconstruct complete story hierarchy from GitHub issues.
        
        Args:
            epic_issue_number: GitHub issue number of the Epic
            repository_name: Repository name (optional)
            
        Returns:
            StoryHierarchy instance if successful, None otherwise
        """
        try:
            # Get the Epic issue
            repo_name = repository_name or self.config.github_repository
            epic_issue = await self.github_handler.get_issue(repo_name, epic_issue_number)
            
            # Parse Epic
            epic = await self._parse_epic_from_issue(epic_issue)
            if not epic:
                logger.error(f"Failed to parse Epic from issue #{epic_issue_number}")
                return None
            
            # Find related User Stories
            user_stories = await self._find_user_stories_for_epic(epic.id, repo_name)
            
            # Find Sub-Stories for each User Story
            sub_stories = {}
            for user_story in user_stories:
                user_story_subs = await self._find_sub_stories_for_user_story(user_story.id, repo_name)
                if user_story_subs:
                    sub_stories[user_story.id] = user_story_subs
            
            # Create hierarchy
            hierarchy = StoryHierarchy(
                epic=epic,
                user_stories=user_stories,
                sub_stories=sub_stories
            )
            
            logger.info(f"Reconstructed hierarchy for Epic {epic.id} with {len(user_stories)} user stories")
            return hierarchy
            
        except Exception as e:
            logger.error(f"Failed to reconstruct story hierarchy: {e}")
            return None
    
    async def _find_user_stories_for_epic(self, epic_id: str, repository_name: str) -> List[UserStory]:
        """Find all User Stories belonging to an Epic."""
        try:
            search_query = f"label:{self.storage_config.user_story_label} {epic_id} in:body repo:{repository_name}"
            issues = self.github_handler.github.search_issues(search_query)
            
            user_stories = []
            for issue in issues:
                user_story = await self._parse_user_story_from_issue(issue)
                if user_story and user_story.epic_id == epic_id:
                    user_stories.append(user_story)
            
            return user_stories
            
        except Exception as e:
            logger.error(f"Failed to find user stories for epic {epic_id}: {e}")
            return []
    
    async def _find_sub_stories_for_user_story(self, user_story_id: str, repository_name: str) -> List[SubStory]:
        """Find all Sub-Stories belonging to a User Story."""
        try:
            search_query = f"label:{self.storage_config.sub_story_label} {user_story_id} in:body repo:{repository_name}"
            issues = self.github_handler.github.search_issues(search_query)
            
            sub_stories = []
            for issue in issues:
                sub_story = await self._parse_sub_story_from_issue(issue)
                if sub_story and sub_story.user_story_id == user_story_id:
                    sub_stories.append(sub_story)
            
            return sub_stories
            
        except Exception as e:
            logger.error(f"Failed to find sub stories for user story {user_story_id}: {e}")
            return []
    
    async def _parse_user_story_from_issue(self, issue: Issue) -> Optional[UserStory]:
        """Parse a UserStory from a GitHub issue."""
        try:
            frontmatter, content = self.frontmatter_parser.extract_frontmatter(issue.body or "")
            
            if not frontmatter or frontmatter.get("story_type") != "user_story":
                return None
            
            user_story = UserStory(
                id=frontmatter.get("user_story_id", ""),
                epic_id=frontmatter.get("epic_id", ""),
                title=self._extract_title_from_content(content) or issue.title.replace("User Story: ", ""),
                description=self._extract_description_from_content(content),
                status=StoryStatus(frontmatter.get("status", "draft")),
                user_persona=frontmatter.get("user_persona", ""),
                user_goal=frontmatter.get("user_goal", ""),
                acceptance_criteria=frontmatter.get("acceptance_criteria", []),
                target_repositories=frontmatter.get("target_repositories", []),
                story_points=frontmatter.get("story_points"),
                created_at=datetime.fromisoformat(frontmatter.get("created_at", issue.created_at.isoformat())),
                updated_at=datetime.fromisoformat(frontmatter.get("updated_at", issue.updated_at.isoformat())),
                metadata=frontmatter.get("metadata", {})
            )
            
            # Add GitHub-specific metadata
            user_story.metadata.update({
                "github_issue_number": issue.number,
                "github_repository": issue.repository.full_name,
                "github_url": issue.html_url
            })
            
            return user_story
            
        except Exception as e:
            logger.error(f"Failed to parse UserStory from issue #{issue.number}: {e}")
            return None
    
    async def _parse_sub_story_from_issue(self, issue: Issue) -> Optional[SubStory]:
        """Parse a SubStory from a GitHub issue."""
        try:
            frontmatter, content = self.frontmatter_parser.extract_frontmatter(issue.body or "")
            
            if not frontmatter or frontmatter.get("story_type") != "sub_story":
                return None
            
            sub_story = SubStory(
                id=frontmatter.get("sub_story_id", ""),
                user_story_id=frontmatter.get("user_story_id", ""),
                title=self._extract_title_from_content(content) or issue.title,
                description=self._extract_description_from_content(content),
                status=StoryStatus(frontmatter.get("status", "draft")),
                department=frontmatter.get("department", ""),
                technical_requirements=frontmatter.get("technical_requirements", []),
                dependencies=frontmatter.get("dependencies", []),
                target_repository=frontmatter.get("target_repository", ""),
                assignee=frontmatter.get("assignee"),
                estimated_hours=frontmatter.get("estimated_hours"),
                created_at=datetime.fromisoformat(frontmatter.get("created_at", issue.created_at.isoformat())),
                updated_at=datetime.fromisoformat(frontmatter.get("updated_at", issue.updated_at.isoformat())),
                metadata=frontmatter.get("metadata", {})
            )
            
            # Add GitHub-specific metadata
            sub_story.metadata.update({
                "github_issue_number": issue.number,
                "github_repository": issue.repository.full_name,
                "github_url": issue.html_url
            })
            
            return sub_story
            
        except Exception as e:
            logger.error(f"Failed to parse SubStory from issue #{issue.number}: {e}")
            return None
    
    # Utility Methods
    
    def _extract_title_from_content(self, content: str) -> Optional[str]:
        """Extract title from content (first H1 header)."""
        if not content:
            return None
        
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        
        return None
    
    def _extract_description_from_content(self, content: str) -> str:
        """Extract description from content (everything after first H1 header)."""
        if not content:
            return ""
        
        lines = content.strip().split('\n')
        description_lines = []
        found_title = False
        
        for line in lines:
            if line.strip().startswith('# ') and not found_title:
                found_title = True
                continue
            elif found_title:
                description_lines.append(line)
        
        return '\n'.join(description_lines).strip()