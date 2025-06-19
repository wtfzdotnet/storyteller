"""Main CLI interface for AI Story Management System."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

import typer
from src.storyteller.automation.workflow_processor import WorkflowProcessor
from src.storyteller.config import get_config
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

# Setup paths for imports
import setup_path

# Initialize CLI application
app = typer.Typer(
    name="storyteller",
    help="AI-Powered Story Management System for Recipe Authority Platform",
    rich_markup_mode="rich",
)

# Initialize console for rich output
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.getLogger().setLevel(level)

    # Suppress verbose logging from external libraries
    logging.getLogger("github").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


# Story management commands
story_app = typer.Typer(help="Story creation and management commands")
app.add_typer(story_app, name="story")


@story_app.command("create")
def create_story(
    content: str = typer.Argument(..., help="Story content to process"),
    repository: Optional[str] = typer.Option(
        None, "--repository", "-r", help="Target repository"
    ),
    roles: Optional[List[str]] = typer.Option(
        None, "--roles", help="Specific expert roles to use"
    ),
    context_file: Optional[Path] = typer.Option(
        None, "--context", help="JSON file with additional context"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Create a new user story with expert analysis."""

    setup_logging(debug)

    async def _create_story():
        try:
            config = get_config()
            processor = WorkflowProcessor(config)

            # Load additional context if provided
            context = None
            if context_file and context_file.exists():
                import json

                with open(context_file) as f:
                    context = json.load(f)

            # Show progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Processing story with expert analysis...", total=None
                )

                result = await processor.create_story_workflow(
                    content=content, repository=repository, roles=roles, context=context
                )

                progress.update(task, completed=True)

            if result.success:
                console.print("[green]✓[/green] Story created successfully!")

                # Display results
                data = result.data
                console.print(f"\n[bold]Story ID:[/bold] {data['story_id']}")
                console.print(
                    f"[bold]Expert Analyses:[/bold] {data['expert_analyses_count']}"
                )
                console.print(
                    f"[bold]Target Repositories:[/bold] {', '.join(data['target_repositories'])}"
                )

                if data.get("github_issues"):
                    console.print("\n[bold]Created GitHub Issues:[/bold]")
                    table = Table()
                    table.add_column("Repository")
                    table.add_column("Issue #")
                    table.add_column("URL")

                    for issue in data["github_issues"]:
                        table.add_row(
                            issue["repository"], str(issue["number"]), issue["url"]
                        )

                    console.print(table)
            else:
                console.print(f"[red]✗[/red] {result.message}")
                if result.error:
                    console.print(f"[red]Error:[/red] {result.error}")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]✗ Failed to create story:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_create_story())


