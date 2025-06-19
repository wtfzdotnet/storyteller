"""Unit tests for GitHub storage manager."""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from config import Config, StorageConfig
from github_storage import (
    GitHubIssueMetadata,
    GitHubStorageManager,
)
from github_storage import StorageConfig as GSStorageConfig
from github_storage import (
    YAMLFrontmatterParser,
)
from models import Epic, StoryStatus, StoryType, SubStory, UserStory
from story_manager import StoryAnalysis


class TestYAMLFrontmatterParser(unittest.TestCase):
    """Test YAML frontmatter parsing functionality."""

    def setUp(self):
        self.parser = YAMLFrontmatterParser()

    def test_extract_frontmatter_valid(self):
        """Test extracting valid YAML frontmatter."""
        content = """---
epic_id: epic_001
story_type: epic
status: draft
target_repositories:
  - backend
  - frontend
---

# Epic: Test Epic
This is the epic description."""

        frontmatter, remaining = self.parser.extract_frontmatter(content)

        self.assertEqual(frontmatter["epic_id"], "epic_001")
        self.assertEqual(frontmatter["story_type"], "epic")
        self.assertEqual(frontmatter["status"], "draft")
        self.assertEqual(frontmatter["target_repositories"], ["backend", "frontend"])
        self.assertTrue(remaining.startswith("# Epic: Test Epic"))

    def test_extract_frontmatter_none(self):
        """Test content without frontmatter."""
        content = "# Regular Content\nJust regular content."

        frontmatter, remaining = self.parser.extract_frontmatter(content)

        self.assertEqual(frontmatter, {})
        self.assertEqual(remaining, content)

    def test_extract_frontmatter_invalid_yaml(self):
        """Test handling invalid YAML frontmatter."""
        content = """---
invalid: yaml: content[
---

# Content"""

        frontmatter, remaining = self.parser.extract_frontmatter(content)

        self.assertEqual(frontmatter, {})
        self.assertEqual(remaining, content)

    def test_create_frontmatter_content(self):
        """Test creating content with frontmatter."""
        metadata = {
            "epic_id": "epic_001",
            "story_type": "epic",
            "target_repositories": ["backend"],
        }
        content = "# Epic Title\nEpic description"

        result = self.parser.create_frontmatter_content(metadata, content)

        self.assertTrue(result.startswith("---\n"))
        self.assertIn("epic_id: epic_001", result)
        self.assertIn("story_type: epic", result)
        self.assertIn("# Epic Title", result)

    def test_create_frontmatter_empty_metadata(self):
        """Test creating content with empty metadata."""
        content = "# Epic Title\nEpic description"

        result = self.parser.create_frontmatter_content({}, content)

        self.assertEqual(result, content)


