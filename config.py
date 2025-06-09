import os
import logging
import re
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class RepositoryConfig:
    """Configuration for a single repository in multi-repository setup."""
    name: str
    type: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    story_labels: List[str] = field(default_factory=list)

@dataclass
class MultiRepositoryConfig:
    """Configuration for multi-repository setup."""
    repositories: Dict[str, RepositoryConfig] = field(default_factory=dict)
    default_repository: Optional[str] = None
    story_workflow: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MultiRepositoryConfig':
        """Create from dictionary loaded from JSON."""
        repositories = {}
        for key, repo_data in data.get('repositories', {}).items():
            repositories[key] = RepositoryConfig(**repo_data)
        
        return cls(
            repositories=repositories,
            default_repository=data.get('default_repository'),
            story_workflow=data.get('story_workflow', {})
        )
    
    def get_repository(self, key: str) -> Optional[RepositoryConfig]:
        """Get repository configuration by key."""
        return self.repositories.get(key)
    
    def get_dependencies(self, repository_key: str) -> List[str]:
        """Get dependencies for a repository."""
        repo = self.get_repository(repository_key)
        return repo.dependencies if repo else []

@dataclass
class Config:
    """Configuration class for AI Jules application."""
    
    # API Keys
    openai_api_key: Optional[str] = None
    github_token: Optional[str] = None
    
    # Endpoints
    ollama_api_host: str = "http://localhost:11434"
    
    # GitHub Configuration (backward compatibility)
    github_repository: Optional[str] = None
    
    # Multi-repository Configuration
    multi_repository_config: Optional[MultiRepositoryConfig] = None
    storyteller_config_path: Optional[Path] = None
    
    # LLM Configuration
    default_llm_provider: str = "github"
    
    # Runtime Configuration
    log_level: str = "INFO"
    max_retries: int = 3
    timeout_seconds: int = 30
    
    # Auto-consensus Configuration
    auto_consensus_enabled: bool = False
    auto_consensus_threshold: int = 70  # Default consensus threshold when auto-consensus is enabled
    auto_consensus_max_iterations: int = 10  # Max iterations before giving up
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_required_fields()
        self._validate_formats()
        self._validate_provider_config()
        self._load_storyteller_config()
    
    def _load_storyteller_config(self):
        """Load .storyteller/config.json if it exists."""
        # Look for .storyteller/config.json in current directory and parent directories
        current_path = Path.cwd()
        for path_candidate in [current_path] + list(current_path.parents):
            storyteller_config_path = path_candidate / '.storyteller' / 'config.json'
            if storyteller_config_path.exists():
                try:
                    with open(storyteller_config_path, 'r') as f:
                        config_data = json.load(f)
                    self.multi_repository_config = MultiRepositoryConfig.from_dict(config_data)
                    self.storyteller_config_path = storyteller_config_path
                    logger = logging.getLogger(__name__)
                    logger.info(f"Loaded multi-repository config from {storyteller_config_path}")
                    break
                except (json.JSONDecodeError, Exception) as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to load .storyteller/config.json from {storyteller_config_path}: {e}")
    
    def is_multi_repository_mode(self) -> bool:
        """Check if multi-repository mode is enabled."""
        return self.multi_repository_config is not None and len(self.multi_repository_config.repositories) > 0
    
    def get_target_repository(self, repository_key: Optional[str] = None) -> Optional[str]:
        """Get target repository name for operations."""
        if self.is_multi_repository_mode():
            if repository_key:
                repo_config = self.multi_repository_config.get_repository(repository_key)
                return repo_config.name if repo_config else None
            elif self.multi_repository_config.default_repository:
                repo_config = self.multi_repository_config.get_repository(self.multi_repository_config.default_repository)
                return repo_config.name if repo_config else None
        
        # Fallback to single repository mode
        return self.github_repository
    
    def get_repository_list(self) -> List[str]:
        """Get list of available repository keys."""
        if self.is_multi_repository_mode():
            return list(self.multi_repository_config.repositories.keys())
        return ['default'] if self.github_repository else []
    
    def get_repository_dependencies(self, repository_key: str) -> List[str]:
        """Get dependencies for a repository."""
        if self.is_multi_repository_mode():
            return self.multi_repository_config.get_dependencies(repository_key)
        return []
    
    def _validate_required_fields(self):
        """Validate required configuration fields."""
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN is required")
        
        # Validate repository configuration - either single repo or multi-repo setup
        if not self.github_repository and not self.is_multi_repository_mode():
            raise ValueError("Either GITHUB_REPOSITORY is required or .storyteller/config.json must define repositories")
    
    def _validate_formats(self):
        """Validate format of configuration values."""
        # Validate GitHub repository format for single repository mode
        if self.github_repository and not re.match(r'^[\w.-]+/[\w.-]+$', self.github_repository):
            raise ValueError(
                f"Invalid GITHUB_REPOSITORY format: {self.github_repository}. "
                "Expected 'owner/repo'"
            )
        
        # Validate multi-repository configuration
        if self.is_multi_repository_mode():
            for key, repo in self.multi_repository_config.repositories.items():
                if not re.match(r'^[\w.-]+/[\w.-]+$', repo.name):
                    raise ValueError(
                        f"Invalid repository name format in .storyteller/config.json: {repo.name}. "
                        "Expected 'owner/repo'"
                    )
        
        # Validate log level
        valid_log_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid log level: {self.log_level}. "
                f"Must be one of: {', '.join(valid_log_levels)}"
            )
    
    def _validate_provider_config(self):
        """Validate LLM provider configuration."""
        valid_providers = {'openai', 'ollama', 'github'}
        
        if self.default_llm_provider not in valid_providers:
            raise ValueError(
                f"Unsupported LLM provider: {self.default_llm_provider}. "
                f"Supported values: {', '.join(valid_providers)}"
            )
        
        # Provider-specific validation
        if self.default_llm_provider == 'openai' and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        
        if self.default_llm_provider == 'ollama' and not self.ollama_api_host:
            raise ValueError("OLLAMA_API_HOST is required when using Ollama provider")
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> 'Config':
        """Create configuration from environment variables."""
        # Load environment variables
        if env_file:
            load_dotenv(env_file)
        else:
            # Try multiple common locations
            for path in [
                Path.cwd() / '.env',
                Path(__file__).parent.parent.parent / '.env',
                Path.home() / '.env'
            ]:
                if path.exists():
                    load_dotenv(path)
                    break
            else:
                load_dotenv()  # Load from environment
        
        return cls(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            github_token=os.getenv('GITHUB_TOKEN'),
            ollama_api_host=os.getenv('OLLAMA_API_HOST', 'http://localhost:11434'),
            github_repository=os.getenv('GITHUB_REPOSITORY'),
            default_llm_provider=os.getenv('DEFAULT_LLM_PROVIDER', 'github').lower(),
            log_level=os.getenv('LOG_LEVEL', 'INFO').upper(),
            max_retries=int(os.getenv('MAX_RETRIES', '3')),
            timeout_seconds=int(os.getenv('TIMEOUT_SECONDS', '30')),
            auto_consensus_enabled=os.getenv('AUTO_CONSENSUS_ENABLED', 'false').lower() == 'true',
            auto_consensus_threshold=int(os.getenv('AUTO_CONSENSUS_THRESHOLD', '70')),
            auto_consensus_max_iterations=int(os.getenv('AUTO_CONSENSUS_MAX_ITERATIONS', '10'))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        result = {
            'openai_api_key': '***' if self.openai_api_key else None,
            'github_token': '***' if self.github_token else None,
            'ollama_api_host': self.ollama_api_host,
            'github_repository': self.github_repository,
            'default_llm_provider': self.default_llm_provider,
            'log_level': self.log_level,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds,
            'auto_consensus_enabled': self.auto_consensus_enabled,
            'auto_consensus_threshold': self.auto_consensus_threshold,
            'auto_consensus_max_iterations': self.auto_consensus_max_iterations,
            'multi_repository_mode': self.is_multi_repository_mode(),
        }
        
        if self.is_multi_repository_mode():
            result['available_repositories'] = list(self.multi_repository_config.repositories.keys())
            result['default_repository'] = self.multi_repository_config.default_repository
        
        return result


def setup_logging(config: Config) -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {config.log_level} level")
    
    return logger


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
        logger = setup_logging(_config)
        logger.info(f"Configuration loaded: {_config.to_dict()}")
    return _config


# Backwards compatibility exports
config = get_config()
OPENAI_API_KEY = config.openai_api_key
GITHUB_TOKEN = config.github_token
OLLAMA_API_HOST = config.ollama_api_host
GITHUB_REPOSITORY = config.github_repository
DEFAULT_LLM_PROVIDER = config.default_llm_provider

# Example of how to use these variables in other modules:
# from .config import OPENAI_API_KEY, GITHUB_TOKEN
# print(f"OpenAI Key: {OPENAI_API_KEY}")
# print(f"GitHub Token: {GITHUB_TOKEN}")
