import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from llm_handler import LLMService
from github_handler import GitHubService, Issue as GitHubIssue # Renamed to avoid clash
from config import get_config

logger = logging.getLogger(__name__)

class UserStory(BaseModel):
    id: Optional[int] = None
    title: str
    body: str
    status: Optional[str] = "new" # e.g., "new", "needs_feedback", "pending_review", "agreed", "implemented"
    roles_involved: List[str] = Field(default_factory=list)
    feedback_log: List[Dict[str, str]] = Field(default_factory=list) # Store feedback history
    # raw_github_issue: Optional[Any] = None # Avoid storing raw issue directly if possible, or use specific fields
    github_url: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True # To allow GitHubIssue if we decide to use raw_github_issue

class StoryOrchestrator:
    def __init__(self, llm_service: LLMService, github_service: GitHubService, config: Optional['Config'] = None):
        self.llm_service = llm_service
        self.github_service = github_service
        self.config = config or get_config()
        self.use_repository_prompts = self._can_use_repository_prompts()
        logger.info("StoryOrchestrator initialized.")
        if self.use_repository_prompts:
            logger.info("Repository-based prompts are enabled for GitHub Models.")
        if self.config.is_multi_repository_mode():
            logger.info(f"Multi-repository mode enabled with {len(self.config.get_repository_list())} repositories")

    def _can_use_repository_prompts(self):
        """Determine if repository-based prompts can be used"""
        # Check if using GitHub provider and repository is set
        return (getattr(self.llm_service, 'provider_name', '') == 'github' and 
                getattr(self.llm_service, 'github_repository', None) is not None)
                
    def _get_role_documentation_paths(self, roles_to_consult):
        """Get documentation paths for requested roles"""
        role_paths = []
        # Always include the main AI.md context
        role_paths.append("AI.md")
        
        # Add requested role documentation files
        for role in roles_to_consult:
            # Convert role names like "System Architect" to file paths like "docs/ai/roles/system-architect.md"
            role_name = '-'.join(word.lower() for word in role.split())
            role_path = f"docs/ai/roles/{role_name}.md"
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
    
    def create_github_service_for_repository(self, repository_key: Optional[str] = None) -> GitHubService:
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
        title = "Generated User Story" # Default title
        body = llm_response # Default body if parsing fails
        try:
            lines = llm_response.strip().split('\n')
            title_line = next((line for line in lines if line.lower().startswith("title:")), None)
            if title_line:
                title = title_line.split(":", 1)[1].strip()
            
            body_start_index = -1
            for i, line in enumerate(lines):
                if line.lower().startswith("body:"):
                    body_start_index = i
                    break
                # Fallback if "Body:" prefix is missing but "As a" is present
                if "as a" in line.lower() and "i want" in line.lower() and "so that" in line.lower():
                    body_start_index = i # Assume this line is the start of the body
                    # and the "Body:" prefix was omitted by LLM
                    if lines[body_start_index].lower().startswith("body:"): # handle if it was found
                         body = '\n'.join(lines[body_start_index:]).split(":",1)[1].strip()
                    else: # if "Body:" prefix is not there
                         body = '\n'.join(lines[body_start_index:]) 
                    break


            if body_start_index != -1:
                # If "Body:" prefix was found and stripped
                if lines[body_start_index].lower().startswith("body:"):
                    body_content_lines = lines[body_start_index:]
                    body = '\n'.join(body_content_lines).split(":", 1)[1].strip()
                else: # if "Body:" prefix was not found, join from the identified line
                    body_content_lines = lines[body_start_index:]
                    body = '\n'.join(body_content_lines).strip()

            if not body.lower().startswith("as a"): # Ensure standard format if possible
                 logger.warning(f"LLM generated story body might not follow 'As a...' format. Body: {body[:100]}")


        except Exception as e:
            logger.error(f"Error parsing LLM story output: {e}. Raw response: {llm_response[:200]}")
        
        # Fallback if parsing completely fails to extract meaningful title/body
        if not title or title == "Generated User Story":
            title = "User Story Generation Attempt"
        if not body or body == llm_response: # if body is still the original response
            body = f"LLM provided the following details for the story:\n{llm_response}"
            logger.warning("Using fallback for story body as parsing failed.")

        return {"title": title, "body": body}

    async def create_new_story(self, initial_prompt: str, roles_to_consult: List[str], 
                               target_repo_info: Optional[str] = None, 
                               target_repository_key: Optional[str] = None) -> Optional[UserStory]:
        """
        Creates a new user story using LLM and posts it to GitHub.
        
        Args:
            initial_prompt: The user's request for the story
            roles_to_consult: List of roles to involve in the story
            target_repo_info: Optional context about the target repository
            target_repository_key: Repository key for multi-repository mode
        """
        # Determine target repository
        target_repo = self.config.get_target_repository(target_repository_key)
        if not target_repo:
            logger.error(f"No target repository found for key: {target_repository_key}")
            return None
            
        logger.info(f"Creating new story based on prompt: '{initial_prompt[:50]}...' for roles: {roles_to_consult}")
        logger.info(f"Target repository: {target_repo}")

        # Build enhanced context for multi-repository mode
        repo_context = target_repo_info or target_repo
        if self.config.is_multi_repository_mode() and target_repository_key:
            repo_config = self.config.multi_repository_config.get_repository(target_repository_key)
            if repo_config:
                repo_context = f"{repo_config.description} ({repo_config.type})"
                dependencies = self.get_repository_dependencies(target_repository_key)
                if dependencies:
                    repo_context += f". Dependencies: {', '.join(dependencies)}"

        llm_prompt = (
            f"You are a highly experienced Product Owner. Your task is to generate a user story based on the following request:\n"
            f"Request: '{initial_prompt}'\n\n"
            f"The user story should be well-defined, actionable, and follow the standard format.\n"
            f"Consider that the following roles will be involved in its implementation and potential feedback: {', '.join(roles_to_consult)}.\n"
            f"If the request implies multiple features, focus on the most critical one for this user story.\n"
            f"Provide the output in the following format:\n"
            f"Title: [Concise Story Title]\n"
            f"Body: As a [specific user type], I want [a specific action/feature] so that [a clear benefit/value].\n\n"
            f"Additional details or acceptance criteria can be added below the main body if necessary, but ensure the primary body is concise."
        )
        
        if repo_context:
            llm_prompt += f"\n\nThe story will be part of the '{repo_context}' project. Keep this context in mind."

        try:
            # If using GitHub Models with repository-based prompts
            if self.use_repository_prompts:
                role_docs = self._get_role_documentation_paths(roles_to_consult)
                logger.info(f"Using repository-based prompt with role docs: {role_docs}")
                llm_response = await self.llm_service.query_llm(
                    llm_prompt, 
                    repository_references=role_docs
                )
            else:
                llm_response = await self.llm_service.query_llm(llm_prompt)
                
            if not llm_response:
                logger.error("LLM returned an empty response for story generation.")
                return None
            
            parsed_story = self._parse_llm_story_output(llm_response)
            story_title = parsed_story["title"]
            story_body = parsed_story["body"]

            # Convert role names to needs/* labels consistently with workflow processor
            role_labels = []
            for role_name in roles_to_consult:
                role_slug = role_name.replace(' ', '-').lower()
                role_labels.append(f"needs/{role_slug}")
            
            labels = ["user_story", "ai_generated"] + role_labels
            
            logger.info(f"Creating GitHub issue with Title: '{story_title}'")
            created_issue = self.github_service.create_issue(
                title=story_title, 
                body=story_body, 
                labels=labels
            )

            if created_issue:
                user_story = UserStory(
                    id=created_issue.number,
                    title=created_issue.title,
                    body=created_issue.body or "", # Ensure body is not None
                    status="draft",
                    roles_involved=roles_to_consult,
                    github_url=created_issue.html_url
                )
                logger.info(f"Successfully created story #{user_story.id} - '{user_story.title}'")
                # Add a comment indicating it was AI generated and what roles are expected for feedback
                self.github_service.add_comment_to_issue(
                    created_issue.number,
                    f"This user story was automatically generated based on the prompt: '{initial_prompt}'.\n\n"
                    f"Awaiting feedback from the following roles: {', '.join(roles_to_consult)}."
                )
                return user_story
            else:
                logger.error("Failed to create GitHub issue for the new story.")
                return None
        except Exception as e:
            logger.error(f"Error in create_new_story: {e}", exc_info=True)
            return None

    async def create_multi_repository_stories(self, initial_prompt: str, roles_to_consult: List[str], 
                                            target_repositories: Optional[List[str]] = None) -> Dict[str, Optional[UserStory]]:
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
            logger.warning("Multi-repository mode not enabled, falling back to single repository")
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
                logger.warning(f"Repository configuration not found for key: {repo_key}")
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
                    target_repository_key=repo_key
                )
                results[repo_key] = story
                
                if story:
                    logger.info(f"Created story #{story.id} in repository {repo_config.name}")
                    # Add cross-repository references
                    await self._add_cross_repository_references(story, repo_key, results)
                else:
                    logger.error(f"Failed to create story in repository {repo_config.name}")
                    
            except Exception as e:
                logger.error(f"Error creating story in repository {repo_key}: {e}")
                results[repo_key] = None
        
        return results
    
    def _sort_repositories_by_dependencies(self, repository_keys: List[str]) -> List[str]:
        """Sort repositories by dependencies (dependencies first)."""
        sorted_repos = []
        remaining_repos = repository_keys.copy()
        
        while remaining_repos:
            # Find repositories with no unresolved dependencies
            ready_repos = []
            for repo_key in remaining_repos:
                dependencies = self.get_repository_dependencies(repo_key)
                # Check if all dependencies are already processed or not in target list
                if all(dep not in remaining_repos or dep in sorted_repos for dep in dependencies):
                    ready_repos.append(repo_key)
            
            if not ready_repos:
                # Circular dependency or missing dependency - just add remaining
                logger.warning(f"Potential circular dependencies detected, adding remaining repos: {remaining_repos}")
                sorted_repos.extend(remaining_repos)
                break
            
            # Add ready repositories
            sorted_repos.extend(ready_repos)
            for repo in ready_repos:
                remaining_repos.remove(repo)
        
        return sorted_repos
    
    def _customize_prompt_for_repository(self, original_prompt: str, repo_key: str, 
                                       repo_config, existing_results: Dict[str, Optional[UserStory]]) -> str:
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
                    dependency_context.append(f"- {dep}: (will be implemented separately)")
            
            if dependency_context:
                customized_prompt += f"\n\nThis story depends on the following components:\n"
                customized_prompt += "\n".join(dependency_context)
        
        return customized_prompt
    
    async def _add_cross_repository_references(self, story: UserStory, repo_key: str, 
                                             all_results: Dict[str, Optional[UserStory]]):
        """Add references to related stories in other repositories."""
        if not story or not story.id:
            return
        
        references = []
        dependencies = self.get_repository_dependencies(repo_key)
        
        for dep in dependencies:
            if dep in all_results and all_results[dep]:
                dep_story = all_results[dep]
                references.append(f"- Depends on: {dep_story.title} (#{dep_story.id}) in {dep} repository")
        
        # Add references to stories that depend on this one
        for other_repo, other_story in all_results.items():
            if (other_repo != repo_key and other_story and 
                repo_key in self.get_repository_dependencies(other_repo)):
                references.append(f"- Required by: {other_story.title} (#{other_story.id}) in {other_repo} repository")
        
        if references:
            reference_comment = "**Cross-Repository Dependencies:**\n\n" + "\n".join(references)
            self.github_service.add_comment_to_issue(story.id, reference_comment)

    async def gather_feedback_and_iterate(self, story_id: int, roles_providing_feedback: List[str]) -> Optional[UserStory]:
        logger.info(f"Gathering feedback for story #{story_id} from roles: {roles_providing_feedback}")
        
        github_issue = self.github_service.get_issue(story_id)
        if not github_issue:
            logger.error(f"Story #{story_id} not found on GitHub.")
            return None

        current_story_repr = UserStory(
            id=github_issue.number,
            title=github_issue.title,
            body=github_issue.body or "",
            status=github_issue.state, # "open" or "closed"
            github_url=github_issue.html_url,
            # roles_involved can be inferred from labels or passed if known
        )
        # Load existing comments into feedback_log
        existing_comments = self.github_service.get_issue_comments(story_id)
        for comment in existing_comments:
            current_story_repr.feedback_log.append({
                "role": comment.user.login, # Using GitHub username as role placeholder
                "comment": comment.body
            })
        
        # Simulate Feedback Generation using LLM for each role
        generated_feedback_texts = []
        for role in roles_providing_feedback:
            feedback_prompt = (
                f"You are the {role}. Review the following user story and provide your specific feedback, "
                f"concerns, potential edge cases, and any suggestions for improvement from your perspective.\n\n"
                f"User Story Title: {github_issue.title}\n"
                f"User Story Body:\n{github_issue.body}\n\n"
                f"Focus on aspects relevant to your role. Be concise and actionable."
            )
            try:
                # If using GitHub Models with repository-based prompts
                if self.use_repository_prompts:
                    # Get role-specific documentation paths
                    role_docs = self._get_role_documentation_paths([role])
                    logger.info(f"Using repository-based prompt for {role} with docs: {role_docs}")
                    feedback_comment_text = await self.llm_service.query_llm(
                        feedback_prompt, 
                        repository_references=role_docs
                    )
                else:
                    feedback_comment_text = await self.llm_service.query_llm(feedback_prompt)
                    
                if feedback_comment_text:
                    comment_body = f"**AI-Generated Feedback from Perspective of {role}**:\n\n{feedback_comment_text}"
                    self.github_service.add_comment_to_issue(story_id, comment_body)
                    current_story_repr.feedback_log.append({"role": f"{role} (AI)", "comment": feedback_comment_text})
                    generated_feedback_texts.append(f"Feedback from {role} (AI):\n{feedback_comment_text}")
                else:
                    logger.warning(f"LLM returned no feedback for role {role} on story {story_id}")
            except Exception as e:
                logger.error(f"Error generating LLM feedback for role {role} on story {story_id}: {e}")

        if not generated_feedback_texts and not existing_comments: # No feedback to process
            logger.info(f"No new or existing feedback to process for story #{story_id}.")
            current_story_repr.status = "pending_human_review" # Or keep as is
            # Potentially update labels on GitHub if status changes meaningfully
            # self.github_service.update_issue(story_id, labels=["user_story", "pending_human_review"])
            return current_story_repr

        # LLM Summarizes Feedback and Suggests Modifications
        all_feedback_str = "\n\n---\n\n".join(
            [f"Comment from {fb['role']}:\n{fb['comment']}" for fb in current_story_repr.feedback_log]
        )
        
        summary_prompt = (
            f"You are a Sprint Master / Lead Facilitator. The following user story has received feedback from various roles.\n\n"
            f"Original User Story Title: {github_issue.title}\n"
            f"Original User Story Body:\n{github_issue.body}\n\n"
            f"Collected Feedback:\n{all_feedback_str}\n\n"
            f"Your tasks are to:\n"
            f"1. Briefly summarize the key positive and negative feedback points.\n"
            f"2. Identify any conflicting feedback or areas requiring clarification.\n"
            f"3. Suggest a revised user story (Title and Body) that attempts to address the actionable feedback. If feedback is minimal or only positive, suggest keeping it as is or with minor enhancements.\n"
            f"4. If significant clarification is needed, formulate 1-2 key questions to ask the team.\n\n"
            f"Present your output clearly, with sections for Summary, Conflicts/Clarifications, Suggested Revision (Title and Body), and Questions for Team (if any)."
        )

        try:
            # If using GitHub Models with repository-based prompts
            if self.use_repository_prompts:
                # Get role documentation for a lead facilitator role
                role_docs = ["AI.md", "docs/ai/roles/ProductOwner.md"]
                logger.info(f"Using repository-based prompt for feedback summary with docs: {role_docs}")
                llm_summary_and_suggestions = await self.llm_service.query_llm(
                    summary_prompt, 
                    repository_references=role_docs
                )
            else:
                llm_summary_and_suggestions = await self.llm_service.query_llm(summary_prompt)
                
            if llm_summary_and_suggestions:
                # Post LLM's summary and suggestions as a comment for human review
                self.github_service.add_comment_to_issue(
                    story_id,
                    f"**AI Suggested Iteration and Feedback Summary**:\n\n{llm_summary_and_suggestions}"
                )
                current_story_repr.status = "pending_review" # Or "needs_iteration_review"
                # Update labels on GitHub to reflect this status
                self.github_service.update_issue(story_id, labels=["user_story", "pending_review", "ai_suggestions_added"])
                logger.info(f"Posted LLM summary and suggestions for story #{story_id}.")
            else:
                logger.warning(f"LLM returned no summary/suggestions for story {story_id}")
        except Exception as e:
            logger.error(f"Error processing LLM summary/suggestions for story {story_id}: {e}")

        return current_story_repr

    def get_story_details(self, story_id: int) -> Optional[UserStory]:
        logger.info(f"Fetching details for story #{story_id}")
        github_issue = self.github_service.get_issue(story_id)
        if not github_issue:
            logger.warning(f"Story #{story_id} not found on GitHub.")
            return None

        comments = self.github_service.get_issue_comments(story_id)
        feedback_log = [{"role": comment.user.login, "comment": comment.body} for comment in comments]
        
        # Infer roles_involved from labels if possible (simple example)
        roles_involved = []
        if github_issue.labels:
            for label in github_issue.labels:
                if label.name.startswith("role:"):
                    roles_involved.append(label.name.split(":",1)[1].capitalize())
        
        user_story = UserStory(
            id=github_issue.number,
            title=github_issue.title,
            body=github_issue.body or "",
            status=github_issue.state, # "open" or "closed" - can be more granular based on labels
            roles_involved=roles_involved,
            feedback_log=feedback_log,
            github_url=github_issue.html_url
        )
        logger.info(f"Successfully retrieved details for story #{user_story.id}")
        return user_story

    async def check_agreement(self, story_id: int, participating_roles: List[str]) -> bool:
        logger.info(f"Checking agreement for story #{story_id} among roles: {participating_roles}")
        comments = self.github_service.get_issue_comments(story_id)
        if not comments:
            logger.info(f"No comments found for story #{story_id}. Agreement cannot be determined.")
            return False

        # Combine comments into a single text for LLM analysis
        # Consider filtering for comments from specific users if roles can be mapped to users
        formatted_comments = "\n\n---\n\n".join(
            [f"Comment from {comment.user.login} (posted at {comment.created_at}):\n{comment.body}" for comment in comments]
        )

        # Basic check: if no participating_roles, agreement is vacuously true or false based on policy
        if not participating_roles:
            logger.warning("No participating roles provided for agreement check. Returning False.")
            return False

        agreement_prompt = (
            f"Review the following comments for user story #{story_id}. The story involves these roles: {', '.join(participating_roles)}.\n"
            f"Determine if the comments indicate that all explicitly mentioned participating roles have expressed agreement, approval, or satisfaction with the current state of the user story. "
            f"Look for phrases like 'approved', 'agreed', 'looks good', 'LGTM', 'ready for implementation', or similar positive affirmations from each role.\n"
            f"If a role has raised concerns or asked for further changes recently, they have not agreed.\n"
            f"Consider recent comments more heavily than older ones if there's a sequence of discussion.\n"
            f"Based *only* on the provided comments, respond with a single word: YES or NO.\n\n"
            f"Comments:\n{formatted_comments}"
        )

        try:
            # If using GitHub Models with repository-based prompts
            if self.use_repository_prompts:
                # Use general context for agreement checking
                role_docs = ["AI.md"]
                logger.info(f"Using repository-based prompt for agreement check with docs: {role_docs}")
                agreement_response = await self.llm_service.query_llm(
                    agreement_prompt, 
                    repository_references=role_docs
                )
            else:
                agreement_response = await self.llm_service.query_llm(agreement_prompt)
                
            logger.info(f"Agreement check response for story #{story_id}: {agreement_response}")
            # Look for a clear YES in the response, be strict
            agreement = 'yes' in agreement_response.lower() and len(agreement_response.strip()) < 10
            if agreement:
                logger.info(f"Agreement detected for story #{story_id} among roles {participating_roles}")
            else:
                logger.info(f"No clear agreement for story #{story_id} among roles {participating_roles}")
            return agreement
        except Exception as e:
            logger.error(f"Error checking agreement for story {story_id}: {e}")
            # In case of error, assume no agreement
            return False

    async def finalize_story_with_iterations(self, story_id: int, preserve_original: bool, dry_run: bool, format_type: str) -> Optional[Dict[str, Any]]:
        """
        Analyzes iteration history and creates a comprehensive finalized story.
        
        Args:
            story_id: GitHub issue number
            preserve_original: Whether to preserve original story in collapsible section
            dry_run: If True, returns content without updating GitHub
            format_type: Output format ('structured', 'detailed', 'markdown')
            
        Returns:
            Dict with 'content' and 'story' keys, or None if failed
        """
        logger.info(f"Finalizing story #{story_id} with iterations analysis")
        
        # Get the current issue
        github_issue = self.github_service.get_issue(story_id)
        if not github_issue:
            logger.error(f"Story #{story_id} not found on GitHub.")
            return None
        
        # Get all comments (feedback iterations)
        comments = self.github_service.get_issue_comments(story_id)
        
        # Extract iteration history from AI-generated comments
        iteration_history = []
        for comment in comments:
            comment_body = comment.body or ""
            # Look for AI-generated feedback and iteration comments
            if any(keyword in comment_body for keyword in [
                'AI-Generated Feedback', 'Iteration Analysis', 'Role Feedback', 
                'AI Suggested Iteration', 'Feedback Summary'
            ]):
                iteration_history.append({
                    'author': comment.user.login,
                    'created_at': comment.created_at,
                    'body': comment_body
                })
        
        if not iteration_history:
            logger.warning(f"No iteration history found for story #{story_id}")
            # Still allow finalization with just the original content
        
        logger.info(f"Found {len(iteration_history)} iterations to analyze")
        
        # Create comprehensive summary prompt
        iteration_text = "\n\n".join([
            f"--- Iteration {i+1} ({item['created_at'].strftime('%Y-%m-%d %H:%M UTC')}) ---\n{item['body']}" 
            for i, item in enumerate(iteration_history)
        ]) if iteration_history else "No iterations found."
        
        summary_prompt = f"""
        Analyze the following user story and its iteration history to create a comprehensive, finalized story.
        
        **Original Story:**
        Title: {github_issue.title}
        Body: {github_issue.body or "No description provided"}
        
        **Iteration History:**
        {iteration_text}
        
        Please provide a structured analysis with the following sections:
        
        ## Executive Summary
        Provide a high-level overview of what was refined and the key insights gained.
        
        ## Product Owner Perspective
        Focus on:
        - Business value and user needs
        - Acceptance criteria refinements
        - Priority and scope considerations
        - Market/user feedback integration
        
        ## Developer Perspective
        Focus on:
        - Technical feasibility and implementation approach
        - Dependencies and technical constraints
        - Architecture and design considerations
        - Effort estimation insights
        
        ## QA Perspective
        Focus on:
        - Testing scenarios and edge cases
        - Quality criteria and definition of done
        - Risk assessment and mitigation
        - User acceptance testing considerations
        
        ## Finalized User Story
        Provide a complete, actionable user story incorporating all feedback:
        - Clear user type, action, and benefit
        - Comprehensive acceptance criteria
        - Well-defined scope and boundaries
        
        ## Key Evolution
        Summarize what changed from the original story and why.
        
        ## Outstanding Questions
        List any unresolved items that need stakeholder input.
        
        Format this as clear, structured markdown suitable for a GitHub issue.
        """
        
        logger.info("Generating comprehensive story analysis...")
        try:
            summary_response = await self.llm_service.query_llm(summary_prompt, model="gpt-4o")
        except Exception as e:
            logger.error(f"Error generating story summary: {e}")
            return None
        
        if not summary_response:
            logger.error("LLM returned empty response for story finalization")
            return None
        
        # Format the content based on requested format
        if format_type == 'structured':
            updated_content = self._format_structured_story(
                github_issue.title, summary_response, github_issue.body, iteration_history, preserve_original
            )
        elif format_type == 'detailed':
            updated_content = self._format_detailed_story(
                github_issue.title, summary_response, github_issue.body, iteration_history
            )
        else:  # markdown
            updated_content = summary_response
        
        if dry_run:
            return {
                'content': updated_content,
                'story': None
            }
        
        # Update the issue
        logger.info(f"Updating issue #{story_id} with finalized story...")
        try:
            updated_issue = self.github_service.update_issue(story_id, title=github_issue.title, body=updated_content)
            if not updated_issue:
                logger.error(f"Failed to update issue #{story_id}")
                return None
            
            # Add finalization labels
            self.github_service.add_label_to_issue(story_id, "story/finalized")
            self.github_service.add_label_to_issue(story_id, "needs/user-approval")
            
            # Remove iteration-related labels and old state labels
            current_labels = [label.name for label in github_issue.labels]
            labels_to_remove = []
            for label in ['story/enriching', 'story/reviewing', 'story/consensus', 'story/ready']:
                if label in current_labels:
                    labels_to_remove.append(label)
            
            for label in current_labels:
                if label.startswith('iteration/') or label.startswith('consensus/'):
                    labels_to_remove.append(label)
            
            # Remove old labels
            for label in labels_to_remove:
                self.github_service.remove_label_from_issue(story_id, label)
            
            # Add a comment indicating finalization
            finalization_comment = (
                "🎯 **Story Finalized with Iteration Analysis**\n\n"
                f"This story has been analyzed and finalized based on {len(iteration_history)} iteration(s). "
                "The story content has been updated with comprehensive insights from multiple perspectives.\n\n"
                "**Next Steps:**\n"
                "- ✅ Review the finalized story content above\n"
                "- 👍 Add the `approved/user` label if you approve the finalized version\n"
                "- 🔄 The story will automatically transition to ready for development upon approval\n\n"
                f"**Format:** {format_type} | **Original Preserved:** {'Yes' if preserve_original else 'No'}"
            )
            self.github_service.add_comment_to_issue(story_id, finalization_comment)
            
            # Create updated UserStory representation
            finalized_story = UserStory(
                id=updated_issue.number,
                title=updated_issue.title,
                body=updated_issue.body or "",
                status="finalized_pending_approval",
                github_url=updated_issue.html_url
            )
            
            logger.info(f"Successfully finalized story #{story_id}")
            return {
                'content': updated_content,
                'story': finalized_story
            }
            
        except Exception as e:
            logger.error(f"Error updating issue #{story_id}: {e}")
            return None
    
    def _format_structured_story(self, title: str, analysis: str, original_body: str, iterations: List[Dict], preserve_original: bool) -> str:
        """Format story in structured format with preserved original"""
        content = f"# {title}\n\n{analysis}\n\n---\n\n"
        
        if preserve_original:
            content += f"""<details>
<summary>📋 Original Story (Click to expand)</summary>

**Original Description:**
{original_body or "No original description provided"}

**Iteration Summary:**
- **Total Iterations:** {len(iterations)}
- **Last Updated:** {iterations[-1]['created_at'].strftime('%Y-%m-%d %H:%M UTC') if iterations else 'N/A'}
- **AI Processing:** Complete

</details>"""
        
        return content
    
    def _format_detailed_story(self, title: str, analysis: str, original_body: str, iterations: List[Dict]) -> str:
        """Format story with detailed iteration history"""
        content = f"# {title}\n\n{analysis}\n\n---\n\n## 🔄 Complete Iteration History\n\n"
        
        if iterations:
            for i, iteration in enumerate(iterations):
                content += f"### Iteration {i+1} - {iteration['created_at'].strftime('%Y-%m-%d %H:%M UTC')}\n"
                content += f"**Author:** {iteration['author']}\n\n"
                content += f"{iteration['body']}\n\n---\n\n"
        else:
            content += "No iterations recorded.\n\n"
        
        content += f"""## 📋 Original Story

**Original Description:**
{original_body or "No original description provided"}
"""
        
        return content


