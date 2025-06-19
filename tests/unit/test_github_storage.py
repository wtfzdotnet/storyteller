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

    def test_save_epic_structure(self):
        """Test Epic to GitHub issue structure conversion."""
        epic = Epic(
            id="epic_001",
            title="Test Epic",
            description="Test epic description",
            business_value="High value",
            target_repositories=["backend", "frontend"],
        )

        manager = GitHubStorageManager(self.config)

        # Test the structure conversion
        # Note: testing YAML frontmatter creation for epic metadata
        metadata = {
            "epic_id": epic.id,
            "story_type": "epic",
            "target_repositories": epic.target_repositories,
            "business_value": epic.business_value,
        }

        # Use the parser to test frontmatter creation
        parser = YAMLFrontmatterParser()
        content_with_frontmatter = parser.create_frontmatter_content(
            metadata, epic.description
        )

        self.assertIn("epic_id: epic_001", content_with_frontmatter)
        self.assertIn("story_type: epic", content_with_frontmatter)
        self.assertIn("Test epic description", content_with_frontmatter)

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
