"""Unit tests for the recovery and resumption system."""

import os
import sys
import tempfile
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
    RecoveryState,
    RecoveryStatus,
    WorkflowCheckpoint,
)
from recovery_manager import RecoveryManager


class TestRecoveryManager:
    """Test the recovery and resumption functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()

        self.config = Config(
            github_token="test_token",
            repositories={},
            default_repository="test",
        )

        # Mock dependencies
        with (
            patch("recovery_manager.DatabaseManager") as mock_db_class,
            patch("recovery_manager.GitHubHandler") as mock_github_class,
        ):
            self.mock_db = MagicMock()
            mock_db_class.return_value = self.mock_db
            
            self.mock_github = MagicMock()
            mock_github_class.return_value = self.mock_github

            self.recovery_manager = RecoveryManager(self.config)

        # Test data
        self.test_failure = PipelineFailure(
            id="failure_test123",
            repository="test/repo",
            branch="main",
            commit_sha="abc123",
            pipeline_id="run_456",
            job_name="test",
            step_name="pytest",
            failure_message="Test failed",
            category=FailureCategory.TESTING,
            severity=FailureSeverity.MEDIUM,
        )

        self.test_checkpoint = WorkflowCheckpoint(
            id="checkpoint_test123",
            repository="test/repo",
            workflow_name="CI",
            run_id="run_456",
            commit_sha="abc123",
            checkpoint_type="job",
            checkpoint_name="build_complete",
            workflow_state={"step": "build", "status": "completed"},
            environment_context={"python_version": "3.11", "node_version": "18"},
            dependencies=["src/requirements.txt"],
            artifacts=["dist/app.tar.gz"],
        )

    def teardown_method(self):
        """Clean up after tests."""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass

    @pytest.mark.asyncio
    async def test_create_checkpoint(self):
        """Test creating a workflow checkpoint."""
        self.mock_db.store_workflow_checkpoint.return_value = True

        checkpoint = await self.recovery_manager.create_checkpoint(
            repository="test/repo",
            workflow_name="CI",
            run_id="run_123",
            commit_sha="def456",
            checkpoint_type="step",
            checkpoint_name="tests_passed",
            workflow_state={"current_step": "testing"},
            environment_context={"env": "test"},
            dependencies=["requirements.txt"],
            artifacts=["test_results.xml"],
        )

        assert checkpoint.repository == "test/repo"
        assert checkpoint.workflow_name == "CI"
        assert checkpoint.run_id == "run_123"
        assert checkpoint.commit_sha == "def456"
        assert checkpoint.checkpoint_name == "tests_passed"
        assert checkpoint.workflow_state == {"current_step": "testing"}
        
        self.mock_db.store_workflow_checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_retry_recovery(self):
        """Test initiating a retry recovery."""
        self.mock_db.store_recovery_state.return_value = True

        recovery_state = await self.recovery_manager.initiate_recovery(
            self.test_failure, recovery_type="retry"
        )

        assert recovery_state.failure_id == self.test_failure.id
        assert recovery_state.repository == self.test_failure.repository
        assert recovery_state.recovery_type == "retry"
        assert recovery_state.status == RecoveryStatus.PENDING
        assert len(recovery_state.recovery_plan) > 0
        
        self.mock_db.store_recovery_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_resume_recovery(self):
        """Test initiating a resume recovery."""
        self.mock_db.store_recovery_state.return_value = True
        
        # Set the checkpoint creation time to be before the failure detection time
        self.test_checkpoint.created_at = datetime.now(timezone.utc).replace(hour=10)
        self.test_failure.detected_at = datetime.now(timezone.utc).replace(hour=12)
        
        self.mock_db.get_workflow_checkpoints.return_value = [self.test_checkpoint]

        recovery_state = await self.recovery_manager.initiate_recovery(
            self.test_failure, recovery_type="resume"
        )

        assert recovery_state.recovery_type == "resume"
        assert recovery_state.target_checkpoint_id == self.test_checkpoint.id
        
        self.mock_db.get_workflow_checkpoints.assert_called_once()
        self.mock_db.store_recovery_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_retry_recovery(self):
        """Test executing a retry recovery."""
        recovery_state = RecoveryState(
            failure_id=self.test_failure.id,
            repository=self.test_failure.repository,
            recovery_type="retry",
            status=RecoveryStatus.PENDING,
            recovery_context={
                "original_failure": {
                    "category": "linting",
                    "severity": "medium",
                    "job_name": "lint",
                    "step_name": "flake8",
                }
            },
        )

        self.mock_db.store_recovery_state.return_value = True

        success = await self.recovery_manager.execute_recovery(recovery_state)

        # Linting failures should have high success rate
        assert success is True
        assert recovery_state.status == RecoveryStatus.COMPLETED
        assert len(recovery_state.progress_steps) > 0
        
        # Verify database calls
        assert self.mock_db.store_recovery_state.call_count >= 2

    @pytest.mark.asyncio
    async def test_execute_resume_recovery(self):
        """Test executing a resume recovery."""
        recovery_state = RecoveryState(
            failure_id=self.test_failure.id,
            repository=self.test_failure.repository,
            recovery_type="resume",
            target_checkpoint_id=self.test_checkpoint.id,
            status=RecoveryStatus.PENDING,
        )

        self.mock_db.store_recovery_state.return_value = True
        self.mock_db.get_workflow_checkpoints.return_value = [self.test_checkpoint]

        success = await self.recovery_manager.execute_recovery(recovery_state)

        assert success is True
        assert recovery_state.status == RecoveryStatus.COMPLETED
        assert len(recovery_state.progress_steps) > 0

    @pytest.mark.asyncio
    async def test_validate_state_valid_checkpoint(self):
        """Test state validation for a valid checkpoint."""
        validation = await self.recovery_manager.validate_state(self.test_checkpoint)

        assert validation["is_valid"] is True
        assert len(validation["errors"]) == 0
        assert "checked_at" in validation

    @pytest.mark.asyncio
    async def test_validate_state_empty_workflow_state(self):
        """Test state validation with empty workflow state."""
        empty_checkpoint = WorkflowCheckpoint(
            repository="test/repo",
            workflow_name="CI",
            run_id="run_123",
            commit_sha="abc123",
            workflow_state={},  # Empty state
        )

        validation = await self.recovery_manager.validate_state(empty_checkpoint)

        assert validation["is_valid"] is True
        assert len(validation["warnings"]) > 0
        assert any("Empty workflow state" in w for w in validation["warnings"])

    @pytest.mark.asyncio
    async def test_rollback_to_checkpoint(self):
        """Test rolling back to a checkpoint."""
        # Mock validation to return valid state
        with patch.object(
            self.recovery_manager, "validate_state", 
            return_value={"is_valid": True, "errors": [], "warnings": []}
        ):
            success = await self.recovery_manager.rollback_to_checkpoint(
                self.test_checkpoint, reason="test_rollback"
            )

            assert success is True

    @pytest.mark.asyncio
    async def test_rollback_to_invalid_checkpoint(self):
        """Test rollback failure with invalid checkpoint."""
        # Mock validation to return invalid state
        with patch.object(
            self.recovery_manager, "validate_state",
            return_value={"is_valid": False, "errors": ["Corrupted state"], "warnings": []}
        ):
            success = await self.recovery_manager.rollback_to_checkpoint(
                self.test_checkpoint, reason="test_rollback"
            )

            assert success is False

    def test_get_recovery_dashboard_data(self):
        """Test getting recovery dashboard data."""
        # Mock database returns
        recovery_states = [
            RecoveryState(
                id="recovery_1",
                failure_id="failure_1",
                repository="test/repo",
                recovery_type="retry",
                status=RecoveryStatus.COMPLETED,
            ),
            RecoveryState(
                id="recovery_2",
                failure_id="failure_2",
                repository="test/repo",
                recovery_type="resume",
                status=RecoveryStatus.FAILED,
            ),
        ]

        checkpoints = [self.test_checkpoint]

        self.mock_db.get_recovery_states.return_value = recovery_states
        self.mock_db.get_workflow_checkpoints.return_value = checkpoints

        dashboard_data = self.recovery_manager.get_recovery_dashboard_data()

        assert dashboard_data["recovery_summary"]["total_recoveries"] == 2
        assert dashboard_data["recovery_summary"]["successful_recoveries"] == 1
        assert dashboard_data["recovery_summary"]["failed_recoveries"] == 1
        assert dashboard_data["recovery_summary"]["success_rate"] == 50.0

        assert "retry" in dashboard_data["recovery_by_type"]
        assert "resume" in dashboard_data["recovery_by_type"]

        assert len(dashboard_data["recent_recoveries"]) == 2
        assert len(dashboard_data["recent_checkpoints"]) == 1

    @pytest.mark.asyncio
    async def test_find_resumption_point_no_checkpoints(self):
        """Test finding resumption point when no checkpoints exist."""
        self.mock_db.get_workflow_checkpoints.return_value = []

        resumption_point = await self.recovery_manager._find_resumption_point(self.test_failure)

        assert resumption_point is None

    @pytest.mark.asyncio
    async def test_find_resumption_point_with_valid_checkpoint(self):
        """Test finding resumption point with valid checkpoints."""
        # Create a checkpoint that's before the failure
        valid_checkpoint = WorkflowCheckpoint(
            id="checkpoint_valid",
            repository=self.test_failure.repository,
            workflow_name="CI",
            run_id=self.test_failure.pipeline_id,
            commit_sha=self.test_failure.commit_sha,
            created_at=datetime.now(timezone.utc).replace(hour=10),  # Earlier time
        )
        
        # Set failure detection time to be later
        self.test_failure.detected_at = datetime.now(timezone.utc).replace(hour=12)

        self.mock_db.get_workflow_checkpoints.return_value = [valid_checkpoint]

        resumption_point = await self.recovery_manager._find_resumption_point(self.test_failure)

        assert resumption_point is not None
        assert resumption_point.id == valid_checkpoint.id

    @pytest.mark.asyncio
    async def test_create_recovery_plan_retry(self):
        """Test creating a recovery plan for retry."""
        plan = await self.recovery_manager._create_recovery_plan(self.test_failure, "retry")

        assert len(plan) > 0
        assert "analyze_failure_cause" in plan
        assert "trigger_workflow_retry" in plan
        assert "validate_success" in plan

    @pytest.mark.asyncio
    async def test_create_recovery_plan_resume(self):
        """Test creating a recovery plan for resume."""
        plan = await self.recovery_manager._create_recovery_plan(self.test_failure, "resume")

        assert len(plan) > 0
        assert "identify_resumption_point" in plan
        assert "restore_environment_context" in plan
        assert "resume_from_checkpoint" in plan

    @pytest.mark.asyncio
    async def test_create_recovery_plan_rollback(self):
        """Test creating a recovery plan for rollback."""
        plan = await self.recovery_manager._create_recovery_plan(self.test_failure, "rollback")

        assert len(plan) > 0
        assert "identify_rollback_target" in plan
        assert "execute_rollback_operations" in plan
        assert "validate_rollback_success" in plan

    @pytest.mark.asyncio
    async def test_execute_recovery_unknown_type(self):
        """Test executing recovery with unknown recovery type."""
        recovery_state = RecoveryState(
            failure_id=self.test_failure.id,
            repository=self.test_failure.repository,
            recovery_type="unknown_type",
            status=RecoveryStatus.PENDING,
        )

        self.mock_db.store_recovery_state.return_value = True

        success = await self.recovery_manager.execute_recovery(recovery_state)

        assert success is False
        assert recovery_state.status == RecoveryStatus.FAILED