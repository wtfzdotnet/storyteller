"""Workflow processor for CLI and automation interfaces."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from automation.label_manager import LabelManager
from config import Config, get_config
from story_manager import StoryManager

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """Result of a workflow operation."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowProcessor:
    """Processor for story workflow operations."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.story_manager = StoryManager(self.config)
        self.label_manager = LabelManager(self.config)

    async def create_story_workflow(
        self,
        content: str,
        repository: Optional[str] = None,
        roles: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Execute the complete story creation workflow."""

        try:
            # Determine target repositories
            target_repositories = None
            if repository:
                if repository in self.config.repositories:
                    target_repositories = [repository]
                else:
                    return WorkflowResult(
                        success=False,
                        message=f"Unknown repository: {repository}",
                        error="Repository not found in configuration",
                    )

            # Create the story
            result = await self.story_manager.create_story(
                content=content,
                target_repositories=target_repositories,
                required_roles=roles,
                context=context,
            )

            return WorkflowResult(
                success=True,
                message=f"Story created successfully: {result['story_id']}",
                data=result,
            )

        except Exception as e:
            logger.error(f"Story workflow failed: {e}")
            return WorkflowResult(
                success=False, message="Story creation failed", error=str(e)
            )

    async def create_multi_repository_story(
        self,
        content: str,
        repositories: List[str],
        roles: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Create a story across multiple repositories."""

        try:
            # Validate repositories
            valid_repos = []
            for repo in repositories:
                if repo in self.config.repositories:
                    valid_repos.append(repo)
                else:
                    logger.warning(f"Skipping unknown repository: {repo}")

            if not valid_repos:
                return WorkflowResult(
                    success=False,
                    message="No valid repositories specified",
                    error="All specified repositories are unknown",
                )

            # Create story across repositories
            result = await self.story_manager.create_story(
                content=content,
                target_repositories=valid_repos,
                required_roles=roles,
                context=context,
            )

            return WorkflowResult(
                success=True,
                message=f"Multi-repository story created: {result['story_id']}",
                data=result,
            )

        except Exception as e:
            logger.error(f"Multi-repository story workflow failed: {e}")
            return WorkflowResult(
                success=False,
                message="Multi-repository story creation failed",
                error=str(e),
            )

    async def analyze_story_workflow(
        self,
        content: str,
        roles: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Analyze a story without creating GitHub issues."""

        try:
            processed_story = await self.story_manager.analyze_story_only(
                content=content, required_roles=roles, context=context
            )

            # Format analysis for display
            analysis_data = {
                "story_id": processed_story.story_id,
                "expert_analyses": [
                    {
                        "role": analysis.role_name,
                        "recommendations": analysis.recommendations,
                        "concerns": analysis.concerns,
                    }
                    for analysis in processed_story.expert_analyses
                ],
                "synthesized_analysis": processed_story.synthesized_analysis,
                "target_repositories": processed_story.target_repositories,
                "metadata": processed_story.metadata,
            }

            return WorkflowResult(
                success=True,
                message=f"Story analysis completed: {processed_story.story_id}",
                data=analysis_data,
            )

        except Exception as e:
            logger.error(f"Story analysis workflow failed: {e}")
            return WorkflowResult(
                success=False, message="Story analysis failed", error=str(e)
            )

    def list_repositories_workflow(self) -> WorkflowResult:
        """List available repositories."""

        try:
            repositories = self.story_manager.get_available_repositories()

            repo_list = []
            for key, description in repositories.items():
                repo_config = self.config.repositories[key]
                repo_list.append(
                    {
                        "key": key,
                        "name": repo_config.name,
                        "type": repo_config.type,
                        "description": description,
                        "dependencies": repo_config.dependencies,
                    }
                )

            return WorkflowResult(
                success=True,
                message=f"Found {len(repositories)} repositories",
                data={"repositories": repo_list},
            )

        except Exception as e:
            logger.error(f"List repositories failed: {e}")
            return WorkflowResult(
                success=False, message="Failed to list repositories", error=str(e)
            )

    def list_roles_workflow(self) -> WorkflowResult:
        """List available expert roles."""

        try:
            roles = self.story_manager.get_available_roles()

            # Group roles by category
            role_categories = {
                "Technical Leadership": [],
                "Product & Strategy": [],
                "Domain Expertise": [],
                "Specialized Nutrition": [],
                "Technical Specialists": [],
                "Other": [],
            }

            # Categorize roles based on naming patterns
            for role in sorted(roles):
                if any(
                    keyword in role
                    for keyword in ["architect", "developer", "devops", "security"]
                ):
                    role_categories["Technical Leadership"].append(role)
                elif any(keyword in role for keyword in ["product", "ux", "ui"]):
                    role_categories["Product & Strategy"].append(role)
                elif any(keyword in role for keyword in ["chef", "food", "domain"]):
                    role_categories["Domain Expertise"].append(role)
                elif any(keyword in role for keyword in ["nutritionist", "dietitian"]):
                    role_categories["Specialized Nutrition"].append(role)
                elif any(keyword in role for keyword in ["qa", "ai", "expert"]):
                    role_categories["Technical Specialists"].append(role)
                else:
                    role_categories["Other"].append(role)

            return WorkflowResult(
                success=True,
                message=f"Found {len(roles)} expert roles",
                data={"roles": role_categories, "total_count": len(roles)},
            )

        except Exception as e:
            logger.error(f"List roles failed: {e}")
            return WorkflowResult(
                success=False, message="Failed to list roles", error=str(e)
            )

    def get_story_status_workflow(self, story_id: str) -> WorkflowResult:
        """Get status of a story."""

        try:
            status = self.story_manager.get_story_status(story_id)

            if status is None:
                return WorkflowResult(
                    success=False,
                    message=f"Story not found: {story_id}",
                    error="Story ID not found",
                )

            return WorkflowResult(
                success=True, message=f"Story status retrieved: {story_id}", data=status
            )

        except Exception as e:
            logger.error(f"Get story status failed: {e}")
            return WorkflowResult(
                success=False, message="Failed to get story status", error=str(e)
            )

    async def validate_configuration_workflow(self) -> WorkflowResult:
        """Validate the current configuration."""

        try:
            issues = []

            # Check GitHub token
            if not self.config.github_token:
                issues.append("GitHub token not configured")

            # Check repositories
            if not self.config.repositories:
                issues.append("No repositories configured")
            else:
                for key, repo_config in self.config.repositories.items():
                    if not repo_config.name:
                        issues.append(f"Repository {key} missing name")
                    if not repo_config.type:
                        issues.append(f"Repository {key} missing type")

            # Check role files
            role_files = list(Path(".storyteller/roles").glob("*.md"))
            if not role_files:
                issues.append("No expert role files found in .storyteller/roles/")

            # Check LLM configuration
            if (
                not self.config.openai_api_key
                and self.config.default_llm_provider == "openai"
            ):
                issues.append("OpenAI provider selected but no API key configured")

            if issues:
                return WorkflowResult(
                    success=False,
                    message=f"Configuration has {len(issues)} issues",
                    data={"issues": issues},
                )
            else:
                return WorkflowResult(
                    success=True,
                    message="Configuration is valid",
                    data={
                        "repositories": len(self.config.repositories),
                        "role_files": len(role_files),
                        "llm_provider": self.config.default_llm_provider,
                    },
                )

        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return WorkflowResult(
                success=False, message="Configuration validation failed", error=str(e)
            )

    async def batch_process_stories(
        self, stories: List[Dict[str, Any]]
    ) -> WorkflowResult:
        """Process multiple stories in batch."""

        try:
            results = []

            for i, story_data in enumerate(stories):
                try:
                    result = await self.create_story_workflow(
                        content=story_data.get("content", ""),
                        repository=story_data.get("repository"),
                        roles=story_data.get("roles"),
                        context=story_data.get("context"),
                    )
                    results.append(
                        {
                            "index": i,
                            "success": result.success,
                            "story_id": (
                                result.data.get("story_id") if result.data else None
                            ),
                            "message": result.message,
                            "error": result.error,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "index": i,
                            "success": False,
                            "story_id": None,
                            "message": "Processing failed",
                            "error": str(e),
                        }
                    )

            successful = sum(1 for r in results if r["success"])

            return WorkflowResult(
                success=True,
                message=f"Batch processing completed: {successful}/{len(stories)} successful",
                data={
                    "results": results,
                    "total": len(stories),
                    "successful": successful,
                },
            )

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return WorkflowResult(
                success=False, message="Batch processing failed", error=str(e)
            )
