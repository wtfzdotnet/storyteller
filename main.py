import asyncio
import logging
from typing import List, Optional

import typer
# Attempt to load .env file at the very beginning, before other modules might need it.
# This is especially important if config.py is not explicitly imported first by all modules.
from dotenv import load_dotenv

load_dotenv()  # Loads .env from current directory or parent. If main.py is in ai/ai_core, .env should be in project root.
# For robustness, specify path if needed: load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


from github_handler import GitHubService
from llm_handler import LLMService
from story_manager import (StoryOrchestrator,  # UserStory for type hinting
                           UserStory)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create main app and command groups
app = typer.Typer(help="AI-powered backlog and sprint management tool.")

# Story Management Commands (primary user-facing commands)
story_app = typer.Typer(help="Story lifecycle management commands")
app.add_typer(story_app, name="story", help="Story lifecycle management")

# Workflow/Automation Commands (system/integration commands)
workflow_app = typer.Typer(help="Workflow automation and system commands")
app.add_typer(
    workflow_app, name="workflow", help="Workflow automation and system integration"
)

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
        _orchestrator_instance = (
            orchestrator  # Store if we wanted to reuse, not strictly necessary here
        )
        return orchestrator
    except ValueError as ve:
        logger.error(f"Configuration error during service initialization: {ve}")
        typer.echo(f"Error: Configuration problem. {ve}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(
            f"Unexpected error during service initialization: {e}", exc_info=True
        )
        typer.echo(f"Error: Could not initialize services. {e}", err=True)
        raise typer.Exit(code=1)


DEFAULT_ROLES_TO_CONSULT = ["Product Owner", "Lead Developer", "QA Engineer"]
DEFAULT_ROLES_FOR_FEEDBACK = ["Technical Lead", "UX Designer", "Product Owner"]


@story_app.command(name="config", help="Show current configuration status.")
def show_config_command():
    """
    Display current configuration including repository mode, available repositories,
    and configuration sources.
    """
    from config import get_config

    config = get_config()

    typer.secho("📋 Current Configuration:", fg=typer.colors.BLUE, bold=True)
    typer.echo("")

    # Basic configuration
    typer.echo(f"🔧 GitHub Token: {'✅ Set' if config.github_token else '❌ Not set'}")
    typer.echo(f"🤖 Default LLM Provider: {config.default_llm_provider}")
    typer.echo(f"📊 Log Level: {config.log_level}")
    typer.echo("")

    # Repository configuration
    if config.is_multi_repository_mode():
        typer.secho("🏢 Multi-Repository Mode: ✅ Enabled", fg=typer.colors.GREEN)
        typer.echo(f"📂 Configuration Source: {config.storyteller_config_path}")
        typer.echo(f"📁 Available Repositories: {len(config.get_repository_list())}")

        for key in config.get_repository_list():
            repo_config = config.multi_repository_config.get_repository(key)
            is_default = key == config.multi_repository_config.default_repository
            marker = "⭐" if is_default else "  "
            typer.echo(f"   {marker} {key}: {repo_config.name} ({repo_config.type})")

        if config.multi_repository_config.default_repository:
            typer.echo(
                f"🎯 Default Repository: {config.multi_repository_config.default_repository}"
            )
    else:
        typer.secho("🏢 Multi-Repository Mode: ❌ Disabled", fg=typer.colors.YELLOW)
        typer.echo(f"📁 Single Repository: {config.github_repository}")
        typer.echo("")
        typer.secho("💡 To enable multi-repository mode:", fg=typer.colors.CYAN)
        typer.echo(
            "   Create a .storyteller/config.json file with repository definitions"
        )
        typer.echo("   See .storyteller/README.md for configuration examples")


