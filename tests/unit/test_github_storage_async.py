"""Async unit tests for GitHub storage manager."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from config import Config
from github_storage import (
    GitHubStorageManager,
)
from github_storage import StorageConfig as GSStorageConfig
from models import Epic, StoryStatus, StoryType, SubStory, UserStory
from story_manager import StoryAnalysis


@pytest.fixture
def config():
    """Create test configuration."""
    return Config(
        storage=GSStorageConfig(
            primary="github",
            cache_enabled=False,
            deployment_context="pipeline",
        ),
        github_token="test_token",
        github_repository="test/repo",
    )


@pytest.mark.asyncio
@patch("github_storage.GitHubHandler")
async def test_save_user_story(mock_github_handler_class, config):
    """Test saving a User Story to GitHub."""
    # Setup mocks
    mock_handler = AsyncMock()
    mock_github_handler_class.return_value = mock_handler

    mock_issue = MagicMock()
    mock_issue.number = 124
    mock_issue.repository.full_name = "test/repo"
    mock_handler.create_issue.return_value = mock_issue

    # Create manager and test User Story
    manager = GitHubStorageManager(config)
    user_story = UserStory(
        id="story_001",
        epic_id="epic_001",
        title="Test User Story",
        description="Test user story description",
        user_persona="Developer",
        user_goal="Create feature",
        target_repositories=["backend"],
    )

    # Test save operation
    result = await manager.save_user_story(user_story)

    # Verify issue creation was called
    mock_handler.create_issue.assert_called_once()
    call_args = mock_handler.create_issue.call_args[0][0]  # IssueData

    assert call_args.title == "User Story: Test User Story"
    assert "storyteller" in call_args.labels
    assert "user-story" in call_args.labels
    assert "epic_001" in call_args.body  # Should contain epic_id in frontmatter
    assert result == mock_issue


@pytest.mark.asyncio
@patch("github_storage.GitHubHandler")
async def test_save_sub_story(mock_github_handler_class, config):
    """Test saving a Sub-Story to GitHub."""
    # Setup mocks
    mock_handler = AsyncMock()
    mock_github_handler_class.return_value = mock_handler

    mock_issue = MagicMock()
    mock_issue.number = 125
    mock_issue.repository.full_name = "test/repo"
    mock_handler.create_issue.return_value = mock_issue

    # Create manager and test Sub-Story
    manager = GitHubStorageManager(config)
    sub_story = SubStory(
        id="sub_001",
        user_story_id="story_001",
        title="Test Sub-Story",
        description="Test sub-story description",
        department="backend",
        target_repository="backend",
        status=StoryStatus.DRAFT,
    )

    # Test save operation
    result = await manager.save_sub_story(sub_story)

    # Verify issue creation was called
    mock_handler.create_issue.assert_called_once()
    call_args = mock_handler.create_issue.call_args[0][0]  # IssueData

    assert call_args.title == "Sub-Story (backend): Test Sub-Story"
    assert "storyteller" in call_args.labels
    assert "sub-story" in call_args.labels
    assert "department:backend" in call_args.labels
    assert "story_001" in call_args.body  # Should contain user_story_id in frontmatter
    assert result == mock_issue


@pytest.mark.asyncio
@patch("github_storage.GitHubHandler")
async def test_save_expert_analysis(mock_github_handler_class, config):
    """Test saving expert analysis as a comment."""
    # Setup mocks
    mock_handler = AsyncMock()
    mock_github_handler_class.return_value = mock_handler

    # Create manager and test analysis
    manager = GitHubStorageManager(config)
    analysis = StoryAnalysis(
        role_name="system-architect",
        analysis="This is a well-structured epic.",
        recommendations=["Add security review", "Consider performance"],
        concerns=["Performance impact", "Security considerations"],
    )

    # Test save operation
    await manager.save_expert_analysis(123, analysis, "test/repo")

    # Verify comment addition was called
    mock_handler.add_issue_comment.assert_called_once()
    call_args = mock_handler.add_issue_comment.call_args

    assert call_args[0][0] == "test/repo"  # repository_name
    assert call_args[0][1] == 123  # issue_number
    comment_body = call_args[0][2]  # comment

    assert "Expert Analysis: system-architect" in comment_body
    assert "This is a well-structured epic." in comment_body
    assert "Add security review" in comment_body
    assert "Performance impact" in comment_body


@pytest.mark.asyncio
@patch("github_storage.GitHubHandler")
async def test_parse_epic_from_issue(mock_github_handler_class, config):
    """Test parsing an Epic from a GitHub issue."""
    # Setup mocks
    mock_handler = AsyncMock()
    mock_github_handler_class.return_value = mock_handler

    mock_issue = MagicMock()
    mock_issue.number = 123
    mock_issue.title = "Epic: Test Epic"
    mock_issue.body = """---
epic_id: epic_001
story_type: epic
status: draft
target_repositories:
  - backend
  - frontend
business_value: High customer impact
acceptance_criteria:
  - Feature works correctly
  - Performance is acceptable
---

# Epic: Test Epic

This is a test epic with comprehensive feature set.

## Acceptance Criteria
- User can authenticate
- System is secure
- Performance meets requirements"""
    mock_issue.repository.full_name = "test/repo"
    mock_issue.created_at = datetime(2024, 1, 1, 0, 0, 0)
    mock_issue.updated_at = datetime(2024, 1, 1, 12, 0, 0)
    mock_issue.labels = [
        MagicMock(name="storyteller"),
        MagicMock(name="epic"),
    ]

    # Create manager
    manager = GitHubStorageManager(config)

    # Test parsing
    epic = await manager._parse_epic_from_issue(mock_issue)

    assert epic.id == "epic_001"
    assert epic.title == "Epic: Test Epic"
    assert epic.status.value == "draft"  # Use .value for enum comparison
    assert epic.target_repositories == ["backend", "frontend"]
    assert "High customer impact" in epic.business_value
    assert len(epic.acceptance_criteria) == 2
    assert "Feature works correctly" in epic.acceptance_criteria
    assert epic.metadata["github_issue_number"] == 123
    assert epic.metadata["github_repository"] == "test/repo"


@pytest.mark.asyncio
@patch("github_storage.GitHubHandler")
async def test_parse_epic_from_issue_invalid(mock_github_handler_class, config):
    """Test parsing from an invalid issue."""
    # Setup mocks
    mock_handler = AsyncMock()
    mock_github_handler_class.return_value = mock_handler

    mock_issue = MagicMock()
    mock_issue.number = 456
    mock_issue.title = "Regular Issue: Not a Story"
    mock_issue.body = "This is just a regular issue without frontmatter."
    mock_issue.repository.full_name = "test/repo"
    mock_issue.labels = [MagicMock(name="bug")]

    # Create manager
    manager = GitHubStorageManager(config)

    # Test parsing - should return None for non-story issues
    epic = await manager._parse_epic_from_issue(mock_issue)

    assert epic is None