class TestGitHubStorageManager(unittest.TestCase):
    """Test GitHub storage manager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.config = Config(
            github_token="test_token",
            github_repository="test/repo",
            storage=GSStorageConfig(
                primary="github", cache_enabled=False, deployment_context="pipeline"
            ),
        )

    @patch("github_storage.GitHubHandler")
    def test_init_ephemeral_mode(self, mock_github_handler):
        """Test initialization in ephemeral mode."""
        storage_config = GSStorageConfig(
            primary="github", cache_enabled=False, deployment_context="pipeline"
        )

        manager = GitHubStorageManager(self.config, storage_config)

        self.assertIsNotNone(manager.github_handler)
        self.assertIsNone(manager._sqlite_cache)

    @patch("github_storage.GitHubHandler")
    def test_init_persistent_mode_with_cache(self, mock_github_handler_class):
        """Test initialization in persistent mode with cache."""
        storage_config = GSStorageConfig(
            primary="github", cache_enabled=True, deployment_context="mcp"
        )

        manager = GitHubStorageManager(self.config, storage_config)

        self.assertIsNotNone(manager.github_handler)
        # The cache might be None if DatabaseManager is not available, which is fine
        # This test just ensures no exception is thrown during initialization

    @patch("github_storage.GitHubHandler")
    @pytest.mark.asyncio
    async def test_save_epic(self, mock_github_handler_class):
        """Test saving an Epic to GitHub."""
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler

        mock_issue = MagicMock()
        mock_issue.number = 123
        mock_issue.repository.full_name = "test/repo"
        mock_handler.create_issue.return_value = mock_issue

        # Create manager and test Epic
        manager = GitHubStorageManager(self.config)
        epic = Epic(
            id="epic_001",
            title="Test Epic",
            description="Test epic description",
            business_value="High value",
            target_repositories=["backend", "frontend"],
        )

        # Test save operation
        result = await manager.save_epic(epic)

        # Verify issue creation was called
        mock_handler.create_issue.assert_called_once()
        call_args = mock_handler.create_issue.call_args[0][0]  # IssueData

        self.assertEqual(call_args.title, "Epic: Test Epic")
        self.assertIn("storyteller", call_args.labels)
        self.assertIn("epic", call_args.labels)
        self.assertIn("epic_id: epic_001", call_args.body)
        self.assertIn("story_type: epic", call_args.body)
        self.assertEqual(result, mock_issue)

    @patch("github_storage.GitHubHandler")
    @pytest.mark.asyncio
    async def test_save_user_story(self, mock_github_handler_class):
        """Test saving a User Story to GitHub."""
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler

        mock_issue = MagicMock()
        mock_issue.number = 124
        mock_issue.repository.full_name = "test/repo"
        mock_handler.create_issue.return_value = mock_issue

        # Create manager and test User Story
        manager = GitHubStorageManager(self.config)
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

        self.assertEqual(call_args.title, "User Story: Test User Story")
        self.assertIn("storyteller", call_args.labels)
        self.assertIn("user-story", call_args.labels)
        self.assertIn("user_story_id: story_001", call_args.body)
        self.assertIn("epic_id: epic_001", call_args.body)
        self.assertEqual(result, mock_issue)

    @patch("github_storage.GitHubHandler")
    @pytest.mark.asyncio
    async def test_save_sub_story(self, mock_github_handler_class):
        """Test saving a Sub-Story to GitHub."""
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler

        mock_issue = MagicMock()
        mock_issue.number = 125
        mock_issue.repository.full_name = "test/repo"
        mock_handler.create_issue.return_value = mock_issue

        # Create manager and test Sub-Story
        manager = GitHubStorageManager(self.config)
        sub_story = SubStory(
            id="substory_001",
            user_story_id="story_001",
            title="Test Sub-Story",
            description="Test sub-story description",
            department="frontend",
            target_repository="frontend",
            assignee="developer@example.com",
        )

        # Test save operation
        result = await manager.save_sub_story(sub_story)

        # Verify issue creation was called
        mock_handler.create_issue.assert_called_once()
        call_args = mock_handler.create_issue.call_args[0][0]  # IssueData

        self.assertEqual(call_args.title, "Sub-Story (frontend): Test Sub-Story")
        self.assertIn("storyteller", call_args.labels)
        self.assertIn("sub-story", call_args.labels)
        self.assertIn("department:frontend", call_args.labels)
        self.assertIn("sub_story_id: substory_001", call_args.body)
        self.assertIn("user_story_id: story_001", call_args.body)
        self.assertEqual(call_args.assignees, ["developer@example.com"])
        self.assertEqual(result, mock_issue)

    @patch("github_storage.GitHubHandler")
    @pytest.mark.asyncio
    async def test_save_expert_analysis(self, mock_github_handler_class):
        """Test saving expert analysis as a comment."""
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler

        # Create manager and test analysis
        manager = GitHubStorageManager(self.config)
        analysis = StoryAnalysis(
            role_name="system-architect",
            analysis="This is a well-structured epic.",
            recommendations=["Add security review", "Consider scalability"],
            concerns=["Performance impact", "Complexity"],
            metadata={"confidence_score": 85, "story_points": 5, "estimated_hours": 20},
        )

        # Test save operation
        await manager.save_expert_analysis(123, analysis, "test/repo")

        # Verify comment addition was called
        mock_handler.add_issue_comment.assert_called_once()
        call_args = mock_handler.add_issue_comment.call_args

        self.assertEqual(call_args[0][0], "test/repo")  # repository_name
        self.assertEqual(call_args[0][1], 123)  # issue_number
        comment_body = call_args[0][2]  # comment

        self.assertIn("Expert Analysis: system-architect", comment_body)
        self.assertIn("**confidence_score**: 85", comment_body)
        self.assertIn("This is a well-structured epic.", comment_body)
        self.assertIn("Add security review", comment_body)
        self.assertIn("Performance impact", comment_body)

    @patch("github_storage.GitHubHandler")
    @pytest.mark.asyncio
    async def test_parse_epic_from_issue(self, mock_github_handler_class):
        """Test parsing an Epic from a GitHub issue."""
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler

        # Create mock issue
        mock_issue = MagicMock()
        mock_issue.number = 123
        mock_issue.title = "Epic: Test Epic"
        mock_issue.body = """---