@story_app.command(
    name="list-repositories",
    help="List available repositories in multi-repository mode.",
)
def list_repositories_command():
    """
    List all available repositories configured in .storyteller/config.json.
    Shows repository types, descriptions, and dependencies.
    """
    from config import get_config

    config = get_config()

    if not config.is_multi_repository_mode():
        typer.secho("Multi-repository mode is not enabled.", fg=typer.colors.YELLOW)
        typer.echo(f"Current single repository: {config.github_repository}")
        typer.echo(
            "\nTo enable multi-repository mode, create a .storyteller/config.json file."
        )
        return

    typer.secho("📁 Available Repositories:", fg=typer.colors.BLUE, bold=True)
    typer.echo("")

    for key, repo_config in config.multi_repository_config.repositories.items():
        is_default = key == config.multi_repository_config.default_repository
        marker = "⭐ " if is_default else "   "

        typer.secho(f"{marker}{key}", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"   Repository: {repo_config.name}")
        typer.echo(f"   Type: {repo_config.type}")
        typer.echo(f"   Description: {repo_config.description}")

        if repo_config.dependencies:
            typer.echo(f"   Dependencies: {', '.join(repo_config.dependencies)}")
        else:
            typer.echo("   Dependencies: None")

        if repo_config.story_labels:
            typer.echo(f"   Default Labels: {', '.join(repo_config.story_labels)}")

        typer.echo("")

    if config.multi_repository_config.default_repository:
        typer.secho(
            f"⭐ Default repository: {config.multi_repository_config.default_repository}",
            fg=typer.colors.CYAN,
        )


