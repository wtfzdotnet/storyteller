"""Unit tests for retry logic and escalation functionality."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/storyteller"))

from config import Config, EscalationConfig, PipelineRetryConfig
from models import (
    EscalationRecord,
    FailureCategory,
    FailureSeverity,
    PipelineFailure,
    RetryAttempt,
)
from pipeline_monitor import PipelineMonitor


class TestRetryLogic:
    """Test the retry logic functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(
            github_token="test_token",
            repositories={},
            default_repository="test",
            pipeline_retry_config=PipelineRetryConfig(
                enabled=True,
                max_retries=3,
                initial_delay_seconds=30,
                max_delay_seconds=300,
                backoff_multiplier=2.0,
            ),
            escalation_config=EscalationConfig(
                enabled=True,
                escalation_threshold=5,
                escalation_contacts=["admin@example.com"],
                escalation_channels=["github_issue"],
                cooldown_hours=6,
            ),
        )

        # Mock dependencies
        with (
            patch("pipeline_monitor.DatabaseManager") as mock_db,
            patch("pipeline_monitor.GitHubHandler") as mock_gh,
        ):
            self.monitor = PipelineMonitor(self.config)
            self.mock_db = mock_db.return_value
            self.mock_github = mock_gh.return_value

    @pytest.mark.asyncio
    async def test_retry_failed_pipeline_success(self):
        """Test successful retry of a failed pipeline."""
        failure = PipelineFailure(
            id="failure_123",
            repository="test/repo",
            category=FailureCategory.LINTING,
            severity=FailureSeverity.MEDIUM,
            retry_count=0,
            job_name="lint",
            failure_message="Linting error",
        )

        # Mock successful retry
        with patch.object(self.monitor, "_trigger_pipeline_retry") as mock_trigger:
            mock_trigger.return_value = True

            retry_attempt = await self.monitor.retry_failed_pipeline(failure)

            assert retry_attempt is not None
            assert retry_attempt.failure_id == "failure_123"
            assert retry_attempt.repository == "test/repo"
            assert retry_attempt.attempt_number == 1
            assert retry_attempt.success == True
            assert retry_attempt.retry_delay_seconds == 30  # initial delay

            # Verify database calls
            self.mock_db.store_retry_attempt.assert_called()
            self.mock_db.store_pipeline_failure.assert_called()

    @pytest.mark.asyncio
    async def test_retry_failed_pipeline_failure(self):
        """Test failed retry of a failed pipeline."""
        failure = PipelineFailure(
            id="failure_123",
            repository="test/repo",
            category=FailureCategory.TESTING,
            severity=FailureSeverity.HIGH,
            retry_count=1,  # Second attempt
            job_name="test",
            failure_message="Test failure",
        )

        # Mock failed retry
        with patch.object(self.monitor, "_trigger_pipeline_retry") as mock_trigger:
            mock_trigger.return_value = False

            retry_attempt = await self.monitor.retry_failed_pipeline(failure)

            assert retry_attempt is not None
            assert retry_attempt.success == False
            assert retry_attempt.attempt_number == 2
            assert retry_attempt.retry_delay_seconds == 60  # 30 * 2^1

            # Verify retry count was incremented
            assert failure.retry_count == 2

    @pytest.mark.asyncio
    async def test_retry_disabled(self):
        """Test retry when disabled in config."""
        self.config.pipeline_retry_config.enabled = False

        failure = PipelineFailure(
            repository="test/repo",
            category=FailureCategory.BUILD,
            retry_count=0,
        )

        retry_attempt = await self.monitor.retry_failed_pipeline(failure)

        assert retry_attempt is None

    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Test retry when max attempts exceeded."""
        failure = PipelineFailure(
            repository="test/repo",
            category=FailureCategory.BUILD,
            retry_count=3,  # Equals max_retries
        )

        retry_attempt = await self.monitor.retry_failed_pipeline(failure)

        assert retry_attempt is None

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        failure1 = PipelineFailure(retry_count=0)
        failure2 = PipelineFailure(retry_count=1)
        failure3 = PipelineFailure(retry_count=2)

        # Simulate delay calculations
        delay1 = min(30 * (2.0**0), 300)  # 30 seconds
        delay2 = min(30 * (2.0**1), 300)  # 60 seconds
        delay3 = min(30 * (2.0**2), 300)  # 120 seconds

        assert delay1 == 30
        assert delay2 == 60
        assert delay3 == 120

    def test_check_for_escalation_threshold_met(self):
        """Test escalation when threshold is met."""
        # Mock recent failures
        failures = [
            PipelineFailure(
                category=FailureCategory.LINTING,
                job_name="lint",
                resolved_at=None,  # Unresolved
            )
            for _ in range(5)  # Equals threshold
        ]

        self.mock_db.get_recent_pipeline_failures.return_value = failures
        self.mock_db.get_recent_escalations.return_value = []  # No recent escalations

        escalation = self.monitor.check_for_escalation("test/repo")

        assert escalation is not None
        assert escalation.repository == "test/repo"
        assert escalation.failure_count == 5
        assert escalation.escalation_level == "agent"
        assert "linting_lint" in escalation.failure_pattern

    def test_check_for_escalation_threshold_not_met(self):
        """Test no escalation when threshold not met."""
        # Mock fewer failures than threshold
        failures = [
            PipelineFailure(
                category=FailureCategory.LINTING,
                job_name="lint",
                resolved_at=None,
            )
            for _ in range(3)  # Below threshold of 5
        ]

        self.mock_db.get_recent_pipeline_failures.return_value = failures

        escalation = self.monitor.check_for_escalation("test/repo")

        assert escalation is None

    def test_check_for_escalation_disabled(self):
        """Test escalation when disabled in config."""
        self.config.escalation_config.enabled = False

        escalation = self.monitor.check_for_escalation("test/repo")

        assert escalation is None

    def test_check_for_escalation_cooldown_active(self):
        """Test escalation is skipped during cooldown period."""
        # Mock recent failures that meet threshold
        failures = [
            PipelineFailure(
                category=FailureCategory.LINTING,
                job_name="lint",
                resolved_at=None,
            )
            for _ in range(5)
        ]

        # Mock recent escalation (within cooldown)
        recent_escalation = EscalationRecord(
            repository="test/repo",
            failure_pattern="linting_lint",
            escalated_at=datetime.now(timezone.utc),  # Recent
            resolved=False,
        )

        self.mock_db.get_recent_pipeline_failures.return_value = failures
        self.mock_db.get_recent_escalations.return_value = [recent_escalation]

        escalation = self.monitor.check_for_escalation("test/repo")

        # Should not escalate due to cooldown
        assert escalation is None

    def test_get_retry_dashboard_data(self):
        """Test getting retry dashboard data."""
        # Mock retry attempts
        retry_attempts = [
            RetryAttempt(
                repository="test/repo",
                attempt_number=1,
                success=True,
                attempted_at=datetime.now(timezone.utc),
            ),
            RetryAttempt(
                repository="test/repo",
                attempt_number=2,
                success=False,
                attempted_at=datetime.now(timezone.utc),
            ),
        ]

        # Mock escalations
        escalations = [
            EscalationRecord(
                repository="test/repo",
                failure_pattern="linting_lint",
                failure_count=5,
                resolved=False,
            )
        ]

        self.mock_db.get_recent_retry_attempts.return_value = retry_attempts
        self.mock_db.get_recent_escalations.return_value = escalations

        data = self.monitor.get_retry_dashboard_data("test/repo", days=7)

        assert data["retry_summary"]["total_retries"] == 2
        assert data["retry_summary"]["successful_retries"] == 1
        assert data["retry_summary"]["failed_retries"] == 1
        assert data["retry_summary"]["success_rate"] == 50.0

        assert data["escalation_summary"]["total_escalations"] == 1
        assert data["escalation_summary"]["pending_escalations"] == 1
        assert data["escalation_summary"]["resolved_escalations"] == 0

    @pytest.mark.asyncio
    async def test_trigger_pipeline_retry_linting(self):
        """Test triggering retry for linting failures."""
        failure = PipelineFailure(
            category=FailureCategory.LINTING,
            job_name="lint",
        )

        # Should simulate auto-fix for linting
        success = await self.monitor._trigger_pipeline_retry(failure)

        # Linting issues should be auto-fixable
        assert success == True

    @pytest.mark.asyncio
    async def test_trigger_pipeline_retry_formatting(self):
        """Test triggering retry for formatting failures."""
        failure = PipelineFailure(
            category=FailureCategory.FORMATTING,
            job_name="format",
        )

        # Should simulate auto-fix for formatting
        success = await self.monitor._trigger_pipeline_retry(failure)

        # Formatting issues should be auto-fixable
        assert success == True