@story_app.command("create-multi")
def create_multi_repository_story(
    content: str = typer.Argument(..., help="Story content to process"),
    repos: str = typer.Option(
        ..., "--repos", help="Comma-separated list of target repositories"
    ),
    roles: Optional[List[str]] = typer.Option(
        None, "--roles", help="Specific expert roles to use"
    ),
    context_file: Optional[Path] = typer.Option(
        None, "--context", help="JSON file with additional context"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Create a user story across multiple repositories."""

    setup_logging(debug)

    async def _create_multi_story():
        try:
            config = get_config()
            processor = WorkflowProcessor(config)

            # Parse repository list
            repository_list = [repo.strip() for repo in repos.split(",")]

            # Load additional context if provided
            context = None
            if context_file and context_file.exists():
                import json

                with open(context_file) as f:
                    context = json.load(f)

            # Show progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Creating multi-repository story...", total=None
                )

                result = await processor.create_multi_repository_story(
                    content=content,
                    repositories=repository_list,
                    roles=roles,
                    context=context,
                )

                progress.update(task, completed=True)

            if result.success:
                console.print(
                    "[green]✓[/green] Multi-repository story created successfully!"
                )

                # Display results
                data = result.data
                console.print(f"\n[bold]Story ID:[/bold] {data['story_id']}")
                console.print(
                    f"[bold]Target Repositories:[/bold] {', '.join(data['target_repositories'])}"
                )

                if data.get("github_issues"):
                    console.print(
                        f"\n[bold]Created {len(data['github_issues'])} GitHub Issues:[/bold]"
                    )
                    table = Table()
                    table.add_column("Repository")
                    table.add_column("Issue #")
                    table.add_column("URL")

                    for issue in data["github_issues"]:
                        table.add_row(
                            issue["repository"], str(issue["number"]), issue["url"]
                        )

                    console.print(table)
            else:
                console.print(f"[red]✗[/red] {result.message}")
                if result.error:
                    console.print(f"[red]Error:[/red] {result.error}")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]✗ Failed to create multi-repository story:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_create_multi_story())


@story_app.command("analyze")
def analyze_story(
    content: str = typer.Argument(..., help="Story content to analyze"),
    roles: Optional[List[str]] = typer.Option(
        None, "--roles", help="Specific expert roles to use"
    ),
    context_file: Optional[Path] = typer.Option(
        None, "--context", help="JSON file with additional context"
    ),
    show_full: bool = typer.Option(False, "--full", help="Show full analysis details"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Analyze a story without creating GitHub issues."""

    setup_logging(debug)

    async def _analyze_story():
        try:
            config = get_config()
            processor = WorkflowProcessor(config)

            # Load additional context if provided
            context = None
            if context_file and context_file.exists():
                import json

                with open(context_file) as f:
                    context = json.load(f)

            # Show progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Analyzing story with expert roles...", total=None
                )

                result = await processor.analyze_story_workflow(
                    content=content, roles=roles, context=context
                )

                progress.update(task, completed=True)

            if result.success:
                console.print("[green]✓[/green] Story analysis completed!")

                data = result.data
                console.print(f"\n[bold]Story ID:[/bold] {data['story_id']}")
                console.print(
                    f"[bold]Expert Analyses:[/bold] {len(data['expert_analyses'])}"
                )
                console.print(
                    f"[bold]Target Repositories:[/bold] {', '.join(data['target_repositories'])}"
                )

                # Show expert analyses summary
                console.print("\n[bold]Expert Analysis Summary:[/bold]")
                for analysis in data["expert_analyses"]:
                    console.print(f"\n[blue]● {analysis['role']}[/blue]")
                    if analysis.get("recommendations"):
                        console.print("  [green]Recommendations:[/green]")
                        for rec in analysis["recommendations"][:3]:  # Show first 3
                            console.print(f"    • {rec}")
                    if analysis.get("concerns"):
                        console.print("  [yellow]Concerns:[/yellow]")
                        for concern in analysis["concerns"][:3]:  # Show first 3
                            console.print(f"    • {concern}")

                # Show synthesized analysis
                if show_full and data.get("synthesized_analysis"):
                    console.print("\n[bold]Synthesized Analysis:[/bold]")
                    panel = Panel(
                        data["synthesized_analysis"],
                        title="Complete Analysis",
                        border_style="blue",
                    )
                    console.print(panel)
            else:
                console.print(f"[red]✗[/red] {result.message}")
                if result.error:
                    console.print(f"[red]Error:[/red] {result.error}")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]✗ Failed to analyze story:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_analyze_story())


