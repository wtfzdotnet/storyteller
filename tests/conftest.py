"""Pytest configuration and shared fixtures for Storyteller tests."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add src paths to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "src" / "storyteller"))

# Set dummy environment variables for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


@pytest.fixture
def temp_database():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    yield db_path

    # Cleanup
    if Path(db_path).exists():
        Path(db_path).unlink()


@pytest.fixture
def sample_epic_data():
    """Sample epic data for testing."""
    return {
        "title": "Test Epic",
        "description": "Test epic description",
        "business_value": "High value feature",
        "target_repositories": ["storyteller"],
        "estimated_story_points": 13,
    }


@pytest.fixture
def sample_user_story_data():
    """Sample user story data for testing."""
    return {
        "epic_id": "epic_123",
        "title": "Test User Story",
        "description": "As a user, I want...",
        "user_persona": "Test User",
        "user_goal": "Achieve something",
        "acceptance_criteria": ["AC 1", "AC 2"],
        "target_repositories": ["backend"],
        "story_points": 5,
    }


@pytest.fixture
def sample_sub_story_data():
    """Sample sub-story data for testing."""
    return {
        "user_story_id": "user_story_123",
        "title": "Backend API Implementation",
        "description": "Implement REST API",
        "department": "backend",
        "technical_requirements": ["Req 1", "Req 2"],
        "dependencies": ["sub_story_456"],
        "target_repository": "backend",
        "estimated_hours": 16.5,
    }


@pytest.fixture
def mock_github_config():
    """Mock GitHub configuration for testing."""
    from config import Config

    return Config(
        github_token="test_token",
        default_llm_provider="github",
        debug_mode=True,
    )


@pytest.fixture
def conversation_participant():
    """Basic conversation participant for testing."""
    from models import ConversationParticipant

    return ConversationParticipant(name="Test", role="developer")


@pytest.fixture
def test_message():
    """Basic message for testing."""
    from models import Message

    return Message(
        content="Test message",
        sender="test_sender",
        timestamp="2024-01-01T00:00:00Z",
    )