if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv
    from ..ai_core.llm_handler import LLMService # Relative import for testing
    from ..ai_core.github_handler import GitHubService # Relative import for testing
    
    # Load .env file from project root
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        print(f"Loaded .env file from: {dotenv_path}")
    else:
        # Fallback for running from project root
        load_dotenv()
        print(f"Attempted to load .env from default location.")

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    async def test_story_orchestrator():
        logger.info("--- Starting StoryOrchestrator Test ---")
        
        # Ensure necessary env vars are set
        if not os.getenv("GITHUB_TOKEN") or not os.getenv("GITHUB_REPOSITORY") or \
           (not os.getenv("OPENAI_API_KEY") and os.getenv("DEFAULT_LLM_PROVIDER", "openai") == "openai"):
            logger.error("Missing one or more required environment variables for testing: "
                         "GITHUB_TOKEN, GITHUB_REPOSITORY, OPENAI_API_KEY (if using OpenAI).")
            return

        try:
            llm_service = LLMService() # Uses config from .env
            github_service = GitHubService() # Uses config from .env
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
                target_repo_info=repo_name 
            )

            if not new_story or not new_story.id:
                logger.error("Failed to create new story. Aborting further tests.")
                return
            
            logger.info(f"Successfully created story: ID={new_story.id}, Title='{new_story.title}', URL: {new_story.github_url}")
            story_id_for_test = new_story.id

            # 2. Get story details
            logger.info(f"\n--- Test 2: Get Story Details for Story #{story_id_for_test} ---")
            story_details = orchestrator.get_story_details(story_id_for_test)
            if story_details:
                logger.info(f"Retrieved details: ID={story_details.id}, Title='{story_details.title}', Status='{story_details.status}'")
                logger.info(f"Body: {story_details.body[:100]}...")
                logger.info(f"Roles involved from labels: {story_details.roles_involved}")
            else:
                logger.error(f"Failed to retrieve details for story #{story_id_for_test}.")
                # Clean up created issue before exiting if retrieval failed
                logger.info(f"Attempting to close issue #{story_id_for_test} due to error...")
                github_service.update_issue(story_id_for_test, state="closed", body=f"{new_story.body}\n\n---\nClosed due to test error.")
                return


            # 3. Gather feedback and iterate
            # For testing, roles_providing_feedback might be a subset or same as roles_to_consult
            roles_for_feedback_simulation = ["Data Analyst", "UX Designer"] 
            logger.info(f"\n--- Test 3: Gather Feedback & Iterate for Story #{story_id_for_test} (Simulating: {roles_for_feedback_simulation}) ---")
            iterated_story = await orchestrator.gather_feedback_and_iterate(story_id_for_test, roles_for_feedback_simulation)
            if iterated_story:
                logger.info(f"Iteration process completed for story #{iterated_story.id}. Status: {iterated_story.status}")
                logger.info(f"Check GitHub issue for AI-generated feedback and summary: {iterated_story.github_url}")
            else:
                logger.error(f"Failed to gather feedback/iterate for story #{story_id_for_test}.")
                # Attempt cleanup
                logger.info(f"Attempting to close issue #{story_id_for_test} due to error...")
                github_service.update_issue(story_id_for_test, state="closed", body=f"{new_story.body}\n\n---\nClosed due to test error.")
                return

            # 4. Check for agreement (this is likely to be False initially)
            logger.info(f"\n--- Test 4: Check Agreement for Story #{story_id_for_test} (Roles: {roles_for_story}) ---")
            # Add a slight delay for comments to be processed by GitHub if check_agreement is too fast
            await asyncio.sleep(5) # 5 seconds delay
            
            # Simulate adding a manual "approval" comment for one role to test LLM's interpretation
            # This would typically be a human action
            logger.info(f"Manually adding a test 'approval' comment from 'Product Owner' for story #{story_id_for_test}")
            github_service.add_comment_to_issue(story_id_for_test, "Product Owner: LGTM, approved for development!")
            await asyncio.sleep(2) # Short delay for comment to post

            agreement_reached = await orchestrator.check_agreement(story_id_for_test, roles_for_story)
            logger.info(f"Agreement check for story #{story_id_for_test} (expecting False or True based on LLM interpretation of AI + manual comments): {agreement_reached}")
            if agreement_reached:
                logger.info(f"LLM determined agreement was reached for story #{story_id_for_test}.")
                github_service.update_issue(story_id_for_test, labels=["user_story", "agreed", "ai_validated_agreement"])
            else:
                logger.info(f"LLM determined agreement was NOT reached for story #{story_id_for_test}.")


            # Clean up: Close the test issue
            logger.info(f"\n--- Test Cleanup: Closing Story #{story_id_for_test} ---")
            final_body_for_closure = orchestrator.get_story_details(story_id_for_test).body # Get latest body
            closed_issue = github_service.update_issue(story_id_for_test, state="closed", body=f"{final_body_for_closure}\n\n---\nTest completed and issue closed.")
            if closed_issue and closed_issue.state == "closed":
                logger.info(f"Successfully closed story #{story_id_for_test}.")
            else:
                logger.error(f"Failed to close story #{story_id_for_test} during cleanup.")

        except Exception as e:
            logger.error(f"An unexpected error occurred during StoryOrchestrator test: {e}", exc_info=True)
            # If an issue was created and its ID is known, try to close it
            if 'story_id_for_test' in locals() and story_id_for_test:
                 logger.warning(f"Attempting emergency cleanup of issue #{story_id_for_test} due to error: {e}")
                 try:
                     gh_service_cleanup = GitHubService() # New instance if previous failed
                     gh_service_cleanup.update_issue(story_id_for_test, state="closed", body=f"Issue closed due to test script error: {e}")
                     logger.info(f"Emergency closure of issue #{story_id_for_test} attempted.")
                 except Exception as cleanup_e:
                     logger.error(f"Failed emergency cleanup of issue #{story_id_for_test}: {cleanup_e}")


        logger.info("--- StoryOrchestrator Test Finished ---")

    if __name__ == "__main__":
        # This setup is for running the test script directly.
        # Ensure that Python can find the `ai` package.
        # If you are in the project root, run as `python -m ai.ai_core.story_manager`
        asyncio.run(test_story_orchestrator())
