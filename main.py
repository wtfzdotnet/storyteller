"""Main CLI interface for AI Story Management System."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

import typer
from automation.workflow_processor import WorkflowProcessor
from config import get_config
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
