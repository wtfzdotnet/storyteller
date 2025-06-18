"""Configuration management for AI Story Management System."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv


@dataclass
class RepositoryConfig:
    """Configuration for a single repository."""

    name: str
    type: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    story_labels: List[str] = field(default_factory=list)
    auto_assign: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class StoryWorkflowConfig:
    """Configuration for story workflow settings."""

    create_subtickets: bool = True
    respect_dependencies: bool = True


@dataclass
class WebhookConfig:
    """Configuration for webhook-based status transitions."""

    enabled: bool = True
    secret: Optional[str] = None
    status_mappings: Dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineRetryConfig:
    """Configuration for pipeline failure retry logic."""

    enabled: bool = True
    max_retries: int = 3
    initial_delay_seconds: int = 30
    max_delay_seconds: int = 300
    backoff_multiplier: float = 2.0
    retry_timeout_hours: int = 24


@dataclass
class EscalationConfig:
    """Configuration for failure escalation process."""

    enabled: bool = True
    escalation_threshold: int = 5  # Number of persistent failures before escalation
    escalation_contacts: List[str] = field(default_factory=list)
    escalation_channels: List[str] = field(default_factory=lambda: ["github_issue"])
    cooldown_hours: int = 6  # Hours to wait before re-escalating same issue


@dataclass
class Config:
    """Main configuration class for the AI Story Management System."""

    # GitHub Configuration
    github_token: str
    github_repository: Optional[str] = None

    # LLM Configuration
    default_llm_provider: str = "github"
    openai_api_key: Optional[str] = None
    ollama_api_host: str = "http://localhost:11434"

    # Application Configuration
    log_level: str = "INFO"
    max_retries: int = 3
    timeout_seconds: int = 30

    # Auto-Consensus Configuration
    auto_consensus_enabled: bool = False
    auto_consensus_threshold: int = 70
    auto_consensus_max_iterations: int = 10

    # Development Configuration
    debug_mode: bool = False

    # Webhook Configuration
    webhook_config: WebhookConfig = field(default_factory=WebhookConfig)
    webhook_secret: Optional[str] = None

    # Pipeline Retry Configuration
    pipeline_retry_config: PipelineRetryConfig = field(default_factory=PipelineRetryConfig)
    
    # Escalation Configuration
    escalation_config: EscalationConfig = field(default_factory=EscalationConfig)

    # Multi-Repository Configuration
    repositories: Dict[str, RepositoryConfig] = field(default_factory=dict)
    default_repository: str = "backend"
    story_workflow: StoryWorkflowConfig = field(default_factory=StoryWorkflowConfig)

    # Paths
    storyteller_dir: Path = field(default_factory=lambda: Path(".storyteller"))
    roles_dir: Path = field(default_factory=lambda: Path(".storyteller/roles"))
    config_file: Path = field(default_factory=lambda: Path(".storyteller/config.json"))


def load_config() -> Config:
    """Load configuration from environment variables and config files."""

    # Load environment variables
    load_dotenv()

    # Required GitHub configuration
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable is required")

    # Create base config from environment
    config = Config(
        github_token=github_token,
        github_repository=os.getenv("GITHUB_REPOSITORY"),
        default_llm_provider=os.getenv("DEFAULT_LLM_PROVIDER", "github"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        ollama_api_host=os.getenv("OLLAMA_API_HOST", "http://localhost:11434"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "30")),
        auto_consensus_enabled=os.getenv("AUTO_CONSENSUS_ENABLED", "false").lower()
        == "true",
        auto_consensus_threshold=int(os.getenv("AUTO_CONSENSUS_THRESHOLD", "70")),
        auto_consensus_max_iterations=int(
            os.getenv("AUTO_CONSENSUS_MAX_ITERATIONS", "10")
        ),
        debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
        webhook_secret=os.getenv("WEBHOOK_SECRET"),
    )

    # Load multi-repository configuration if exists
    config_file = Path(".storyteller/config.json")
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # Parse repositories
            repositories = {}
            for repo_key, repo_data in config_data.get("repositories", {}).items():
                repositories[repo_key] = RepositoryConfig(
                    name=repo_data["name"],
                    type=repo_data["type"],
                    description=repo_data["description"],
                    dependencies=repo_data.get("dependencies", []),
                    story_labels=repo_data.get("story_labels", []),
                    auto_assign=repo_data.get("auto_assign", {}),
                )

            config.repositories = repositories
            config.default_repository = config_data.get("default_repository", "backend")

            # Parse story workflow config
            workflow_data = config_data.get("story_workflow", {})
            config.story_workflow = StoryWorkflowConfig(
                create_subtickets=workflow_data.get("create_subtickets", True),
                respect_dependencies=workflow_data.get("respect_dependencies", True),
            )

            # Parse webhook config
            webhook_data = config_data.get("webhook_config", {})
            config.webhook_config = WebhookConfig(
                enabled=webhook_data.get("enabled", True),
                secret=webhook_data.get("secret"),
                status_mappings=webhook_data.get("status_mappings", {}),
            )

            # Parse pipeline retry config
            retry_data = config_data.get("pipeline_retry_config", {})
            config.pipeline_retry_config = PipelineRetryConfig(
                enabled=retry_data.get("enabled", True),
                max_retries=retry_data.get("max_retries", 3),
                initial_delay_seconds=retry_data.get("initial_delay_seconds", 30),
                max_delay_seconds=retry_data.get("max_delay_seconds", 300),
                backoff_multiplier=retry_data.get("backoff_multiplier", 2.0),
                retry_timeout_hours=retry_data.get("retry_timeout_hours", 24),
            )

            # Parse escalation config
            escalation_data = config_data.get("escalation_config", {})
            config.escalation_config = EscalationConfig(
                enabled=escalation_data.get("enabled", True),
                escalation_threshold=escalation_data.get("escalation_threshold", 5),
                escalation_contacts=escalation_data.get("escalation_contacts", []),
                escalation_channels=escalation_data.get("escalation_channels", ["github_issue"]),
                cooldown_hours=escalation_data.get("cooldown_hours", 6),
            )

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid configuration file: {e}")

    return config


def get_config() -> Config:
    """Get the singleton configuration instance."""
    if not hasattr(get_config, "_config"):
        get_config._config = load_config()
    return get_config._config


def get_repository_config(repository_key: str) -> Optional[RepositoryConfig]:
    """Get configuration for a specific repository."""
    config = get_config()
    return config.repositories.get(repository_key)


def list_repositories() -> Dict[str, RepositoryConfig]:
    """List all configured repositories."""
    config = get_config()
    return config.repositories


def load_role_files() -> Dict[str, str]:
    """Load all role definition files from .storyteller/roles/."""
    config = get_config()
    roles = {}

    if not config.roles_dir.exists():
        return roles

    for role_file in config.roles_dir.glob("*.md"):
        role_name = role_file.stem
        try:
            with open(role_file, "r", encoding="utf-8") as f:
                roles[role_name] = f.read()
        except Exception as e:
            print(f"Warning: Could not load role file {role_file}: {e}")

    return roles
