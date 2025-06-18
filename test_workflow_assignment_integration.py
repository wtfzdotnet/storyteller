"""Tests for workflow processor assignment integration."""

import unittest
from unittest.mock import AsyncMock, Mock, patch

from automation.workflow_processor import WorkflowProcessor
from config import Config


class TestWorkflowProcessorAssignment(unittest.TestCase):
    """Test workflow processor assignment functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a proper mock config
        self.config = Mock(spec=Config)
        self.config.github_token = "test_token"
        self.config.default_llm_provider = "github"
        self.config.repositories = {}

        # Mock the story manager to avoid complex initialization
        with patch("automation.workflow_processor.StoryManager") as mock_story_manager:
            mock_story_manager.return_value = Mock()
            with patch(
                "automation.workflow_processor.LabelManager"
            ) as mock_label_manager:
                mock_label_manager.return_value = Mock()
                self.processor = WorkflowProcessor(self.config)

    def test_processor_has_assignment_engine(self):
        """Test that workflow processor has assignment engine."""
        self.assertTrue(hasattr(self.processor, "assignment_engine"))
        self.assertIsNotNone(self.processor.assignment_engine)

    async def test_process_story_assignment_not_eligible(self):
        """Test processing assignment for non-eligible story."""

        async def run_test():
            story_id = "test_story_001"
            story_content = (
                "Redesign entire system architecture with complex security requirements"
            )

            result = await self.processor.process_story_assignment(
                story_id=story_id, story_content=story_content
            )

            self.assertTrue(result.success)
            self.assertFalse(result.data["assigned"])
            self.assertIn("complexity", result.data["reason"])

        await run_test()

    async def test_process_story_assignment_eligible(self):
        """Test processing assignment for eligible story."""

        async def run_test():
            story_id = "test_story_002"
            story_content = "Update button text on login page"

            result = await self.processor.process_story_assignment(
                story_id=story_id, story_content=story_content
            )

            self.assertTrue(result.success)
            self.assertTrue(result.data["assigned"])
            self.assertEqual(result.data["assignee"], "copilot-sve-agent")

        await run_test()

    async def test_process_story_assignment_manual_override(self):
        """Test processing assignment with manual override."""

        async def run_test():
            story_id = "test_story_003"
            story_content = "Complex architecture changes"

            result = await self.processor.process_story_assignment(
                story_id=story_id, story_content=story_content, manual_override=True
            )

            self.assertTrue(result.success)
            self.assertTrue(result.data["assigned"])
            self.assertEqual(result.data["assignee"], "copilot-sve-agent")
            self.assertEqual(result.data["reason"], "manual_override")

        await run_test()

    def test_get_assignment_queue_workflow(self):
        """Test getting assignment queue workflow."""
        # Process some assignments first
        import asyncio

        async def setup_assignments():
            await self.processor.process_story_assignment("story_1", "Simple task 1")
            await self.processor.process_story_assignment("story_2", "Simple task 2")

        asyncio.run(setup_assignments())

        result = self.processor.get_assignment_queue_workflow()

        self.assertTrue(result.success)
        self.assertIn("queue", result.data)
        self.assertIn("statistics", result.data)

    def test_get_assignment_statistics_workflow(self):
        """Test getting assignment statistics workflow."""
        result = self.processor.get_assignment_statistics_workflow()

        self.assertTrue(result.success)
        self.assertIn("total_processed", result.data)
        self.assertIn("assigned", result.data)
        self.assertIn("assignment_rate", result.data)

    async def test_assignment_with_github_integration(self):
        """Test assignment with GitHub issue integration."""

        async def run_test():
            # Mock GitHub handler
            mock_github_handler = AsyncMock()
            self.processor.story_manager.github_handler = mock_github_handler

            story_id = "test_story_004"
            story_content = "Add user validation"
            story_metadata = {
                "github_issues": [{"repository": "test-repo", "issue_number": 123}]
            }

            result = await self.processor.process_story_assignment(
                story_id=story_id,
                story_content=story_content,
                story_metadata=story_metadata,
            )

            self.assertTrue(result.success)
            self.assertTrue(result.data["assigned"])

            # Verify GitHub handler was called
            mock_github_handler.update_issue.assert_called_once()
            mock_github_handler.notify_assignment.assert_called_once()

        await run_test()


if __name__ == "__main__":
    unittest.main()
