import logging
import asyncio
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass

import github
from github import GithubException, UnknownObjectException, Issue, IssueComment

from .config import get_config, Config

logger = logging.getLogger(__name__)


@dataclass
class GitHubOperationResult:
    """Result of a GitHub operation."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    
    @classmethod
    def success_result(cls, data: Any) -> 'GitHubOperationResult':
        return cls(success=True, data=data)
    
    @classmethod
    def error_result(cls, error: str, status_code: Optional[int] = None) -> 'GitHubOperationResult':
        return cls(success=False, error=error, status_code=status_code)


class GitHubError(Exception):
    """Custom exception for GitHub operations."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GitHubRateLimitError(GitHubError):
    """Exception for rate limit exceeded."""
    pass


class GitHubConnectionError(GitHubError):
    """Exception for connection issues."""
    pass

class GitHubService:
    """Enhanced GitHub service with better error handling and async support."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the GitHubService.
        
        Args:
            config: Configuration object. If None, uses global config.
            
        Raises:
            GitHubError: If initialization fails.
        """
        self.config = config or get_config()
        self.token = self.config.github_token
        self.repository_name = self.config.github_repository
        self.max_retries = self.config.max_retries
        self.timeout = self.config.timeout_seconds
        
        self._github_client: Optional[github.Github] = None
        self._repo: Optional[github.Repository.Repository] = None
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize GitHub client and repository."""
        try:
            self._github_client = github.Github(
                self.token,
                timeout=self.timeout,
                retry=self.max_retries
            )
            
            # Test connection and get repository
            self._repo = self._github_client.get_repo(self.repository_name)
            
            # Verify access by making a simple API call
            _ = self._repo.name
            
            logger.info(f"Successfully connected to repository: {self.repository_name}")
            
        except UnknownObjectException:
            error_msg = f"Repository '{self.repository_name}' not found or access denied"
            logger.error(error_msg)
            raise GitHubError(error_msg, 404)
            
        except GithubException as e:
            error_msg = f"Failed to initialize GitHub client: {e.data.get('message', str(e))}"
            logger.error(error_msg)
            
            if e.status == 401:
                raise GitHubError("Invalid GitHub token", 401)
            elif e.status == 403:
                raise GitHubRateLimitError("Rate limit exceeded", 403)
            else:
                raise GitHubConnectionError(error_msg, e.status)
        
        except Exception as e:
            error_msg = f"Unexpected error during GitHub client initialization: {e}"
            logger.error(error_msg)
            raise GitHubConnectionError(error_msg)
    
    @property
    def github_client(self) -> github.Github:
        """Get the GitHub client instance."""
        if self._github_client is None:
            raise GitHubError("GitHub client not initialized")
        return self._github_client
    
    @property
    def repo(self) -> github.Repository.Repository:
        """Get the repository instance."""
        if self._repo is None:
            raise GitHubError("Repository not initialized")
        return self._repo
    
    def _handle_github_exception(self, e: GithubException, operation: str) -> GitHubOperationResult:
        """Handle GitHub exceptions and return appropriate result."""
        error_message = e.data.get('message', str(e)) if hasattr(e, 'data') and e.data else str(e)
        
        if e.status == 401:
            error_msg = f"Authentication failed for {operation}: Invalid token"
        elif e.status == 403:
            error_msg = f"Access forbidden for {operation}: {error_message}"
        elif e.status == 404:
            error_msg = f"Resource not found for {operation}: {error_message}"
        elif e.status == 422:
            error_msg = f"Validation failed for {operation}: {error_message}"
        else:
            error_msg = f"GitHub API error for {operation}: {error_message}"
        
        logger.error(error_msg)
        return GitHubOperationResult.error_result(error_msg, e.status)
    
    async def _retry_operation(self, operation, *args, **kwargs) -> GitHubOperationResult:
        """Retry an operation with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                result = operation(*args, **kwargs)
                return GitHubOperationResult.success_result(result)
                
            except GithubException as e:
                if e.status == 403 and 'rate limit' in str(e).lower():
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}")
                        await asyncio.sleep(wait_time)
                        continue
                
                return self._handle_github_exception(e, operation.__name__)
                
            except Exception as e:
                error_msg = f"Unexpected error in {operation.__name__}: {e}"
                logger.error(error_msg)
                return GitHubOperationResult.error_result(error_msg)
        
        return GitHubOperationResult.error_result(f"Failed after {self.max_retries} attempts")

    async def create_issue(
        self, 
        title: str, 
        body: str = "", 
        labels: Optional[List[str]] = None, 
        assignees: Optional[List[str]] = None
    ) -> GitHubOperationResult:
        """
        Create a new issue in the repository.
        
        Args:
            title: The title of the issue.
            body: The body/content of the issue.
            labels: A list of label names to apply to the issue.
            assignees: A list of GitHub usernames to assign to the issue.
            
        Returns:
            GitHubOperationResult with the created Issue or error details.
        """
        if not title or not title.strip():
            return GitHubOperationResult.error_result("Issue title cannot be empty")
        
        def _create_issue():
            issue_params = {
                "title": title.strip(),
                "body": body or "",
            }
            
            if labels:
                issue_params["labels"] = labels
            if assignees:
                issue_params["assignees"] = assignees
            
            issue = self.repo.create_issue(**issue_params)
            logger.info(f"Successfully created issue #{issue.number}: '{title}' in {self.repository_name}")
            return issue
        
        return await self._retry_operation(_create_issue)

    async def get_issue(self, issue_number: int) -> GitHubOperationResult:
        """
        Retrieve an issue by its number.
        
        Args:
            issue_number: The number of the issue.
            
        Returns:
            GitHubOperationResult with the Issue or error details.
        """
        if issue_number <= 0:
            return GitHubOperationResult.error_result("Issue number must be positive")
        
        def _get_issue():
            issue = self.repo.get_issue(number=issue_number)
            logger.debug(f"Successfully retrieved issue #{issue_number} from {self.repository_name}")
            return issue
        
        return await self._retry_operation(_get_issue)

    def update_issue(self, issue_number: int, title: Optional[str] = None, body: Optional[str] = None, 
                     state: Optional[str] = None, labels: Optional[List[str]] = None, 
                     assignees: Optional[List[str]] = None) -> Optional[Issue]:
        """
        Updates an existing issue. Only provided parameters are updated.

        Args:
            issue_number: The number of the issue to update.
            title: New title for the issue.
            body: New body for the issue.
            state: New state for the issue (e.g., "open", "closed").
            labels: New list of labels. To remove all labels, pass an empty list. To leave labels unchanged, pass None.
            assignees: New list of assignees. To remove all assignees, pass an empty list.

        Returns:
            The updated github.Issue.Issue object, or None if update failed or issue not found.
        """
        issue = self.get_issue(issue_number)
        if not issue:
            logger.error(f"Cannot update issue #{issue_number} as it was not found in {self.repository_name}.")
            return None

        edit_params = {}
        if title is not None:
            edit_params['title'] = title
        if body is not None:
            edit_params['body'] = body
        if state is not None:
            edit_params['state'] = state
        if labels is not None: # PyGithub handles label replacement or clearing with empty list
            edit_params['labels'] = labels
        if assignees is not None: # PyGithub handles assignee replacement or clearing
            edit_params['assignees'] = assignees
        
        if not edit_params:
            logger.info(f"No parameters provided for updating issue #{issue_number}. No changes made.")
            return issue # Return the original issue if no changes

        try:
            issue.edit(**edit_params)
            logger.info(f"Successfully updated issue #{issue_number} in {self.repository_name}.")
            # Re-fetch the issue if edit() doesn't return the updated object directly with all fields
            # or if there are caching concerns. For PyGithub, issue object is updated in place.
            return issue
        except GithubException as e:
            logger.error(f"Failed to update issue #{issue_number} in {self.repository_name}: {e.data.get('message', str(e))}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while updating issue #{issue_number}: {e}")
            return None

    async def add_comment_to_issue(self, issue_number: int, comment_body: str) -> GitHubOperationResult:
        """
        Add a comment to an existing issue.
        
        Args:
            issue_number: The number of the issue.
            comment_body: The content of the comment.
            
        Returns:
            GitHubOperationResult with the created IssueComment or error details.
        """
        if not comment_body or not comment_body.strip():
            return GitHubOperationResult.error_result("Comment body cannot be empty")
        
        # First get the issue
        issue_result = await self.get_issue(issue_number)
        if not issue_result.success:
            return GitHubOperationResult.error_result(
                f"Cannot add comment to issue #{issue_number}: {issue_result.error}"
            )
        
        def _add_comment():
            comment = issue_result.data.create_comment(comment_body.strip())
            logger.info(f"Successfully added comment to issue #{issue_number} in {self.repository_name}")
            return comment
        
        return await self._retry_operation(_add_comment)

    def get_issue_comments(self, issue_number: int) -> List[IssueComment]:
        """
        Retrieves all comments for a given issue.

        Args:
            issue_number: The number of the issue.

        Returns:
            A list of github.IssueComment.IssueComment objects, or an empty list if issue not found or error.
        """
        issue = self.get_issue(issue_number)
        if not issue:
            logger.error(f"Cannot get comments for issue #{issue_number} as it was not found.")
            return []
        
        try:
            comments = list(issue.get_comments()) # Convert PaginatedList to list
            logger.info(f"Retrieved {len(comments)} comments for issue #{issue_number} from {self.repository_name}")
            return comments
        except GithubException as e:
            logger.error(f"Failed to retrieve comments for issue #{issue_number}: {e.data.get('message', str(e))}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while retrieving comments for issue #{issue_number}: {e}")
            return []

    def search_issues(self, query: str, qualifier: str = "") -> List[Issue]:
        """
        Searches for issues in the configured repository.
        The query should be what you'd type into the GitHub search bar, without "repo:owner/repo".
        Example: "is:open label:bug milestone:v1.0"

        Args:
            query: The search query string (e.g., "is:open label:bug").
            qualifier: Additional search qualifiers (e.g. sort options), if any.

        Returns:
            A list of github.Issue.Issue objects matching the search, or an empty list on error.
        """
        if not query:
            logger.warning("Search query is empty. Returning no issues.")
            return []

        full_query = f"repo:{self.repository_name} {query.strip()}"
        if qualifier:
            full_query += f" {qualifier.strip()}"
            
        logger.info(f"Searching issues with query: '{full_query}'")
        try:
            # github_client.search_issues returns a PaginatedList of NamedUser
            # We need to iterate over it to get the issues
            # search_issues returns Issue objects directly if the query is repo-scoped
            issues_paginated_list = self.github_client.search_issues(query=full_query)
            issues = list(issues_paginated_list) # Convert PaginatedList to list
            logger.info(f"Found {len(issues)} issues matching query '{query}' in {self.repository_name}")
            return issues
        except GithubException as e:
            logger.error(f"Failed to search issues in {self.repository_name} with query '{query}': {e.data.get('message', str(e))}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while searching issues with query '{query}': {e}")
            return []

    def get_repository_labels(self) -> List[github.Label.Label]:
        """
        Retrieves all labels for the configured repository.

        Returns:
            A list of github.Label.Label objects, or an empty list on error.
        """
        try:
            labels_paginated_list = self.repo.get_labels()
            labels = list(labels_paginated_list) # Convert PaginatedList to list
            logger.info(f"Retrieved {len(labels)} labels for repository {self.repository_name}")
            return labels
        except GithubException as e:
            logger.error(f"Failed to retrieve labels for repository {self.repository_name}: {e.data.get('message', str(e))}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while retrieving labels for {self.repository_name}: {e}")
            return []

    def create_label(self, name: str, color: str, description: str = "") -> Optional[github.Label.Label]:
        """
        Creates a new label in the repository.

        Args:
            name: The name of the label.
            color: The hex color code for the label (e.g., "FFA500", without '#').
            description: An optional description for the label.

        Returns:
            The created github.Label.Label object, or None if creation failed.
        """
        try:
            # Ensure color does not start with '#' as PyGithub expects hex without it
            if color.startswith("#"):
                color = color[1:]
            
            label = self.repo.create_label(name=name, color=color, description=description)
            logger.info(f"Successfully created label '{name}' with color '#{color}' in {self.repository_name}")
            return label
        except GithubException as e:
            # Check if error is because label already exists
            if e.status == 422 and any("already_exists" in error.get("code", "") for error in e.data.get("errors", [])):
                logger.warning(f"Label '{name}' already exists in {self.repository_name}. Cannot create.")
                # Try to fetch the existing label instead of returning None
                try:
                    return self.repo.get_label(name)
                except GithubException:
                    return None # If fetching existing also fails
            logger.error(f"Failed to create label '{name}' in {self.repository_name}: {e.data.get('message', str(e))}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while creating label '{name}': {e}")
            return None

    def update_label(self, current_name: str, new_name: Optional[str] = None, color: Optional[str] = None, description: Optional[str] = None) -> Optional[github.Label.Label]:
        """
        Updates an existing label in the repository.

        Args:
            current_name: The current name of the label to update.
            new_name: The new name for the label. If None, name is not changed.
            color: The new hex color code (e.g., "FFA500", without '#'). If None, color is not changed.
            description: The new description. If None, description is not changed. To clear description, pass "".

        Returns:
            The updated github.Label.Label object, or None if update failed or label not found.
        """
        try:
            label = self.repo.get_label(current_name)
            
            # PyGithub's label.edit() requires the name parameter, even if not changing it
            final_name = new_name if new_name is not None else current_name
            final_color = color[1:] if color and color.startswith("#") else color if color is not None else label.color
            final_description = description if description is not None else label.description
            
            # Only update if there are actual changes
            if (final_name != current_name or 
                final_color != label.color or 
                final_description != label.description):
                
                label.edit(name=final_name, color=final_color, description=final_description)
            else:
                logger.info(f"No changes needed for label '{current_name}'. Current values match requested values.")
                return label
            logger.info(f"Successfully updated label '{current_name}' (new name: '{label.name}') in {self.repository_name}")
            return label
        except UnknownObjectException:
            logger.error(f"Label '{current_name}' not found in {self.repository_name}. Cannot update.")
            return None
        except GithubException as e:
            logger.error(f"Failed to update label '{current_name}' in {self.repository_name}: {e.data.get('message', str(e))}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while updating label '{current_name}': {e}")
            return None

    async def add_label_to_issue(self, issue_number: int, label_name: str) -> GitHubOperationResult:
        """
        Add a single label to an existing issue.
        
        Args:
            issue_number: The number of the issue.
            label_name: The name of the label to add.
            
        Returns:
            GitHubOperationResult indicating success or failure.
        """
        if not label_name or not label_name.strip():
            return GitHubOperationResult.error_result("Label name cannot be empty")
        
        # First get the issue
        issue_result = await self.get_issue(issue_number)
        if not issue_result.success:
            return GitHubOperationResult.error_result(
                f"Cannot add label to issue #{issue_number}: {issue_result.error}"
            )
        
        def _add_label():
            issue = issue_result.data
            current_label_names = [l.name for l in issue.labels]
            
            if label_name.strip() in current_label_names:
                logger.debug(f"Label '{label_name}' already present on issue #{issue_number}")
                return True  # Already applied
            
            issue.add_to_labels(label_name.strip())
            logger.info(f"Successfully added label '{label_name}' to issue #{issue_number}")
            return True
        
        return await self._retry_operation(_add_label)

    async def remove_label_from_issue(self, issue_number: int, label_name: str) -> GitHubOperationResult:
        """
        Remove a single label from an existing issue.
        
        Args:
            issue_number: The number of the issue.
            label_name: The name of the label to remove.
            
        Returns:
            GitHubOperationResult indicating success or failure.
        """
        if not label_name or not label_name.strip():
            return GitHubOperationResult.error_result("Label name cannot be empty")
        
        # First get the issue
        issue_result = await self.get_issue(issue_number)
        if not issue_result.success:
            return GitHubOperationResult.error_result(
                f"Cannot remove label from issue #{issue_number}: {issue_result.error}"
            )
        
        def _remove_label():
            issue = issue_result.data
            current_label_names = [l.name for l in issue.labels]
            
            if label_name.strip() not in current_label_names:
                logger.debug(f"Label '{label_name}' not found on issue #{issue_number}")
                return True  # Already removed
            
            issue.remove_from_labels(label_name.strip())
            logger.info(f"Successfully removed label '{label_name}' from issue #{issue_number}")
            return True
        
        return await self._retry_operation(_remove_label)
    
    async def update_issue(
        self, 
        issue_number: int, 
        title: Optional[str] = None, 
        body: Optional[str] = None,
        state: Optional[str] = None, 
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> GitHubOperationResult:
        """
        Update an existing issue.
        
        Args:
            issue_number: The number of the issue to update.
            title: New title for the issue.
            body: New body for the issue.
            state: New state for the issue ("open" or "closed").
            labels: New list of labels. To remove all, pass empty list.
            assignees: New list of assignees. To remove all, pass empty list.
            
        Returns:
            GitHubOperationResult with the updated Issue or error details.
        """
        # First get the issue
        issue_result = await self.get_issue(issue_number)
        if not issue_result.success:
            return GitHubOperationResult.error_result(
                f"Cannot update issue #{issue_number}: {issue_result.error}"
            )
        
        def _update_issue():
            issue = issue_result.data
            edit_params = {}
            
            if title is not None:
                edit_params['title'] = title.strip()
            if body is not None:
                edit_params['body'] = body
            if state is not None:
                if state not in ['open', 'closed']:
                    raise ValueError(f"Invalid state: {state}. Must be 'open' or 'closed'")
                edit_params['state'] = state
            if labels is not None:
                edit_params['labels'] = labels
            if assignees is not None:
                edit_params['assignees'] = assignees
            
            if not edit_params:
                logger.debug(f"No parameters provided for updating issue #{issue_number}")
                return issue
            
            issue.edit(**edit_params)
            logger.info(f"Successfully updated issue #{issue_number} in {self.repository_name}")
            return issue
        
        return await self._retry_operation(_update_issue)
    
    async def get_issue_comments(self, issue_number: int) -> GitHubOperationResult:
        """
        Retrieve all comments for a given issue.
        
        Args:
            issue_number: The number of the issue.
            
        Returns:
            GitHubOperationResult with list of IssueComments or error details.
        """
        # First get the issue
        issue_result = await self.get_issue(issue_number)
        if not issue_result.success:
            return GitHubOperationResult.error_result(
                f"Cannot get comments for issue #{issue_number}: {issue_result.error}"
            )
        
        def _get_comments():
            issue = issue_result.data
            comments = list(issue.get_comments())
            logger.debug(f"Retrieved {len(comments)} comments for issue #{issue_number}")
            return comments
        
        return await self._retry_operation(_get_comments)
    
    async def search_issues(self, query: str, qualifier: str = "") -> GitHubOperationResult:
        """
        Search for issues in the configured repository.
        
        Args:
            query: The search query string (e.g., "is:open label:bug").
            qualifier: Additional search qualifiers.
            
        Returns:
            GitHubOperationResult with list of Issues or error details.
        """
        if not query or not query.strip():
            return GitHubOperationResult.error_result("Search query cannot be empty")
        
        def _search_issues():
            full_query = f"repo:{self.repository_name} {query.strip()}"
            if qualifier:
                full_query += f" {qualifier.strip()}"
            
            logger.debug(f"Searching issues with query: '{full_query}'")
            issues_paginated = self.github_client.search_issues(query=full_query)
            issues = list(issues_paginated)
            logger.info(f"Found {len(issues)} issues matching query '{query}'")
            return issues
        
        return await self._retry_operation(_search_issues)
    
    async def get_repository_labels(self) -> GitHubOperationResult:
        """
        Retrieve all labels for the configured repository.
        
        Returns:
            GitHubOperationResult with list of Labels or error details.
        """
        def _get_labels():
            labels_paginated = self.repo.get_labels()
            labels = list(labels_paginated)
            logger.debug(f"Retrieved {len(labels)} labels for repository {self.repository_name}")
            return labels
        
        return await self._retry_operation(_get_labels)
    
    async def create_label(
        self, 
        name: str, 
        color: str, 
        description: str = ""
    ) -> GitHubOperationResult:
        """
        Create a new label in the repository.
        
        Args:
            name: The name of the label.
            color: The hex color code (with or without '#').
            description: Optional description for the label.
            
        Returns:
            GitHubOperationResult with the created Label or error details.
        """
        if not name or not name.strip():
            return GitHubOperationResult.error_result("Label name cannot be empty")
        
        if not color or not color.strip():
            return GitHubOperationResult.error_result("Label color cannot be empty")
        
        def _create_label():
            # Clean color (remove # if present)
            clean_color = color.strip().lstrip('#')
            
            # Validate hex color
            if not all(c in '0123456789ABCDEFabcdef' for c in clean_color) or len(clean_color) != 6:
                raise ValueError(f"Invalid hex color: {color}")
            
            try:
                label = self.repo.create_label(
                    name=name.strip(), 
                    color=clean_color, 
                    description=description
                )
                logger.info(f"Successfully created label '{name}' with color '#{clean_color}'")
                return label
                
            except GithubException as e:
                # Handle case where label already exists
                if e.status == 422 and "already_exists" in str(e.data):
                    logger.warning(f"Label '{name}' already exists")
                    # Try to fetch existing label
                    existing_label = self.repo.get_label(name.strip())
                    return existing_label
                raise
        
        return await self._retry_operation(_create_label)
    
    async def update_label(
        self, 
        current_name: str, 
        new_name: Optional[str] = None,
        color: Optional[str] = None, 
        description: Optional[str] = None
    ) -> GitHubOperationResult:
        """
        Update an existing label in the repository.
        
        Args:
            current_name: The current name of the label to update.
            new_name: The new name for the label.
            color: The new hex color code.
            description: The new description.
            
        Returns:
            GitHubOperationResult with the updated Label or error details.
        """
        if not current_name or not current_name.strip():
            return GitHubOperationResult.error_result("Current label name cannot be empty")
        
        def _update_label():
            try:
                label = self.repo.get_label(current_name.strip())
            except UnknownObjectException:
                raise ValueError(f"Label '{current_name}' not found")
            
            # Determine final values
            final_name = new_name.strip() if new_name else current_name.strip()
            final_color = color.strip().lstrip('#') if color else label.color
            final_description = description if description is not None else label.description
            
            # Validate color if provided
            if color and (not all(c in '0123456789ABCDEFabcdef' for c in final_color) or len(final_color) != 6):
                raise ValueError(f"Invalid hex color: {color}")
            
            # Check if changes are needed
            if (final_name == current_name.strip() and 
                final_color == label.color and 
                final_description == label.description):
                logger.debug(f"No changes needed for label '{current_name}'")
                return label
            
            label.edit(name=final_name, color=final_color, description=final_description)
            logger.info(f"Successfully updated label '{current_name}' -> '{final_name}'")
            return label
        
        return await self._retry_operation(_update_label)
    
    @asynccontextmanager
    async def batch_operations(self):
        """
        Context manager for batch operations with improved error handling.
        
        Usage:
            async with github_service.batch_operations():
                await github_service.create_issue(...)
                await github_service.add_label_to_issue(...)
        """
        operations = []
        try:
            yield operations
        except Exception as e:
            logger.error(f"Batch operation failed: {e}")
            raise
        finally:
            if operations:
                logger.info(f"Completed batch operation with {len(operations)} operations")
    
    async def health_check(self) -> GitHubOperationResult:
        """
        Perform a health check on the GitHub service.
        
        Returns:
            GitHubOperationResult indicating service health.
        """
        try:
            # Simple API call to test connectivity
            rate_limit = self.github_client.get_rate_limit()
            remaining = rate_limit.core.remaining
            total = rate_limit.core.limit
            
            health_info = {
                'repository': self.repository_name,
                'rate_limit_remaining': remaining,
                'rate_limit_total': total,
                'rate_limit_percentage': (remaining / total) * 100 if total > 0 else 0
            }
            
            logger.info(f"GitHub service health check passed: {health_info}")
            return GitHubOperationResult.success_result(health_info)
            
        except Exception as e:
            error_msg = f"GitHub service health check failed: {e}"
            logger.error(error_msg)
            return GitHubOperationResult.error_result(error_msg)

# Type aliases for backwards compatibility  
GitHubIssue = Issue
GitHubComment = IssueComment


# Backwards compatibility functions
def get_issue(issue_number: int) -> Optional[Issue]:
    """Backwards compatibility function."""
    import asyncio
    service = GitHubService()
    result = asyncio.run(service.get_issue(issue_number))
    return result.data if result.success else None


def create_issue(title: str, body: str = "", labels: Optional[List[str]] = None, assignees: Optional[List[str]] = None) -> Optional[Issue]:
    """Backwards compatibility function."""
    import asyncio
    service = GitHubService()
    result = asyncio.run(service.create_issue(title, body, labels, assignees))
    return result.data if result.success else None


def add_comment_to_issue(issue_number: int, comment_body: str) -> Optional[IssueComment]:
    """Backwards compatibility function."""
    import asyncio
    service = GitHubService()
    result = asyncio.run(service.add_comment_to_issue(issue_number, comment_body))
    return result.data if result.success else None


def add_label_to_issue(issue_number: int, label_name: str) -> bool:
    """Backwards compatibility function."""
    import asyncio
    service = GitHubService()
    result = asyncio.run(service.add_label_to_issue(issue_number, label_name))
    return result.success


def remove_label_from_issue(issue_number: int, label_name: str) -> bool:
    """Backwards compatibility function."""
    import asyncio
    service = GitHubService()
    result = asyncio.run(service.remove_label_from_issue(issue_number, label_name))
    return result.success


# Example/Test function
async def test_github_service():
    """Test function for GitHubService."""
    logger.info("Starting GitHubService test...")
    
    try:
        gh_service = GitHubService()
        
        # Health check
        health_result = await gh_service.health_check()
        if not health_result.success:
            logger.error(f"Health check failed: {health_result.error}")
            return
        
        logger.info(f"GitHub service healthy: {health_result.data}")
        
        # Test batch operations
        async with gh_service.batch_operations() as ops:
            # Create test issue
            issue_result = await gh_service.create_issue(
                "Test Issue from Enhanced GitHubService",
                "This is a test issue with improved error handling.",
                ["test", "automated"]
            )
            
            if issue_result.success:
                issue = issue_result.data
                logger.info(f"Created test issue #{issue.number}")
                
                # Add comment
                comment_result = await gh_service.add_comment_to_issue(
                    issue.number, 
                    "Test comment from enhanced service"
                )
                
                if comment_result.success:
                    logger.info("Added test comment")
                
                # Update issue to close it
                close_result = await gh_service.update_issue(
                    issue.number,
                    state="closed",
                    body="Test completed - closing issue"
                )
                
                if close_result.success:
                    logger.info(f"Closed test issue #{issue.number}")
            
        logger.info("GitHubService test completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    import asyncio
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(test_github_service())
