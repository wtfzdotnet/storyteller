import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import Config, get_config
from github_handler import GitHubService
from github_handler import Issue as GitHubIssue  # Renamed to avoid clash
from llm_handler import LLMService

logger = logging.getLogger(__name__)


class UserStory(BaseModel):
    id: Optional[int] = None
    title: str
    body: str
    status: Optional[str] = (
        "new"  # e.g., "new", "needs_feedback", "pending_review", "agreed", "implemented"
    )
    roles_involved: List[str] = Field(default_factory=list)
    feedback_log: List[Dict[str, str]] = Field(
        default_factory=list
    )  # Store feedback history
    # raw_github_issue: Optional[Any] = None # Avoid storing raw issue directly if possible, or use specific fields
    github_url: Optional[str] = None

    class Config:
        arbitrary_types_allowed = (
            True  # To allow GitHubIssue if we decide to use raw_github_issue
        )


class StoryOrchestrator:
    def __init__(
        self,
        llm_service: LLMService,
        github_service: GitHubService,
        config: Optional["Config"] = None,
    ):
        self.llm_service = llm_service
        self.github_service = github_service
        self.config = config or get_config()
        self.use_repository_prompts = self._can_use_repository_prompts()
        self._last_consulted_roles = []  # Track roles for reporting
        logger.info("StoryOrchestrator initialized.")
        if self.use_repository_prompts:
            logger.info("Repository-based prompts are enabled for GitHub Models.")
        if self.config.is_multi_repository_mode():
            logger.info(
                f"Multi-repository mode enabled with {len(self.config.get_repository_list())} repositories"
            )

    def _can_use_repository_prompts(self):
        """Determine if repository-based prompts can be used"""
        # Check if using GitHub provider and repository is set
        return (
            getattr(self.llm_service, "provider_name", "") == "github"
            and getattr(self.llm_service, "github_repository", None) is not None
        )

    def _get_role_documentation_paths(self, roles_to_consult):
        """Get documentation paths for requested roles"""
        role_paths = []
        # Always include the main AI.md context
        role_paths.append("AI.md")

        # Add requested role documentation files
        for role in roles_to_consult:
            # Convert role names like "System Architect" to file paths like ".storyteller/roles/system-architect.md"
            role_name = "-".join(word.lower() for word in role.split())
            role_path = f".storyteller/roles/{role_name}.md"
            role_paths.append(role_path)

        return role_paths

    def get_available_repositories(self) -> List[str]:
        """Get list of available repository keys for multi-repository mode."""
        return self.config.get_repository_list()

    def get_repository_dependencies(self, repository_key: str) -> List[str]:
        """Get dependencies for a repository."""
        if self.config.is_multi_repository_mode():
            return self.config.multi_repository_config.get_dependencies(repository_key)
        return []

    def create_github_service_for_repository(
        self, repository_key: Optional[str] = None
    ) -> GitHubService:
        """Create a GitHub service instance for a specific repository."""
        target_repo = self.config.get_target_repository(repository_key)
        if not target_repo:
            raise ValueError(f"No repository found for key: {repository_key}")

        # Create a new GitHub service instance for the target repository
        # This assumes GitHubService can be configured with a different repository
        # We'll need to extend GitHubService to support dynamic repository switching
        return self.github_service  # For now, return the existing service

    def _parse_llm_story_output(self, llm_response: str) -> Dict[str, str]:
        """
        Parses LLM response to extract story title and body.
        Assumes format:
        Title: [Story Title]
        Body: As a [user type], I want [action] so that [benefit].
        """
        title = "Generated User Story"  # Default title
        body = llm_response  # Default body if parsing fails
        try:
            lines = llm_response.strip().split("\n")
            title_line = next(
                (line for line in lines if line.lower().startswith("title:")), None
            )
            if title_line:
                title = title_line.split(":", 1)[1].strip()

            body_start_index = -1
            for i, line in enumerate(lines):
                if line.lower().startswith("body:"):
                    body_start_index = i
                    break
                # Fallback if "Body:" prefix is missing but "As a" is present
                if (
                    "as a" in line.lower()
                    and "i want" in line.lower()
                    and "so that" in line.lower()
                ):
                    body_start_index = i  # Assume this line is the start of the body
                    # and the "Body:" prefix was omitted by LLM
                    if (
                        lines[body_start_index].lower().startswith("body:")
                    ):  # handle if it was found
                        body = (
                            "\n".join(lines[body_start_index:]).split(":", 1)[1].strip()
                        )
                    else:  # if "Body:" prefix is not there
                        body = "\n".join(lines[body_start_index:])
                    break

            if body_start_index != -1:
                # If "Body:" prefix was found and stripped
                if lines[body_start_index].lower().startswith("body:"):
                    body_content_lines = lines[body_start_index:]
                    body = "\n".join(body_content_lines).split(":", 1)[1].strip()
                else:  # if "Body:" prefix was not found, join from the identified line
                    body_content_lines = lines[body_start_index:]
                    body = "\n".join(body_content_lines).strip()

            if not body.lower().startswith(
                "as a"
            ):  # Ensure standard format if possible
                logger.warning(
                    f"LLM generated story body might not follow 'As a...' format. Body: {body[:100]}"
                )

        except Exception as e:
            logger.error(
                f"Error parsing LLM story output: {e}. Raw response: {llm_response[:200]}"
            )

        # Fallback if parsing completely fails to extract meaningful title/body
        if not title or title == "Generated User Story":
            title = "User Story Generation Attempt"
        if not body or body == llm_response:  # if body is still the original response
            body = f"LLM provided the following details for the story:\n{llm_response}"
            logger.warning("Using fallback for story body as parsing failed.")

        return {"title": title, "body": body}

    async def create_complete_story(
        self,
        initial_prompt: str,
        roles_to_consult: List[str],
        target_repo_info: Optional[str] = None,
        repository: Optional[str] = None,
    ) -> Optional[UserStory]:
        """
        Creates a complete, actionable user story using local AI processing.
        
        This simplified approach does all refinement locally before creating the GitHub issue,
        resulting in a ready-to-implement story without iteration on GitHub.
        
        Args:
            initial_prompt: The user's initial idea or requirement
            roles_to_consult: List of roles to consider perspectives from
            target_repo_info: Optional repository context
            repository: Target repository key for multi-repository mode
            
        Returns:
            UserStory object with GitHub issue created, or None if failed
        """
        logger.info(f"Creating complete story from prompt: '{initial_prompt}'")
        logger.info(f"Consulting roles: {roles_to_consult}")
        
        # Track roles for reporting
        self._last_consulted_roles = roles_to_consult
        
        # Local story refinement - gather perspectives from all roles at once
        refined_story = await self._refine_story_locally(
            initial_prompt, roles_to_consult, target_repo_info, repository
        )
        
        if not refined_story:
            logger.error("Failed to refine story locally")
            return None
            
        # Create the GitHub issue with the complete, refined story
        story = await self._create_github_story(
            refined_story["title"],
            refined_story["body"], 
            repository
        )
        
        if story:
            logger.info(f"Successfully created complete story #{story.id}")
        
        return story
        
    async def _refine_story_locally(
        self,
        initial_prompt: str,
        roles_to_consult: List[str],
        target_repo_info: Optional[str] = None,
        repository: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Refine the story locally by gathering input from all roles at once.
        """
        # Build comprehensive prompt that considers all perspectives
        repo_context = ""
        if repository and self.config.is_multi_repository_mode():
            repo_config = self.config.multi_repository_config.get_repository(repository)
            if repo_config:
                repo_context = f"""
Repository Context:
- Repository: {repo_config.name} ({repo_config.type})
- Description: {repo_config.description}
- Focus areas: {repo_config.type}-specific considerations
"""
        elif target_repo_info:
            repo_context = f"Repository Context: {target_repo_info}"
            
        comprehensive_prompt = f"""
Create a complete, actionable user story based on the following initial idea. Consider perspectives from all specified roles to ensure the story is comprehensive and ready for development.

Initial Idea: {initial_prompt}

{repo_context}

Consider these role perspectives:
{self._build_role_perspectives(roles_to_consult)}

Create a user story that includes:
1. Clear user story format: "As a [user], I want [goal] so that [benefit]"
2. Comprehensive acceptance criteria covering all edge cases
3. Technical considerations for implementation
4. Testing scenarios and quality requirements
5. Clear scope and boundaries

Format the response as:
## Title
[Concise story title]

## User Story
[Complete user story description]

## Acceptance Criteria
[Detailed acceptance criteria as checklist]

## Technical Notes
[Implementation considerations]

## Testing Scenarios
[Key test cases to consider]

Ensure the story is actionable and contains all information needed for development without further iteration.
"""

        try:
            if self.use_repository_prompts and repository:
                # Use repository-specific documentation if available
                role_docs = self._get_role_documentation_paths(roles_to_consult)
                response = await self.llm_service.query_llm(
                    comprehensive_prompt, repository_references=role_docs
                )
            else:
                response = await self.llm_service.query_llm(comprehensive_prompt)
                
            if response:
                return self._parse_story_response(response)
            else:
                logger.error("LLM returned empty response for story refinement")
                return None
                
        except Exception as e:
            logger.error(f"Error during local story refinement: {e}")
            return None
            
    def _build_role_perspectives(self, roles: List[str]) -> str:
        """Build role perspective descriptions for the prompt."""
        role_descriptions = {
            "Product Owner": "Business value, user needs, market requirements, acceptance criteria",
            "Lead Developer": "Technical feasibility, architecture, implementation complexity, dependencies",
            "QA Engineer": "Testing scenarios, edge cases, quality criteria, validation requirements",
            "UX Designer": "User experience, usability, accessibility, user journey",
            "DevOps Engineer": "Deployment, infrastructure, monitoring, performance requirements",
            "Security Engineer": "Security considerations, compliance, data protection, threat modeling",
            "Data Analyst": "Data requirements, analytics, reporting, metrics",
            "Technical Lead": "Technical strategy, code quality, best practices, team coordination",
        }
        
        perspectives = []
        for role in roles:
            description = role_descriptions.get(role, "General project considerations")
            perspectives.append(f"- {role}: {description}")
            
        return "\n".join(perspectives)
        
    def _parse_story_response(self, response: str) -> Dict[str, str]:
        """Parse the LLM response into title and body components."""
        lines = response.strip().split('\n')
        title = ""
        body_lines = []
        
        # Find title
        for i, line in enumerate(lines):
            if line.strip().startswith('## Title'):
                if i + 1 < len(lines):
                    title = lines[i + 1].strip()
                break
        
        # Use the full response as body, or extract everything after title
        if title:
            # Find where the body content starts (after title section)
            title_section_end = -1
            for i, line in enumerate(lines):
                if line.strip() == title:
                    title_section_end = i
                    break
            
            if title_section_end >= 0 and title_section_end + 1 < len(lines):
                body_lines = lines[title_section_end + 1:]
            else:
                body_lines = lines
        else:
            # Fallback: use first line as title, rest as body
            if lines:
                title = lines[0].strip().replace('## Title', '').replace('#', '').strip()
                body_lines = lines[1:] if len(lines) > 1 else lines
        
        # Clean up body
        body = '\n'.join(body_lines).strip()
        
        # Ensure we have both title and body
        if not title:
            title = "User Story: " + (body.split('\n')[0][:50] + "..." if body else "Generated Story")
        if not body:
            body = response  # Fallback to full response
            
        return {
            "title": title,
            "body": body
        }
        
    async def _create_github_story(
        self,
        title: str,
        body: str,
        repository: Optional[str] = None
    ) -> Optional[UserStory]:
        """Create the GitHub issue with simplified labeling."""
        try:
            # Determine target repository
            target_repo = None
            if repository and self.config.is_multi_repository_mode():
                repo_config = self.config.multi_repository_config.get_repository(repository)
                if repo_config:
                    target_repo = repo_config.name
            
            # Simple labels - just mark as story and ready
            labels = ["story", "ready-for-development"]
            
            # Add repository-specific labels if in multi-repo mode
            if repository and self.config.is_multi_repository_mode():
                repo_config = self.config.multi_repository_config.get_repository(repository)
                if repo_config and repo_config.story_labels:
                    labels.extend(repo_config.story_labels)
            
            # Create the issue
            create_result = await self.github_service.create_issue(
                title=title,
                body=body,
                labels=labels,
                target_repository=target_repo
            )
            
            if not create_result.success:
                logger.error(f"Failed to create GitHub issue: {create_result.error}")
                return None
                
            github_issue = create_result.data
            
            # Create UserStory object
            story = UserStory(
                id=github_issue.number,
                title=github_issue.title,
                body=github_issue.body or "",
                status="ready",
                github_url=github_issue.html_url,
                roles_involved=[]  # Could be inferred from content if needed
            )
            
            # Add creation comment
            creation_comment = (
                "🚀 **Complete Story Created**\n\n"
                "This story has been refined with input from multiple perspectives and is ready for development. "
                "No further iteration is needed.\n\n"
                f"**Roles Consulted:** {', '.join(self._last_consulted_roles or [])}\n"
                "**Status:** Ready for development"
            )
            
            await self.github_service.add_comment_to_issue(story.id, creation_comment)
            
            return story
            
        except Exception as e:
            logger.error(f"Error creating GitHub story: {e}")
            return None

    # REMOVED: Original create_new_story method - replaced with create_complete_story for simplified approach

    async def create_refactor_tickets(
        self,
        refactor_request: str,
        refactor_type: str,
        target_repositories: Optional[List[str]] = None,
        specific_files: Optional[List[str]] = None,
    ) -> Dict[str, Optional[UserStory]]:
        """
        Creates immediate refactor tickets across repositories with relevant file context.

        Args:
            refactor_request: Description of the refactor needed
            refactor_type: Type of refactor (general, extract, move, rename, optimize, modernize)
            target_repositories: List of repository keys to target (None = all repositories)
            specific_files: Specific files to include in context

        Returns:
            Dictionary mapping repository keys to created UserStory objects
        """
        logger.info(f"Creating refactor tickets for: {refactor_request}")
        logger.info(f"Refactor type: {refactor_type}")

        if not self.config.is_multi_repository_mode():
            logger.info("Single repository mode - creating single refactor ticket")
            single_ticket = await self._create_single_refactor_ticket(
                refactor_request, refactor_type, specific_files
            )
            return {"default": single_ticket}

        # Determine target repositories
        if target_repositories is None:
            target_repositories = self.config.get_repository_list()

        results = {}
        logger.info(
            f"Creating refactor tickets across repositories: {target_repositories}"
        )

        # For refactors, we don't need dependency ordering as they're independent tasks
        for repo_key in target_repositories:
            repo_config = self.config.multi_repository_config.get_repository(repo_key)
            if not repo_config:
                logger.warning(
                    f"Repository configuration not found for key: {repo_key}"
                )
                results[repo_key] = None
                continue

            try:
                # Discover relevant files for this repository
                relevant_files = await self._discover_relevant_files(
                    refactor_request, refactor_type, repo_key, specific_files
                )

                # Create repository-specific refactor ticket
                ticket = await self._create_repository_refactor_ticket(
                    refactor_request,
                    refactor_type,
                    repo_key,
                    repo_config,
                    relevant_files,
                )
                results[repo_key] = ticket

                if ticket:
                    logger.info(
                        f"Created refactor ticket #{ticket.id} in repository {repo_config.name}"
                    )
                else:
                    logger.error(
                        f"Failed to create refactor ticket in repository {repo_config.name}"
                    )

            except Exception as e:
                logger.error(
                    f"Error creating refactor ticket in repository {repo_key}: {e}"
                )
                results[repo_key] = None

        return results

    async def _create_single_refactor_ticket(
        self,
        refactor_request: str,
        refactor_type: str,
        specific_files: Optional[List[str]] = None,
    ) -> Optional[UserStory]:
        """Create a single refactor ticket for single repository mode."""
        relevant_files = await self._discover_relevant_files(
            refactor_request, refactor_type, None, specific_files
        )

        # Get refactor-specific roles
        roles_to_consult = self._get_refactor_roles(refactor_type)

        # Create the refactor prompt with file context
        refactor_prompt = self._create_refactor_prompt(
            refactor_request, refactor_type, None, relevant_files
        )

        # Create the ticket immediately (skip consensus workflow)
        ticket = await self._create_immediate_ticket(
            refactor_prompt, roles_to_consult, refactor_type, relevant_files
        )

        return ticket

    async def _create_repository_refactor_ticket(
        self,
        refactor_request: str,
        refactor_type: str,
        repo_key: str,
        repo_config,
        relevant_files: List[str],
    ) -> Optional[UserStory]:
        """Create a repository-specific refactor ticket."""
        # Get refactor-specific roles
        roles_to_consult = self._get_refactor_roles(refactor_type)

        # Create repository-specific refactor prompt
        refactor_prompt = self._create_refactor_prompt(
            refactor_request, refactor_type, repo_key, relevant_files
        )

        # Create the ticket immediately (skip consensus workflow)
        ticket = await self._create_immediate_ticket(
            refactor_prompt, roles_to_consult, refactor_type, relevant_files, repo_key
        )

        return ticket

    async def _discover_relevant_files(
        self,
        refactor_request: str,
        refactor_type: str,
        repo_key: Optional[str],
        specific_files: Optional[List[str]],
    ) -> List[str]:
        """
        Discover relevant files based on the refactor request and type.
        """
        relevant_files = []

        # If specific files are provided, use them
        if specific_files:
            logger.info(f"Using provided specific files: {specific_files}")
            return specific_files

        # Use AI to analyze the refactor request and suggest relevant files/patterns
        discovery_prompt = f"""
        Analyze the following refactor request and suggest relevant file patterns, directories, or specific files that would likely be involved.

        Refactor Request: {refactor_request}
        Refactor Type: {refactor_type}
        Repository Type: {repo_key if repo_key else 'general'}

        Based on the refactor type, consider:
        - extract: Look for files that might contain the code to be extracted
        - move: Identify source and target locations
        - rename: Find files that reference the items to be renamed  
        - optimize: Locate performance-critical files or bottlenecks
        - modernize: Find outdated patterns, dependencies, or syntax
        - general: Analyze the request for relevant areas

        Provide a list of file patterns or specific files (one per line) that would be relevant for this refactor.
        Focus on commonly modified file types for this type of change.
        Examples:
        - **/*.py (for Python files)
        - src/auth/*.js (for authentication JavaScript files)
        - config/*.yml (for configuration files)
        - README.md (for documentation updates)
        """

        try:
            if self.use_repository_prompts:
                # Get repository context for file discovery
                role_docs = ["AI.md"]
                if repo_key:
                    role_docs.append(f".storyteller/roles/{repo_key}-specific.md")

                file_suggestions = await self.llm_service.query_llm(
                    discovery_prompt, repository_references=role_docs
                )
            else:
                file_suggestions = await self.llm_service.query_llm(discovery_prompt)

            if file_suggestions:
                # Parse the response to extract file patterns
                lines = file_suggestions.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        # Clean up common formatting
                        if line.startswith("- "):
                            line = line[2:]
                        relevant_files.append(line)

                logger.info(
                    f"AI suggested {len(relevant_files)} relevant file patterns"
                )
            else:
                logger.warning("AI returned no file suggestions")

        except Exception as e:
            logger.error(f"Error discovering relevant files: {e}")

        # Add default patterns based on refactor type if no suggestions
        if not relevant_files:
            relevant_files = self._get_default_file_patterns(refactor_type, repo_key)

        return relevant_files

    def _get_default_file_patterns(
        self, refactor_type: str, repo_key: Optional[str]
    ) -> List[str]:
        """Get default file patterns based on refactor type and repository."""
        defaults = {
            "extract": ["**/*.py", "**/*.js", "**/*.ts", "src/**/*"],
            "move": ["**/*.py", "**/*.js", "**/*.ts", "**/*.md"],
            "rename": ["**/*.py", "**/*.js", "**/*.ts", "**/*.json", "**/*.yml"],
            "optimize": ["**/*.py", "**/*.js", "**/*.ts", "**/*.sql"],
            "modernize": [
                "**/*.py",
                "**/*.js",
                "**/*.ts",
                "package.json",
                "requirements.txt",
            ],
            "general": ["**/*.py", "**/*.js", "**/*.ts", "**/*.md"],
        }

        patterns = defaults.get(refactor_type, defaults["general"])

        # Customize based on repository type
        if repo_key:
            repo_config = (
                self.config.multi_repository_config.get_repository(repo_key)
                if self.config.is_multi_repository_mode()
                else None
            )
            if repo_config:
                if repo_config.type == "backend":
                    patterns = ["**/*.py", "**/*.sql", "**/*.yml", "**/*.json"]
                elif repo_config.type == "frontend":
                    patterns = [
                        "**/*.js",
                        "**/*.ts",
                        "**/*.jsx",
                        "**/*.tsx",
                        "**/*.css",
                        "**/*.scss",
                    ]
                elif repo_config.type == "mobile":
                    patterns = [
                        "**/*.swift",
                        "**/*.kt",
                        "**/*.dart",
                        "**/*.js",
                        "**/*.ts",
                    ]

        return patterns

    def _get_refactor_roles(self, refactor_type: str) -> List[str]:
        """Get appropriate roles based on refactor type."""
        role_mapping = {
            "extract": ["Senior Developer", "Software Architect", "Code Reviewer"],
            "move": ["Senior Developer", "DevOps Engineer", "Tech Lead"],
            "rename": ["Senior Developer", "Documentation Specialist", "QA Engineer"],
            "optimize": ["Performance Engineer", "Senior Developer", "DevOps Engineer"],
            "modernize": ["Tech Lead", "Senior Developer", "Security Engineer"],
            "general": ["Senior Developer", "Tech Lead", "Code Reviewer"],
        }

        return role_mapping.get(refactor_type, role_mapping["general"])

    def _create_refactor_prompt(
        self,
        refactor_request: str,
        refactor_type: str,
        repo_key: Optional[str],
        relevant_files: List[str],
    ) -> str:
        """Create a comprehensive refactor prompt with context."""
        repo_context = ""
        if repo_key and self.config.is_multi_repository_mode():
            repo_config = self.config.multi_repository_config.get_repository(repo_key)
            if repo_config:
                repo_context = f"\n\nRepository Context: {repo_config.name} ({repo_config.type})\nDescription: {repo_config.description}"

        file_context = ""
        if relevant_files:
            file_context = f"\n\nRelevant Files/Patterns:\n" + "\n".join(
                f"- {file}" for file in relevant_files
            )

        prompt = f"""# Refactor Task: {refactor_request}

## Refactor Type: {refactor_type.title()}

## Task Description
{refactor_request}{repo_context}{file_context}

## Deliverables
As a refactor task, this should result in:

1. **Analysis**: Understanding of current state and what needs to change
2. **Planning**: Step-by-step refactor plan with risk assessment
3. **Implementation**: Actual code changes required
4. **Testing**: How to verify the refactor maintains functionality
5. **Documentation**: Updates to documentation, comments, or README files

## Acceptance Criteria
- [ ] Code is refactored according to the specified requirements
- [ ] All existing functionality is preserved
- [ ] Code quality is improved (readability, maintainability, performance)
- [ ] Tests pass and cover refactored code
- [ ] Documentation is updated to reflect changes
- [ ] No breaking changes for existing API consumers

## Additional Context
This is an immediate refactor task that bypasses the normal story consensus workflow.
Focus on technical implementation details and provide clear guidance for the development team.
"""

        return prompt

    async def _create_immediate_ticket(
        self,
        prompt: str,
        roles_to_consult: List[str],
        refactor_type: str,
        relevant_files: List[str],
        target_repository_key: Optional[str] = None,
    ) -> Optional[UserStory]:
        """Create an immediate ticket without going through consensus workflow."""
        # Generate a proper title and body using AI
        title_prompt = f"""
        Create a concise, descriptive title (under 80 characters) for this refactor ticket:
        
        {prompt[:500]}...
        
        The title should start with "Refactor:" and clearly indicate what is being refactored.
        """

        try:
            if self.use_repository_prompts:
                role_docs = self._get_role_documentation_paths(["Technical Lead"])
                story_title = await self.llm_service.query_llm(
                    title_prompt, repository_references=role_docs
                )
            else:
                story_title = await self.llm_service.query_llm(title_prompt)

            # Clean up the title
            if story_title:
                story_title = story_title.strip().strip('"').strip("'")
                if not story_title.startswith("Refactor:"):
                    story_title = f"Refactor: {story_title}"
            else:
                story_title = f"Refactor: {refactor_type.title()} Task"

        except Exception as e:
            logger.error(f"Error generating refactor title: {e}")
            story_title = f"Refactor: {refactor_type.title()} Task"

        # Convert role names to needs/* labels for immediate creation
        role_labels = []
        for role_name in roles_to_consult:
            role_slug = role_name.replace(" ", "-").lower()
            role_labels.append(f"needs/{role_slug}")

        # Add refactor-specific labels
        labels = [
            "refactor",
            f"refactor/{refactor_type}",
            "ready-for-development",
        ] + role_labels

        # Add repository-specific labels if in multi-repo mode
        if target_repository_key and self.config.is_multi_repository_mode():
            repo_config = self.config.multi_repository_config.get_repository(
                target_repository_key
            )
            if repo_config and repo_config.story_labels:
                labels.extend(repo_config.story_labels)

        logger.info(f"Creating immediate refactor ticket with title: '{story_title}'")

        # Create the GitHub issue directly
        try:
            created_issue_result = await self.github_service.create_issue(
                title=story_title, body=prompt, labels=labels
            )

            if created_issue_result.success:
                created_issue = created_issue_result.data
                user_story = UserStory(
                    id=created_issue.number,
                    title=created_issue.title,
                    body=created_issue.body or "",
                    status="ready",  # Immediate ready status
                    roles_involved=roles_to_consult,
                    github_url=created_issue.html_url,
                )

                # Add immediate context comment with file information
                if relevant_files:
                    files_comment = (
                        f"**🔧 Refactor Context**\n\n"
                        f"**Type**: {refactor_type.title()}\n"
                        f"**Relevant Files/Patterns**:\n"
                        + "\n".join(f"- `{file}`" for file in relevant_files)
                        + f"\n\n**Assigned Roles**: {', '.join(roles_to_consult)}\n\n"
                        f"This refactor ticket was created immediately and is ready for development. "
                        f"Review the file patterns above to understand the scope of changes needed."
                    )
                    await self.github_service.add_comment_to_issue(
                        created_issue.number, files_comment
                    )

                logger.info(
                    f"Successfully created immediate refactor ticket #{created_issue.number}"
                )
                return user_story
            else:
                logger.error("Failed to create GitHub issue for refactor ticket")
                return None

        except Exception as e:
            logger.error(f"Error creating immediate refactor ticket: {e}")
            return None

    async def create_multi_repository_stories(
        self,
        initial_prompt: str,
        roles_to_consult: List[str],
        target_repositories: Optional[List[str]] = None,
    ) -> Dict[str, Optional[UserStory]]:
        """
        Creates user stories across multiple repositories with dependency awareness.

        Args:
            initial_prompt: The user's request for the story
            roles_to_consult: List of roles to involve in the stories
            target_repositories: List of repository keys to target (None = all repositories)

        Returns:
            Dictionary mapping repository keys to created UserStory objects
        """
        if not self.config.is_multi_repository_mode():
            logger.warning(
                "Multi-repository mode not enabled, falling back to single repository"
            )
            single_story = await self.create_new_story(initial_prompt, roles_to_consult)
            return {"default": single_story}

        # Determine target repositories
        if target_repositories is None:
            target_repositories = self.config.get_repository_list()

        results = {}
        logger.info(f"Creating stories across repositories: {target_repositories}")

        # Sort repositories by dependencies (dependencies first)
        sorted_repos = self._sort_repositories_by_dependencies(target_repositories)

        for repo_key in sorted_repos:
            repo_config = self.config.multi_repository_config.get_repository(repo_key)
            if not repo_config:
                logger.warning(
                    f"Repository configuration not found for key: {repo_key}"
                )
                results[repo_key] = None
                continue

            # Customize prompt based on repository type and dependencies
            repo_specific_prompt = self._customize_prompt_for_repository(
                initial_prompt, repo_key, repo_config, results
            )

            try:
                story = await self.create_new_story(
                    repo_specific_prompt,
                    roles_to_consult,
                    target_repository_key=repo_key,
                )
                results[repo_key] = story

                if story:
                    logger.info(
                        f"Created story #{story.id} in repository {repo_config.name}"
                    )
                    # Add cross-repository references
                    await self._add_cross_repository_references(
                        story, repo_key, results
                    )
                else:
                    logger.error(
                        f"Failed to create story in repository {repo_config.name}"
                    )

            except Exception as e:
                logger.error(f"Error creating story in repository {repo_key}: {e}")
                results[repo_key] = None

        return results

    def _sort_repositories_by_dependencies(
        self, repository_keys: List[str]
    ) -> List[str]:
        """Sort repositories by dependencies (dependencies first)."""
        sorted_repos = []
        remaining_repos = repository_keys.copy()

        while remaining_repos:
            # Find repositories with no unresolved dependencies
            ready_repos = []
            for repo_key in remaining_repos:
                dependencies = self.get_repository_dependencies(repo_key)
                # Check if all dependencies are already processed or not in target list
                if all(
                    dep not in remaining_repos or dep in sorted_repos
                    for dep in dependencies
                ):
                    ready_repos.append(repo_key)

            if not ready_repos:
                # Circular dependency or missing dependency - just add remaining
                logger.warning(
                    f"Potential circular dependencies detected, adding remaining repos: {remaining_repos}"
                )
                sorted_repos.extend(remaining_repos)
                break

            # Add ready repositories
            sorted_repos.extend(ready_repos)
            for repo in ready_repos:
                remaining_repos.remove(repo)

        return sorted_repos

    def _customize_prompt_for_repository(
        self,
        original_prompt: str,
        repo_key: str,
        repo_config,
        existing_results: Dict[str, Optional[UserStory]],
    ) -> str:
        """Customize the prompt based on repository type and existing stories."""
        dependencies = self.get_repository_dependencies(repo_key)

        customized_prompt = f"{original_prompt}\n\n"
        customized_prompt += f"Focus on the {repo_config.type} aspects of this request."

        if dependencies:
            dependency_context = []
            for dep in dependencies:
                if dep in existing_results and existing_results[dep]:
                    story = existing_results[dep]
                    dependency_context.append(f"- {dep}: {story.title} (#{story.id})")
                else:
                    dependency_context.append(
                        f"- {dep}: (will be implemented separately)"
                    )

            if dependency_context:
                customized_prompt += (
                    f"\n\nThis story depends on the following components:\n"
                )
                customized_prompt += "\n".join(dependency_context)

        return customized_prompt

    async def _add_cross_repository_references(
        self,
        story: UserStory,
        repo_key: str,
        all_results: Dict[str, Optional[UserStory]],
    ):
        """Add references to related stories in other repositories."""
        if not story or not story.id:
            return

        references = []
        dependencies = self.get_repository_dependencies(repo_key)

        for dep in dependencies:
            if dep in all_results and all_results[dep]:
                dep_story = all_results[dep]
                references.append(
                    f"- Depends on: {dep_story.title} (#{dep_story.id}) in {dep} repository"
                )

        # Add references to stories that depend on this one
        for other_repo, other_story in all_results.items():
            if (
                other_repo != repo_key
                and other_story
                and repo_key in self.get_repository_dependencies(other_repo)
            ):
                references.append(
                    f"- Required by: {other_story.title} (#{other_story.id}) in {other_repo} repository"
                )

        if references:
            reference_comment = "**Cross-Repository Dependencies:**\n\n" + "\n".join(
                references
            )
            await self.github_service.add_comment_to_issue(story.id, reference_comment)

    # REMOVED: gather_feedback_and_iterate - simplified approach does local processing instead

    async def get_story_details(self, story_id: int) -> Optional[UserStory]:
        logger.info(f"Fetching details for story #{story_id}")
        github_issue_result = await self.github_service.get_issue(story_id)
        if not github_issue_result.success:
            logger.warning(f"Story #{story_id} not found on GitHub.")
            return None
        github_issue = github_issue_result.data

        comments_result = await self.github_service.get_issue_comments(story_id)
        feedback_log = []
        if comments_result.success:
            feedback_log = [
                {"role": comment.user.login, "comment": comment.body}
                for comment in comments_result.data
            ]

        # Infer roles_involved from labels if possible (simple example)
        roles_involved = []
        if github_issue.labels:
            for label in github_issue.labels:
                if label.name.startswith("role:"):
                    roles_involved.append(label.name.split(":", 1)[1].capitalize())

        user_story = UserStory(
            id=github_issue.number,
            title=github_issue.title,
            body=github_issue.body or "",
            status=github_issue.state,  # "open" or "closed" - can be more granular based on labels
            roles_involved=roles_involved,
            feedback_log=feedback_log,
            github_url=github_issue.html_url,
        )
        logger.info(f"Successfully retrieved details for story #{user_story.id}")
        return user_story

    # REMOVED: check_agreement - simplified approach doesn't need consensus checking

    # REMOVED: finalize_story_with_iterations - simplified approach creates ready stories directly
