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
from story_manager import StoryOrchestrator, UserStory  # UserStory for type hinting

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
):
    """
    Generates a new user story from an initial prompt, considering specified roles,
    and creates an issue on GitHub. Supports both single and multi-repository modes.
    If --use-repository-prompts is enabled, the LLM will use repository documentation (AI.md and role docs) as context.

    The simplified version creates complete, actionable stories directly without GitHub iteration.
    """
    from config import get_config

    config = get_config()

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
            orchestrator.create_complete_story(
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


# REMOVED: Complex iteration command - replaced with simplified local processing


# REMOVED: Complex agreement checking command - replaced with simplified local processing


@story_app.command(
    name="refactor",
    help="Creates immediate refactor tickets across repositories with relevant file context.",
)
def refactor_command(
    refactor_request: str = typer.Argument(
        ...,
        help="Description of the refactor needed (e.g., 'Extract authentication logic into a service')",
    ),
    repositories: Optional[List[str]] = typer.Option(
        None,
        "--repos",
        "-r",
        help="Comma-separated list of repository keys to target (default: all repositories).",
    ),
    include_files: Optional[List[str]] = typer.Option(
        None,
        "--files",
        "-f",
        help="Specific files to include in context (comma-separated paths).",
    ),
    refactor_type: str = typer.Option(
        "general",
        "--type",
        "-t",
        help="Type of refactor: general, extract, move, rename, optimize, modernize.",
    ),
    use_repository_prompts: bool = typer.Option(
        False,
        "--use-repository-prompts",
        help="Enable repository-based prompts for GitHub Models.",
    ),
):
    """
    Creates immediate refactor tickets across repositories with relevant file context.
    Unlike normal stories, refactor tickets skip the consensus workflow and are created immediately
    with context about relevant files and roles based on the refactor type.
    """
    from config import get_config

    config = get_config()

    if not config.is_multi_repository_mode():
        typer.secho(
            "Warning: Multi-repository mode is not enabled. Creating refactor in single repository mode.",
            fg=typer.colors.YELLOW,
        )

    orchestrator = _initialize_services()
    if use_repository_prompts:
        orchestrator.use_repository_prompts = True

    # Handle repository selection
    target_repos = repositories
    if isinstance(target_repos, str):
        target_repos = [repo.strip() for repo in target_repos.split(",")]

    # Validate repository keys for multi-repository mode
    if config.is_multi_repository_mode():
        available_repos = config.get_repository_list()
        if target_repos:
            invalid_repos = [
                repo for repo in target_repos if repo not in available_repos
            ]
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

    # Handle file inclusions
    specific_files = include_files
    if isinstance(specific_files, str):
        specific_files = [file.strip() for file in specific_files.split(",")]

    logger.info(f"Creating refactor tickets for: {refactor_request}")
    logger.info(f"Refactor type: {refactor_type}")
    logger.info(f"Target repositories: {target_repos or ['default']}")
    if specific_files:
        logger.info(f"Including specific files: {specific_files}")

    try:
        results = asyncio.run(
            orchestrator.create_refactor_tickets(
                refactor_request, refactor_type, target_repos, specific_files
            )
        )

        success_count = sum(1 for ticket in results.values() if ticket is not None)

        if success_count > 0:
            typer.secho(
                f"✅ Successfully created {success_count} refactor ticket(s)!",
                fg=typer.colors.GREEN,
            )
            typer.echo("")

            if config.is_multi_repository_mode() and target_repos:
                for repo_key, ticket in results.items():
                    if ticket:
                        repo_config = config.multi_repository_config.get_repository(
                            repo_key
                        )
                        typer.echo(
                            f"🔧 {repo_key} ({repo_config.name}): #{ticket.id} - {ticket.title}"
                        )
                        if ticket.github_url:
                            typer.echo(f"   🔗 {ticket.github_url}")
                    else:
                        typer.echo(f"❌ {repo_key}: Failed to create refactor ticket")
            else:
                # Single repository mode
                for ticket in results.values():
                    if ticket:
                        typer.echo(f"🔧 #{ticket.id} - {ticket.title}")
                        if ticket.github_url:
                            typer.echo(f"   🔗 {ticket.github_url}")
                        break
        else:
            typer.secho(
                "Failed to create any refactor tickets. Check logs for details.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

    except Exception as e:
        logger.error(f"Error during refactor ticket creation: {e}", exc_info=True)
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


# REMOVED: Complex finalization command - simplified approach creates ready stories directly


# REMOVED: Complex approval commands - simplified approach creates ready stories directly


# REMOVED: Complex workflow processor - simplified approach doesn't need extensive automation


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
