import asyncio
import logging
import typer
from typing import List, Optional

# Attempt to load .env file at the very beginning, before other modules might need it.
# This is especially important if config.py is not explicitly imported first by all modules.
from dotenv import load_dotenv
load_dotenv() # Loads .env from current directory or parent. If main.py is in ai/ai_core, .env should be in project root.
# For robustness, specify path if needed: load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


from ai_core.llm_handler import LLMService
from ai_core.github_handler import GitHubService
from ai_core.story_manager import StoryOrchestrator, UserStory # UserStory for type hinting

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create main app and command groups
app = typer.Typer(help="AI-powered backlog and sprint management tool.")

# Story Management Commands (primary user-facing commands)
story_app = typer.Typer(help="Story lifecycle management commands")
app.add_typer(story_app, name="story", help="Story lifecycle management")

# Workflow/Automation Commands (system/integration commands)
workflow_app = typer.Typer(help="Workflow automation and system commands")
app.add_typer(workflow_app, name="workflow", help="Workflow automation and system integration")

# Global variable to hold initialized services, to avoid re-initializing on every command
# if the CLI is run in a way that the Python process persists (e.g. a REPL, not typical for Typer CLI)
# For simple CLI calls, _initialize_services will be called each time, which is fine.
_orchestrator_instance: Optional[StoryOrchestrator] = None

def _initialize_services() -> StoryOrchestrator:
    global _orchestrator_instance
    # This simple CLI structure will re-initialize per command.
    # If this was a long-running service, we'd cache the instance.
    # For now, direct initialization is clear and works.
    try:
        logger.info("Initializing services...")
        llm_service = LLMService()  # Relies on config.py and .env
        github_service = GitHubService()  # Relies on config.py and .env
        orchestrator = StoryOrchestrator(llm_service, github_service)
        logger.info("Services initialized successfully.")
        _orchestrator_instance = orchestrator # Store if we wanted to reuse, not strictly necessary here
        return orchestrator
    except ValueError as ve:
        logger.error(f"Configuration error during service initialization: {ve}")
        typer.echo(f"Error: Configuration problem. {ve}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Unexpected error during service initialization: {e}", exc_info=True)
        typer.echo(f"Error: Could not initialize services. {e}", err=True)
        raise typer.Exit(code=1)

DEFAULT_ROLES_TO_CONSULT = ["Product Owner", "Lead Developer", "QA Engineer"]
DEFAULT_ROLES_FOR_FEEDBACK = ["Technical Lead", "UX Designer", "Product Owner"]


