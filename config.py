"""Configuration management for AI Story Management System."""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


class LanguageType(Enum):
    """Supported repository languages."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    REACT = "react"
    VUE = "vue"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CSHARP = "csharp"
    OTHER = "other"


class PlatformChoice(Enum):
    """Supported platform configurations for different repositories."""

    # Frontend/JavaScript platforms
    REACT = "react"
    TAILWIND = "tailwind"
    VITE = "vite"
    NEXT_JS = "nextjs"
    WEBPACK = "webpack"
    STORYBOOK = "storybook"
    VITEST = "vitest"
    JEST = "jest"
    CYPRESS = "cypress"
    PLAYWRIGHT = "playwright"

    # Go/Backend platforms
    GOKIT = "gokit"
    GIN = "gin"
    ECHO = "echo"
    FIBER = "fiber"
    GRPC = "grpc"
    PROTOBUF = "protobuf"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    TESTIFY = "testify"
    GORM = "gorm"


@dataclass
class RulesetAction:
    """A single action within a ruleset."""

    name: str
    description: str
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Ruleset:
    """Language/platform-specific rules and actions."""

    name: str
    description: str
    language: LanguageType
    platforms: List[PlatformChoice] = field(default_factory=list)
    actions: List[RulesetAction] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)


@dataclass
class RepositoryConfig:
    """Configuration for a single repository."""

    name: str
    type: str
    description: str
    language: LanguageType = LanguageType.OTHER
    platforms: List[PlatformChoice] = field(default_factory=list)
    ruleset: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    story_labels: List[str] = field(default_factory=list)
    auto_assign: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class StoryWorkflowConfig:
    """Configuration for story workflow settings."""

    create_subtickets: bool = True
    respect_dependencies: bool = True


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

    # Multi-Repository Configuration
    repositories: Dict[str, RepositoryConfig] = field(default_factory=dict)
    rulesets: Dict[str, Ruleset] = field(default_factory=dict)
    default_repository: str = "backend"
    story_workflow: StoryWorkflowConfig = field(default_factory=StoryWorkflowConfig)

    # Paths
    storyteller_dir: Path = field(default_factory=lambda: Path(".storyteller"))
    roles_dir: Path = field(default_factory=lambda: Path(".storyteller/roles"))
    rulesets_dir: Path = field(default_factory=lambda: Path(".storyteller/rulesets"))
    templates_dir: Path = field(default_factory=lambda: Path(".storyteller/templates"))
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
                # Parse language type
                language_str = repo_data.get("language", "other")
                try:
                    language = LanguageType(language_str)
                except ValueError:
                    language = LanguageType.OTHER

                # Parse platform choices
                platforms = []
                for platform_str in repo_data.get("platforms", []):
                    try:
                        platforms.append(PlatformChoice(platform_str))
                    except ValueError:
                        continue  # Skip invalid platform choices

                repositories[repo_key] = RepositoryConfig(
                    name=repo_data["name"],
                    type=repo_data["type"],
                    description=repo_data["description"],
                    language=language,
                    platforms=platforms,
                    ruleset=repo_data.get("ruleset"),
                    dependencies=repo_data.get("dependencies", []),
                    story_labels=repo_data.get("story_labels", []),
                    auto_assign=repo_data.get("auto_assign", {}),
                )

            config.repositories = repositories
            config.default_repository = config_data.get("default_repository", "backend")

            # Parse rulesets
            rulesets = {}
            for ruleset_key, ruleset_data in config_data.get("rulesets", {}).items():
                # Parse language type
                language_str = ruleset_data.get("language", "other")
                try:
                    language = LanguageType(language_str)
                except ValueError:
                    language = LanguageType.OTHER

                # Parse platform choices
                platforms = []
                for platform_str in ruleset_data.get("platforms", []):
                    try:
                        platforms.append(PlatformChoice(platform_str))
                    except ValueError:
                        continue

                # Parse actions
                actions = []
                for action_data in ruleset_data.get("actions", []):
                    actions.append(
                        RulesetAction(
                            name=action_data["name"],
                            description=action_data["description"],
                            enabled=action_data.get("enabled", True),
                            parameters=action_data.get("parameters", {}),
                        )
                    )

                rulesets[ruleset_key] = Ruleset(
                    name=ruleset_data["name"],
                    description=ruleset_data["description"],
                    language=language,
                    platforms=platforms,
                    actions=actions,
                    file_patterns=ruleset_data.get("file_patterns", []),
                    dependencies=ruleset_data.get("dependencies", []),
                    dev_dependencies=ruleset_data.get("dev_dependencies", []),
                )

            config.rulesets = rulesets

            # Parse story workflow config
            workflow_data = config_data.get("story_workflow", {})
            config.story_workflow = StoryWorkflowConfig(
                create_subtickets=workflow_data.get("create_subtickets", True),
                respect_dependencies=workflow_data.get("respect_dependencies", True),
            )

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid configuration file: {e}")

    # Load default rulesets if none configured
    if not config.rulesets:
        config.rulesets = load_default_rulesets()

    return config


def load_default_rulesets() -> Dict[str, Ruleset]:
    """Load default rulesets for common language/platform combinations."""
    rulesets = {}

    # Python ruleset
    rulesets["python-default"] = Ruleset(
        name="Python Default",
        description="Default ruleset for Python projects",
        language=LanguageType.PYTHON,
        actions=[
            RulesetAction(
                name="test_generation",
                description="Generate pytest test files",
                parameters={"framework": "pytest", "coverage_target": 80},
            ),
            RulesetAction(
                name="component_analysis",
                description="Analyze Python classes and modules",
                parameters={"analyze_complexity": True, "suggest_improvements": True},
            ),
            RulesetAction(
                name="qa_strategy",
                description="Python-specific QA recommendations",
                parameters={"include_type_checking": True, "include_linting": True},
            ),
        ],
        file_patterns=["*.py", "**/*.py"],
        dependencies=["pytest", "black", "flake8", "mypy"],
        dev_dependencies=["pytest-cov", "pytest-mock"],
    )

    # TypeScript + React + Vite ruleset
    rulesets["typescript-react-vite"] = Ruleset(
        name="TypeScript React Vite",
        description="Ruleset for TypeScript React projects with Vite",
        language=LanguageType.TYPESCRIPT,
        platforms=[PlatformChoice.REACT, PlatformChoice.VITE, PlatformChoice.VITEST],
        actions=[
            RulesetAction(
                name="component_generation",
                description="Generate React components with TypeScript",
                parameters={"framework": "react", "use_typescript": True},
            ),
            RulesetAction(
                name="test_generation",
                description="Generate Vitest test files",
                parameters={"framework": "vitest", "testing_library": "react"},
            ),
            RulesetAction(
                name="storybook_integration",
                description="Generate Storybook stories",
                parameters={"storybook_version": "7.x"},
            ),
        ],
        file_patterns=["*.ts", "*.tsx", "**/*.ts", "**/*.tsx"],
        dependencies=["react", "react-dom", "typescript"],
        dev_dependencies=["vite", "vitest", "@vitejs/plugin-react", "@storybook/react"],
    )

    # TypeScript + React + Tailwind ruleset
    rulesets["typescript-react-tailwind"] = Ruleset(
        name="TypeScript React Tailwind",
        description="Ruleset for TypeScript React projects with Tailwind CSS",
        language=LanguageType.TYPESCRIPT,
        platforms=[PlatformChoice.REACT, PlatformChoice.TAILWIND],
        actions=[
            RulesetAction(
                name="component_generation",
                description="Generate React components with Tailwind classes",
                parameters={
                    "framework": "react",
                    "use_typescript": True,
                    "css_framework": "tailwind",
                },
            ),
            RulesetAction(
                name="test_generation",
                description="Generate Jest test files with testing-library",
                parameters={"framework": "jest", "testing_library": "react"},
            ),
        ],
        file_patterns=["*.ts", "*.tsx", "**/*.ts", "**/*.tsx"],
        dependencies=["react", "react-dom", "typescript"],
        dev_dependencies=[
            "tailwindcss",
            "postcss",
            "autoprefixer",
            "jest",
            "@testing-library/react",
        ],
    )

    # Go + Go kit ruleset
    rulesets["go-gokit"] = Ruleset(
        name="Go with Go Kit",
        description="Ruleset for Go projects using Go kit microservice framework",
        language=LanguageType.GO,
        platforms=[PlatformChoice.GOKIT, PlatformChoice.GRPC, PlatformChoice.DOCKER],
        actions=[
            RulesetAction(
                name="service_generation",
                description="Generate Go kit service interfaces and implementations",
                parameters={
                    "framework": "gokit",
                    "include_middleware": True,
                    "include_metrics": True,
                    "include_logging": True,
                },
            ),
            RulesetAction(
                name="endpoint_generation",
                description="Generate Go kit endpoints for service methods",
                parameters={
                    "transport": "http",
                    "include_validation": True,
                },
            ),
            RulesetAction(
                name="transport_generation",
                description="Generate HTTP transport layer for endpoints",
                parameters={
                    "router": "gorilla/mux",
                    "middleware": ["logging", "cors", "recovery"],
                },
            ),
            RulesetAction(
                name="test_generation",
                description="Generate Go tests with testify",
                parameters={
                    "framework": "testify",
                    "include_benchmarks": True,
                    "mock_external_deps": True,
                },
            ),
            RulesetAction(
                name="docker_generation",
                description="Generate Dockerfile and docker-compose configurations",
                parameters={
                    "base_image": "alpine",
                    "include_health_check": True,
                },
            ),
        ],
        file_patterns=["*.go", "**/*.go"],
        dependencies=[
            "github.com/go-kit/kit",
            "github.com/gorilla/mux",
            "github.com/go-kit/log",
        ],
        dev_dependencies=[
            "github.com/stretchr/testify",
            "github.com/golang/mock",
        ],
    )

    return rulesets


def get_config() -> Config:
    """Get the singleton configuration instance."""
    if not hasattr(get_config, "_config"):
        get_config._config = load_config()
    return get_config._config


def get_repository_config(repository_key: str) -> Optional[RepositoryConfig]:
    """Get configuration for a specific repository."""
    config = get_config()
    return config.repositories.get(repository_key)


def get_ruleset(ruleset_key: str) -> Optional[Ruleset]:
    """Get a specific ruleset by key."""
    config = get_config()
    return config.rulesets.get(ruleset_key)


def get_repository_ruleset(repository_key: str) -> Optional[Ruleset]:
    """Get the ruleset for a specific repository."""
    repo_config = get_repository_config(repository_key)
    if not repo_config or not repo_config.ruleset:
        return None
    return get_ruleset(repo_config.ruleset)


def get_applicable_rulesets(
    language: LanguageType, platforms: Optional[List[PlatformChoice]] = None
) -> List[Ruleset]:
    """Get all rulesets applicable to a given language and platform combination."""
    if platforms is None:
        platforms = []

    config = get_config()
    applicable = []

    for ruleset in config.rulesets.values():
        if ruleset.language == language:
            # Check if all required platforms are present
            if not ruleset.platforms or all(
                platform in platforms for platform in ruleset.platforms
            ):
                applicable.append(ruleset)

    return applicable


def list_repositories() -> Dict[str, RepositoryConfig]:
    """List all configured repositories."""
    config = get_config()
    return config.repositories


def list_rulesets() -> Dict[str, Ruleset]:
    """List all configured rulesets."""
    config = get_config()
    return config.rulesets


def get_repository_actions(repository_key: str) -> List[RulesetAction]:
    """Get all applicable actions for a repository based on its ruleset."""
    ruleset = get_repository_ruleset(repository_key)
    if not ruleset:
        return []
    return [action for action in ruleset.actions if action.enabled]


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


def ensure_template_directories():
    """Ensure all template directories exist."""
    config = get_config()

    # Create main template directories
    directories = [
        config.templates_dir,
        config.templates_dir / "components",
        config.templates_dir / "tests",
        config.templates_dir / "storybook",
        config.templates_dir / "python",
        config.templates_dir / "typescript",
        config.templates_dir / "react",
        config.templates_dir / "vue",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
