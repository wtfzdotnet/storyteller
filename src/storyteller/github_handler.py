"""GitHub API handler for AI Story Management System."""

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from config import Config, RepositoryConfig
from github import Github, Repository
from github.GithubException import GithubException
from github.Issue import Issue
from models import ProjectData, ProjectField

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

    def list_issues(
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
                "*Auto-generated by Storyteller*",
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

    async def get_file_content(
        self, repository_name: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        """Get the content of a file from a repository."""

        try:
            repo = self.get_repository(repository_name)
            content_file = repo.get_contents(file_path, ref=ref)

            if isinstance(content_file, list):
                # Multiple files returned - shouldn't happen for specific file path
                logger.warning(
                    f"Multiple files returned for {file_path} in {repository_name}"
                )
                return None

            # Decode content if it's base64 encoded
            if content_file.encoding == "base64":
                content = base64.b64decode(content_file.content).decode("utf-8")
            else:
                content = content_file.content

            return content

        except GithubException as e:
            if e.status == 404:
                logger.debug(f"File not found: {file_path} in {repository_name}")
            else:
                logger.error(
                    f"Failed to get file {file_path} from {repository_name}: {e}"
                )
            return None
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return None

    async def list_repository_files(
        self,
        repository_name: str,
        path: str = "",
        ref: str = "main",
        recursive: bool = False,
        file_extensions: Optional[List[str]] = None,
    ) -> List[Tuple[str, str]]:
        """List files in a repository directory.

        Returns:
            List of tuples (file_path, file_type)
        """

        try:
            repo = self.get_repository(repository_name)
            files = []

            def _process_contents(contents, current_path=""):
                for content in contents:
                    full_path = f"{current_path}/{content.name}".lstrip("/")

                    if content.type == "file":
                        # Filter by extension if specified
                        if file_extensions:
                            if any(full_path.endswith(ext) for ext in file_extensions):
                                files.append((full_path, content.type))
                        else:
                            files.append((full_path, content.type))
                    elif content.type == "dir" and recursive:
                        # Recursively get directory contents
                        try:
                            sub_contents = repo.get_contents(full_path, ref=ref)
                            if isinstance(sub_contents, list):
                                _process_contents(sub_contents, full_path)
                        except GithubException:
                            # Skip directories we can't access
                            continue

            contents = repo.get_contents(path, ref=ref)
            if isinstance(contents, list):
                _process_contents(contents, path)
            else:
                # Single file
                if contents.type == "file":
                    full_path = f"{path}/{contents.name}".lstrip("/")
                    files.append((full_path, contents.type))

            return files

        except GithubException as e:
            logger.error(f"Failed to list files in {repository_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error listing repository files: {e}")
            return []

    async def get_repository_structure(
        self, repository_name: str, ref: str = "main"
    ) -> Dict[str, Any]:
        """Get a summary of the repository structure and key files."""

        try:
            repo = self.get_repository(repository_name)
            structure = {
                "name": repository_name,
                "default_branch": repo.default_branch,
                "language": repo.language,
                "languages": {},
                "key_files": [],
                "directories": [],
                "file_count": 0,
                "total_size": 0,
            }

            # Get language statistics
            try:
                languages = repo.get_languages()
                structure["languages"] = dict(languages)
            except Exception:
                pass

            # Get key files (README, package files, config files, etc.)
            key_file_patterns = [
                "README.md",
                "README.rst",
                "README.txt",
                "readme.md",
                "package.json",
                "requirements.txt",
                "Cargo.toml",
                "go.mod",
                "pom.xml",
                "build.gradle",
                "Makefile",
                "Dockerfile",
                ".gitignore",
                "LICENSE",
                "CHANGELOG.md",
            ]

            for pattern in key_file_patterns:
                try:
                    content = repo.get_contents(pattern, ref=ref)
                    if not isinstance(content, list):
                        structure["key_files"].append(
                            {
                                "name": content.name,
                                "path": content.path,
                                "size": content.size,
                            }
                        )
                except Exception:
                    continue

            # Get top-level directory structure
            try:
                contents = repo.get_contents("", ref=ref)
                if isinstance(contents, list):
                    for content in contents:
                        if content.type == "dir":
                            structure["directories"].append(content.name)
                        else:
                            structure["file_count"] += 1
                            structure["total_size"] += content.size or 0
            except Exception:
                pass

            return structure

        except GithubException as e:
            logger.error(
                f"Failed to get repository structure for {repository_name}: {e}"
            )
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error getting repository structure: {e}")
            return {"error": str(e)}

    # GitHub Projects API Methods

    def _execute_graphql_query(
        self, query: str, variables: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against GitHub's API."""

        headers = {
            "Authorization": f"Bearer {self.config.github_token}",
            "Content-Type": "application/json",
        }

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = requests.post(
            "https://api.github.com/graphql", headers=headers, json=payload, timeout=30
        )

        if response.status_code != 200:
            raise Exception(
                f"GraphQL request failed: {response.status_code} - {response.text}"
            )

        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")

        return result.get("data", {})

    async def create_project(
        self, project_data: ProjectData, repository_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new GitHub Project (v2)."""

        try:
            # Get repository node ID if creating a repository-level project
            repo_node_id = None
            if repository_name:
                repo = self.get_repository(repository_name)
                repo_node_id = repo.node_id

            # Determine if this is an organization or repository project
            if project_data.organization_login:
                # Organization-level project
                mutation = """
                mutation($login: String!, $title: String!, $description: String!) {
                    createProjectV2(input: {
                        ownerId: $login
                        title: $title
                        description: $description
                    }) {
                        projectV2 {
                            id
                            title
                            url
                            number
                        }
                    }
                }
                """
                variables = {
                    "login": project_data.organization_login,
                    "title": project_data.title,
                    "description": project_data.description,
                }
                # Note: We'll need to get the organization ID first
                org_query = """
                query($login: String!) {
                    organization(login: $login) {
                        id
                    }
                }
                """
                org_result = self._execute_graphql_query(
                    org_query, {"login": project_data.organization_login}
                )
                org_id = org_result["organization"]["id"]
                variables["login"] = org_id

            elif repo_node_id:
                # Repository-level project
                mutation = """
                mutation($ownerId: ID!, $title: String!, $description: String!) {
                    createProjectV2(input: {
                        ownerId: $ownerId
                        title: $title
                        description: $description
                    }) {
                        projectV2 {
                            id
                            title
                            url
                            number
                        }
                    }
                }
                """
                variables = {
                    "ownerId": repo_node_id,
                    "title": project_data.title,
                    "description": project_data.description,
                }
            else:
                raise ValueError(
                    "Either repository_name or organization_login must be provided"
                )

            result = self._execute_graphql_query(mutation, variables)
            project = result["createProjectV2"]["projectV2"]

            logger.info(
                f"Created GitHub Project: {project['title']} (ID: {project['id']})"
            )
            return project

        except Exception as e:
            logger.error(f"Failed to create GitHub Project: {e}")
            raise Exception(f"GitHub Projects API error: {e}")

    async def add_issue_to_project(
        self, project_id: str, issue_number: int, repository_name: str
    ) -> Dict[str, Any]:
        """Add an issue to a GitHub Project."""

        try:
            # Get issue node ID
            repo = self.get_repository(repository_name)
            issue = repo.get_issue(issue_number)
            issue_node_id = issue.node_id

            mutation = """
            mutation($projectId: ID!, $contentId: ID!) {
                addProjectV2ItemById(input: {
                    projectId: $projectId
                    contentId: $contentId
                }) {
                    item {
                        id
                        content {
                            ... on Issue {
                                title
                                number
                            }
                        }
                    }
                }
            }
            """

            variables = {"projectId": project_id, "contentId": issue_node_id}

            result = self._execute_graphql_query(mutation, variables)
            item = result["addProjectV2ItemById"]["item"]

            logger.info(f"Added issue #{issue_number} to project {project_id}")
            return item

        except Exception as e:
            logger.error(f"Failed to add issue to project: {e}")
            raise Exception(f"GitHub Projects API error: {e}")

    async def update_project_item_field(
        self, project_id: str, item_id: str, field_id: str, value: Any
    ) -> Dict[str, Any]:
        """Update a custom field value for a project item."""

        try:
            mutation = """
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!,
                     $value: ProjectV2FieldValue!) {
                updateProjectV2ItemFieldValue(input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: $value
                }) {
                    projectV2Item {
                        id
                    }
                }
            }
            """

            variables = {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "value": value,
            }

            result = self._execute_graphql_query(mutation, variables)

            logger.info(f"Updated project item {item_id} field {field_id}")
            return result["updateProjectV2ItemFieldValue"]["projectV2Item"]

        except Exception as e:
            logger.error(f"Failed to update project item field: {e}")
            raise Exception(f"GitHub Projects API error: {e}")

    async def get_project_fields(self, project_id: str) -> List[ProjectField]:
        """Get all custom fields for a GitHub Project."""

        try:
            query = """
            query($projectId: ID!) {
                node(id: $projectId) {
                    ... on ProjectV2 {
                        fields(first: 20) {
                            nodes {
                                ... on ProjectV2Field {
                                    id
                                    name
                                    dataType
                                }
                                ... on ProjectV2SingleSelectField {
                                    id
                                    name
                                    dataType
                                    options {
                                        id
                                        name
                                    }
                                }
                                ... on ProjectV2IterationField {
                                    id
                                    name
                                    dataType
                                    configuration {
                                        iterations {
                                            id
                                            title
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """

            variables = {"projectId": project_id}
            result = self._execute_graphql_query(query, variables)

            fields = []
            field_nodes = result["node"]["fields"]["nodes"]

            for field_node in field_nodes:
                options = []
                if "options" in field_node:
                    options = [
                        {"id": opt["id"], "name": opt["name"]}
                        for opt in field_node["options"]
                    ]
                elif (
                    "configuration" in field_node
                    and "iterations" in field_node["configuration"]
                ):
                    options = [
                        {"id": it["id"], "name": it["title"]}
                        for it in field_node["configuration"]["iterations"]
                    ]

                field = ProjectField(
                    id=field_node["id"],
                    name=field_node["name"],
                    data_type=field_node["dataType"],
                    options=options,
                )
                fields.append(field)

            logger.info(f"Retrieved {len(fields)} fields for project {project_id}")
            return fields

        except Exception as e:
            logger.error(f"Failed to get project fields: {e}")
            raise Exception(f"GitHub Projects API error: {e}")

    async def bulk_add_issues_to_project(
        self,
        project_id: str,
        issue_data: List[Tuple[int, str]],  # List of (issue_number, repository_name)
    ) -> List[Dict[str, Any]]:
        """Add multiple issues to a project in bulk."""

        results = []
        for issue_number, repository_name in issue_data:
            try:
                result = await self.add_issue_to_project(
                    project_id, issue_number, repository_name
                )
                results.append(
                    {"success": True, "data": result, "issue_number": issue_number}
                )
            except Exception as e:
                logger.error(f"Failed to add issue #{issue_number} to project: {e}")
                results.append(
                    {"success": False, "error": str(e), "issue_number": issue_number}
                )

        success_count = sum(1 for r in results if r["success"])
        logger.info(
            f"Bulk operation completed: {success_count}/{len(issue_data)} "
            f"issues added successfully"
        )

        return results

    async def sync_story_to_project(
        self,
        story_hierarchy: Any,  # StoryHierarchy object
        project_id: str,
        field_mappings: Dict[str, str] = None,  # Map story fields to project field IDs
    ) -> Dict[str, Any]:
        """Synchronize a story hierarchy with a GitHub Project."""

        field_mappings = field_mappings or {}
        sync_results = {"epic": None, "user_stories": [], "sub_stories": []}

        try:
            # Create issues for the story hierarchy if they don't exist
            # This assumes issues have been created and we're syncing to project

            # Get project fields for field mapping
            project_fields = await self.get_project_fields(project_id)
            field_lookup = {field.name: field.id for field in project_fields}

            # Sync epic (if it has an associated issue)
            if (
                hasattr(story_hierarchy.epic, "github_issue_number")
                and story_hierarchy.epic.github_issue_number
            ):
                epic_item = await self.add_issue_to_project(
                    project_id,
                    story_hierarchy.epic.github_issue_number,
                    (
                        story_hierarchy.epic.target_repositories[0]
                        if story_hierarchy.epic.target_repositories
                        else "default"
                    ),
                )

                # Update custom fields based on story metadata
                if "Status" in field_lookup and story_hierarchy.epic.status:
                    await self.update_project_item_field(
                        project_id,
                        epic_item["id"],
                        field_lookup["Status"],
                        {"text": story_hierarchy.epic.status.value},
                    )

                sync_results["epic"] = epic_item

            # Sync user stories
            for user_story in story_hierarchy.user_stories:
                if (
                    hasattr(user_story, "github_issue_number")
                    and user_story.github_issue_number
                ):
                    story_item = await self.add_issue_to_project(
                        project_id,
                        user_story.github_issue_number,
                        (
                            user_story.target_repositories[0]
                            if user_story.target_repositories
                            else "default"
                        ),
                    )
                    sync_results["user_stories"].append(story_item)

            # Sync sub-stories
            for sub_story_list in story_hierarchy.sub_stories.values():
                for sub_story in sub_story_list:
                    if (
                        hasattr(sub_story, "github_issue_number")
                        and sub_story.github_issue_number
                    ):
                        sub_item = await self.add_issue_to_project(
                            project_id,
                            sub_story.github_issue_number,
                            sub_story.target_repository or "default",
                        )
                        sync_results["sub_stories"].append(sub_item)

            logger.info(f"Synchronized story hierarchy to project {project_id}")
            return sync_results

        except Exception as e:
            logger.error(f"Failed to sync story hierarchy to project: {e}")
            raise Exception(f"Story synchronization error: {e}")

    async def create_project_for_epic(
        self,
        epic: Any,  # Epic object
        repository_name: Optional[str] = None,
        organization_login: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a GitHub Project specifically for an Epic."""

        project_data = ProjectData(
            title=f"Epic: {epic.title}",
            description=(
                f"{epic.description}\n\nEpic ID: {epic.id}\n"
                f"Business Value: {epic.business_value}"
            ),
            repository_id=None,
            organization_login=organization_login,
        )

        project = await self.create_project(project_data, repository_name)

        logger.info(f"Created project for epic {epic.id}: {project['title']}")
        return project

    async def get_cross_repository_progress_data(
        self, epic_id: str, repositories: List[str]
    ) -> Dict[str, Any]:
        """Fetch real-time progress data across multiple repositories for an epic."""
        progress_data = {
            "epic_id": epic_id,
            "repositories": {},
            "issues_by_repository": {},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        for repository_name in repositories:
            try:
                repo_data = await self._fetch_repository_progress(
                    repository_name, epic_id
                )
                progress_data["repositories"][repository_name] = repo_data
                progress_data["issues_by_repository"][repository_name] = repo_data.get(
                    "issues", []
                )
            except Exception as e:
                logger.error(
                    f"Failed to fetch progress for repository {repository_name}: {e}"
                )
                progress_data["repositories"][repository_name] = {
                    "error": str(e),
                    "status": "error",
                }

        return progress_data

    async def _fetch_repository_progress(
        self, repository_name: str, epic_id: str
    ) -> Dict[str, Any]:
        """Fetch progress data for a specific repository related to an epic."""
        try:
            repo = self.get_repository(repository_name)

            # Search for issues related to the epic
            # Using a search query to find issues with epic reference
            query = f"repo:{repository_name} {epic_id} in:title,body"
            issues = list(repo.get_issues(state="all"))

            # Filter issues that reference the epic
            epic_related_issues = []
            for issue in issues:
                if epic_id in issue.title or epic_id in (issue.body or ""):
                    epic_related_issues.append(issue)

            # Calculate progress metrics
            total_issues = len(epic_related_issues)
            closed_issues = sum(
                1 for issue in epic_related_issues if issue.state == "closed"
            )
            open_issues = total_issues - closed_issues

            progress_percentage = (
                (closed_issues / total_issues * 100) if total_issues > 0 else 0
            )

            # Get issue details for visualization
            issue_details = []
            for issue in epic_related_issues[:20]:  # Limit to most recent 20
                issue_details.append(
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "state": issue.state,
                        "created_at": issue.created_at.isoformat(),
                        "updated_at": issue.updated_at.isoformat(),
                        "assignee": issue.assignee.login if issue.assignee else None,
                        "labels": [label.name for label in issue.labels],
                    }
                )

            return {
                "repository": repository_name,
                "total_issues": total_issues,
                "closed_issues": closed_issues,
                "open_issues": open_issues,
                "progress_percentage": round(progress_percentage, 1),
                "status": (
                    "completed"
                    if closed_issues == total_issues and total_issues > 0
                    else "in_progress" if closed_issues > 0 else "not_started"
                ),
                "issues": issue_details,
                "last_fetched": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Error fetching repository progress for {repository_name}: {e}"
            )
            raise

    async def update_cross_repository_project_progress(
        self, project_id: str, epic_id: str, repositories: List[str]
    ) -> Dict[str, Any]:
        """Update GitHub project with real-time progress from multiple repositories."""
        try:
            # Fetch current progress data
            progress_data = await self.get_cross_repository_progress_data(
                epic_id, repositories
            )

            # Get project fields for updating
            project_fields = await self.get_project_fields(project_id)
            field_lookup = {field.name: field.id for field in project_fields}

            # Update project with aggregated progress
            updates_made = []

            # If there's a "Cross-Repo Progress" field, update it
            if "Cross-Repo Progress" in field_lookup:
                total_issues = sum(
                    repo_data.get("total_issues", 0)
                    for repo_data in progress_data["repositories"].values()
                    if "error" not in repo_data
                )
                closed_issues = sum(
                    repo_data.get("closed_issues", 0)
                    for repo_data in progress_data["repositories"].values()
                    if "error" not in repo_data
                )
                overall_percentage = (
                    (closed_issues / total_issues * 100) if total_issues > 0 else 0
                )

                # Note: Actual field update would require the item ID, which would come from the sync process
                updates_made.append(f"Overall progress: {overall_percentage:.1f}%")

            logger.info(f"Updated cross-repository progress for project {project_id}")
            return {
                "project_id": project_id,
                "epic_id": epic_id,
                "updates_made": updates_made,
                "progress_data": progress_data,
            }

        except Exception as e:
            logger.error(f"Failed to update cross-repository project progress: {e}")
            raise

    async def enable_real_time_progress_tracking(
        self, epic_id: str, repositories: List[str], webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable real-time progress tracking for an epic across repositories."""
        tracking_config = {
            "epic_id": epic_id,
            "repositories": repositories,
            "webhook_url": webhook_url,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tracking_events": [
                "issues.opened",
                "issues.closed",
                "issues.reopened",
                "pull_request.opened",
                "pull_request.closed",
                "pull_request.merged",
            ],
        }

        # In a real implementation, this would:
        # 1. Set up webhooks on each repository (if webhook_url provided)
        # 2. Store tracking configuration in database
        # 3. Initialize progress monitoring

        logger.info(
            f"Enabled real-time progress tracking for epic {epic_id} across {len(repositories)} repositories"
        )
        return tracking_config

    async def notify_assignment(
        self,
        repository_name: str,
        issue_number: int,
        assignee: str,
        assignment_reason: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a notification comment when assigning a story to copilot-sve-agent."""

        try:
            # Create notification message
            notification_parts = [
                "🤖 **Automated Assignment**",
                "",
                f"This issue has been automatically assigned to @{assignee}.",
                f"**Reason**: {assignment_reason}",
            ]

            # Add additional context if provided
            if additional_context:
                notification_parts.append("")
                notification_parts.append("**Assignment Details:**")
                for key, value in additional_context.items():
                    notification_parts.append(f"- **{key}**: {value}")

            notification_parts.extend(
                [
                    "",
                    "---",
                    "*This assignment was made by the Storyteller automation system.*",
                    "*To override this assignment, update the assignee manually.*",
                ]
            )

            notification_message = "\n".join(notification_parts)

            # Add the notification comment
            await self.add_issue_comment(
                repository_name=repository_name,
                issue_number=issue_number,
                comment=notification_message,
            )

            logger.info(
                f"Added assignment notification for issue #{issue_number} "
                f"in {repository_name} (assigned to {assignee})"
            )

        except Exception as e:
            logger.error(
                f"Failed to add assignment notification for issue #{issue_number}: {e}"
            )
            # Don't re-raise - assignment notification failure shouldn't break the workflow