@story_app.command("status")
def get_story_status(
    story_id: str = typer.Argument(..., help="Story ID to check"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Get the status of a story."""

    setup_logging(debug)

    try:
        config = get_config()
        processor = WorkflowProcessor(config)

        result = processor.get_story_status_workflow(story_id)

        if result.success:
            data = result.data
            console.print(f"[green]✓[/green] Story found: {story_id}")

            table = Table(title=f"Story Status: {story_id}")
            table.add_column("Property")
            table.add_column("Value")

            table.add_row("Status", data["status"])
            table.add_row("Created", data["created_at"])
            table.add_row("Expert Analyses", str(data["expert_analyses_count"]))
            table.add_row("Target Repositories", ", ".join(data["target_repositories"]))

            console.print(table)
        else:
            console.print(f"[red]✗[/red] {result.message}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Failed to get story status:[/red] {e}")
        if debug:
            console.print_exception()
        sys.exit(1)


@story_app.command("list-repositories")
def list_repositories(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """List available repositories."""

    setup_logging(debug)

    try:
        config = get_config()
        processor = WorkflowProcessor(config)

        result = processor.list_repositories_workflow()

        if result.success:
            repositories = result.data["repositories"]

            console.print(f"[green]✓[/green] Found {len(repositories)} repositories:")

            table = Table()
            table.add_column("Key")
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Description")
            table.add_column("Dependencies")

            for repo in repositories:
                deps = (
                    ", ".join(repo["dependencies"]) if repo["dependencies"] else "None"
                )
                table.add_row(
                    repo["key"], repo["name"], repo["type"], repo["description"], deps
                )

            console.print(table)
        else:
            console.print(f"[red]✗[/red] {result.message}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Failed to list repositories:[/red] {e}")
        if debug:
            console.print_exception()
        sys.exit(1)


@story_app.command("list-roles")
def list_roles(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """List available expert roles."""

    setup_logging(debug)

    try:
        config = get_config()
        processor = WorkflowProcessor(config)

        result = processor.list_roles_workflow()

        if result.success:
            role_categories = result.data["roles"]
            total_count = result.data["total_count"]

            console.print(f"[green]✓[/green] Found {total_count} expert roles:")

            for category, roles in role_categories.items():
                if roles:
                    console.print(f"\n[bold blue]{category}:[/bold blue]")
                    for role in roles:
                        console.print(f"  • {role}")
        else:
            console.print(f"[red]✗[/red] {result.message}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Failed to list roles:[/red] {e}")
        if debug:
            console.print_exception()
        sys.exit(1)


@story_app.command("breakdown-epic")
def breakdown_epic(
    epic_id: str = typer.Argument(..., help="Epic ID to break down"),
    max_stories: int = typer.Option(
        5, "--max-stories", help="Maximum number of user stories to create"
    ),
    repositories: Optional[List[str]] = typer.Option(
        None, "--repos", help="Target repositories for the user stories"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Break down an epic into user stories using AI analysis."""

    setup_logging(debug)

    async def _breakdown_epic():
        try:
            from story_manager import StoryManager

            story_manager = StoryManager()

            # Show progress
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Breaking down epic {epic_id} into user stories...", total=None
                )

                user_stories = await story_manager.breakdown_epic_to_user_stories(
                    epic_id=epic_id,
                    max_user_stories=max_stories,
                    target_repositories=repositories,
                )

                progress.update(task, completed=True)

            console.print(
                f"[green]✓[/green] Successfully broke down epic into {len(user_stories)} user stories!"
            )

            # Display created user stories
            table = Table(title=f"User Stories Created from Epic {epic_id}")
            table.add_column("ID", style="cyan")
            table.add_column("Title")
            table.add_column("Persona")
            table.add_column("Story Points", justify="center")
            table.add_column("Target Repos")

            for story in user_stories:
                repos_str = (
                    ", ".join(story.target_repositories)
                    if story.target_repositories
                    else "N/A"
                )
                points_str = str(story.story_points) if story.story_points else "N/A"
                table.add_row(
                    story.id,
                    story.title[:50] + "..." if len(story.title) > 50 else story.title,
                    story.user_persona,
                    points_str,
                    repos_str,
                )

            console.print(table)

            # Show hierarchy
            hierarchy = story_manager.get_epic_hierarchy(epic_id)
            if hierarchy:
                progress_info = hierarchy.get_epic_progress()
                console.print(
                    f"\n[bold]Epic Progress:[/bold] "
                    f"{progress_info['completed']}/{progress_info['total']} "
                    f"user stories completed"
                )

        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]✗ Failed to break down epic:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_breakdown_epic())


