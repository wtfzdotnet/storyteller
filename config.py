import os
import logging
import re
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration class for AI Jules application."""
    
    # API Keys
    openai_api_key: Optional[str] = None
    github_token: Optional[str] = None
    
    # Endpoints
    ollama_api_host: str = "http://localhost:11434"
    
    # GitHub Configuration
    github_repository: Optional[str] = None
    
    # LLM Configuration
    default_llm_provider: str = "github"
    
    # Runtime Configuration
    log_level: str = "INFO"
    max_retries: int = 3
    timeout_seconds: int = 30
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_required_fields()
        self._validate_formats()
        self._validate_provider_config()
    
    def _validate_required_fields(self):
        """Validate required configuration fields."""
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN is required")
        
        if not self.github_repository:
            raise ValueError("GITHUB_REPOSITORY is required")
    
    def _validate_formats(self):
        """Validate format of configuration values."""
        # Validate GitHub repository format
        if not re.match(r'^[\w.-]+/[\w.-]+$', self.github_repository):
            raise ValueError(
                f"Invalid GITHUB_REPOSITORY format: {self.github_repository}. "
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
            timeout_seconds=int(os.getenv('TIMEOUT_SECONDS', '30'))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'openai_api_key': '***' if self.openai_api_key else None,
            'github_token': '***' if self.github_token else None,
            'ollama_api_host': self.ollama_api_host,
            'github_repository': self.github_repository,
            'default_llm_provider': self.default_llm_provider,
            'log_level': self.log_level,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds
        }


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
