"""GitHub API handler for AI Story Management System."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from github import Github, Repository
from github.GithubException import GithubException
from github.Issue import Issue

from config import Config, RepositoryConfig

logger = logging.getLogger(__name__)


@dataclass
class IssueData:
    """Data structure for GitHub issue creation."""

    title: str
    body: str
    labels: List[str]
    assignees: List[str]
    milestone: Optional[str] = None
    repository: Optional[str] = None


class GitHubHandler:
    """Handler for GitHub API operations."""

    def __init__(self, config: Config):
        self.config = config
        self.github = Github(config.github_token)
        self._repositories: Dict[str, Repository] = {}

    def get_repository(self, repo_name: str) -> Repository:
        """Get a GitHub repository object with caching."""

        if repo_name not in self._repositories:
            try:
                self._repositories[repo_name] = self.github.get_repo(repo_name)
            except GithubException as e:
                raise Exception(f"Failed to access repository {repo_name}: {e}")

        return self._repositories[repo_name]

    async def create_issue(
        self, issue_data: IssueData, repository_name: Optional[str] = None
    ) -> Issue:
        """Create a GitHub issue."""

        # Determine target repository
        target_repo = repository_name or issue_data.repository
        if not target_repo:
            # Use default repository from config or single repo mode
            if self.config.repositories:
                target_repo = self.config.repositories[
                    self.config.default_repository
                ].name
            elif self.config.github_repository:
                target_repo = self.config.github_repository
            else:
                raise ValueError("No target repository specified")

        try:
            repo = self.get_repository(target_repo)

            # Create the issue
            issue = repo.create_issue(
                title=issue_data.title,
                body=issue_data.body,
                labels=issue_data.labels,
                assignees=issue_data.assignees,
                milestone=None,  # Milestone handling can be added later
            )

            logger.info(
                f"Created issue #{issue.number} in {target_repo}: {issue_data.title}"
            )
            return issue

        except GithubException as e:
            logger.error(f"Failed to create issue in {target_repo}: {e}")
            raise Exception(f"GitHub API error: {e}")

    async def update_issue(
        self,
        repository_name: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        state: Optional[str] = None,
    ) -> Issue:
        """Update an existing GitHub issue."""

        try:
            repo = self.get_repository(repository_name)
            issue = repo.get_issue(issue_number)

            # Update fields if provided
            if title is not None:
                issue.edit(title=title)
            if body is not None:
                issue.edit(body=body)
            if labels is not None:
                issue.edit(labels=labels)
            if assignees is not None:
                issue.edit(assignees=assignees)
            if state is not None:
                if state.lower() == "closed":
                    issue.edit(state="closed")
                elif state.lower() == "open":
                    issue.edit(state="open")

            logger.info(f"Updated issue #{issue_number} in {repository_name}")
            return issue

        except GithubException as e:
            logger.error(
                f"Failed to update issue #{issue_number} in {repository_name}: {e}"
            )
            raise Exception(f"GitHub API error: {e}")

    async def add_issue_comment(
        self, repository_name: str, issue_number: int, comment: str
    ) -> None:
        """Add a comment to a GitHub issue."""

        try:
            repo = self.get_repository(repository_name)
            issue = repo.get_issue(issue_number)
            issue.create_comment(comment)

            logger.info(f"Added comment to issue #{issue_number} in {repository_name}")

        except GithubException as e:
            logger.error(f"Failed to add comment to issue #{issue_number}: {e}")
            raise Exception(f"GitHub API error: {e}")

    async def get_issue(self, repository_name: str, issue_number: int) -> Issue:
        """Get a GitHub issue by number."""

        try:
            repo = self.get_repository(repository_name)
            return repo.get_issue(issue_number)

        except GithubException as e:
            logger.error(
                f"Failed to get issue #{issue_number} from {repository_name}: {e}"
            )
            raise Exception(f"GitHub API error: {e}")

    async def list_issues(
        self,
        repository_name: str,
        state: str = "open",
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        limit: int = 30,
    ) -> List[Issue]:
        """List GitHub issues with filtering."""

        try:
            repo = self.get_repository(repository_name)

            # Build filter parameters
            kwargs = {"state": state}
            if labels:
                kwargs["labels"] = labels
            if assignee:
                kwargs["assignee"] = assignee

            issues = list(repo.get_issues(**kwargs)[:limit])

            logger.info(f"Retrieved {len(issues)} issues from {repository_name}")
            return issues

        except GithubException as e:
            logger.error(f"Failed to list issues from {repository_name}: {e}")
            raise Exception(f"GitHub API error: {e}")

    def format_story_as_issue(
        self,
        story_content: str,
        expert_analysis: str,
        repository_config: RepositoryConfig,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> IssueData:
        """Format a story and expert analysis as a GitHub issue."""

        # Extract title from story content (first line or generate from content)
        lines = story_content.strip().split("\n")
        title = lines[0].strip()
        if title.startswith("#"):
            title = title.lstrip("#").strip()
        elif len(title) > 80:
            # If first line is too long, generate a shorter title
            title = f"Story: {title[:60]}..."

        # Build issue body
        body_parts = [
            "# User Story",
            "",
            story_content,
            "",
            "# Expert Analysis",
            "",
            expert_analysis,
        ]

        # Add additional context if provided
        if additional_context:
            body_parts.extend(["", "# Additional Context", ""])
            for key, value in additional_context.items():
                body_parts.append(f"**{key}**: {value}")

        # Add repository-specific information
        body_parts.extend(
            [
                "",
                "---",
                f"*Repository Type*: {repository_config.type}",
                f"*Auto-generated by Storyteller*",
            ]
        )

        body = "\n".join(body_parts)

        # Determine labels
        labels = repository_config.story_labels.copy()
        labels.append("user_story")

        # Determine assignees
        assignees = []
        if "assignee" in repository_config.auto_assign:
            assignees.extend(repository_config.auto_assign["assignee"])

        return IssueData(
            title=title,
            body=body,
            labels=labels,
            assignees=assignees,
            repository=repository_config.name,
        )

    async def create_story_issue(
        self,
        story_content: str,
        expert_analysis: str,
        repository_key: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Issue:
        """Create a GitHub issue for a processed story."""

        # Get repository configuration
        repo_config = self.config.repositories.get(repository_key)
        if not repo_config:
            raise ValueError(f"Repository configuration not found: {repository_key}")

        # Format the story as an issue
        issue_data = self.format_story_as_issue(
            story_content=story_content,
            expert_analysis=expert_analysis,
            repository_config=repo_config,
            additional_context=additional_context,
        )

        # Create the issue
        return await self.create_issue(issue_data, repo_config.name)

    async def create_cross_repository_stories(
        self,
        story_content: str,
        expert_analysis: str,
        target_repositories: List[str],
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> List[Issue]:
        """Create related stories across multiple repositories."""

        created_issues = []

        # Sort repositories by dependency order
        sorted_repos = self._sort_repositories_by_dependencies(target_repositories)

        for repo_key in sorted_repos:
            repo_config = self.config.repositories.get(repo_key)
            if not repo_config:
                logger.warning(f"Skipping unknown repository: {repo_key}")
                continue

            # Add cross-repository context
            cross_repo_context = additional_context.copy() if additional_context else {}
            cross_repo_context["Related Repositories"] = ", ".join(target_repositories)

            # Add dependency information
            if repo_config.dependencies:
                cross_repo_context["Dependencies"] = ", ".join(repo_config.dependencies)

            try:
                issue = await self.create_story_issue(
                    story_content=story_content,
                    expert_analysis=expert_analysis,
                    repository_key=repo_key,
                    additional_context=cross_repo_context,
                )
                created_issues.append(issue)

                # Add cross-references to previously created issues
                if len(created_issues) > 1:
                    await self._add_cross_references(created_issues)

            except Exception as e:
                logger.error(f"Failed to create story in repository {repo_key}: {e}")
                # Continue with other repositories
                continue

        return created_issues

    def _sort_repositories_by_dependencies(
        self, repository_keys: List[str]
    ) -> List[str]:
        """Sort repositories by dependency order (dependencies first)."""

        sorted_repos = []
        remaining_repos = set(repository_keys)

        while remaining_repos:
            # Find repositories with no unresolved dependencies
            ready_repos = []
            for repo_key in remaining_repos:
                repo_config = self.config.repositories.get(repo_key)
                if not repo_config:
                    ready_repos.append(repo_key)
                    continue

                # Check if all dependencies are already processed
                unresolved_deps = set(repo_config.dependencies) & remaining_repos
                if not unresolved_deps:
                    ready_repos.append(repo_key)

            if not ready_repos:
                # Circular dependency or missing dependency - just take remaining
                ready_repos = list(remaining_repos)

            # Add ready repositories to sorted list
            for repo_key in ready_repos:
                sorted_repos.append(repo_key)
                remaining_repos.remove(repo_key)

        return sorted_repos

    async def _add_cross_references(self, issues: List[Issue]) -> None:
        """Add cross-references between related issues."""

        if len(issues) < 2:
            return

        for i, issue in enumerate(issues):
            other_issues = [other for j, other in enumerate(issues) if j != i]

            reference_text = "**Related Issues:**\n"
            for other in other_issues:
                reference_text += f"- {other.repository.full_name}#{other.number}\n"

            try:
                await self.add_issue_comment(
                    repository_name=issue.repository.full_name,
                    issue_number=issue.number,
                    comment=reference_text,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to add cross-reference to issue #{issue.number}: {e}"
                )