@story_app.command(name="create", help="Creates a new user story using AI and posts it to GitHub.")
def create_story_command(
    initial_prompt: str = typer.Argument(..., help="The initial idea or requirement for the user story."),
    roles_to_consult: Optional[List[str]] = typer.Option(
        None, "--roles", "-r", 
        help="Comma-separated list of roles to consult (e.g., ProductOwner,LeadDeveloper). Overrides default."
    ),
    target_repo_info: Optional[str] = typer.Option(None, "--repo-context", help="Optional context about the target repository for the LLM."),
    use_repository_prompts: bool = typer.Option(
        False, "--use-repository-prompts", help="Enable repository-based prompts for GitHub Models (uses AI.md and role docs as context)."
    )
):
    """
    Generates a new user story from an initial prompt, considering specified roles,
    and creates an issue on GitHub.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md and role docs) as context.
    """
    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True

    actual_roles = roles_to_consult if roles_to_consult else DEFAULT_ROLES_TO_CONSULT
    if isinstance(actual_roles, str): # If Typer passes a single string from comma-separated list
        actual_roles = [role.strip() for role in actual_roles.split(',')]
    elif actual_roles is None: # Ensure it's a list for the orchestrator
        actual_roles = DEFAULT_ROLES_TO_CONSULT


    logger.info(f"Executing create_story_command with prompt: '{initial_prompt}', roles: {actual_roles}")
    
    try:
        story = asyncio.run(orchestrator.create_new_story(initial_prompt, actual_roles, target_repo_info))
        if story and story.id:
            typer.secho(f"User story #{story.id} created successfully!", fg=typer.colors.GREEN)
            typer.echo(f"Title: {story.title}")
            typer.echo(f"URL: {story.github_url if story.github_url else 'N/A'}")
        else:
            typer.secho("Failed to create user story. Check logs for details.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error during story creation: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(name="get", help="Retrieves and displays details of a user story from GitHub.")
def get_story_command(
    story_id: int = typer.Argument(..., help="The GitHub issue number of the user story.")
):
    """
    Fetches and shows details for a specific user story, including its body, status,
    roles involved (derived from labels), and comments.
    """
    orchestrator = _initialize_services()
    logger.info(f"Executing get_story_command for story_id: {story_id}")

    try:
        story = orchestrator.get_story_details(story_id) # This is a synchronous method
        if story:
            typer.secho(f"Story #{story.id}: {story.title}", fg=typer.colors.CYAN)
            typer.echo(f"Status: {story.status}")
            typer.echo(f"URL: {story.github_url if story.github_url else 'N/A'}")
            typer.echo("\nBody:")
            typer.echo(story.body)
            typer.echo(f"\nRoles Involved (from labels): {', '.join(story.roles_involved) if story.roles_involved else 'N/A'}")
            
            typer.echo("\nFeedback Log:")
            if story.feedback_log:
                for feedback_item in story.feedback_log:
                    commenter = feedback_item.get('role', 'Unknown User')
                    comment_text = feedback_item.get('comment', '')
                    typer.echo(f"- {typer.style(commenter, fg=typer.colors.BLUE)}: {comment_text[:150].replace(chr(10), ' ')}...")
            else:
                typer.echo("  No feedback comments found.")
        else:
            typer.secho(f"Story with ID {story_id} not found.", fg=typer.colors.YELLOW)
    except Exception as e:
        logger.error(f"Error retrieving story {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(name="iterate", help="Simulates feedback gathering for a story and suggests iterations.")
def iterate_story_command(
    story_id: int = typer.Argument(..., help="The GitHub issue number to gather feedback for and iterate upon."),
    roles_for_feedback: Optional[List[str]] = typer.Option(
        None, "--roles", "-r",
        help="Comma-separated list of roles to simulate feedback from. Overrides default."
    ),
    use_repository_prompts: bool = typer.Option(
        False, "--use-repository-prompts", help="Enable repository-based prompts for GitHub Models (uses AI.md and role docs as context)."
    )
):
    """
    Triggers the AI to simulate feedback from specified roles for an existing user story.
    The AI will then summarize this feedback and suggest modifications, posting all as comments on GitHub.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md and role docs) as context.
    """
    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True
    
    actual_roles = roles_for_feedback if roles_for_feedback else DEFAULT_ROLES_FOR_FEEDBACK
    if isinstance(actual_roles, str): # If Typer passes a single string
        actual_roles = [role.strip() for role in actual_roles.split(',')]
    elif actual_roles is None:
        actual_roles = DEFAULT_ROLES_FOR_FEEDBACK


    logger.info(f"Executing iterate_story_command for story_id: {story_id}, roles: {actual_roles}")

    try:
        story = asyncio.run(orchestrator.gather_feedback_and_iterate(story_id, actual_roles))
        if story:
            typer.secho(f"Iteration process completed for story #{story.id}.", fg=typer.colors.GREEN)
            typer.echo("AI-generated feedback and suggestions have been posted as comments on GitHub.")
            typer.echo(f"URL: {story.github_url if story.github_url else 'N/A'}")
            typer.echo(f"Current story status on GitHub: {story.status}") # Status might be from GitHub issue state or labels
        else:
            typer.secho(f"Failed to iterate on story #{story_id}. It might not exist or an error occurred.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error during story iteration for {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(name="check-agreement", help="Uses AI to analyze comments and check if specified roles have agreed on a story.")
def check_agreement_command(
    story_id: int = typer.Argument(..., help="The GitHub issue number to check for agreement."),
    participating_roles: List[str] = typer.Option(
        ..., "--roles", "-r",
        help="Comma-separated list of essential roles that must agree (e.g., ProductOwner,LeadDeveloper)."
    ),
    use_repository_prompts: bool = typer.Option(
        False, "--use-repository-prompts", help="Enable repository-based prompts for GitHub Models (uses AI.md as context)."
    )
):
    """
    Analyzes GitHub comments for a user story to determine if key participating roles
    have expressed agreement or satisfaction.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md) as context.
    """
    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True

    actual_roles = participating_roles
    if isinstance(actual_roles, str): # Should be handled by Typer's List[str] but as a fallback
        actual_roles = [role.strip() for role in actual_roles.split(',')]
    if not actual_roles: # Typer should enforce ... for Option, but defensive check
        typer.secho("Error: At least one participating role must be specified with --roles.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    logger.info(f"Executing check_agreement_command for story_id: {story_id}, roles: {actual_roles}")

    try:
        has_agreed = asyncio.run(orchestrator.check_agreement(story_id, actual_roles))
        if has_agreed:
            typer.secho(f"AI analysis suggests that all specified roles ({', '.join(actual_roles)}) have agreed on story #{story_id}.", fg=typer.colors.GREEN)
        else:
            typer.secho(f"AI analysis suggests that agreement from all specified roles ({', '.join(actual_roles)}) on story #{story_id} has NOT yet been reached.", fg=typer.colors.YELLOW)
            typer.echo("Please review comments on GitHub for details.")
    except Exception as e:
        logger.error(f"Error during agreement check for {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(name="finalize", help="Summarizes iterations and finalizes a story.")
def finalize_story_command(
    story_id: int = typer.Argument(..., help="The GitHub issue number of the story to finalize."),
    preserve_original: bool = typer.Option(True, "--preserve-original/--no-preserve-original", help="Preserve original story in a collapsible section"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be updated without making changes"),
    format_type: str = typer.Option("structured", "--format", help="Output format: structured, detailed, or markdown"),
    use_repository_prompts: bool = typer.Option(
        False, "--use-repository-prompts", help="Enable repository-based prompts for GitHub Models (uses AI.md and role docs as context)."
    )
):
    """
    Summarizes iterations from PO/Developer/Tester perspectives and creates a finalized story.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md and role docs) as context.
    """
    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True
    logger.info(f"Executing finalize_story_command for story_id: {story_id}")
    
    if format_type not in ['structured', 'detailed', 'markdown']:
        typer.secho("Error: Format must be one of: structured, detailed, markdown", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    
    try:
        result = asyncio.run(orchestrator.finalize_story_with_iterations(
            story_id, preserve_original, dry_run, format_type
        ))
        
        if result:
            if dry_run:
                typer.secho("🔍 DRY RUN - Content that would be updated:", fg=typer.colors.CYAN)
                typer.echo("="*60)
                typer.echo(result.get('content', ''))
                typer.echo("="*60)
                typer.secho(f"ℹ️  Remove --dry-run to actually update issue #{story_id}", fg=typer.colors.BLUE)
            else:
                typer.secho(f"✅ Story #{story_id} has been finalized!", fg=typer.colors.GREEN)
                typer.secho(f"🏷️  Added labels: story/finalized, needs/user-approval", fg=typer.colors.BLUE)
                typer.secho(f"👤 The story now awaits your approval - add 'approved/user' label to proceed", fg=typer.colors.YELLOW)
                typer.secho(f"🔄 Once approved, the story will automatically return to 'story/ready' for development", fg=typer.colors.CYAN)
                
                story = result.get('story')
                if story and story.github_url:
                    typer.echo(f"URL: {story.github_url}")
        else:
            typer.secho(f"Failed to finalize story #{story_id}. Check logs for details.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
            
    except Exception as e:
        logger.error(f"Error finalizing story {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command(name="approve-story", help="Approve a finalized story for development.")
def approve_story_command(
    story_id: int = typer.Argument(..., help="The GitHub issue number of the story to approve."),
    auto_transition: bool = typer.Option(True, "--auto-transition/--no-auto-transition", help="Automatically transition to ready state after approval")
):
    """
    Approve a finalized story by adding the approved/user label.
    
    This command approves a story that has been finalized and is awaiting user approval.
    The story will automatically transition through the approval workflow.
    """
    orchestrator = _initialize_services()
    logger.info(f"Executing approve_story_command for story_id: {story_id}")
    
    try:
        # Get current story
        github_issue = orchestrator.github_service.get_issue(story_id)
        if not github_issue:
            typer.secho(f"Error: Story #{story_id} not found", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        
        current_labels = [label.name for label in github_issue.labels]
        
        # Check if story is in finalized state awaiting approval
        if 'story/finalized' not in current_labels:
            typer.secho(f"Error: Story #{story_id} is not in finalized state", fg=typer.colors.RED, err=True)
            typer.secho("Use 'finalize-story' command first to finalize the story", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)
        
        if 'needs/user-approval' not in current_labels:
            typer.secho(f"Error: Story #{story_id} is not awaiting user approval", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        
        if 'approved/user' in current_labels:
            typer.secho(f"Story #{story_id} is already approved", fg=typer.colors.YELLOW)
            return
        
        # Add approval label
        success = orchestrator.github_service.add_label_to_issue(story_id, "approved/user")
        if not success:
            typer.secho(f"Error: Failed to add approval label to story #{story_id}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        
        typer.secho(f"✅ Story #{story_id} has been approved!", fg=typer.colors.GREEN)
        typer.secho(f"🏷️  Added label: approved/user", fg=typer.colors.BLUE)
        
        if auto_transition:
            typer.secho(f"🔄 The story will automatically transition to ready state via workflow automation", fg=typer.colors.CYAN)
        
        # Add approval comment
        approval_comment = (
            "👍 **Story Approved by User**\n\n"
            "This finalized story has been approved and is ready to proceed to the development workflow. "
            "The automated workflow will handle the transition to the ready state."
        )
        orchestrator.github_service.add_comment_to_issue(story_id, approval_comment)
        
        if github_issue.html_url:
            typer.echo(f"URL: {github_issue.html_url}")
            
    except Exception as e:
        logger.error(f"Error approving story {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command(name="list-pending-approvals", help="List stories awaiting user approval.")
def list_pending_approvals_command(
    show_details: bool = typer.Option(False, "--details", help="Show detailed information for each story")
):
    """
    List all stories that are finalized and awaiting user approval.
    
    This command helps identify stories that need manual user approval to proceed
    through the development workflow.
    """
    orchestrator = _initialize_services()
    logger.info("Executing list_pending_approvals_command")
    
    try:
        # Search for issues with finalized and needs approval labels
        search_query = f"repo:{orchestrator.github_service.repository_name} is:issue is:open label:story/finalized label:needs/user-approval"
        
        try:
            # Use GitHub search API through PyGithub
            issues = orchestrator.github_service.github_client.search_issues(search_query)
            issue_list = list(issues)
        except Exception as e:
            logger.warning(f"GitHub search failed, falling back to manual filtering: {e}")
            # Fallback: get all open issues and filter manually
            repo = orchestrator.github_service.github_client.get_repo(orchestrator.github_service.repository_name)
            all_issues = repo.get_issues(state='open')
            issue_list = []
            for issue in all_issues:
                labels = [label.name for label in issue.labels]
                if 'story/finalized' in labels and 'needs/user-approval' in labels:
                    issue_list.append(issue)
        
        if not issue_list:
            typer.secho("📋 No stories are currently awaiting user approval", fg=typer.colors.GREEN)
            return
        
        typer.secho(f"📋 Found {len(issue_list)} story(s) awaiting user approval:", fg=typer.colors.BLUE)
        typer.echo("")
        
        for issue in issue_list:
            labels = [label.name for label in issue.labels]
            
            # Basic info
            typer.secho(f"#{issue.number}: {issue.title}", fg=typer.colors.WHITE, bold=True)
            typer.echo(f"  🔗 URL: {issue.html_url}")
            
            if show_details:
                # Show more details
                created_date = issue.created_at.strftime("%Y-%m-%d %H:%M UTC")
                updated_date = issue.updated_at.strftime("%Y-%m-%d %H:%M UTC")
                typer.echo(f"  📅 Created: {created_date}")
                typer.echo(f"  🔄 Updated: {updated_date}")
                
                # Show relevant labels
                relevant_labels = [l for l in labels if l.startswith(('story/', 'needs/', 'approved/', 'complexity/'))]
                if relevant_labels:
                    typer.echo(f"  🏷️  Labels: {', '.join(relevant_labels)}")
                
                # Show truncated body
                if issue.body:
                    body_preview = issue.body[:100] + "..." if len(issue.body) > 100 else issue.body
                    typer.echo(f"  📝 Preview: {body_preview}")
            
            typer.echo(f"  ✅ To approve: Add 'approved/user' label or run: python -m ai_core.main approve-story {issue.number}")
            typer.echo("")
        
        typer.secho(f"💡 Use --details flag for more information", fg=typer.colors.YELLOW)
        
    except Exception as e:
        logger.error(f"Error listing pending approvals: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command("workflow-processor")
def workflow_processor_command(
    issue_number: int = typer.Option(..., "--issue-number", help="GitHub issue number"),
    trigger_event: str = typer.Option(..., "--trigger-event", help="GitHub event that triggered the workflow"),
    action: Optional[str] = typer.Option(None, "--action", help="Action for the event"),
    current_labels: str = typer.Option("", "--current-labels", help="Comma-separated string of current issue labels"),
    comment_body: Optional[str] = typer.Option(None, "--comment-body", help="Body of the comment if trigger_event is 'issue_comment'"),
    actor: Optional[str] = typer.Option(None, "--actor", help="GitHub username of the actor who triggered the event"),
    log_level: str = typer.Option("INFO", "--log-level", help="Set the logging level")
):
    """Process GitHub issue events for story lifecycle automation."""
    import asyncio
    from ai_core.automation.workflow_processor import process_story_state
    
    # Set up logging
    effective_log_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=effective_log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Workflow Processor started via CLI. Args: Issue: {issue_number}, Event: {trigger_event}, "
                f"Action: {action}, Actor: {actor}, Labels: '{current_labels}', LogLevel: {log_level}")
    
    async def run_processor():
        try:
            orchestrator = _initialize_services()
            github_service = orchestrator.github_service
            llm_service = orchestrator.llm_service
            
            await process_story_state(
                issue_number=issue_number,
                trigger_event=trigger_event,
                action=action,
                current_labels_str=current_labels,
                comment_body=comment_body,
                actor=actor,
                github_service=github_service,
                llm_service=llm_service,
                story_orchestrator=orchestrator
            )
        except Exception as e:
            logger.error(f"[{issue_number}] Unhandled error in process_story_state: {e}", exc_info=True)
            raise typer.Exit(code=1)
    
    try:
        asyncio.run(run_processor())
        logger.info(f"Workflow Processor finished. Issue: {issue_number}, Event: {trigger_event}, Action: {action}")
    except Exception as e:
        logger.error(f"Workflow processor failed: {e}", exc_info=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    # This allows running the CLI:
    # python -m ai.ai_core.main create-story "My new feature" -r "Product Owner" -r "Engineer"
    # or if ai/ is in PYTHONPATH: python ai_core/main.py create-story ...
    
    # Note: The load_dotenv() at the top of the file is crucial.
    # If .env is in project root (e.g., /path/to/project/.env) and you run from /path/to/project:
    # `python -m ai.ai_core.main ...`
    # load_dotenv() should find it.
    # If you run `python ai/ai_core/main.py ...` (from project root), load_dotenv() also works.
    
    # Ensure that .env has GITHUB_TOKEN, GITHUB_REPOSITORY, and LLM configs (OPENAI_API_KEY or OLLAMA_API_HOST)
    logger.info("AI Story Management CLI starting up...")
    app()
