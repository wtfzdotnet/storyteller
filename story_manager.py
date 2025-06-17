"""Core Story Management for AI Story Management System."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from config import Config, get_config, load_role_files
from github_handler import GitHubHandler, IssueData
from llm_handler import LLMHandler, LLMResponse
from database import DatabaseManager
from models import Epic, UserStory, SubStory, StoryHierarchy, StoryStatus, StoryType

logger = logging.getLogger(__name__)


@dataclass
class StoryAnalysis:
    """Analysis of a story by an expert role."""

    role_name: str
    analysis: str
    recommendations: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProcessedStory:
    """A fully processed story with expert analyses."""

    story_id: str
    original_content: str
    expert_analyses: List[StoryAnalysis]
    synthesized_analysis: str
    target_repositories: List[str]
    status: str = "processed"
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StoryRequest:
    """Request to create and process a story."""

    content: str
    target_repositories: Optional[List[str]] = None
    required_roles: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None


class StoryProcessor:
    """Core story processing engine with multi-expert analysis."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.llm_handler = LLMHandler(self.config)
        self.github_handler = GitHubHandler(self.config)
        self.database = DatabaseManager()  # Add database support
        self.role_definitions = load_role_files()
        self._processing_queue: Dict[str, ProcessedStory] = {}

    def _generate_story_id(self) -> str:
        """Generate a unique story ID."""
        import uuid

        return f"story_{uuid.uuid4().hex[:8]}"

    async def analyze_story_content(self, story_content: str) -> Dict[str, Any]:
        """Analyze story content to determine relevant roles and repositories."""

        system_prompt = """You are analyzing a user story to determine:
1. Which expert roles should analyze this story
2. Which repositories (backend, frontend, storyteller) are most relevant
3. Key themes and complexity indicators

Available expert roles include: system-architect, lead-developer, security-expert, 
domain-expert-food-nutrition, professional-chef, ux-ui-designer, product-owner, 
qa-engineer, devops-engineer, ai-expert, and various nutrition specialists.

Repository types:
- backend: API services, data processing, business logic
- frontend: User interfaces, client applications
- storyteller: Story management and workflow tools

Respond with a JSON object containing:
{
  "recommended_roles": ["role1", "role2", ...],
  "target_repositories": ["repo1", "repo2", ...],
  "complexity": "low|medium|high",
  "themes": ["theme1", "theme2", ...],
  "reasoning": "explanation of choices"
}"""

        try:
            response = await self.llm_handler.generate_response(
                prompt=f"Analyze this user story:\n\n{story_content}",
                system_prompt=system_prompt,
            )

            # Parse JSON response
            analysis = json.loads(response.content)

            # Validate and clean up the analysis
            analysis["recommended_roles"] = [
                role
                for role in analysis.get("recommended_roles", [])
                if role in self.role_definitions
            ]

            analysis["target_repositories"] = [
                repo
                for repo in analysis.get("target_repositories", [])
                if repo in self.config.repositories
            ]

            return analysis

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse story analysis, using defaults: {e}")
            return {
                "recommended_roles": ["system-architect", "lead-developer"],
                "target_repositories": [self.config.default_repository],
                "complexity": "medium",
                "themes": ["general"],
                "reasoning": "Default analysis due to parsing error",
            }

    async def get_expert_analysis(
        self,
        story_content: str,
        role_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> StoryAnalysis:
        """Get analysis from a specific expert role."""

        if role_name not in self.role_definitions:
            raise ValueError(f"Unknown expert role: {role_name}")

        role_definition = self.role_definitions[role_name]

        try:
            response = await self.llm_handler.analyze_story_with_role(
                story_content=story_content,
                role_definition=role_definition,
                role_name=role_name,
                context=context,
            )

            # Parse the response to extract structured data
            analysis_text = response.content

            # Simple parsing to extract recommendations and concerns
            recommendations = []
            concerns = []

            lines = analysis_text.split("\n")
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                lower_line = line.lower()
                if any(
                    keyword in lower_line
                    for keyword in ["recommend", "suggest", "should"]
                ):
                    if line.startswith("- ") or line.startswith("* "):
                        recommendations.append(line[2:])
                    else:
                        recommendations.append(line)
                elif any(
                    keyword in lower_line
                    for keyword in ["concern", "risk", "issue", "problem"]
                ):
                    if line.startswith("- ") or line.startswith("* "):
                        concerns.append(line[2:])
                    else:
                        concerns.append(line)

            return StoryAnalysis(
                role_name=role_name,
                analysis=analysis_text,
                recommendations=recommendations,
                concerns=concerns,
                metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage,
                },
            )

        except Exception as e:
            logger.error(f"Failed to get analysis from {role_name}: {e}")
            raise

    async def process_story_with_experts(
        self,
        story_content: str,
        expert_roles: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[StoryAnalysis]:
        """Process a story with multiple expert roles in parallel."""

        # Create analysis tasks for all expert roles
        analysis_tasks = [
            self.get_expert_analysis(story_content, role_name, context)
            for role_name in expert_roles
            if role_name in self.role_definitions
        ]

        if not analysis_tasks:
            raise ValueError("No valid expert roles provided")

        # Execute all analyses in parallel
        try:
            analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            # Filter out failed analyses and log errors
            successful_analyses = []
            for i, result in enumerate(analyses):
                if isinstance(result, Exception):
                    logger.error(
                        f"Expert analysis failed for {expert_roles[i]}: {result}"
                    )
                else:
                    successful_analyses.append(result)

            if not successful_analyses:
                raise Exception("All expert analyses failed")

            logger.info(f"Completed {len(successful_analyses)} expert analyses")
            return successful_analyses

        except Exception as e:
            logger.error(f"Failed to process story with experts: {e}")
            raise

    async def synthesize_analyses(
        self, story_content: str, expert_analyses: List[StoryAnalysis]
    ) -> str:
        """Synthesize multiple expert analyses into a comprehensive analysis."""

        # Prepare expert analyses for synthesis
        analysis_data = [
            {
                "role_name": analysis.role_name,
                "analysis": analysis.analysis,
                "recommendations": analysis.recommendations,
                "concerns": analysis.concerns,
            }
            for analysis in expert_analyses
        ]

        try:
            response = await self.llm_handler.synthesize_expert_analyses(
                story_content=story_content, expert_analyses=analysis_data
            )

            return response.content

        except Exception as e:
            logger.error(f"Failed to synthesize expert analyses: {e}")

            # Fallback: Create a simple concatenation
            synthesis_parts = [
                "# Comprehensive Story Analysis",
                "",
                f"Based on analysis from {len(expert_analyses)} expert roles:",
                f"- {', '.join([a.role_name for a in expert_analyses])}",
                "",
            ]

            for analysis in expert_analyses:
                synthesis_parts.extend(
                    [f"## {analysis.role_name} Analysis", analysis.analysis, ""]
                )

            return "\n".join(synthesis_parts)

    async def determine_target_repositories(
        self,
        story_content: str,
        expert_analyses: List[StoryAnalysis],
        requested_repos: Optional[List[str]] = None,
    ) -> List[str]:
        """Determine target repositories for story distribution."""

        if requested_repos:
            # Validate requested repositories
            valid_repos = [
                repo for repo in requested_repos if repo in self.config.repositories
            ]
            if valid_repos:
                return valid_repos

        # Analyze story content to determine repositories
        content_analysis = await self.analyze_story_content(story_content)
        suggested_repos = content_analysis.get("target_repositories", [])

        if suggested_repos:
            return suggested_repos

        # Default to configured default repository
        return [self.config.default_repository]

    async def process_story(self, story_request: StoryRequest) -> ProcessedStory:
        """Process a complete story through the expert analysis workflow."""

        story_id = self._generate_story_id()
        logger.info(f"Processing story {story_id}")

        try:
            # Analyze story content to determine roles and repositories
            content_analysis = await self.analyze_story_content(story_request.content)

            # Determine expert roles
            expert_roles = (
                story_request.required_roles or content_analysis["recommended_roles"]
            )
            if not expert_roles:
                expert_roles = ["system-architect", "lead-developer"]  # Default minimum

            logger.info(f"Using expert roles: {expert_roles}")

            # Get expert analyses
            expert_analyses = await self.process_story_with_experts(
                story_content=story_request.content,
                expert_roles=expert_roles,
                context=story_request.context,
            )

            # Synthesize analyses
            synthesized_analysis = await self.synthesize_analyses(
                story_content=story_request.content, expert_analyses=expert_analyses
            )

            # Determine target repositories
            target_repositories = await self.determine_target_repositories(
                story_content=story_request.content,
                expert_analyses=expert_analyses,
                requested_repos=story_request.target_repositories,
            )

            # Create processed story
            processed_story = ProcessedStory(
                story_id=story_id,
                original_content=story_request.content,
                expert_analyses=expert_analyses,
                synthesized_analysis=synthesized_analysis,
                target_repositories=target_repositories,
                metadata={
                    "content_analysis": content_analysis,
                    "processing_time": datetime.utcnow().isoformat(),
                    "expert_count": len(expert_analyses),
                },
            )

            # Store in processing queue
            self._processing_queue[story_id] = processed_story

            logger.info(f"Completed processing story {story_id}")
            return processed_story

        except Exception as e:
            logger.error(f"Failed to process story {story_id}: {e}")
            raise

    async def create_github_issues(self, processed_story: ProcessedStory) -> List[Any]:
        """Create GitHub issues for a processed story."""

        try:
            if len(processed_story.target_repositories) == 1:
                # Single repository - create one issue
                issue = await self.github_handler.create_story_issue(
                    story_content=processed_story.original_content,
                    expert_analysis=processed_story.synthesized_analysis,
                    repository_key=processed_story.target_repositories[0],
                    additional_context=processed_story.metadata,
                )
                return [issue]
            else:
                # Multiple repositories - create cross-repository issues
                issues = await self.github_handler.create_cross_repository_stories(
                    story_content=processed_story.original_content,
                    expert_analysis=processed_story.synthesized_analysis,
                    target_repositories=processed_story.target_repositories,
                    additional_context=processed_story.metadata,
                )
                return issues

        except Exception as e:
            logger.error(
                f"Failed to create GitHub issues for story {processed_story.story_id}: {e}"
            )
            raise

    async def process_and_create_story(
        self, story_request: StoryRequest
    ) -> Dict[str, Any]:
        """Process a story and create GitHub issues in one operation."""

        try:
            # Process the story
            processed_story = await self.process_story(story_request)

            # Create GitHub issues
            created_issues = await self.create_github_issues(processed_story)

            # Update story status
            processed_story.status = "completed"
            processed_story.metadata["github_issues"] = [
                {
                    "repository": issue.repository.full_name,
                    "number": issue.number,
                    "url": issue.html_url,
                }
                for issue in created_issues
            ]

            return {
                "story_id": processed_story.story_id,
                "status": "completed",
                "expert_analyses_count": len(processed_story.expert_analyses),
                "target_repositories": processed_story.target_repositories,
                "github_issues": processed_story.metadata["github_issues"],
                "processing_metadata": processed_story.metadata,
            }

        except Exception as e:
            logger.error(f"Failed to process and create story: {e}")
            raise

    def get_story_status(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a story by ID."""

        if story_id not in self._processing_queue:
            return None

        story = self._processing_queue[story_id]
        return {
            "story_id": story.story_id,
            "status": story.status,
            "created_at": story.created_at.isoformat(),
            "expert_analyses_count": len(story.expert_analyses),
            "target_repositories": story.target_repositories,
            "metadata": story.metadata,
        }

    def list_available_roles(self) -> List[str]:
        """List all available expert roles."""
        return list(self.role_definitions.keys())

    def list_available_repositories(self) -> List[str]:
        """List all configured repositories."""
        return list(self.config.repositories.keys())


class StoryManager:
    """High-level story management interface."""

    def __init__(self, config: Optional[Config] = None):
        self.processor = StoryProcessor(config)
        self.database = self.processor.database

    async def create_story(
        self,
        content: str,
        target_repositories: Optional[List[str]] = None,
        required_roles: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new story with expert analysis and GitHub issues."""

        story_request = StoryRequest(
            content=content,
            target_repositories=target_repositories,
            required_roles=required_roles,
            context=context,
        )

        return await self.processor.process_and_create_story(story_request)

    async def analyze_story_only(
        self,
        content: str,
        required_roles: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ProcessedStory:
        """Analyze a story without creating GitHub issues."""

        story_request = StoryRequest(
            content=content, required_roles=required_roles, context=context
        )

        return await self.processor.process_story(story_request)

    # New hierarchical story management methods
    
    def create_epic(
        self,
        title: str,
        description: str,
        business_value: str = "",
        acceptance_criteria: List[str] = None,
        target_repositories: List[str] = None,
        estimated_duration_weeks: Optional[int] = None
    ) -> Epic:
        """Create a new epic."""
        epic = Epic(
            title=title,
            description=description,
            business_value=business_value,
            acceptance_criteria=acceptance_criteria or [],
            target_repositories=target_repositories or [],
            estimated_duration_weeks=estimated_duration_weeks
        )
        
        self.database.save_story(epic)
        logger.info(f"Created epic: {epic.title} (ID: {epic.id})")
        return epic
    
    def create_user_story(
        self,
        epic_id: str,
        title: str,
        description: str,
        user_persona: str = "",
        user_goal: str = "",
        acceptance_criteria: List[str] = None,
        target_repositories: List[str] = None,
        story_points: Optional[int] = None
    ) -> UserStory:
        """Create a new user story under an epic."""
        user_story = UserStory(
            epic_id=epic_id,
            title=title,
            description=description,
            user_persona=user_persona,
            user_goal=user_goal,
            acceptance_criteria=acceptance_criteria or [],
            target_repositories=target_repositories or [],
            story_points=story_points
        )
        
        self.database.save_story(user_story)
        logger.info(f"Created user story: {user_story.title} (ID: {user_story.id}) under epic {epic_id}")
        return user_story
    
    def create_sub_story(
        self,
        user_story_id: str,
        title: str,
        description: str,
        department: str = "",
        technical_requirements: List[str] = None,
        dependencies: List[str] = None,
        target_repository: str = "",
        assignee: Optional[str] = None,
        estimated_hours: Optional[float] = None
    ) -> SubStory:
        """Create a new sub-story under a user story."""
        sub_story = SubStory(
            user_story_id=user_story_id,
            title=title,
            description=description,
            department=department,
            technical_requirements=technical_requirements or [],
            dependencies=dependencies or [],
            target_repository=target_repository,
            assignee=assignee,
            estimated_hours=estimated_hours
        )
        
        self.database.save_story(sub_story)
        logger.info(f"Created sub-story: {sub_story.title} (ID: {sub_story.id}) under user story {user_story_id}")
        return sub_story
    
    def get_epic_hierarchy(self, epic_id: str) -> Optional[StoryHierarchy]:
        """Get complete epic hierarchy including all user stories and sub-stories."""
        return self.database.get_epic_hierarchy(epic_id)
    
    def get_story(self, story_id: str):
        """Get a story by ID."""
        return self.database.get_story(story_id)
    
    def update_story_status(self, story_id: str, status: StoryStatus) -> bool:
        """Update the status of a story."""
        return self.database.update_story_status(story_id, status)
    
    def get_all_epics(self) -> List[Epic]:
        """Get all epics in the system."""
        return self.database.get_all_epics()
    
    def delete_story(self, story_id: str) -> bool:
        """Delete a story and all its children."""
        return self.database.delete_story(story_id)
    
    def add_story_relationship(self, source_id: str, target_id: str, relationship_type: str, metadata: Dict[str, Any] = None):
        """Add a relationship between two stories."""
        self.database.add_story_relationship(source_id, target_id, relationship_type, metadata)
    
    def link_github_issue(self, story_id: str, repository_name: str, issue_number: int, issue_url: str):
        """Link a story to a GitHub issue."""
        self.database.link_github_issue(story_id, repository_name, issue_number, issue_url)

    def get_available_roles(self) -> List[str]:
        """Get list of available expert roles."""
        return self.processor.list_available_roles()

    def get_available_repositories(self) -> Dict[str, str]:
        """Get list of available repositories with descriptions."""
        repos = {}
        for key, config in self.processor.config.repositories.items():
            repos[key] = config.description
        return repos

    def get_story_status(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a story by ID."""
        # First check the hierarchical database
        story = self.database.get_story(story_id)
        if story:
            return {
                "story_id": story.id,
                "story_type": type(story).__name__.lower(),
                "status": story.status.value,
                "title": story.title,
                "created_at": story.created_at.isoformat(),
                "updated_at": story.updated_at.isoformat(),
            }
        
        # Fall back to legacy processing queue
        return self.processor.get_story_status(story_id)
