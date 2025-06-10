"""Basic tests for the AI Story Management System."""

import asyncio
import os
from pathlib import Path

from config import Config, get_config, load_role_files
from story_manager import StoryManager, StoryRequest


def test_config_loading():
    """Test configuration loading."""
    # Set a dummy GitHub token for testing
    os.environ["GITHUB_TOKEN"] = "test_token"

    try:
        config = get_config()
        assert config.github_token == "test_token"
        assert config.default_llm_provider == "github"
    finally:
        # Clean up
        if hasattr(get_config, "_config"):
            delattr(get_config, "_config")


def test_role_files_loading():
    """Test loading role definition files."""
    roles = load_role_files()

    # Should load roles from .storyteller/roles/
    assert isinstance(roles, dict)
    assert len(roles) > 0

    # Check for specific roles
    assert "system-architect" in roles
    assert "lead-developer" in roles
    assert "ai-expert" in roles


def test_story_manager_initialization():
    """Test story manager initialization."""
    # Set dummy environment for testing
    os.environ["GITHUB_TOKEN"] = "test_token"

    try:
        story_manager = StoryManager()
        assert story_manager is not None
        assert story_manager.processor is not None

        # Test available roles
        roles = story_manager.get_available_roles()
        assert isinstance(roles, list)
        assert len(roles) > 0

        # Test available repositories
        repos = story_manager.get_available_repositories()
        assert isinstance(repos, dict)

    finally:
        # Clean up
        if hasattr(get_config, "_config"):
            delattr(get_config, "_config")


def test_story_request_creation():
    """Test story request data structure."""
    story_request = StoryRequest(
        content="Test user story for recipe management",
        target_repositories=["backend"],
        required_roles=["system-architect", "lead-developer"],
        context={"priority": "high"},
    )

    assert story_request.content == "Test user story for recipe management"
    assert story_request.target_repositories == ["backend"]
    assert story_request.required_roles == ["system-architect", "lead-developer"]
    assert story_request.context["priority"] == "high"


async def test_story_content_analysis():
    """Test story content analysis (without actual API calls)."""
    # Set dummy environment for testing
    os.environ["GITHUB_TOKEN"] = "test_token"

    try:
        story_manager = StoryManager()

        # This would normally make an API call, but we'll just test structure
        # In a real test, we'd mock the LLM response
        story_content = "Create a user authentication system for the recipe platform"

        # Test the story processor has the analyze method
        assert hasattr(story_manager.processor, "analyze_story_content")
        assert hasattr(story_manager.processor, "get_expert_analysis")

    finally:
        # Clean up
        if hasattr(get_config, "_config"):
            delattr(get_config, "_config")


if __name__ == "__main__":
    # Run basic tests
    print("Running basic tests...")

    test_config_loading()
    print("✓ Config loading test passed")

    test_role_files_loading()
    print("✓ Role files loading test passed")

    test_story_manager_initialization()
    print("✓ Story manager initialization test passed")

    test_story_request_creation()
    print("✓ Story request creation test passed")

    asyncio.run(test_story_content_analysis())
    print("✓ Story content analysis test passed")

    print("\n✅ All basic tests passed!")