@story_app.command("assign")
def process_assignment(
    story_id: str = typer.Argument(..., help="Story ID to process for assignment"),
    story_content: str = typer.Option(
        "", "--content", help="Story content (if not stored in system)"
    ),
    manual_override: bool = typer.Option(
        False, "--override", help="Manually override assignment rules"
    ),
    complexity: Optional[str] = typer.Option(
        None, "--complexity", help="Manual complexity override (low/medium/high)"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Process automatic assignment for a story."""

    setup_logging(debug)

    async def _process_assignment():
        try:
            config = get_config()
            processor = WorkflowProcessor(config)

            # Build story metadata if provided
            story_metadata = {}
            if complexity:
                story_metadata["manual_complexity"] = complexity

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Processing assignment for story {story_id}...", total=None
                )

                result = await processor.process_story_assignment(
                    story_id=story_id,
                    story_content=story_content,
                    story_metadata=story_metadata,
                    manual_override=manual_override,
                )

                progress.update(task, completed=True)

            if result.success:
                if result.data["assigned"]:
                    console.print(
                        f"[green]✓[/green] Story {story_id} assigned to {result.data['assignee']}"
                    )
                    console.print(f"[blue]Reason:[/blue] {result.data['explanation']}")

                    if result.data.get("metadata"):
                        console.print("[blue]Details:[/blue]")
                        for key, value in result.data["metadata"].items():
                            console.print(f"  • {key}: {value}")
                else:
                    console.print(f"[yellow]⚠[/yellow] Story {story_id} not assigned")
                    console.print(f"[blue]Reason:[/blue] {result.data['explanation']}")
            else:
                console.print(f"[red]✗[/red] {result.message}")
                if result.error:
                    console.print(f"[red]Error:[/red] {result.error}")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]✗ Assignment processing failed:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_process_assignment())


@story_app.command("assignment-queue")
def show_assignment_queue(
    limit: int = typer.Option(
        20, "--limit", "-l", help="Maximum number of items to show"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Show the current assignment queue in chronological order."""

    setup_logging(debug)

    try:
        config = get_config()
        processor = WorkflowProcessor(config)

        result = processor.get_assignment_queue_workflow()

        if result.success:
            queue = result.data["queue"]
            statistics = result.data["statistics"]

            console.print(f"[green]✓[/green] Assignment Queue ({len(queue)} items)")

            # Show statistics
            stats_table = Table(title="Assignment Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", justify="right")

            stats_table.add_row("Total Processed", str(statistics["total_processed"]))
            stats_table.add_row("Successfully Assigned", str(statistics["assigned"]))
            stats_table.add_row("Assignment Rate", f"{statistics['assignment_rate']}%")
            stats_table.add_row("Current Workload", str(statistics["current_workload"]))

            console.print(stats_table)

            if queue:
                # Show assignment queue
                queue_table = Table(title="Assignment Queue (Chronological Order)")
                queue_table.add_column("Story ID", style="cyan")
                queue_table.add_column("Assignee")
                queue_table.add_column("Reason")
                queue_table.add_column("Timestamp")

                for item in queue[:limit]:
                    queue_table.add_row(
                        item["story_id"],
                        item["assignee"],
                        item["reason"],
                        item["timestamp"][:19],  # Trim to readable format
                    )

                console.print(queue_table)

                if len(queue) > limit:
                    console.print(
                        f"[yellow]... and {len(queue) - limit} more items[/yellow]"
                    )
            else:
                console.print("[yellow]No assignments in queue[/yellow]")

        else:
            console.print(f"[red]✗[/red] {result.message}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Failed to get assignment queue:[/red] {e}")
        if debug:
            console.print_exception()
        sys.exit(1)


@story_app.command("assignment-stats")
def show_assignment_statistics(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Show detailed assignment statistics."""

    setup_logging(debug)

    try:
        config = get_config()
        processor = WorkflowProcessor(config)

        result = processor.get_assignment_statistics_workflow()

        if result.success:
            stats = result.data

            console.print("[green]✓[/green] Assignment Statistics")

            # Main statistics
            main_table = Table(title="Overall Statistics")
            main_table.add_column("Metric", style="cyan")
            main_table.add_column("Value", justify="right")

            main_table.add_row("Total Stories Processed", str(stats["total_processed"]))
            main_table.add_row("Successfully Assigned", str(stats["assigned"]))
            main_table.add_row("Assignment Rate", f"{stats['assignment_rate']}%")
            main_table.add_row("Current Agent Workload", str(stats["current_workload"]))

            console.print(main_table)

            # Reason breakdown
            if stats.get("reasons"):
                reason_table = Table(title="Assignment Reasons")
                reason_table.add_column("Reason", style="cyan")
                reason_table.add_column("Count", justify="right")
                reason_table.add_column("Percentage", justify="right")

                total = stats["total_processed"]
                for reason, count in stats["reasons"].items():
                    percentage = (count / total * 100) if total > 0 else 0
                    reason_table.add_row(
                        reason.replace("_", " ").title(),
                        str(count),
                        f"{percentage:.1f}%",
                    )

                console.print(reason_table)

        else:
            console.print(f"[red]✗[/red] {result.message}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Failed to get assignment statistics:[/red] {e}")
        if debug:
            console.print_exception()
        sys.exit(1)


# Consensus management commands
consensus_app = typer.Typer(help="Consensus and manual intervention management")
app.add_typer(consensus_app, name="consensus")


@consensus_app.command("list-interventions")
def list_pending_interventions(
    limit: int = typer.Option(50, "--limit", help="Maximum number of interventions to show"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """List pending manual interventions."""
    
    setup_logging(debug)

    async def _list_interventions():
        try:
            from src.storyteller.conversation_manager import ConversationManager
            
            manager = ConversationManager()
            interventions = manager.get_pending_interventions(limit)
            
            if not interventions:
                console.print("No pending interventions found.")
                return
            
            table = Table(title="Pending Manual Interventions")
            table.add_column("ID", style="cyan")
            table.add_column("Conversation", style="green")
            table.add_column("Reason", style="yellow")
            table.add_column("Type", style="blue")
            table.add_column("Triggered At", style="magenta")
            
            for intervention in interventions:
                table.add_row(
                    intervention["id"],
                    intervention["conversation_id"],
                    intervention["trigger_reason"],
                    intervention["intervention_type"],
                    intervention["triggered_at"][:19],  # Truncate timestamp
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error listing interventions: {e}[/red]")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_list_interventions())


@consensus_app.command("resolve")
def resolve_intervention(
    intervention_id: str = typer.Argument(..., help="ID of the intervention to resolve"),
    decision: str = typer.Option(..., "--decision", help="Human decision for the consensus"),
    rationale: str = typer.Option("", "--rationale", help="Rationale for the decision"),
    intervener_id: str = typer.Option("", "--intervener", help="ID of the person making the decision"),
    intervener_role: str = typer.Option("project-manager", "--role", help="Role of the intervener"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Resolve a manual intervention with a human decision."""
    
    setup_logging(debug)

    async def _resolve_intervention():
        try:
            from src.storyteller.conversation_manager import ConversationManager
            
            manager = ConversationManager()
            
            # First check if intervention exists
            status = manager.get_intervention_status(intervention_id)
            if not status:
                console.print(f"[red]Intervention {intervention_id} not found.[/red]")
                sys.exit(1)
            
            if status["status"] != "pending":
                console.print(f"[red]Intervention {intervention_id} is not pending (status: {status['status']}).[/red]")
                sys.exit(1)
            
            # Show intervention details
            console.print(Panel(f"""
**Original Decision:** {status['original_decision']}
**Trigger Reason:** {status['trigger_reason']}
**Affected Roles:** {', '.join(status['affected_roles'])}
            """, title=f"Intervention {intervention_id}"))
            
            # Resolve the intervention
            success = await manager.resolve_manual_intervention(
                intervention_id=intervention_id,
                human_decision=decision,
                human_rationale=rationale,
                intervener_id=intervener_id,
                intervener_role=intervener_role,
            )
            
            if success:
                console.print(f"[green]Successfully resolved intervention {intervention_id}[/green]")
                console.print(f"Decision: {decision}")
                if rationale:
                    console.print(f"Rationale: {rationale}")
            else:
                console.print(f"[red]Failed to resolve intervention {intervention_id}[/red]")
                sys.exit(1)
            
        except Exception as e:
            console.print(f"[red]Error resolving intervention: {e}[/red]")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_resolve_intervention())


@consensus_app.command("status")
def get_intervention_status(
    intervention_id: str = typer.Argument(..., help="ID of the intervention to check"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Get the status of a manual intervention."""
    
    setup_logging(debug)

    async def _get_status():
        try:
            from src.storyteller.conversation_manager import ConversationManager
            
            manager = ConversationManager()
            status = manager.get_intervention_status(intervention_id)
            
            if not status:
                console.print(f"[red]Intervention {intervention_id} not found.[/red]")
                sys.exit(1)
            
            # Create detailed status panel
            status_content = f"""
**ID:** {status['id']}
**Conversation ID:** {status['conversation_id']}
**Consensus ID:** {status['consensus_id']}
**Status:** {status['status']}
**Trigger Reason:** {status['trigger_reason']}
**Type:** {status['intervention_type']}
**Original Decision:** {status['original_decision']}
**Triggered At:** {status['triggered_at']}
            """
            
            if status['human_decision']:
                status_content += f"""
**Human Decision:** {status['human_decision']}
**Human Rationale:** {status['human_rationale']}
**Intervener:** {status['intervener_role']} ({status['intervener_id']})
**Resolved At:** {status['resolved_at']}
                """
            
            if status['affected_roles']:
                status_content += f"""
**Affected Roles:** {', '.join(status['affected_roles'])}
                """
            
            console.print(Panel(status_content, title=f"Intervention Status"))
            
            # Show audit trail if available
            if status['audit_trail']:
                table = Table(title="Audit Trail")
                table.add_column("Timestamp", style="cyan")
                table.add_column("Action", style="green")
                table.add_column("Actor", style="yellow")
                table.add_column("Details", style="white")
                
                for entry in status['audit_trail']:
                    table.add_row(
                        entry['timestamp'][:19],  # Truncate timestamp
                        entry['action'],
                        entry['actor'],
                        entry['details'][:50] + "..." if len(entry['details']) > 50 else entry['details']
                    )
                
                console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error getting intervention status: {e}[/red]")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_get_status())


@consensus_app.command("trigger")
def trigger_manual_intervention(
    conversation_id: str = typer.Argument(..., help="ID of the conversation"),
    consensus_id: str = typer.Argument(..., help="ID of the consensus process"),
    reason: str = typer.Option("manual_request", "--reason", help="Reason for triggering intervention"),
    intervention_type: str = typer.Option("decision", "--type", help="Type of intervention"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Manually trigger an intervention for a consensus process."""
    
    setup_logging(debug)

    async def _trigger_intervention():
        try:
            from src.storyteller.conversation_manager import ConversationManager
            
            manager = ConversationManager()
            
            intervention_id = await manager.trigger_manual_intervention(
                conversation_id=conversation_id,
                consensus_id=consensus_id,
                trigger_reason=reason,
                intervention_type=intervention_type,
            )
            
            console.print(f"[green]Successfully triggered manual intervention {intervention_id}[/green]")
            console.print(f"Conversation: {conversation_id}")
            console.print(f"Consensus: {consensus_id}")
            console.print(f"Reason: {reason}")
            console.print(f"Type: {intervention_type}")
            
        except Exception as e:
            console.print(f"[red]Error triggering intervention: {e}[/red]")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_trigger_intervention())


# MCP server commands
mcp_app = typer.Typer(help="MCP (Model Context Protocol) server commands")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("start")
def start_mcp_server(
    transport: str = typer.Option(
        "stdio", "--transport", "-t", help="Transport type (stdio, websocket)"
    ),
    host: str = typer.Option("localhost", "--host", help="Host for websocket server"),
    port: int = typer.Option(8765, "--port", help="Port for websocket server"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Start MCP server for AI assistant integration."""

    setup_logging(debug)

    async def _start_server():
        try:
            from mcp_server import run_mcp_server

            console.print(
                f"[green]Starting MCP server with {transport} transport...[/green]"
            )

            await run_mcp_server(transport=transport, host=host, port=port)

        except Exception as e:
            console.print(f"[red]✗ Failed to start MCP server:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_start_server())


@mcp_app.command("test")
def test_mcp_server(
    method: str = typer.Argument(..., help="MCP method to test"),
    params_file: Optional[Path] = typer.Option(
        None, "--params", help="JSON file with parameters"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Test MCP server functionality."""

    setup_logging(debug)

    async def _test_server():
        try:
            from mcp_server import MCPRequest, MCPStoryServer

            # Load parameters
            params = {}
            if params_file and params_file.exists():
                import json

                with open(params_file) as f:
                    params = json.load(f)

            # Create server and request
            server = MCPStoryServer()
            request = MCPRequest(id="test_request", method=method, params=params)

            console.print(f"[blue]Testing MCP method:[/blue] {method}")

            # Execute request
            response = await server.handle_request(request)

            if response.error:
                console.print(f"[red]✗ Error:[/red] {response.error}")
            else:
                console.print("[green]✓ Success![/green]")

                # Pretty print result
                import json

                result_json = json.dumps(response.result, indent=2, default=str)
                syntax = Syntax(result_json, "json", theme="monokai", line_numbers=True)
                console.print(syntax)

        except Exception as e:
            console.print(f"[red]✗ Failed to test MCP server:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_test_server())


# Pipeline monitoring commands
pipeline_app = typer.Typer(help="Pipeline monitoring and failure analysis commands")
app.add_typer(pipeline_app, name="pipeline")


@pipeline_app.command("dashboard")
def get_pipeline_dashboard(
    repository: Optional[str] = typer.Option(
        None, "--repo", help="Repository to filter by"
    ),
    time_range: str = typer.Option(
        "24h", "--time-range", help="Time range (e.g., 24h, 7d, 30d)"
    ),
    format: str = typer.Option("table", "--format", help="Output format: table, json"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Get pipeline monitoring dashboard data."""
    setup_logging(debug)

    with console.status("[bold green]Getting pipeline dashboard data..."):
        workflow_processor = WorkflowProcessor()
        result = workflow_processor.get_pipeline_dashboard_workflow(
            repository=repository, time_range=time_range
        )

    if not result.success:
        console.print(f"[red]Error: {result.message}[/red]")
        if result.error:
            console.print(f"[red]Details: {result.error}[/red]")
        sys.exit(1)

    if format == "json":
        import json

        console.print(json.dumps(result.data, indent=2))
    else:
        _display_dashboard_table(result.data)

    console.print(f"[green]✓ Dashboard data retrieved for {time_range}[/green]")


@pipeline_app.command("health")
def get_pipeline_health(
    repository: Optional[str] = typer.Option(
        None, "--repo", help="Repository to filter by"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Get current pipeline health status."""
    setup_logging(debug)

    with console.status("[bold green]Getting pipeline health status..."):
        workflow_processor = WorkflowProcessor()
        result = workflow_processor.get_pipeline_health_workflow(repository=repository)

    if not result.success:
        console.print(f"[red]Error: {result.message}[/red]")
        if result.error:
            console.print(f"[red]Details: {result.error}[/red]")
        sys.exit(1)

    _display_health_status(result.data)
    console.print("[green]✓ Health status retrieved[/green]")


@pipeline_app.command("patterns")
def analyze_pipeline_patterns(
    days: int = typer.Option(30, "--days", help="Number of days to analyze"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Analyze pipeline failure patterns."""
    setup_logging(debug)

    with console.status(f"[bold green]Analyzing failure patterns for {days} days..."):
        workflow_processor = WorkflowProcessor()
        result = workflow_processor.analyze_pipeline_patterns_workflow(days=days)

    if not result.success:
        console.print(f"[red]Error: {result.message}[/red]")
        if result.error:
            console.print(f"[red]Details: {result.error}[/red]")
        sys.exit(1)

    _display_patterns_table(result.data)
    console.print(f"[green]✓ {result.message}[/green]")


@pipeline_app.command("export")
def export_pipeline_data(
    repository: Optional[str] = typer.Option(
        None, "--repo", help="Repository to filter by"
    ),
    time_range: str = typer.Option(
        "7d", "--time-range", help="Time range (e.g., 24h, 7d, 30d)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", help="Output file path"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Export pipeline monitoring data."""
    setup_logging(debug)

    with console.status("[bold green]Exporting pipeline data..."):
        workflow_processor = WorkflowProcessor()
        result = workflow_processor.export_pipeline_data_workflow(
            repository=repository, time_range=time_range, format="json"
        )

    if not result.success:
        console.print(f"[red]Error: {result.message}[/red]")
        if result.error:
            console.print(f"[red]Details: {result.error}[/red]")
        sys.exit(1)

    import json

    if output_file:
        with open(output_file, "w") as f:
            json.dump(result.data, f, indent=2)
        console.print(f"[green]✓ Data exported to {output_file}[/green]")
    else:
        console.print(json.dumps(result.data, indent=2))

    console.print(f"[green]✓ {result.message}[/green]")


def _display_dashboard_table(data: dict):
    """Display dashboard data as formatted tables."""
    summary = data.get("summary", {})

    # Summary table
    summary_table = Table(title="Pipeline Dashboard Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")

    summary_table.add_row("Total Failures", str(summary.get("total_failures", 0)))
    summary_table.add_row("Time Period", f"{summary.get('time_period_days', 0)} days")
    summary_table.add_row("Last Updated", summary.get("last_updated", "Unknown"))

    console.print(summary_table)

    # Health metrics
    health_metrics = data.get("health_metrics", {})
    if health_metrics:
        health_table = Table(title="Health Metrics")
        health_table.add_column("Metric", style="cyan")
        health_table.add_column("Value", style="green")

        health_table.add_row(
            "Success Rate", f"{health_metrics.get('success_rate', 0)}%"
        )
        health_table.add_row("Total Runs", str(health_metrics.get("total_runs", 0)))
        health_table.add_row("Failed Runs", str(health_metrics.get("failed_runs", 0)))
        health_table.add_row(
            "Health Score", health_metrics.get("health_score", "unknown")
        )

        console.print(health_table)

    # Failures by category
    by_category = data.get("by_category", {})
    if by_category:
        category_table = Table(title="Failures by Category")
        category_table.add_column("Category", style="cyan")
        category_table.add_column("Count", style="red")

        for category, count in by_category.items():
            category_table.add_row(category.title(), str(count))

        console.print(category_table)


def _display_health_status(data: dict):
    """Display health status information."""
    live_status = data.get("live_status", {})
    health_metrics = data.get("health_metrics", {})

    # Live status
    status_table = Table(title="Live Pipeline Status")
    status_table.add_column("Metric", style="cyan")
    status_table.add_column("Value", style="green")

    status_table.add_row("Active Pipelines", str(live_status.get("total_active", 0)))
    status_table.add_row("Recent Failures", str(live_status.get("recent_failures", 0)))
    status_table.add_row("Timestamp", live_status.get("timestamp", "Unknown"))

    console.print(status_table)

    # Health score with color coding
    health_score = health_metrics.get("health_score", "unknown")
    score_color = {
        "excellent": "green",
        "good": "yellow",
        "fair": "orange",
        "poor": "red",
    }.get(health_score, "white")

    console.print(
        f"Overall Health: [{score_color}]{health_score.title()}[/{score_color}]"
    )


def _display_patterns_table(data: dict):
    """Display failure patterns table."""
    patterns = data.get("patterns", [])

    if not patterns:
        console.print(
            "[yellow]No failure patterns found in the analyzed period.[/yellow]"
        )
        return

    patterns_table = Table(
        title=f"Failure Patterns ({data.get('total_patterns', 0)} found)"
    )
    patterns_table.add_column("Category", style="cyan")
    patterns_table.add_column("Description", style="white", max_width=50)
    patterns_table.add_column("Count", style="red")
    patterns_table.add_column("Repositories", style="green", max_width=30)

    for pattern in patterns:
        repos = ", ".join(pattern.get("repositories", []))
        patterns_table.add_row(
            pattern.get("category", "").title(),
            pattern.get("description", ""),
            str(pattern.get("failure_count", 0)),
            repos,
        )

    console.print(patterns_table)


# API server commands
api_app = typer.Typer(help="API server commands")
app.add_typer(api_app, name="api")


@api_app.command("start")
def start_api_server(
    host: str = typer.Option("localhost", "--host", help="Host to bind API server"),
    port: int = typer.Option(8000, "--port", help="Port to bind API server"),
    reload: bool = typer.Option(
        False, "--reload", help="Enable auto-reload for development"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Start the Epic management API server."""

    setup_logging(debug)

    try:
        import uvicorn

        console.print(f"[green]Starting API server on http://{host}:{port}[/green]")
        console.print("[blue]API Documentation available at:[/blue]")
        console.print(f"  • Swagger UI: http://{host}:{port}/docs")
        console.print(f"  • ReDoc: http://{host}:{port}/redoc")

        uvicorn.run(
            "api:app",
            host=host,
            port=port,
            reload=reload,
            log_level="debug" if debug else "info",
        )
    except Exception as e:
        console.print(f"[red]✗ Failed to start API server:[/red] {e}")
        if debug:
            console.print_exception()
        sys.exit(1)


# Configuration and validation commands
@app.command("validate")
def validate_configuration(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Validate the current configuration."""

    setup_logging(debug)

    async def _validate():
        try:
            config = get_config()
            processor = WorkflowProcessor(config)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Validating configuration...", total=None)

                result = await processor.validate_configuration_workflow()

                progress.update(task, completed=True)

            if result.success:
                console.print("[green]✓[/green] Configuration is valid!")

                data = result.data
                console.print("\n[bold]Configuration Summary:[/bold]")
                console.print(f"• Repositories: {data['repositories']}")
                console.print(f"• Role files: {data['role_files']}")
                console.print(f"• LLM provider: {data['llm_provider']}")
            else:
                console.print("[red]✗[/red] Configuration issues found:")
                for issue in result.data["issues"]:
                    console.print(f"  • {issue}")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]✗ Configuration validation failed:[/red] {e}")
            if debug:
                console.print_exception()
            sys.exit(1)

    asyncio.run(_validate())


@app.command("version")
def show_version():
    """Show version information."""
    console.print("[bold]AI Story Management System[/bold]")
    console.print("Version: 1.0.0")
    console.print("Recipe Authority Platform - Storyteller")


if __name__ == "__main__":
    app()