if __name__ == "__main__":
    import asyncio
    import os

    from dotenv import load_dotenv

    # Load .env file from project root
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        print(f"Loaded .env file from: {dotenv_path}")
    else:
        # Fallback for running from project root
        load_dotenv()
        print(f"Attempted to load .env from default location.")

    try:
        from github_handler import GitHubService
        from llm_handler import LLMService
    except ImportError:
        print(
            "Warning: Could not import services for testing. Skipping test execution."
        )
        exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    async def test_story_orchestrator():
        logger.info("--- Starting StoryOrchestrator Test ---")

        # Ensure necessary env vars are set
        if (
            not os.getenv("GITHUB_TOKEN")
            or not os.getenv("GITHUB_REPOSITORY")
            or (
                not os.getenv("OPENAI_API_KEY")
                and os.getenv("DEFAULT_LLM_PROVIDER", "openai") == "openai"
            )
        ):
            logger.error(
                "Missing one or more required environment variables for testing: "
                "GITHUB_TOKEN, GITHUB_REPOSITORY, OPENAI_API_KEY (if using OpenAI)."
            )
            return

        try:
            llm_service = LLMService()  # Uses config from .env
            github_service = GitHubService()  # Uses config from .env
            orchestrator = StoryOrchestrator(llm_service, github_service)

            repo_name = os.getenv("GITHUB_REPOSITORY")
            logger.info(f"Targeting repository: {repo_name}")

            # 1. Create a new story
            initial_prompt_for_story = "As a marketing manager, I want to be able to track campaign performance in real-time so I can make quick adjustments."
            roles_for_story = ["Product Owner", "Data Analyst", "UX Designer"]

            logger.info(f"\n--- Test 1: Create New Story ---")
            new_story = await orchestrator.create_new_story(
                initial_prompt=initial_prompt_for_story,
                roles_to_consult=roles_for_story,
                target_repo_info=repo_name,
            )

            if not new_story or not new_story.id:
                logger.error("Failed to create new story. Aborting further tests.")
                return

            logger.info(
                f"Successfully created story: ID={new_story.id}, Title='{new_story.title}', URL: {new_story.github_url}"
            )
            story_id_for_test = new_story.id

            # 2. Get story details
            logger.info(
                f"\n--- Test 2: Get Story Details for Story #{story_id_for_test} ---"
            )
            story_details = await orchestrator.get_story_details(story_id_for_test)
            if story_details:
                logger.info(
                    f"Retrieved details: ID={story_details.id}, Title='{story_details.title}', Status='{story_details.status}'"
                )
                logger.info(f"Body: {story_details.body[:100]}...")
                logger.info(
                    f"Roles involved from labels: {story_details.roles_involved}"
                )
            else:
                logger.error(
                    f"Failed to retrieve details for story #{story_id_for_test}."
                )
                # Clean up created issue before exiting if retrieval failed
                logger.info(
                    f"Attempting to close issue #{story_id_for_test} due to error..."
                )
                await github_service.update_issue(
                    story_id_for_test,
                    state="closed",
                    body=f"{new_story.body}\n\n---\nClosed due to test error.",
                )
                return

            # 3. Gather feedback and iterate
            # For testing, roles_providing_feedback might be a subset or same as roles_to_consult
            roles_for_feedback_simulation = ["Data Analyst", "UX Designer"]
            logger.info(
                f"\n--- Test 3: Gather Feedback & Iterate for Story #{story_id_for_test} (Simulating: {roles_for_feedback_simulation}) ---"
            )
            iterated_story = await orchestrator.gather_feedback_and_iterate(
                story_id_for_test, roles_for_feedback_simulation
            )
            if iterated_story:
                logger.info(
                    f"Iteration process completed for story #{iterated_story.id}. Status: {iterated_story.status}"
                )
                logger.info(
                    f"Check GitHub issue for AI-generated feedback and summary: {iterated_story.github_url}"
                )
            else:
                logger.error(
                    f"Failed to gather feedback/iterate for story #{story_id_for_test}."
                )
                # Attempt cleanup
                logger.info(
                    f"Attempting to close issue #{story_id_for_test} due to error..."
                )
                await github_service.update_issue(
                    story_id_for_test,
                    state="closed",
                    body=f"{new_story.body}\n\n---\nClosed due to test error.",
                )
                return

            # 4. Check for agreement (this is likely to be False initially)
            logger.info(
                f"\n--- Test 4: Check Agreement for Story #{story_id_for_test} (Roles: {roles_for_story}) ---"
            )
            # Add a slight delay for comments to be processed by GitHub if check_agreement is too fast
            await asyncio.sleep(5)  # 5 seconds delay

            # Simulate adding a manual "approval" comment for one role to test LLM's interpretation
            # This would typically be a human action
            logger.info(
                f"Manually adding a test 'approval' comment from 'Product Owner' for story #{story_id_for_test}"
            )
            await github_service.add_comment_to_issue(
                story_id_for_test, "Product Owner: LGTM, approved for development!"
            )
            await asyncio.sleep(2)  # Short delay for comment to post

            agreement_reached = await orchestrator.check_agreement(
                story_id_for_test, roles_for_story
            )
            logger.info(
                f"Agreement check for story #{story_id_for_test} (expecting False or True based on LLM interpretation of AI + manual comments): {agreement_reached}"
            )
            if agreement_reached:
                logger.info(
                    f"LLM determined agreement was reached for story #{story_id_for_test}."
                )
                await github_service.update_issue(
                    story_id_for_test,
                    labels=["user_story", "agreed", "ai_validated_agreement"],
                )
            else:
                logger.info(
                    f"LLM determined agreement was NOT reached for story #{story_id_for_test}."
                )

            # Clean up: Close the test issue
            logger.info(f"\n--- Test Cleanup: Closing Story #{story_id_for_test} ---")
            latest_story = await orchestrator.get_story_details(story_id_for_test)
            final_body_for_closure = (
                latest_story.body if latest_story else "Test completed"
            )
            closed_issue_result = await github_service.update_issue(
                story_id_for_test,
                state="closed",
                body=f"{final_body_for_closure}\n\n---\nTest completed and issue closed.",
            )
            if (
                closed_issue_result.success
                and closed_issue_result.data.state == "closed"
            ):
                logger.info(f"Successfully closed story #{story_id_for_test}.")
            else:
                logger.error(
                    f"Failed to close story #{story_id_for_test} during cleanup."
                )

        except Exception as e:
            logger.error(
                f"An unexpected error occurred during StoryOrchestrator test: {e}",
                exc_info=True,
            )
            # If an issue was created and its ID is known, try to close it
            if "story_id_for_test" in locals() and story_id_for_test:
                logger.warning(
                    f"Attempting emergency cleanup of issue #{story_id_for_test} due to error: {e}"
                )
                try:
                    gh_service_cleanup = (
                        GitHubService()
                    )  # New instance if previous failed
                    await gh_service_cleanup.update_issue(
                        story_id_for_test,
                        state="closed",
                        body=f"Issue closed due to test script error: {e}",
                    )
                    logger.info(
                        f"Emergency closure of issue #{story_id_for_test} attempted."
                    )
                except Exception as cleanup_e:
                    logger.error(
                        f"Failed emergency cleanup of issue #{story_id_for_test}: {cleanup_e}"
                    )

        logger.info("--- StoryOrchestrator Test Finished ---")

    if __name__ == "__main__":
        # This setup is for running the test script directly.
        # Ensure that Python can find the `ai` package.
        # If you are in the project root, run as `python -m ai.ai_core.story_manager`
        asyncio.run(test_story_orchestrator())
