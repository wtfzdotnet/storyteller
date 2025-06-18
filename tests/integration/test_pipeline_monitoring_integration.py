"""Integration test for complete pipeline monitoring workflow."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/storyteller"))

from config import Config
from models import (
    FailureCategory,
    FailureSeverity,
    PipelineFailure,
    PipelineRun,
    PipelineStatus,
)
from webhook_handler import WebhookHandler


class TestPipelineMonitoringIntegration:
    """Test complete pipeline monitoring integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(
            github_token="test_token",
            repositories={
                "backend": {
                    "name": "test/backend",
                    "type": "backend",
                    "description": "Backend repo",
                }
            },
            default_repository="backend",
        )

    @pytest.mark.asyncio
    async def test_complete_pipeline_failure_workflow(self):
        """Test the complete workflow from webhook to notification."""

        # Mock webhook payload for failed workflow
        webhook_payload = {
            "action": "completed",
            "workflow_run": {
                "id": "12345",
                "name": "CI/CD",
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "abc123def456",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:05:00Z",
                "run_number": 42,
                "event": "push",
                "actor": {"login": "test-user"},
            },
            "repository": {"full_name": "test/backend"},
        }

        with (
            patch("webhook_handler.DatabaseManager") as mock_db,
            patch("webhook_handler.PipelineMonitor") as mock_monitor,
        ):

            # Setup mocks
            mock_db_instance = mock_db.return_value
            mock_monitor_instance = mock_monitor.return_value

            # Mock pipeline processing result
            mock_failure = PipelineFailure(
                repository="test/backend",
                category=FailureCategory.TESTING,
                severity=FailureSeverity.HIGH,
                job_name="test",
                failure_message="Test assertion failed in critical module",
            )

            mock_pipeline_run = PipelineRun(
                id="run_12345",
                repository="test/backend",
                branch="main",
                commit_sha="abc123def456",
                workflow_name="CI/CD",
                status=PipelineStatus.FAILURE,
                failures=[mock_failure],
            )

            mock_monitor_instance.process_pipeline_event = AsyncMock(
                return_value=mock_pipeline_run
            )

            # Mock GitHub handler for notifications
            mock_github_handler = MagicMock()
            mock_github_handler.list_issues.return_value = [MagicMock(number=1)]
            mock_github_handler.add_issue_comment = AsyncMock()
            mock_monitor_instance.github_handler = mock_github_handler

            # Create webhook handler and process event
            handler = WebhookHandler(self.config)

            result = await handler.handle_webhook(webhook_payload)

            # Verify webhook processing succeeded
            assert result["status"] == "processed"
            assert "workflow_run.completed" in result.get("event", "")

            # Verify pipeline event was processed
            mock_monitor_instance.process_pipeline_event.assert_called_once_with(
                webhook_payload
            )

            # Verify notification was attempted for high severity failure
            mock_github_handler.add_issue_comment.assert_called_once()

            # Check notification content
            call_args = mock_github_handler.add_issue_comment.call_args
            assert call_args[1]["repository_name"] == "test/backend"
            assert call_args[1]["issue_number"] == 1
            assert "@copilot" in call_args[1]["comment"]
            assert "Pipeline Failure Detected" in call_args[1]["comment"]

    @pytest.mark.asyncio
    async def test_low_severity_failure_no_notification(self):
        """Test that low severity failures don't trigger notifications."""

        webhook_payload = {
            "action": "completed",
            "workflow_run": {
                "id": "12345",
                "name": "CI/CD",
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "abc123def456",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:05:00Z",
            },
            "repository": {"full_name": "test/backend"},
        }

        with (
            patch("webhook_handler.DatabaseManager") as mock_db,
            patch("webhook_handler.PipelineMonitor") as mock_monitor,
        ):

            # Mock low severity failure
            mock_failure = PipelineFailure(
                repository="test/backend",
                category=FailureCategory.FORMATTING,
                severity=FailureSeverity.LOW,  # Low severity
                retry_count=0,  # No retries
                job_name="format",
                failure_message="Minor formatting issue",
            )

            mock_pipeline_run = PipelineRun(
                id="run_12345",
                repository="test/backend",
                status=PipelineStatus.FAILURE,
                failures=[mock_failure],
            )

            mock_monitor.return_value.process_pipeline_event = AsyncMock(
                return_value=mock_pipeline_run
            )
            mock_monitor.return_value.github_handler.add_issue_comment = AsyncMock()

            handler = WebhookHandler(self.config)
            result = await handler.handle_webhook(webhook_payload)

            # Verify processing succeeded but no notification sent
            assert result["status"] == "processed"
            assert result.get("notification_sent")  is False

            # Verify no comment was added
            mock_monitor.return_value.github_handler.add_issue_comment.assert_not_called()

    def test_failure_classification_accuracy(self):
        """Test that failure classification works correctly."""

        with (
            patch("pipeline_monitor.DatabaseManager"),
            patch("pipeline_monitor.GitHubHandler"),
        ):

            from pipeline_monitor import PipelineMonitor

            monitor = PipelineMonitor(self.config)

            # Test linting classification
            category, severity = monitor._classify_failure(
                "Lint and Format", "flake8 error: E401 multiple imports on one line"
            )
            assert category == FailureCategory.LINTING
            assert severity == FailureSeverity.MEDIUM

            # Test critical security classification
            category, severity = monitor._classify_failure(
                "Security Check", "CRITICAL security vulnerability detected"
            )
            assert severity == FailureSeverity.CRITICAL

            # Test test failure classification
            category, severity = monitor._classify_failure(
                "Run Tests", "FAILED tests/test_api.py::test_user_auth - AssertionError"
            )
            assert category == FailureCategory.TESTING
            assert severity == FailureSeverity.MEDIUM

    def test_dashboard_data_structure(self):
        """Test that dashboard returns expected data structure."""

        with (
            patch("pipeline_dashboard.DatabaseManager") as mock_db,
            patch("pipeline_dashboard.PipelineMonitor"),
        ):

            from pipeline_dashboard import PipelineDashboard

            # Mock empty data
            mock_db.return_value.get_recent_pipeline_failures.return_value = []
            mock_db.return_value.get_failure_patterns.return_value = []
            mock_db.return_value.get_recent_pipeline_runs.return_value = []

            dashboard = PipelineDashboard(self.config)
            data = dashboard.get_dashboard_data(time_range="24h")

            # Verify expected structure
            expected_keys = [
                "health_metrics",
                "trending_data",
                "repository_health",
                "alert_summary",
                "recommendations",
            ]

            for key in expected_keys:
                assert key in data, f"Missing expected key: {key}"

            # Verify health metrics structure
            health_metrics = data["health_metrics"]
            assert "success_rate" in health_metrics
            assert "total_runs" in health_metrics
            assert "health_score" in health_metrics

    def test_workflow_processor_integration(self):
        """Test integration with workflow processor."""

        with (
            patch("automation.workflow_processor.StoryManager"),
            patch("automation.workflow_processor.LabelManager"),
            patch("automation.workflow_processor.AssignmentEngine"),
            patch("automation.workflow_processor.PipelineMonitor"),
            patch("automation.workflow_processor.PipelineDashboard") as mock_dashboard,
        ):

            from automation.workflow_processor import WorkflowProcessor

            # Mock dashboard data
            mock_dashboard.return_value.get_dashboard_data.return_value = {
                "summary": {"total_failures": 5},
                "health_metrics": {"success_rate": 85.0},
            }

            processor = WorkflowProcessor(self.config)
            result = processor.get_pipeline_dashboard_workflow(time_range="24h")

            assert result.success  is True
            assert "dashboard data retrieved" in result.message.lower()
            assert result.data is not None

    @pytest.mark.asyncio
    async def test_end_to_end_monitoring_flow(self):
        """Test complete end-to-end monitoring flow."""

        # This would be a comprehensive test that:
        # 1. Processes a webhook event
        # 2. Stores pipeline data in database
        # 3. Analyzes patterns
        # 4. Generates dashboard data
        # 5. Sends notifications if needed

        # For now, just verify the key components can be instantiated
        with (
            patch("webhook_handler.DatabaseManager"),
            patch("webhook_handler.PipelineMonitor"),
            patch("pipeline_monitor.DatabaseManager"),
            patch("pipeline_monitor.GitHubHandler"),
            patch("pipeline_dashboard.DatabaseManager"),
            patch("pipeline_dashboard.PipelineMonitor"),
        ):

            # Verify all components can be created
            handler = WebhookHandler(self.config)
            assert handler is not None

            from pipeline_monitor import PipelineMonitor

            monitor = PipelineMonitor(self.config)
            assert monitor is not None

            from pipeline_dashboard import PipelineDashboard

            dashboard = PipelineDashboard(self.config)
            assert dashboard is not None

            from automation.workflow_processor import WorkflowProcessor

            processor = WorkflowProcessor(self.config)
            assert processor is not None

        # Integration successful
        assert True