@story_app.command(
    name="create-multi", help="Creates user stories across multiple repositories."
)
def create_multi_repository_stories_command(
    initial_prompt: str = typer.Argument(
        ..., help="The initial idea or requirement for the user stories."
    ),
    repositories: Optional[List[str]] = typer.Option(
        None,
        "--repos",
        "-r",
        help="Comma-separated list of repository keys to target (default: all repositories).",
    ),
    roles_to_consult: Optional[List[str]] = typer.Option(
        None,
        "--roles",
        help="Comma-separated list of roles to consult (default: standard roles).",
    ),
    use_repository_prompts: bool = typer.Option(
        False,
        "--use-repository-prompts",
        help="Enable repository-based prompts for GitHub Models.",
    ),
):
    """
    Creates user stories across multiple repositories with dependency awareness.
    Stories are created in dependency order (backend before frontend, etc.).
    Cross-repository references are automatically added to link related stories.
    """
    from config import get_config

    config = get_config()

    if not config.is_multi_repository_mode():
        typer.secho(
            "Error: Multi-repository mode is not enabled.",
            fg=typer.colors.RED,
            err=True,
        )
        typer.echo(
            "Create a .storyteller/config.json file to enable multi-repository mode."
        )
        raise typer.Exit(code=1)

    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True

    # Handle repository selection
    target_repos = repositories
    if isinstance(target_repos, str):
        target_repos = [repo.strip() for repo in target_repos.split(",")]

    # Validate repository keys
    available_repos = config.get_repository_list()
    if target_repos:
        invalid_repos = [repo for repo in target_repos if repo not in available_repos]
        if invalid_repos:
            typer.secho(
                f"Error: Unknown repositories: {', '.join(invalid_repos)}",
                fg=typer.colors.RED,
                err=True,
            )
            typer.echo(f"Available repositories: {', '.join(available_repos)}")
            raise typer.Exit(code=1)
    else:
        target_repos = available_repos

    # Handle roles
    actual_roles = roles_to_consult if roles_to_consult else DEFAULT_ROLES_TO_CONSULT
    if isinstance(actual_roles, str):
        actual_roles = [role.strip() for role in actual_roles.split(",")]

    logger.info(f"Creating multi-repository stories for repositories: {target_repos}")
    typer.echo(f"Creating stories across {len(target_repos)} repositories...")

    try:
        results = asyncio.run(
            orchestrator.create_multi_repository_stories(
                initial_prompt, actual_roles, target_repos
            )
        )

        success_count = sum(1 for story in results.values() if story is not None)

        if success_count > 0:
            typer.secho(
                f"✅ Successfully created {success_count}/{len(target_repos)} stories!",
                fg=typer.colors.GREEN,
            )
            typer.echo("")

            for repo_key, story in results.items():
                if story:
                    repo_config = config.multi_repository_config.get_repository(
                        repo_key
                    )
                    typer.echo(
                        f"📝 {repo_key} ({repo_config.name}): #{story.id} - {story.title}"
                    )
                    if story.github_url:
                        typer.echo(f"   🔗 {story.github_url}")
                else:
                    typer.echo(f"❌ {repo_key}: Failed to create story")
        else:
            typer.secho(
                "Failed to create any stories. Check logs for details.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

    except Exception as e:
        logger.error(
            f"Error during multi-repository story creation: {e}", exc_info=True
        )
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(
    name="create", help="Creates a new user story using AI and posts it to GitHub."
)
def create_story_command(
    initial_prompt: str = typer.Argument(
        ..., help="The initial idea or requirement for the user story."
    ),
    roles_to_consult: Optional[List[str]] = typer.Option(
        None,
        "--roles",
        "-r",
        help="Comma-separated list of roles to consult (e.g., ProductOwner,LeadDeveloper). Overrides default.",
    ),
    target_repo_info: Optional[str] = typer.Option(
        None,
        "--repo-context",
        help="Optional context about the target repository for the LLM.",
    ),
    repository: Optional[str] = typer.Option(
        None,
        "--repository",
        help="Target repository key (for multi-repository mode). Uses default if not specified.",
    ),
    use_repository_prompts: bool = typer.Option(
        False,
        "--use-repository-prompts",
        help="Enable repository-based prompts for GitHub Models (uses AI.md and role docs as context).",
    ),
    auto_consensus: bool = typer.Option(
        False,
        "--auto-consensus",
        help="Enable automatic consensus iteration without manual intervention.",
    ),
    consensus_threshold: Optional[int] = typer.Option(
        None,
        "--consensus-threshold",
        help="Consensus threshold percentage (1-100). Default: 70 for auto-consensus, 80 otherwise.",
    ),
    max_iterations: Optional[int] = typer.Option(
        None,
        "--max-iterations",
        help="Maximum iterations before stopping. Default: 10 for auto-consensus, 5 otherwise.",
    ),
):
    """
    Generates a new user story from an initial prompt, considering specified roles,
    and creates an issue on GitHub. Supports both single and multi-repository modes.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md and role docs) as context.
    """
    from config import get_config

    config = get_config()

    # Override config with command-line flags
    if auto_consensus:
        config.auto_consensus_enabled = True
    if consensus_threshold is not None:
        config.auto_consensus_threshold = consensus_threshold
    if max_iterations is not None:
        config.auto_consensus_max_iterations = max_iterations

    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True

    actual_roles = roles_to_consult if roles_to_consult else DEFAULT_ROLES_TO_CONSULT
    if isinstance(
        actual_roles, str
    ):  # If Typer passes a single string from comma-separated list
        actual_roles = [role.strip() for role in actual_roles.split(",")]
    elif actual_roles is None:  # Ensure it's a list for the orchestrator
        actual_roles = DEFAULT_ROLES_TO_CONSULT

    # Validate repository key for multi-repository mode
    if repository and config.is_multi_repository_mode():
        available_repos = config.get_repository_list()
        if repository not in available_repos:
            typer.secho(
                f"Error: Unknown repository '{repository}'",
                fg=typer.colors.RED,
                err=True,
            )
            typer.echo(f"Available repositories: {', '.join(available_repos)}")
            raise typer.Exit(code=1)

    logger.info(
        f"Executing create_story_command with prompt: '{initial_prompt}', roles: {actual_roles}"
    )
    if repository:
        logger.info(f"Target repository: {repository}")

    try:
        story = asyncio.run(
            orchestrator.create_new_story(
                initial_prompt, actual_roles, target_repo_info, repository
            )
        )
        if story and story.id:
            typer.secho(
                f"User story #{story.id} created successfully!", fg=typer.colors.GREEN
            )
            typer.echo(f"Title: {story.title}")
            typer.echo(f"URL: {story.github_url if story.github_url else 'N/A'}")

            if config.is_multi_repository_mode() and repository:
                repo_config = config.multi_repository_config.get_repository(repository)
                if repo_config:
                    typer.echo(f"Repository: {repo_config.name} ({repo_config.type})")
        else:
            typer.secho(
                "Failed to create user story. Check logs for details.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error during story creation: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(
    name="get", help="Retrieves and displays details of a user story from GitHub."
)
def get_story_command(
    story_id: int = typer.Argument(
        ..., help="The GitHub issue number of the user story."
    )
):
    """
    Fetches and shows details for a specific user story, including its body, status,
    roles involved (derived from labels), and comments.
    """
    orchestrator = _initialize_services()
    logger.info(f"Executing get_story_command for story_id: {story_id}")

    try:
        story = orchestrator.get_story_details(story_id)  # This is a synchronous method
        if story:
            typer.secho(f"Story #{story.id}: {story.title}", fg=typer.colors.CYAN)
            typer.echo(f"Status: {story.status}")
            typer.echo(f"URL: {story.github_url if story.github_url else 'N/A'}")
            typer.echo("\nBody:")
            typer.echo(story.body)
            typer.echo(
                f"\nRoles Involved (from labels): {', '.join(story.roles_involved) if story.roles_involved else 'N/A'}"
            )

            typer.echo("\nFeedback Log:")
            if story.feedback_log:
                for feedback_item in story.feedback_log:
                    commenter = feedback_item.get("role", "Unknown User")
                    comment_text = feedback_item.get("comment", "")
                    typer.echo(
                        f"- {typer.style(commenter, fg=typer.colors.BLUE)}: {comment_text[:150].replace(chr(10), ' ')}..."
                    )
            else:
                typer.echo("  No feedback comments found.")
        else:
            typer.secho(f"Story with ID {story_id} not found.", fg=typer.colors.YELLOW)
    except Exception as e:
        logger.error(f"Error retrieving story {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(
    name="iterate",
    help="Simulates feedback gathering for a story and suggests iterations.",
)
def iterate_story_command(
    story_id: int = typer.Argument(
        ..., help="The GitHub issue number to gather feedback for and iterate upon."
    ),
    roles_for_feedback: Optional[List[str]] = typer.Option(
        None,
        "--roles",
        "-r",
        help="Comma-separated list of roles to simulate feedback from. Overrides default.",
    ),
    use_repository_prompts: bool = typer.Option(
        False,
        "--use-repository-prompts",
        help="Enable repository-based prompts for GitHub Models (uses AI.md and role docs as context).",
    ),
    auto_consensus: bool = typer.Option(
        False,
        "--auto-consensus",
        help="Enable automatic consensus iteration without manual intervention.",
    ),
    consensus_threshold: Optional[int] = typer.Option(
        None,
        "--consensus-threshold",
        help="Consensus threshold percentage (1-100). Default: 70 for auto-consensus, 80 otherwise.",
    ),
    max_iterations: Optional[int] = typer.Option(
        None,
        "--max-iterations",
        help="Maximum iterations before stopping. Default: 10 for auto-consensus, 5 otherwise.",
    ),
):
    """
    Triggers the AI to simulate feedback from specified roles for an existing user story.
    The AI will then summarize this feedback and suggest modifications, posting all as comments on GitHub.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md and role docs) as context.
    """
    from config import get_config

    config = get_config()

    # Override config with command-line flags
    if auto_consensus:
        config.auto_consensus_enabled = True
    if consensus_threshold is not None:
        config.auto_consensus_threshold = consensus_threshold
    if max_iterations is not None:
        config.auto_consensus_max_iterations = max_iterations

    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True

    actual_roles = (
        roles_for_feedback if roles_for_feedback else DEFAULT_ROLES_FOR_FEEDBACK
    )
    if isinstance(actual_roles, str):  # If Typer passes a single string
        actual_roles = [role.strip() for role in actual_roles.split(",")]
    elif actual_roles is None:
        actual_roles = DEFAULT_ROLES_FOR_FEEDBACK

    logger.info(
        f"Executing iterate_story_command for story_id: {story_id}, roles: {actual_roles}"
    )

    try:
        story = asyncio.run(
            orchestrator.gather_feedback_and_iterate(story_id, actual_roles)
        )
        if story:
            typer.secho(
                f"Iteration process completed for story #{story.id}.",
                fg=typer.colors.GREEN,
            )
            typer.echo(
                "AI-generated feedback and suggestions have been posted as comments on GitHub."
            )
            typer.echo(f"URL: {story.github_url if story.github_url else 'N/A'}")
            typer.echo(
                f"Current story status on GitHub: {story.status}"
            )  # Status might be from GitHub issue state or labels
        else:
            typer.secho(
                f"Failed to iterate on story #{story_id}. It might not exist or an error occurred.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error during story iteration for {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(
    name="check-agreement",
    help="Uses AI to analyze comments and check if specified roles have agreed on a story.",
)
def check_agreement_command(
    story_id: int = typer.Argument(
        ..., help="The GitHub issue number to check for agreement."
    ),
    participating_roles: List[str] = typer.Option(
        ...,
        "--roles",
        "-r",
        help="Comma-separated list of essential roles that must agree (e.g., ProductOwner,LeadDeveloper).",
    ),
    use_repository_prompts: bool = typer.Option(
        False,
        "--use-repository-prompts",
        help="Enable repository-based prompts for GitHub Models (uses AI.md as context).",
    ),
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
    if isinstance(
        actual_roles, str
    ):  # Should be handled by Typer's List[str] but as a fallback
        actual_roles = [role.strip() for role in actual_roles.split(",")]
    if not actual_roles:  # Typer should enforce ... for Option, but defensive check
        typer.secho(
            "Error: At least one participating role must be specified with --roles.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    logger.info(
        f"Executing check_agreement_command for story_id: {story_id}, roles: {actual_roles}"
    )

    try:
        has_agreed = asyncio.run(orchestrator.check_agreement(story_id, actual_roles))
        if has_agreed:
            typer.secho(
                f"AI analysis suggests that all specified roles ({', '.join(actual_roles)}) have agreed on story #{story_id}.",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                f"AI analysis suggests that agreement from all specified roles ({', '.join(actual_roles)}) on story #{story_id} has NOT yet been reached.",
                fg=typer.colors.YELLOW,
            )
            typer.echo("Please review comments on GitHub for details.")
    except Exception as e:
        logger.error(f"Error during agreement check for {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@story_app.command(name="finalize", help="Summarizes iterations and finalizes a story.")
def finalize_story_command(
    story_id: int = typer.Argument(
        ..., help="The GitHub issue number of the story to finalize."
    ),
    preserve_original: bool = typer.Option(
        True,
        "--preserve-original/--no-preserve-original",
        help="Preserve original story in a collapsible section",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be updated without making changes"
    ),
    format_type: str = typer.Option(
        "structured",
        "--format",
        help="Output format: structured, detailed, or markdown",
    ),
    use_repository_prompts: bool = typer.Option(
        False,
        "--use-repository-prompts",
        help="Enable repository-based prompts for GitHub Models (uses AI.md and role docs as context).",
    ),
):
    """
    Summarizes iterations from PO/Developer/Tester perspectives and creates a finalized story.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md and role docs) as context.
    """
    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True
    logger.info(f"Executing finalize_story_command for story_id: {story_id}")

    if format_type not in ["structured", "detailed", "markdown"]:
        typer.secho(
            "Error: Format must be one of: structured, detailed, markdown",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        result = asyncio.run(
            orchestrator.finalize_story_with_iterations(
                story_id, preserve_original, dry_run, format_type
            )
        )

        if result:
            if dry_run:
                typer.secho(
                    "🔍 DRY RUN - Content that would be updated:", fg=typer.colors.CYAN
                )
                typer.echo("=" * 60)
                typer.echo(result.get("content", ""))
                typer.echo("=" * 60)
                typer.secho(
                    f"ℹ️  Remove --dry-run to actually update issue #{story_id}",
                    fg=typer.colors.BLUE,
                )
            else:
                typer.secho(
                    f"✅ Story #{story_id} has been finalized!", fg=typer.colors.GREEN
                )
                typer.secho(
                    f"🏷️  Added labels: story/finalized, needs/user-approval",
                    fg=typer.colors.BLUE,
                )
                typer.secho(
                    f"👤 The story now awaits your approval - add 'approved/user' label to proceed",
                    fg=typer.colors.YELLOW,
                )
                typer.secho(
                    f"🔄 Once approved, the story will automatically return to 'story/ready' for development",
                    fg=typer.colors.CYAN,
                )

                story = result.get("story")
                if story and story.github_url:
                    typer.echo(f"URL: {story.github_url}")
        else:
            typer.secho(
                f"Failed to finalize story #{story_id}. Check logs for details.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

    except Exception as e:
        logger.error(f"Error finalizing story {story_id}: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command(name="approve-story", help="Approve a finalized story for development.")
def approve_story_command(
    story_id: int = typer.Argument(
        ..., help="The GitHub issue number of the story to approve."
    ),
    auto_transition: bool = typer.Option(
        True,
        "--auto-transition/--no-auto-transition",
        help="Automatically transition to ready state after approval",
    ),
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
            typer.secho(
                f"Error: Story #{story_id} not found", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(code=1)

        current_labels = [label.name for label in github_issue.labels]

        # Check if story is in finalized state awaiting approval
        if "story/finalized" not in current_labels:
            typer.secho(
                f"Error: Story #{story_id} is not in finalized state",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Use 'finalize-story' command first to finalize the story",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(code=1)

        if "needs/user-approval" not in current_labels:
            typer.secho(
                f"Error: Story #{story_id} is not awaiting user approval",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        if "approved/user" in current_labels:
            typer.secho(
                f"Story #{story_id} is already approved", fg=typer.colors.YELLOW
            )
            return

        # Add approval label
        success = orchestrator.github_service.add_label_to_issue(
            story_id, "approved/user"
        )
        if not success:
            typer.secho(
                f"Error: Failed to add approval label to story #{story_id}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        typer.secho(f"✅ Story #{story_id} has been approved!", fg=typer.colors.GREEN)
        typer.secho(f"🏷️  Added label: approved/user", fg=typer.colors.BLUE)

        if auto_transition:
            typer.secho(
                f"🔄 The story will automatically transition to ready state via workflow automation",
                fg=typer.colors.CYAN,
            )

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
    show_details: bool = typer.Option(
        False, "--details", help="Show detailed information for each story"
    )
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
            issues = orchestrator.github_service.github_client.search_issues(
                search_query
            )
            issue_list = list(issues)
        except Exception as e:
            logger.warning(
                f"GitHub search failed, falling back to manual filtering: {e}"
            )
            # Fallback: get all open issues and filter manually
            repo = orchestrator.github_service.github_client.get_repo(
                orchestrator.github_service.repository_name
            )
            all_issues = repo.get_issues(state="open")
            issue_list = []
            for issue in all_issues:
                labels = [label.name for label in issue.labels]
                if "story/finalized" in labels and "needs/user-approval" in labels:
                    issue_list.append(issue)

        if not issue_list:
            typer.secho(
                "📋 No stories are currently awaiting user approval",
                fg=typer.colors.GREEN,
            )
            return

        typer.secho(
            f"📋 Found {len(issue_list)} story(s) awaiting user approval:",
            fg=typer.colors.BLUE,
        )
        typer.echo("")

        for issue in issue_list:
            labels = [label.name for label in issue.labels]

            # Basic info
            typer.secho(
                f"#{issue.number}: {issue.title}", fg=typer.colors.WHITE, bold=True
            )
            typer.echo(f"  🔗 URL: {issue.html_url}")

            if show_details:
                # Show more details
                created_date = issue.created_at.strftime("%Y-%m-%d %H:%M UTC")
                updated_date = issue.updated_at.strftime("%Y-%m-%d %H:%M UTC")
                typer.echo(f"  📅 Created: {created_date}")
                typer.echo(f"  🔄 Updated: {updated_date}")

                # Show relevant labels
                relevant_labels = [
                    l
                    for l in labels
                    if l.startswith(("story/", "needs/", "approved/", "complexity/"))
                ]
                if relevant_labels:
                    typer.echo(f"  🏷️  Labels: {', '.join(relevant_labels)}")

                # Show truncated body
                if issue.body:
                    body_preview = (
                        issue.body[:100] + "..."
                        if len(issue.body) > 100
                        else issue.body
                    )
                    typer.echo(f"  📝 Preview: {body_preview}")

            typer.echo(
                f"  ✅ To approve: Add 'approved/user' label or run: python -m ai_core.main approve-story {issue.number}"
            )
            typer.echo("")

        typer.secho(
            f"💡 Use --details flag for more information", fg=typer.colors.YELLOW
        )

    except Exception as e:
        logger.error(f"Error listing pending approvals: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command("workflow-processor")
def workflow_processor_command(
    issue_number: int = typer.Option(..., "--issue-number", help="GitHub issue number"),
    trigger_event: str = typer.Option(
        ..., "--trigger-event", help="GitHub event that triggered the workflow"
    ),
    action: Optional[str] = typer.Option(None, "--action", help="Action for the event"),
    current_labels: str = typer.Option(
        "", "--current-labels", help="Comma-separated string of current issue labels"
    ),
    comment_body: Optional[str] = typer.Option(
        None,
        "--comment-body",
        help="Body of the comment if trigger_event is 'issue_comment'",
    ),
    actor: Optional[str] = typer.Option(
        None, "--actor", help="GitHub username of the actor who triggered the event"
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Set the logging level"),
):
    """Process GitHub issue events for story lifecycle automation."""
    import asyncio

    from automation.workflow_processor import process_story_state

    # Set up logging
    effective_log_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=effective_log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info(
        f"Workflow Processor started via CLI. Args: Issue: {issue_number}, Event: {trigger_event}, "
        f"Action: {action}, Actor: {actor}, Labels: '{current_labels}', LogLevel: {log_level}"
    )

    async def run_processor():
        try:
            from config import get_config

            config = get_config()

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
                story_orchestrator=orchestrator,
                config=config,
            )
        except Exception as e:
            logger.error(
                f"[{issue_number}] Unhandled error in process_story_state: {e}",
                exc_info=True,
            )
            raise typer.Exit(code=1)

    try:
        asyncio.run(run_processor())
        logger.info(
            f"Workflow Processor finished. Issue: {issue_number}, Event: {trigger_event}, Action: {action}"
        )
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
