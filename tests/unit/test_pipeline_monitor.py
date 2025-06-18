"""Unit tests for pipeline monitoring functionality."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/storyteller'))

from config import Config
from models import (
    FailureCategory,
    FailureSeverity,
    PipelineFailure,
    PipelineRun,
    PipelineStatus,
)
from pipeline_monitor import PipelineMonitor


class TestPipelineMonitor:
    """Test the PipelineMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(
            github_token="test_token",
            repositories={},
            default_repository="test",
        )
        
        # Mock dependencies
        with patch('pipeline_monitor.DatabaseManager') as mock_db, \
             patch('pipeline_monitor.GitHubHandler') as mock_gh:
            self.monitor = PipelineMonitor(self.config)
            self.mock_db = mock_db.return_value
            self.mock_github = mock_gh.return_value

    def test_init_failure_patterns(self):
        """Test initialization of failure classification patterns."""
        assert FailureCategory.LINTING in self.monitor.failure_patterns
        assert FailureCategory.TESTING in self.monitor.failure_patterns
        assert len(self.monitor.failure_patterns[FailureCategory.LINTING]) > 0

    def test_map_github_status(self):
        """Test mapping GitHub workflow status to internal status."""
        assert self.monitor._map_github_status("queued") == PipelineStatus.PENDING
        assert self.monitor._map_github_status("in_progress") == PipelineStatus.IN_PROGRESS
        assert self.monitor._map_github_status("completed") == PipelineStatus.SUCCESS
        assert self.monitor._map_github_status("cancelled") == PipelineStatus.CANCELLED
        assert self.monitor._map_github_status("unknown") == PipelineStatus.PENDING

    def test_classify_failure_linting(self):
        """Test failure classification for linting errors."""
        job_name = "Lint and Test"
        logs = "flake8 error: E401 multiple imports on one line"
        
        category, severity = self.monitor._classify_failure(job_name, logs)
        
        assert category == FailureCategory.LINTING
        assert severity == FailureSeverity.MEDIUM

    def test_classify_failure_testing(self):
        """Test failure classification for test failures."""
        job_name = "Run Tests"
        logs = "FAILED tests/test_example.py::test_function - AssertionError"
        
        category, severity = self.monitor._classify_failure(job_name, logs)
        
        assert category == FailureCategory.TESTING
        assert severity == FailureSeverity.MEDIUM

    def test_classify_failure_critical_security(self):
        """Test failure classification for critical security issues."""
        job_name = "Security Check"
        logs = "CRITICAL security vulnerability detected in dependencies"
        
        category, severity = self.monitor._classify_failure(job_name, logs)
        
        assert severity == FailureSeverity.CRITICAL

    def test_extract_failure_message(self):
        """Test extraction of failure message from logs."""
        logs = """
        Running tests...
        Setting up environment...
        ERROR: Test failed with assertion error
        Some other output
        """
        
        message = self.monitor._extract_failure_message(logs)
        
        assert "ERROR: Test failed with assertion error" in message

    def test_extract_failure_message_empty_logs(self):
        """Test extraction when logs are empty."""
        message = self.monitor._extract_failure_message("")
        
        assert message == "No failure message available"

    def test_extract_key_words(self):
        """Test extraction of key words from failure messages."""
        message = "ImportError: No module named 'test_module' found"
        
        key_words = self.monitor._extract_key_words(message)
        
        # Should extract meaningful words and exclude common ones
        assert "importerror" in key_words.lower()
        assert "module" in key_words.lower()
        assert "test" not in key_words  # Should be filtered out

    def test_generate_resolution_suggestions(self):
        """Test generation of resolution suggestions."""
        suggestions = self.monitor._generate_resolution_suggestions(FailureCategory.LINTING)
        
        assert len(suggestions) > 0
        assert any("flake8" in s.lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_process_pipeline_event_invalid_data(self):
        """Test processing invalid pipeline event data."""
        invalid_event = {}
        
        result = await self.monitor.process_pipeline_event(invalid_event)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_process_pipeline_event_success(self):
        """Test processing successful pipeline event."""
        event_data = {
            "workflow_run": {
                "id": "12345",
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "head_branch": "main",
                "head_sha": "abc123",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:05:00Z",
                "run_number": 42,
                "event": "push",
                "actor": {"login": "test-user"}
            },
            "repository": {
                "full_name": "test/repo"
            }
        }
        
        result = await self.monitor.process_pipeline_event(event_data)
        
        assert result is not None
        assert result.repository == "test/repo"
        assert result.branch == "main"
        assert result.commit_sha == "abc123"
        assert result.workflow_name == "CI"

    @pytest.mark.asyncio
    async def test_process_pipeline_event_failure(self):
        """Test processing failed pipeline event."""
        event_data = {
            "workflow_run": {
                "id": "12345",
                "name": "CI",
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "abc123",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:05:00Z",
                "run_number": 42,
                "event": "push",
                "actor": {"login": "test-user"}
            },
            "repository": {
                "full_name": "test/repo"
            }
        }
        
        # Mock the analyze_pipeline_failure method
        with patch.object(self.monitor, '_analyze_pipeline_failure') as mock_analyze:
            mock_analyze.return_value = None
            
            result = await self.monitor.process_pipeline_event(event_data)
        
        assert result is not None
        mock_analyze.assert_called_once()

    def test_get_failure_dashboard_data_empty(self):
        """Test getting dashboard data with no failures."""
        self.mock_db.get_recent_pipeline_failures.return_value = []
        self.mock_db.get_failure_patterns.return_value = []
        
        data = self.monitor.get_failure_dashboard_data(days=7)
        
        assert data["summary"]["total_failures"] == 0
        assert data["by_category"] == {}
        assert data["by_severity"] == {}

    def test_get_failure_dashboard_data_with_failures(self):
        """Test getting dashboard data with failures."""
        failures = [
            PipelineFailure(
                repository="test/repo1",
                category=FailureCategory.LINTING,
                severity=FailureSeverity.MEDIUM,
                job_name="lint",
                failure_message="Linting error"
            ),
            PipelineFailure(
                repository="test/repo2",
                category=FailureCategory.TESTING,
                severity=FailureSeverity.HIGH,
                job_name="test",
                failure_message="Test failure"
            ),
        ]
        
        self.mock_db.get_recent_pipeline_failures.return_value = failures
        self.mock_db.get_failure_patterns.return_value = []
        
        data = self.monitor.get_failure_dashboard_data(days=7)
        
        assert data["summary"]["total_failures"] == 2
        assert data["by_category"]["linting"] == 1
        assert data["by_category"]["testing"] == 1
        assert data["by_severity"]["medium"] == 1
        assert data["by_severity"]["high"] == 1
        assert data["by_repository"]["test/repo1"] == 1
        assert data["by_repository"]["test/repo2"] == 1

    def test_analyze_failure_patterns_empty(self):
        """Test analyzing failure patterns with no failures."""
        self.mock_db.get_recent_pipeline_failures.return_value = []
        
        patterns = self.monitor.analyze_failure_patterns(days=30)
        
        assert len(patterns) == 0

    def test_analyze_failure_patterns_with_data(self):
        """Test analyzing failure patterns with similar failures."""
        failures = [
            PipelineFailure(
                repository="test/repo1",
                category=FailureCategory.LINTING,
                failure_message="flake8 import error",
                detected_at=datetime.now(timezone.utc)
            ),
            PipelineFailure(
                repository="test/repo2",
                category=FailureCategory.LINTING,
                failure_message="flake8 import problem",
                detected_at=datetime.now(timezone.utc)
            ),
        ]
        
        self.mock_db.get_recent_pipeline_failures.return_value = failures
        self.mock_db.store_failure_pattern.return_value = True
        
        patterns = self.monitor.analyze_failure_patterns(days=30)
        
        # Should create pattern from similar failures
        assert len(patterns) == 1
        assert patterns[0].category == FailureCategory.LINTING
        assert patterns[0].failure_count == 2
        assert len(patterns[0].repositories) == 2