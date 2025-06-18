"""Unit tests for webhook handler pipeline integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/storyteller'))

from config import Config
from models import PipelineFailure, PipelineRun, PipelineStatus, FailureCategory, FailureSeverity
from webhook_handler import WebhookHandler


class TestWebhookHandlerPipeline:
    """Test pipeline monitoring integration in WebhookHandler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(
            github_token="test_token",
            repositories={},
            default_repository="test",
        )
        
        # Mock dependencies
        with patch('webhook_handler.DatabaseManager') as mock_db, \
             patch('webhook_handler.PipelineMonitor') as mock_monitor:
            self.handler = WebhookHandler(self.config)
            self.mock_db = mock_db.return_value
            self.mock_monitor = mock_monitor.return_value

    @pytest.mark.asyncio
    async def test_handle_workflow_run_event_success(self):
        """Test handling successful workflow run event."""
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": "12345",
                "conclusion": "success"
            },
            "repository": {
                "full_name": "test/repo"
            }
        }
        
        # Mock successful pipeline processing
        mock_pipeline_run = PipelineRun(
            id="run_12345",
            repository="test/repo",
            status=PipelineStatus.SUCCESS,
            failures=[]
        )
        self.mock_monitor.process_pipeline_event.return_value = mock_pipeline_run
        
        result = await self.handler._handle_workflow_run_event(
            "workflow_run.completed", payload, "test/repo"
        )
        
        assert result["status"] == "processed"
        assert result["pipeline_status"] == "success"
        assert result["failure_count"] == 0
        assert result["notification_sent"] == False

    @pytest.mark.asyncio
    async def test_handle_workflow_run_event_failure(self):
        """Test handling failed workflow run event."""
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": "12345",
                "conclusion": "failure"
            },
            "repository": {
                "full_name": "test/repo"
            }
        }
        
        # Mock failed pipeline with failures
        mock_failures = [
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.TESTING,
                severity=FailureSeverity.HIGH,
                job_name="test",
                failure_message="Test failed"
            )
        ]
        mock_pipeline_run = PipelineRun(
            id="run_12345",
            repository="test/repo",
            status=PipelineStatus.FAILURE,
            failures=mock_failures
        )
        self.mock_monitor.process_pipeline_event.return_value = mock_pipeline_run
        
        # Mock notification handling
        with patch.object(self.handler, '_handle_pipeline_failures') as mock_handle_failures:
            mock_handle_failures.return_value = {"notification_sent": True, "issues_notified": [1]}
            
            result = await self.handler._handle_workflow_run_event(
                "workflow_run.completed", payload, "test/repo"
            )
        
        assert result["status"] == "processed"
        assert result["pipeline_status"] == "failure"
        assert result["failure_count"] == 1
        assert result["notification_sent"] == True

    @pytest.mark.asyncio
    async def test_handle_workflow_run_event_processing_error(self):
        """Test handling workflow run event when processing fails."""
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": "12345",
                "conclusion": "failure"
            },
            "repository": {
                "full_name": "test/repo"
            }
        }
        
        # Mock processing failure
        self.mock_monitor.process_pipeline_event.return_value = None
        
        result = await self.handler._handle_workflow_run_event(
            "workflow_run.completed", payload, "test/repo"
        )
        
        assert result["status"] == "ignored"
        assert result["reason"] == "failed to process pipeline event"

    def test_should_notify_agent_no_failures(self):
        """Test notification decision with no failures."""
        pipeline_run = PipelineRun(
            repository="test/repo",
            failures=[]
        )
        
        should_notify = self.handler._should_notify_agent(pipeline_run)
        
        assert should_notify == False

    def test_should_notify_agent_high_severity(self):
        """Test notification decision with high severity failures."""
        failures = [
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.TESTING,
                severity=FailureSeverity.HIGH,
                job_name="test",
                failure_message="Critical test failure"
            )
        ]
        pipeline_run = PipelineRun(
            repository="test/repo",
            failures=failures
        )
        
        should_notify = self.handler._should_notify_agent(pipeline_run)
        
        assert should_notify == True

    def test_should_notify_agent_repeated_failures(self):
        """Test notification decision with repeated failures."""
        failures = [
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.LINTING,
                severity=FailureSeverity.MEDIUM,
                retry_count=3,  # High retry count
                job_name="lint",
                failure_message="Repeated linting error"
            )
        ]
        pipeline_run = PipelineRun(
            repository="test/repo",
            failures=failures
        )
        
        should_notify = self.handler._should_notify_agent(pipeline_run)
        
        assert should_notify == True

    def test_should_notify_agent_low_severity_no_retries(self):
        """Test notification decision with low severity, no retries."""
        failures = [
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.FORMATTING,
                severity=FailureSeverity.LOW,
                retry_count=0,
                job_name="format",
                failure_message="Minor formatting issue"
            )
        ]
        pipeline_run = PipelineRun(
            repository="test/repo",
            failures=failures
        )
        
        should_notify = self.handler._should_notify_agent(pipeline_run)
        
        assert should_notify == False

    def test_create_failure_notification(self):
        """Test creation of failure notification message."""
        failures = [
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.LINTING,
                severity=FailureSeverity.MEDIUM,
                job_name="lint",
                failure_message="flake8 error: E401 multiple imports"
            ),
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.TESTING,
                severity=FailureSeverity.HIGH,
                job_name="test",
                failure_message="Test assertion failed"
            )
        ]
        pipeline_run = PipelineRun(
            id="run_12345",
            repository="test/repo",
            branch="main",
            commit_sha="abc123def456",
            workflow_name="CI/CD Pipeline",
            failures=failures
        )
        
        notification = self.handler._create_failure_notification(pipeline_run)
        
        # Check that notification contains expected content
        assert "🚨 Pipeline Failure Detected" in notification
        assert "test/repo" in notification
        assert "main" in notification
        assert "abc123de" in notification  # Truncated commit SHA
        assert "CI/CD Pipeline" in notification
        assert "Linting Issues:" in notification
        assert "Testing Issues:" in notification
        assert "@copilot" in notification
        assert "Failure Count: 2" in notification

    @pytest.mark.asyncio
    async def test_find_related_issues_with_issues(self):
        """Test finding related issues when issues exist."""
        pipeline_run = PipelineRun(
            repository="test/repo",
            branch="main"
        )
        
        # Mock GitHub handler to return issues
        mock_issue = MagicMock()
        mock_issue.number = 42
        self.mock_monitor.github_handler.list_issues.return_value = [mock_issue]
        
        issues = await self.handler._find_related_issues(pipeline_run, "test/repo")
        
        assert issues == [42]

    @pytest.mark.asyncio
    async def test_find_related_issues_no_issues(self):
        """Test finding related issues when no issues exist."""
        pipeline_run = PipelineRun(
            repository="test/repo",
            branch="main"
        )
        
        # Mock GitHub handler to return no issues
        self.mock_monitor.github_handler.list_issues.return_value = []
        
        issues = await self.handler._find_related_issues(pipeline_run, "test/repo")
        
        assert issues == []

    @pytest.mark.asyncio
    async def test_handle_pipeline_failures_with_notification(self):
        """Test handling pipeline failures that trigger notification."""
        failures = [
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.TESTING,
                severity=FailureSeverity.HIGH,
                job_name="test",
                failure_message="Critical test failure"
            )
        ]
        pipeline_run = PipelineRun(
            repository="test/repo",
            failures=failures
        )
        
        # Mock related issues and comment addition
        with patch.object(self.handler, '_find_related_issues') as mock_find_issues:
            mock_find_issues.return_value = [42]
            self.mock_monitor.github_handler.add_issue_comment = AsyncMock()
            
            result = await self.handler._handle_pipeline_failures(pipeline_run, "test/repo")
        
        assert result is not None
        assert result["notification_sent"] == True
        assert result["issues_notified"] == [42]
        assert result["failure_count"] == 1
        
        # Verify comment was added
        self.mock_monitor.github_handler.add_issue_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_pipeline_failures_no_notification(self):
        """Test handling pipeline failures that don't trigger notification."""
        failures = [
            PipelineFailure(
                repository="test/repo",
                category=FailureCategory.FORMATTING,
                severity=FailureSeverity.LOW,
                retry_count=0,
                job_name="format",
                failure_message="Minor formatting issue"
            )
        ]
        pipeline_run = PipelineRun(
            repository="test/repo",
            failures=failures
        )
        
        result = await self.handler._handle_pipeline_failures(pipeline_run, "test/repo")
        
        assert result is None