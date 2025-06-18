"""Workflow processor for CLI and automation interfaces."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from assignment_engine import AssignmentEngine
from automation.label_manager import LabelManager
from config import Config, get_config
from pipeline_dashboard import PipelineDashboard
from pipeline_monitor import PipelineMonitor
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
        self.assignment_engine = AssignmentEngine(self.config)
        self.pipeline_monitor = PipelineMonitor(self.config)
        self.pipeline_dashboard = PipelineDashboard(self.config)

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

    async def process_story_assignment(
        self,
        story_id: str,
        story_content: str,
        story_metadata: Optional[Dict[str, Any]] = None,
        manual_override: bool = False,
    ) -> WorkflowResult:
        """Process automatic assignment for a story."""

        try:
            # Get assignment decision from the engine
            assignment_decision = self.assignment_engine.process_assignment(
                story_id=story_id,
                story_content=story_content,
                story_metadata=story_metadata,
                manual_override=manual_override,
            )

            if not assignment_decision.should_assign:
                return WorkflowResult(
                    success=True,
                    message=f"Story {story_id} not assigned: {assignment_decision.explanation}",
                    data={
                        "assigned": False,
                        "reason": assignment_decision.reason.value,
                        "explanation": assignment_decision.explanation,
                        "metadata": assignment_decision.metadata,
                    },
                )

            # If assignment is approved, update the story if it has GitHub issues
            assignment_data = {
                "assigned": True,
                "assignee": assignment_decision.assignee,
                "reason": assignment_decision.reason.value,
                "explanation": assignment_decision.explanation,
                "metadata": assignment_decision.metadata,
            }

            # Check if story has associated GitHub issues to update
            if story_metadata and "github_issues" in story_metadata:
                github_issues = story_metadata["github_issues"]
                github_handler = self.story_manager.github_handler

                for issue_info in github_issues:
                    repository_name = issue_info.get("repository")
                    issue_number = issue_info.get("issue_number")

                    if repository_name and issue_number:
                        try:
                            # Update issue assignee
                            await github_handler.update_issue(
                                repository_name=repository_name,
                                issue_number=issue_number,
                                assignees=[assignment_decision.assignee],
                            )

                            # Add assignment notification
                            await github_handler.notify_assignment(
                                repository_name=repository_name,
                                issue_number=issue_number,
                                assignee=assignment_decision.assignee,
                                assignment_reason=assignment_decision.explanation,
                                additional_context=assignment_decision.metadata,
                            )

                            logger.info(
                                f"Updated assignment for issue #{issue_number} "
                                f"in {repository_name}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Failed to update GitHub issue #{issue_number}: {e}"
                            )
                            # Continue with other issues

            return WorkflowResult(
                success=True,
                message=f"Story {story_id} assigned to {assignment_decision.assignee}",
                data=assignment_data,
            )

        except Exception as e:
            logger.error(f"Assignment processing failed for story {story_id}: {e}")
            return WorkflowResult(
                success=False,
                message=f"Assignment processing failed for story {story_id}",
                error=str(e),
            )

    def get_assignment_queue_workflow(self) -> WorkflowResult:
        """Get the current assignment queue in chronological order."""

        try:
            queue = self.assignment_engine.get_assignment_queue()
            statistics = self.assignment_engine.get_assignment_statistics()

            return WorkflowResult(
                success=True,
                message=f"Retrieved assignment queue ({len(queue)} items)",
                data={"queue": queue, "statistics": statistics},
            )

        except Exception as e:
            logger.error(f"Failed to get assignment queue: {e}")
            return WorkflowResult(
                success=False, message="Failed to get assignment queue", error=str(e)
            )

    def get_assignment_statistics_workflow(self) -> WorkflowResult:
        """Get assignment statistics for monitoring."""

        try:
            statistics = self.assignment_engine.get_assignment_statistics()

            return WorkflowResult(
                success=True,
                message="Assignment statistics retrieved",
                data=statistics,
            )

        except Exception as e:
            logger.error(f"Failed to get assignment statistics: {e}")
            return WorkflowResult(
                success=False,
                message="Failed to get assignment statistics",
                error=str(e),
            )

    # Pipeline monitoring methods

    def get_pipeline_dashboard_workflow(
        self, repository: Optional[str] = None, time_range: str = "24h"
    ) -> WorkflowResult:
        """Get pipeline monitoring dashboard data."""
        try:
            dashboard_data = self.pipeline_dashboard.get_dashboard_data(
                repository=repository, time_range=time_range
            )

            if "error" in dashboard_data:
                return WorkflowResult(
                    success=False,
                    message="Failed to get dashboard data",
                    error=dashboard_data["error"],
                )

            return WorkflowResult(
                success=True,
                message=f"Pipeline dashboard data retrieved for {time_range}",
                data=dashboard_data,
            )

        except Exception as e:
            logger.error(f"Failed to get pipeline dashboard: {e}")
            return WorkflowResult(
                success=False,
                message="Failed to get pipeline dashboard",
                error=str(e),
            )

    def get_pipeline_health_workflow(self, repository: Optional[str] = None) -> WorkflowResult:
        """Get pipeline health status."""
        try:
            live_status = self.pipeline_dashboard.get_live_status()
            dashboard_data = self.pipeline_dashboard.get_dashboard_data(
                repository=repository, time_range="24h"
            )

            health_summary = {
                "live_status": live_status,
                "health_metrics": dashboard_data.get("health_metrics", {}),
                "alert_summary": dashboard_data.get("alert_summary", {}),
                "recommendations": dashboard_data.get("recommendations", [])[:3],  # Top 3
            }

            return WorkflowResult(
                success=True,
                message="Pipeline health status retrieved",
                data=health_summary,
            )

        except Exception as e:
            logger.error(f"Failed to get pipeline health: {e}")
            return WorkflowResult(
                success=False,
                message="Failed to get pipeline health",
                error=str(e),
            )

    def analyze_pipeline_patterns_workflow(self, days: int = 30) -> WorkflowResult:
        """Analyze pipeline failure patterns."""
        try:
            patterns = self.pipeline_monitor.analyze_failure_patterns(days=days)

            pattern_data = [
                {
                    "pattern_id": p.pattern_id,
                    "category": p.category.value,
                    "description": p.description,
                    "failure_count": p.failure_count,
                    "repositories": p.repositories,
                    "resolution_suggestions": p.resolution_suggestions,
                }
                for p in patterns
            ]

            return WorkflowResult(
                success=True,
                message=f"Analyzed {len(patterns)} failure patterns over {days} days",
                data={
                    "patterns": pattern_data,
                    "analysis_period_days": days,
                    "total_patterns": len(patterns),
                },
            )

        except Exception as e:
            logger.error(f"Failed to analyze pipeline patterns: {e}")
            return WorkflowResult(
                success=False,
                message="Failed to analyze pipeline patterns",
                error=str(e),
            )

    def export_pipeline_data_workflow(
        self,
        repository: Optional[str] = None,
        time_range: str = "7d",
        format: str = "json",
    ) -> WorkflowResult:
        """Export pipeline monitoring data."""
        try:
            export_data = self.pipeline_dashboard.export_dashboard_data(
                repository=repository, time_range=time_range, format=format
            )

            if "error" in export_data:
                return WorkflowResult(
                    success=False,
                    message="Failed to export pipeline data",
                    error=export_data["error"],
                )

            return WorkflowResult(
                success=True,
                message=f"Pipeline data exported for {time_range}",
                data=export_data,
            )

        except Exception as e:
            logger.error(f"Failed to export pipeline data: {e}")
            return WorkflowResult(
                success=False,
                message="Failed to export pipeline data",
                error=str(e),
            )