epic_id: epic_001
story_type: epic
status: draft
business_value: High value
target_repositories:
  - backend
  - frontend
acceptance_criteria:
  - Feature works correctly
  - Performance is acceptable
created_at: '2024-01-01T00:00:00+00:00'
updated_at: '2024-01-01T00:00:00+00:00'
metadata: {}
---

# Epic: Test Epic
This is the epic description with detailed requirements."""
        mock_issue.created_at = datetime.now(timezone.utc)
        mock_issue.updated_at = datetime.now(timezone.utc)
        mock_issue.repository.full_name = "test/repo"
        mock_issue.html_url = "https://github.com/test/repo/issues/123"

        # Create manager and test parsing
        manager = GitHubStorageManager(self.config)
        epic = await manager._parse_epic_from_issue(mock_issue)

        # Verify parsing results
        self.assertIsNotNone(epic)
        self.assertEqual(epic.id, "epic_001")
        self.assertEqual(epic.title, "Test Epic")
        self.assertEqual(
            epic.description, "This is the epic description with detailed requirements."
        )
        self.assertEqual(epic.status, StoryStatus.DRAFT)
        self.assertEqual(epic.business_value, "High value")
        self.assertEqual(epic.target_repositories, ["backend", "frontend"])
        self.assertEqual(
            epic.acceptance_criteria,
            ["Feature works correctly", "Performance is acceptable"],
        )
        self.assertEqual(epic.metadata["github_issue_number"], 123)
        self.assertEqual(epic.metadata["github_repository"], "test/repo")

    @patch("github_storage.GitHubHandler")
    @pytest.mark.asyncio
    async def test_parse_epic_from_issue_invalid(self, mock_github_handler_class):
        """Test parsing from an invalid issue."""
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler

        # Create mock issue without proper frontmatter
        mock_issue = MagicMock()
        mock_issue.number = 123
        mock_issue.title = "Regular Issue"
        mock_issue.body = "Just a regular issue without frontmatter."
        mock_issue.created_at = datetime.now(timezone.utc)
        mock_issue.updated_at = datetime.now(timezone.utc)

        # Create manager and test parsing
        manager = GitHubStorageManager(self.config)
        epic = await manager._parse_epic_from_issue(mock_issue)

        # Should return None for invalid issue
        self.assertIsNone(epic)

    def test_extract_title_from_content(self):
        """Test extracting title from content."""
        manager = GitHubStorageManager(self.config)

        content = "# Epic: Test Title\nSome description here"
        title = manager._extract_title_from_content(content)
        self.assertEqual(title, "Epic: Test Title")

        content_no_title = "Just some content without a title"
        title = manager._extract_title_from_content(content_no_title)
        self.assertIsNone(title)

    def test_extract_description_from_content(self):
        """Test extracting description from content."""
        manager = GitHubStorageManager(self.config)

        content = """# Epic: Test Title

This is the description
with multiple lines.

And paragraphs."""

        description = manager._extract_description_from_content(content)
        expected = """This is the description
with multiple lines.

And paragraphs."""
        self.assertEqual(description, expected)

    def test_format_expert_analysis_comment(self):
        """Test formatting expert analysis as a comment."""
        manager = GitHubStorageManager(self.config)

        analysis = StoryAnalysis(
            role_name="system-architect",
            analysis="Detailed analysis",
            recommendations=["Rec 1", "Rec 2"],
            concerns=["Concern 1"],
            metadata={"story_points": 3, "estimated_hours": 12},
        )

        comment = manager._format_expert_analysis_comment(analysis)

        self.assertIn("Expert Analysis: system-architect", comment)
        self.assertIn("Detailed analysis", comment)
        self.assertIn("- Rec 1", comment)
        self.assertIn("- Concern 1", comment)
        self.assertIn("**story_points**: 3", comment)
        self.assertIn("**estimated_hours**: 12", comment)


if __name__ == "__main__":
    unittest.main()
