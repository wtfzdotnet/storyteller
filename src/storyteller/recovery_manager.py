"""Recovery and resumption system for automated agent workflow failures."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    # Try relative imports first (for package usage)
    from .config import Config
    from .database import DatabaseManager
    from .github_handler import GitHubHandler
    from .models import (
        PipelineFailure,
        RecoveryState,
        RecoveryStatus,
        WorkflowCheckpoint,
    )
except ImportError:
    # Fall back to absolute imports (for direct execution)
    from config import Config
    from database import DatabaseManager
    from github_handler import GitHubHandler
    from models import (
        PipelineFailure,
        RecoveryState,
        RecoveryStatus,
        WorkflowCheckpoint,
    )

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Manages failure recovery and workflow resumption operations."""

    def __init__(self, config: Config):
        self.config = config
        self.database = DatabaseManager()
        self.github_handler = GitHubHandler(config)

    async def create_checkpoint(
        self,
        repository: str,
        workflow_name: str,
        run_id: str,
        commit_sha: str,
        checkpoint_type: str = "step",
        checkpoint_name: str = "",
        workflow_state: Optional[Dict[str, Any]] = None,
        environment_context: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        artifacts: Optional[List[str]] = None,
    ) -> WorkflowCheckpoint:
        """Create a workflow checkpoint for recovery purposes."""
        checkpoint = WorkflowCheckpoint(
            repository=repository,
            workflow_name=workflow_name,
            run_id=run_id,
            commit_sha=commit_sha,
            checkpoint_type=checkpoint_type,
            checkpoint_name=checkpoint_name,
            workflow_state=workflow_state or {},
            environment_context=environment_context or {},
            dependencies=dependencies or [],
            artifacts=artifacts or [],
            metadata={
                "created_by": "recovery_manager",
                "checkpoint_size": len(str(workflow_state or {})),
            },
        )

        # Store checkpoint in database
        success = self.database.store_workflow_checkpoint(checkpoint)
        if not success:
            raise Exception(f"Failed to store checkpoint {checkpoint.id}")

        logger.info(
            f"Created checkpoint {checkpoint.id} for {repository}/{workflow_name} at {checkpoint_name}"
        )
        return checkpoint

    async def initiate_recovery(
        self, failure: PipelineFailure, recovery_type: str = "retry"
    ) -> RecoveryState:
        """Initiate a recovery operation for a pipeline failure."""
        # Identify the best recovery strategy
        recovery_plan = await self._create_recovery_plan(failure, recovery_type)

        # Find target checkpoint if resuming
        target_checkpoint = None
        if recovery_type == "resume":
            target_checkpoint = await self._find_resumption_point(failure)

        # Create recovery state
        recovery_state = RecoveryState(
            failure_id=failure.id,
            repository=failure.repository,
            recovery_type=recovery_type,
            status=RecoveryStatus.PENDING,
            target_checkpoint_id=target_checkpoint.id if target_checkpoint else None,
            recovery_plan=recovery_plan,
            recovery_context={
                "original_failure": {
                    "category": failure.category.value,
                    "severity": failure.severity.value,
                    "job_name": failure.job_name,
                    "step_name": failure.step_name,
                },
                "retry_count": failure.retry_count,
            },
            metadata={
                "initiated_by": "recovery_manager",
                "recovery_strategy": recovery_type,
            },
        )

        # Store recovery state
        success = self.database.store_recovery_state(recovery_state)
        if not success:
            raise Exception(f"Failed to store recovery state {recovery_state.id}")

        logger.info(
            f"Initiated {recovery_type} recovery {recovery_state.id} for failure {failure.id}"
        )
        return recovery_state

    async def execute_recovery(self, recovery_state: RecoveryState) -> bool:
        """Execute a recovery operation."""
        try:
            recovery_state.status = RecoveryStatus.IN_PROGRESS
            self.database.store_recovery_state(recovery_state)

            logger.info(f"Executing recovery {recovery_state.id} ({recovery_state.recovery_type})")

            success = False
            if recovery_state.recovery_type == "retry":
                success = await self._execute_retry_recovery(recovery_state)
            elif recovery_state.recovery_type == "resume":
                success = await self._execute_resume_recovery(recovery_state)
            elif recovery_state.recovery_type == "rollback":
                success = await self._execute_rollback_recovery(recovery_state)
            else:
                raise ValueError(f"Unknown recovery type: {recovery_state.recovery_type}")

            # Update recovery state
            recovery_state.status = RecoveryStatus.COMPLETED if success else RecoveryStatus.FAILED
            recovery_state.completed_at = datetime.now(timezone.utc)
            self.database.store_recovery_state(recovery_state)

            logger.info(
                f"Recovery {recovery_state.id} {'completed successfully' if success else 'failed'}"
            )
            return success

        except Exception as e:
            logger.error(f"Error during recovery execution: {e}")
            recovery_state.status = RecoveryStatus.FAILED
            recovery_state.completed_at = datetime.now(timezone.utc)
            recovery_state.metadata["error"] = str(e)
            self.database.store_recovery_state(recovery_state)
            return False

    async def validate_state(
        self, checkpoint: WorkflowCheckpoint, validate_dependencies: bool = True
    ) -> Dict[str, Any]:
        """Validate workflow state for corruption and consistency."""
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Check checkpoint data integrity
            if not checkpoint.workflow_state:
                validation_results["warnings"].append("Empty workflow state")

            # Validate environment context
            if not checkpoint.environment_context:
                validation_results["warnings"].append("Missing environment context")

            # Check dependencies if requested
            if validate_dependencies and checkpoint.dependencies:
                dependency_issues = await self._validate_dependencies(checkpoint.dependencies)
                if dependency_issues:
                    validation_results["errors"].extend(dependency_issues)
                    validation_results["is_valid"] = False

            # Validate artifacts exist
            if checkpoint.artifacts:
                artifact_issues = await self._validate_artifacts(checkpoint.artifacts)
                if artifact_issues:
                    validation_results["warnings"].extend(artifact_issues)

            logger.info(
                f"State validation for checkpoint {checkpoint.id}: {'valid' if validation_results['is_valid'] else 'invalid'}"
            )

        except Exception as e:
            logger.error(f"Error during state validation: {e}")
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Validation error: {str(e)}")

        return validation_results

    async def rollback_to_checkpoint(
        self, checkpoint: WorkflowCheckpoint, reason: str = "manual_rollback"
    ) -> bool:
        """Rollback workflow to a specific checkpoint."""
        try:
            logger.info(f"Rolling back to checkpoint {checkpoint.id}: {reason}")

            # Validate checkpoint before rollback
            validation = await self.validate_state(checkpoint)
            if not validation["is_valid"]:
                logger.error(f"Cannot rollback to invalid checkpoint: {validation['errors']}")
                return False

            # Execute rollback operations
            rollback_success = await self._execute_rollback_operations(checkpoint)

            if rollback_success:
                logger.info(f"Successfully rolled back to checkpoint {checkpoint.id}")
            else:
                logger.error(f"Failed to rollback to checkpoint {checkpoint.id}")

            return rollback_success

        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return False

    async def _create_recovery_plan(
        self, failure: PipelineFailure, recovery_type: str
    ) -> List[str]:
        """Create a recovery plan based on failure analysis."""
        plan = []

        if recovery_type == "retry":
            plan = [
                "analyze_failure_cause",
                "check_retry_limits",
                "apply_failure_specific_fixes",
                "trigger_workflow_retry",
                "monitor_retry_execution",
                "validate_success",
            ]
        elif recovery_type == "resume":
            plan = [
                "identify_resumption_point",
                "validate_checkpoint_state",
                "restore_environment_context",
                "resolve_dependencies",
                "resume_from_checkpoint",
                "monitor_execution",
                "validate_completion",
            ]
        elif recovery_type == "rollback":
            plan = [
                "identify_rollback_target",
                "validate_rollback_checkpoint",
                "backup_current_state",
                "execute_rollback_operations",
                "restore_environment",
                "validate_rollback_success",
            ]

        # Add failure-specific steps
        if failure.category.value == "linting":
            plan.insert(-2, "apply_linting_fixes")
        elif failure.category.value == "testing":
            plan.insert(-2, "analyze_test_failures")
        elif failure.category.value == "build":
            plan.insert(-2, "check_build_dependencies")

        return plan

    async def _find_resumption_point(self, failure: PipelineFailure) -> Optional[WorkflowCheckpoint]:
        """Find the best checkpoint to resume from."""
        checkpoints = self.database.get_workflow_checkpoints(
            repository=failure.repository, limit=10
        )

        # Find checkpoints related to the failed workflow
        relevant_checkpoints = [
            cp for cp in checkpoints
            if cp.run_id == failure.pipeline_id or 
               cp.commit_sha == failure.commit_sha
        ]

        if not relevant_checkpoints:
            logger.warning(f"No relevant checkpoints found for failure {failure.id}")
            return None

        # Find the latest checkpoint before the failure
        best_checkpoint = None
        for checkpoint in relevant_checkpoints:
            if checkpoint.created_at < failure.detected_at:
                if not best_checkpoint or checkpoint.created_at > best_checkpoint.created_at:
                    best_checkpoint = checkpoint

        if best_checkpoint:
            logger.info(f"Found resumption point: checkpoint {best_checkpoint.id}")
        else:
            logger.warning(f"No suitable resumption point found for failure {failure.id}")

        return best_checkpoint

    async def _execute_retry_recovery(self, recovery_state: RecoveryState) -> bool:
        """Execute retry-based recovery."""
        logger.info(f"Executing retry recovery for {recovery_state.id}")

        # Add progress step
        recovery_state.progress_steps.append({
            "step": "retry_initiation",
            "status": "in_progress",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Simulate retry logic (in real implementation, would trigger GitHub workflow)
        # For now, return success based on failure type
        failure_type = recovery_state.recovery_context.get("original_failure", {}).get("category")
        
        # Linting and formatting failures have higher success rate
        if failure_type in ["linting", "formatting"]:
            success = True
        else:
            # Simulate 70% success rate for other types
            import random
            success = random.random() < 0.7

        # Update progress
        recovery_state.progress_steps.append({
            "step": "retry_execution",
            "status": "completed" if success else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": "success" if success else "failure",
        })

        return success

    async def _execute_resume_recovery(self, recovery_state: RecoveryState) -> bool:
        """Execute resume-based recovery."""
        logger.info(f"Executing resume recovery for {recovery_state.id}")

        if not recovery_state.target_checkpoint_id:
            logger.error("No target checkpoint specified for resume recovery")
            return False

        # Get target checkpoint
        checkpoints = self.database.get_workflow_checkpoints(limit=1)
        target_checkpoint = None
        for cp in checkpoints:
            if cp.id == recovery_state.target_checkpoint_id:
                target_checkpoint = cp
                break

        if not target_checkpoint:
            logger.error(f"Target checkpoint {recovery_state.target_checkpoint_id} not found")
            return False

        # Validate checkpoint state
        validation = await self.validate_state(target_checkpoint)
        if not validation["is_valid"]:
            logger.error(f"Cannot resume from invalid checkpoint: {validation['errors']}")
            return False

        # Add progress steps
        recovery_state.progress_steps.extend([
            {
                "step": "checkpoint_validation",
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "step": "environment_restoration",
                "status": "in_progress",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ])

        # Simulate resumption success (in real implementation, would restore state and continue)
        success = True

        recovery_state.progress_steps.append({
            "step": "workflow_resumption",
            "status": "completed" if success else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return success

    async def _execute_rollback_recovery(self, recovery_state: RecoveryState) -> bool:
        """Execute rollback-based recovery."""
        logger.info(f"Executing rollback recovery for {recovery_state.id}")

        if not recovery_state.rollback_checkpoint_id:
            logger.error("No rollback checkpoint specified")
            return False

        # Get rollback checkpoint
        checkpoints = self.database.get_workflow_checkpoints(limit=10)
        rollback_checkpoint = None
        for cp in checkpoints:
            if cp.id == recovery_state.rollback_checkpoint_id:
                rollback_checkpoint = cp
                break

        if not rollback_checkpoint:
            logger.error(f"Rollback checkpoint {recovery_state.rollback_checkpoint_id} not found")
            return False

        # Execute rollback
        rollback_success = await self.rollback_to_checkpoint(
            rollback_checkpoint, reason="recovery_rollback"
        )

        recovery_state.progress_steps.append({
            "step": "rollback_execution",
            "status": "completed" if rollback_success else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return rollback_success

    async def _execute_rollback_operations(self, checkpoint: WorkflowCheckpoint) -> bool:
        """Execute the actual rollback operations."""
        try:
            # In a real implementation, this would:
            # 1. Restore git state to checkpoint commit
            # 2. Restore environment variables
            # 3. Restore artifacts and dependencies
            # 4. Reset workflow state
            
            logger.info(f"Simulating rollback operations for checkpoint {checkpoint.id}")
            
            # Simulate rollback success
            return True

        except Exception as e:
            logger.error(f"Failed to execute rollback operations: {e}")
            return False

    async def _validate_dependencies(self, dependencies: List[str]) -> List[str]:
        """Validate that dependencies are available and correct."""
        issues = []
        for dep in dependencies:
            # In real implementation, would check if dependency exists and is accessible
            logger.debug(f"Validating dependency: {dep}")
            # For now, assume all dependencies are valid
        return issues

    async def _validate_artifacts(self, artifacts: List[str]) -> List[str]:
        """Validate that artifacts exist and are accessible."""
        issues = []
        for artifact in artifacts:
            # In real implementation, would check if artifact exists
            logger.debug(f"Validating artifact: {artifact}")
            # For now, assume all artifacts are valid
        return issues

    def get_recovery_dashboard_data(self, repository: Optional[str] = None) -> Dict[str, Any]:
        """Get dashboard data for recovery operations."""
        try:
            # Get recent recovery states
            recovery_states = self.database.get_recovery_states(
                repository=repository, limit=50
            )

            # Calculate statistics
            total_recoveries = len(recovery_states)
            successful_recoveries = len([r for r in recovery_states if r.status == RecoveryStatus.COMPLETED])
            failed_recoveries = len([r for r in recovery_states if r.status == RecoveryStatus.FAILED])
            in_progress_recoveries = len([r for r in recovery_states if r.status == RecoveryStatus.IN_PROGRESS])

            success_rate = (successful_recoveries / total_recoveries * 100) if total_recoveries > 0 else 0

            # Group by recovery type
            recovery_by_type = {}
            for recovery in recovery_states:
                recovery_type = recovery.recovery_type
                if recovery_type not in recovery_by_type:
                    recovery_by_type[recovery_type] = {"total": 0, "successful": 0}
                recovery_by_type[recovery_type]["total"] += 1
                if recovery.status == RecoveryStatus.COMPLETED:
                    recovery_by_type[recovery_type]["successful"] += 1

            # Get recent checkpoints
            checkpoints = self.database.get_workflow_checkpoints(
                repository=repository, limit=20
            )

            return {
                "recovery_summary": {
                    "total_recoveries": total_recoveries,
                    "successful_recoveries": successful_recoveries,
                    "failed_recoveries": failed_recoveries,
                    "in_progress_recoveries": in_progress_recoveries,
                    "success_rate": round(success_rate, 2),
                },
                "recovery_by_type": recovery_by_type,
                "recent_recoveries": [
                    {
                        "id": r.id,
                        "type": r.recovery_type,
                        "status": r.status.value,
                        "repository": r.repository,
                        "started_at": r.started_at.isoformat(),
                        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    }
                    for r in recovery_states[:10]  # Last 10 recoveries
                ],
                "recent_checkpoints": [
                    {
                        "id": c.id,
                        "repository": c.repository,
                        "workflow_name": c.workflow_name,
                        "checkpoint_name": c.checkpoint_name,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in checkpoints[:10]  # Last 10 checkpoints
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get recovery dashboard data: {e}")
            return {
                "error": str(e),
                "recovery_summary": {
                    "total_recoveries": 0,
                    "successful_recoveries": 0,
                    "failed_recoveries": 0,
                    "in_progress_recoveries": 0,
                    "success_rate": 0,
                },
            }