"""Integration tests for cross-repository progress tracking with GitHub."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from config import Config
from github_handler import GitHubHandler
from models import Epic


class TestCrossRepositoryGitHubIntegration(unittest.TestCase):
    """Test GitHub integration for cross-repository progress tracking."""

    def setUp(self):
        """Set up test environment."""
        self.config = Config(github_token="test_token")
        self.github_handler = GitHubHandler(self.config)

        self.epic = Epic(
            id="epic_test123",
            title="Test Epic for Cross-Repo Progress",
            target_repositories=["owner/backend", "owner/frontend"],
        )

    @patch("github_handler.Github")
    def test_get_cross_repository_progress_data(self, mock_github):
        """Test fetching cross-repository progress data."""

        async def run_test():
            # Mock GitHub API responses
            mock_repo = MagicMock()
            mock_issue = MagicMock()
            mock_issue.number = 1
            mock_issue.title = "Feature: User Authentication (epic_test123)"
            mock_issue.state = "closed"
            mock_issue.created_at = MagicMock()
            mock_issue.updated_at = MagicMock()
            mock_issue.assignee = None
            mock_issue.labels = []

            mock_repo.get_issues.return_value = [mock_issue]
            self.github_handler.get_repository = MagicMock(return_value=mock_repo)

            # Test the method
            progress_data = (
                await self.github_handler.get_cross_repository_progress_data(
                    self.epic.id, ["owner/backend", "owner/frontend"]
                )
            )

            # Verify structure
            self.assertIn("epic_id", progress_data)
            self.assertIn("repositories", progress_data)
            self.assertIn("issues_by_repository", progress_data)
            self.assertIn("last_updated", progress_data)

            # Verify repositories
            self.assertIn("owner/backend", progress_data["repositories"])
            self.assertIn("owner/frontend", progress_data["repositories"])

            # Verify progress data structure
            for repo_name in ["owner/backend", "owner/frontend"]:
                repo_data = progress_data["repositories"][repo_name]
                self.assertIn("total_issues", repo_data)
                self.assertIn("closed_issues", repo_data)
                self.assertIn("open_issues", repo_data)
                self.assertIn("progress_percentage", repo_data)
                self.assertIn("status", repo_data)

        asyncio.run(run_test())

    @patch("github_handler.Github")
    def test_enable_real_time_progress_tracking(self, mock_github):
        """Test enabling real-time progress tracking."""

        async def run_test():
            repositories = ["owner/backend", "owner/frontend"]
            webhook_url = "https://api.example.com/webhooks/progress"

            tracking_config = (
                await self.github_handler.enable_real_time_progress_tracking(
                    self.epic.id, repositories, webhook_url
                )
            )

            # Verify tracking configuration
            self.assertEqual(tracking_config["epic_id"], self.epic.id)
            self.assertEqual(tracking_config["repositories"], repositories)
            self.assertEqual(tracking_config["webhook_url"], webhook_url)
            self.assertTrue(tracking_config["enabled"])
            self.assertIn("tracking_events", tracking_config)
            self.assertIn("created_at", tracking_config)

        asyncio.run(run_test())

    @patch("github_handler.Github")
    def test_fetch_repository_progress_error_handling(self, mock_github):
        """Test error handling in repository progress fetching."""

        async def run_test():
            # Mock repository that raises an exception
            self.github_handler.get_repository = MagicMock(
                side_effect=Exception("Repository not found")
            )

            progress_data = (
                await self.github_handler.get_cross_repository_progress_data(
                    self.epic.id, ["owner/nonexistent"]
                )
            )

            # Verify error handling
            self.assertIn("owner/nonexistent", progress_data["repositories"])
            repo_data = progress_data["repositories"]["owner/nonexistent"]
            self.assertIn("error", repo_data)
            self.assertEqual(repo_data["status"], "error")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
