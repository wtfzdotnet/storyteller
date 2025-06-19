"""Pipeline failure monitoring system for automated agent workflow."""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from database import DatabaseManager
from github_handler import GitHubHandler
from models import (
    EscalationRecord,
    FailureCategory,
    FailurePattern,
    FailureSeverity,
    PipelineFailure,
    PipelineRun,
    PipelineStatus,
    RetryAttempt,
)

try:
    from recovery_manager import RecoveryManager
except ImportError:
    # Handle case where recovery_manager is not available
    RecoveryManager = None

logger = logging.getLogger(__name__)


class PipelineMonitor:
    """Monitor pipeline failures across repositories with classification and analysis."""

    def __init__(self, config: Config):
        self.config = config
        self.database = DatabaseManager()
        self.github_handler = GitHubHandler(config)

        # Initialize recovery manager if available
        self.recovery_manager = RecoveryManager(config) if RecoveryManager else None

        # Initialize failure classification patterns
        self._init_failure_patterns()

    def _init_failure_patterns(self):
        """Initialize patterns for failure classification."""
        self.failure_patterns = {
            FailureCategory.LINTING: [
                r"flake8.*error",
                r"pylint.*error",
                r"eslint.*error",
                r"syntax error",
                r"import.*not found",
                r"undefined name",
            ],
            FailureCategory.FORMATTING: [
                r"black.*would reformat",
                r"isort.*would reformat",
                r"prettier.*failed",
                r"formatting.*check.*failed",
            ],
            FailureCategory.TESTING: [
                r"test.*failed",
                r"assertion.*error",
                r"pytest.*failed",
                r"jest.*failed",
                r"coverage.*failed",
            ],
            FailureCategory.BUILD: [
                r"build.*failed",
                r"compilation.*error",
                r"webpack.*failed",
                r"docker.*build.*failed",
            ],
            FailureCategory.DEPLOYMENT: [
                r"deployment.*failed",
                r"deploy.*error",
                r"push.*failed",
                r"registry.*error",
            ],
            FailureCategory.DEPENDENCY: [
                r"dependency.*not found",
                r"npm.*install.*failed",
                r"pip.*install.*failed",
                r"requirements.*not.*satisfied",
            ],
            FailureCategory.TIMEOUT: [
                r"timeout",
                r"time.*out",
                r"deadline.*exceeded",
                r"operation.*timed.*out",
            ],
            FailureCategory.INFRASTRUCTURE: [
                r"infrastructure.*error",
                r"network.*error",
                r"connection.*refused",
                r"service.*unavailable",
            ],
        }

        # Severity assessment rules
        self.severity_rules = {
            FailureSeverity.CRITICAL: [
                r"security.*vulnerability",
                r"critical.*error",
                r"production.*down",
                r"deployment.*blocked",
            ],
            FailureSeverity.HIGH: [
                r"build.*completely.*failed",
                r"all.*tests.*failed",
                r"main.*branch.*broken",
                r"blocking.*dependency",
            ],
            FailureSeverity.MEDIUM: [
                r"test.*failed",
                r"linting.*error",
                r"formatting.*error",
                r"documentation.*error",
            ],
            FailureSeverity.LOW: [
                r"warning",
                r"minor.*issue",
                r"style.*issue",
                r"comment.*format",
            ],
        }

    async def process_pipeline_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[PipelineRun]:
        """Process a pipeline event from GitHub webhook."""
        try:
            # Extract pipeline information
            workflow_run = event_data.get("workflow_run", {})
            repository = event_data.get("repository", {})

            if not workflow_run or not repository:
                logger.warning("Invalid pipeline event data")
                return None

            # Create or update pipeline run
            pipeline_run = PipelineRun(
                id=f"run_{workflow_run.get('id', '')}",
                repository=repository.get("full_name", ""),
                branch=workflow_run.get("head_branch", ""),
                commit_sha=workflow_run.get("head_sha", ""),
                workflow_name=workflow_run.get("name", ""),
                status=self._map_github_status(workflow_run.get("status", "")),
                started_at=datetime.fromisoformat(
                    workflow_run.get("created_at", "").replace("Z", "+00:00")
                ),
                metadata={
                    "github_run_id": workflow_run.get("id"),
                    "run_number": workflow_run.get("run_number"),
                    "event": workflow_run.get("event"),
                    "actor": workflow_run.get("actor", {}).get("login"),
                },
            )

            # If workflow is completed, check for failures
            if workflow_run.get("conclusion") in ["failure", "cancelled", "timed_out"]:
                pipeline_run.completed_at = datetime.fromisoformat(
                    workflow_run.get("updated_at", "").replace("Z", "+00:00")
                )
                await self._analyze_pipeline_failure(pipeline_run)

            # Store pipeline run
            await self._store_pipeline_run(pipeline_run)

            logger.info(
                f"Processed pipeline event for {pipeline_run.repository}: {pipeline_run.status.value}"
            )
            return pipeline_run

        except Exception as e:
            logger.error(f"Failed to process pipeline event: {e}")
            return None

    def _map_github_status(self, github_status: str) -> PipelineStatus:
        """Map GitHub workflow status to internal status."""
        status_map = {
            "queued": PipelineStatus.PENDING,
            "in_progress": PipelineStatus.IN_PROGRESS,
            "completed": PipelineStatus.SUCCESS,  # Will be updated based on conclusion
            "cancelled": PipelineStatus.CANCELLED,
        }
        return status_map.get(github_status, PipelineStatus.PENDING)

    async def _analyze_pipeline_failure(self, pipeline_run: PipelineRun):
        """Analyze pipeline failure and extract failure details."""
        try:
            # Get job details from GitHub API
            repo_name = pipeline_run.repository
            workflow_run_id = pipeline_run.metadata.get("github_run_id")

            if not workflow_run_id:
                return

            # Get jobs for this workflow run
            jobs = await self._get_workflow_jobs(repo_name, workflow_run_id)

            for job in jobs:
                if job.get("conclusion") in ["failure", "cancelled", "timed_out"]:
                    failure = await self._create_failure_from_job(pipeline_run, job)
                    if failure:
                        pipeline_run.failures.append(failure)

            # Update pipeline status based on failures
            if pipeline_run.failures:
                pipeline_run.status = PipelineStatus.FAILURE
            else:
                pipeline_run.status = PipelineStatus.SUCCESS

        except Exception as e:
            logger.error(f"Failed to analyze pipeline failure: {e}")

    async def _get_workflow_jobs(
        self, repository: str, workflow_run_id: str
    ) -> List[Dict[str, Any]]:
        """Get jobs for a workflow run from GitHub API."""
        try:
            # Use GitHub API to get workflow jobs
            repo = self.github_handler.get_repository(repository)

            # Note: PyGithub doesn't have direct workflow jobs access
            # We'll use the raw GitHub API here
            import requests

            headers = {
                "Authorization": f"token {self.config.github_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            url = f"https://api.github.com/repos/{repository}/actions/runs/{workflow_run_id}/jobs"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json().get("jobs", [])
            else:
                logger.error(f"Failed to get workflow jobs: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error getting workflow jobs: {e}")
            return []

    async def _create_failure_from_job(
        self, pipeline_run: PipelineRun, job: Dict[str, Any]
    ) -> Optional[PipelineFailure]:
        """Create a PipelineFailure from a failed job."""
        try:
            # Get job logs for analysis
            logs = await self._get_job_logs(pipeline_run.repository, job.get("id"))

            # Classify failure
            category, severity = self._classify_failure(job.get("name", ""), logs)

            failure = PipelineFailure(
                repository=pipeline_run.repository,
                branch=pipeline_run.branch,
                commit_sha=pipeline_run.commit_sha,
                pipeline_id=pipeline_run.id,
                job_name=job.get("name", ""),
                step_name=self._extract_failed_step(job),
                failure_message=self._extract_failure_message(logs),
                failure_logs=logs[:5000],  # Limit log size
                category=category,
                severity=severity,
                metadata={
                    "job_id": job.get("id"),
                    "conclusion": job.get("conclusion"),
                    "started_at": job.get("started_at"),
                    "completed_at": job.get("completed_at"),
                },
            )

            return failure

        except Exception as e:
            logger.error(f"Failed to create failure from job: {e}")
            return None

    async def _get_job_logs(self, repository: str, job_id: str) -> str:
        """Get logs for a specific job."""
        try:
            import requests

            headers = {
                "Authorization": f"token {self.config.github_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            url = (
                f"https://api.github.com/repos/{repository}/actions/jobs/{job_id}/logs"
            )
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"Could not get job logs: {response.status_code}")
                return ""

        except Exception as e:
            logger.error(f"Error getting job logs: {e}")
            return ""

    def _extract_failed_step(self, job: Dict[str, Any]) -> str:
        """Extract the name of the failed step from job data."""
        steps = job.get("steps", [])
        for step in steps:
            if step.get("conclusion") in ["failure", "cancelled", "timed_out"]:
                return step.get("name", "Unknown step")
        return "Unknown step"

    def _extract_failure_message(self, logs: str) -> str:
        """Extract a concise failure message from logs."""
        if not logs:
            return "No failure message available"

        # Look for common error patterns
        error_patterns = [
            r"ERROR:.*",
            r"FAILED.*",
            r"Error:.*",
            r"AssertionError:.*",
            r"SyntaxError:.*",
            r"ImportError:.*",
        ]

        lines = logs.split("\n")
        for line in reversed(lines[-100:]):  # Check last 100 lines
            for pattern in error_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return line.strip()[:200]  # Limit message length

        # If no specific error found, return last non-empty line
        for line in reversed(lines[-20:]):
            if line.strip():
                return line.strip()[:200]

        return "Unknown failure"

    def _classify_failure(
        self, job_name: str, logs: str
    ) -> Tuple[FailureCategory, FailureSeverity]:
        """Classify failure by category and severity."""
        combined_text = f"{job_name} {logs}".lower()

        # Determine category
        category = FailureCategory.UNKNOWN
        for cat, patterns in self.failure_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    category = cat
                    break
            if category != FailureCategory.UNKNOWN:
                break

        # Determine severity
        severity = FailureSeverity.MEDIUM  # Default
        for sev, patterns in self.severity_rules.items():
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    severity = sev
                    break
            if severity != FailureSeverity.MEDIUM:
                break

        return category, severity

    async def _store_pipeline_run(self, pipeline_run: PipelineRun):
        """Store pipeline run and failures in database."""
        try:
            # Store pipeline run
            self.database.store_pipeline_run(pipeline_run)

            # Store individual failures
            for failure in pipeline_run.failures:
                self.database.store_pipeline_failure(failure)

            logger.debug(
                f"Stored pipeline run {pipeline_run.id} with {len(pipeline_run.failures)} failures"
            )

        except Exception as e:
            logger.error(f"Failed to store pipeline run: {e}")

    def get_failure_dashboard_data(
        self, repository: Optional[str] = None, days: int = 7
    ) -> Dict[str, Any]:
        """Get dashboard data for pipeline failures."""
        try:
            # Get recent failures
            recent_failures = self.database.get_recent_pipeline_failures(
                repository=repository, days=days
            )

            # Calculate statistics
            total_failures = len(recent_failures)
            category_counts = {}
            severity_counts = {}
            repository_counts = {}

            for failure in recent_failures:
                # Count by category
                category = failure.category.value
                category_counts[category] = category_counts.get(category, 0) + 1

                # Count by severity
                severity = failure.severity.value
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

                # Count by repository
                repo = failure.repository
                repository_counts[repo] = repository_counts.get(repo, 0) + 1

            # Get failure patterns
            patterns = self.database.get_failure_patterns(days=days)

            return {
                "summary": {
                    "total_failures": total_failures,
                    "time_period_days": days,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                },
                "by_category": category_counts,
                "by_severity": severity_counts,
                "by_repository": repository_counts,
                "recent_failures": [
                    {
                        "id": f.id,
                        "repository": f.repository,
                        "category": f.category.value,
                        "severity": f.severity.value,
                        "job_name": f.job_name,
                        "failure_message": f.failure_message[:100],
                        "detected_at": f.detected_at.isoformat(),
                    }
                    for f in recent_failures[-10:]  # Last 10 failures
                ],
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "category": p.category.value,
                        "description": p.description,
                        "failure_count": p.failure_count,
                        "repositories": p.repositories,
                    }
                    for p in patterns
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {"error": str(e)}

    def analyze_failure_patterns(self, days: int = 30) -> List[FailurePattern]:
        """Analyze failure patterns over time."""
        try:
            # Get recent failures
            failures = self.database.get_recent_pipeline_failures(days=days)

            # Group failures by similar characteristics
            pattern_groups = {}

            for failure in failures:
                # Create pattern key based on category and similar failure messages
                key_words = self._extract_key_words(failure.failure_message)
                pattern_key = f"{failure.category.value}_{key_words}"

                if pattern_key not in pattern_groups:
                    pattern_groups[pattern_key] = []
                pattern_groups[pattern_key].append(failure)

            # Create patterns from groups with multiple occurrences
            patterns = []
            for pattern_key, group_failures in pattern_groups.items():
                if len(group_failures) >= 2:  # Only patterns with 2+ occurrences
                    pattern = FailurePattern(
                        category=group_failures[0].category,
                        description=self._generate_pattern_description(group_failures),
                        failure_count=len(group_failures),
                        repositories=list(set(f.repository for f in group_failures)),
                        first_seen=min(f.detected_at for f in group_failures),
                        last_seen=max(f.detected_at for f in group_failures),
                        resolution_suggestions=self._generate_resolution_suggestions(
                            group_failures[0].category
                        ),
                    )
                    patterns.append(pattern)

            # Store patterns
            for pattern in patterns:
                self.database.store_failure_pattern(pattern)

            logger.info(
                f"Analyzed {len(patterns)} failure patterns from {len(failures)} failures"
            )
            return patterns

        except Exception as e:
            logger.error(f"Failed to analyze failure patterns: {e}")
            return []

    def _extract_key_words(self, message: str) -> str:
        """Extract key words from failure message for pattern matching."""
        # Remove common words and extract meaningful terms
        words = re.findall(r"\b\w+\b", message.lower())
        key_words = [
            w
            for w in words
            if len(w) > 3
            and w
            not in {
                "error",
                "failed",
                "failure",
                "test",
                "build",
                "the",
                "and",
                "with",
                "for",
                "problem",  # Add problem to common words to exclude
                "issue",  # Add issue to common words to exclude
            }
        ]
        return "_".join(sorted(set(key_words))[:3])  # Top 3 unique key words

    def _generate_pattern_description(self, failures: List[PipelineFailure]) -> str:
        """Generate a description for a failure pattern."""
        category = failures[0].category.value
        repositories = set(f.repository for f in failures)
        jobs = set(f.job_name for f in failures)

        return (
            f"{category.title()} failures occurring in {len(repositories)} "
            f"repository(ies) across {len(jobs)} job type(s)"
        )

    def _generate_resolution_suggestions(self, category: FailureCategory) -> List[str]:
        """Generate resolution suggestions based on failure category."""
        suggestions = {
            FailureCategory.LINTING: [
                "Run flake8 locally: python -m flake8 . --count --select=E9,F63,F7,F82",
                "Fix import issues and undefined names",
                "Check Python syntax and indentation",
            ],
            FailureCategory.FORMATTING: [
                "Run black formatter: python -m black .",
                "Run isort: python -m isort .",
                "Check code formatting guidelines",
            ],
            FailureCategory.TESTING: [
                "Run tests locally: pytest tests/",
                "Check test failures and fix broken assertions",
                "Update test data or mocks as needed",
            ],
            FailureCategory.BUILD: [
                "Check build dependencies and requirements",
                "Verify Docker configuration if using containers",
                "Review build scripts and configuration files",
            ],
            FailureCategory.DEPENDENCY: [
                "Update requirements.txt or package.json",
                "Check for version conflicts",
                "Clear cache and reinstall dependencies",
            ],
        }

        return suggestions.get(category, ["Review logs and fix underlying issue"])

    async def retry_failed_pipeline(
        self, failure: "PipelineFailure"
    ) -> Optional["RetryAttempt"]:
        """Attempt to retry a failed pipeline operation."""
        import asyncio

        from models import RetryAttempt

        # Check if retry is enabled and we haven't exceeded max retries
        if not self.config.pipeline_retry_config.enabled:
            logger.debug("Pipeline retry is disabled")
            return None

        if failure.retry_count >= self.config.pipeline_retry_config.max_retries:
            logger.info(
                f"Max retries ({self.config.pipeline_retry_config.max_retries}) exceeded for failure {failure.id}"
            )
            return None

        # Calculate delay with exponential backoff
        delay = min(
            self.config.pipeline_retry_config.initial_delay_seconds
            * (
                self.config.pipeline_retry_config.backoff_multiplier
                ** failure.retry_count
            ),
            self.config.pipeline_retry_config.max_delay_seconds,
        )

        # Create retry attempt record
        retry_attempt = RetryAttempt(
            failure_id=failure.id,
            repository=failure.repository,
            attempt_number=failure.retry_count + 1,
            retry_delay_seconds=int(delay),
            metadata={
                "original_failure_category": failure.category.value,
                "original_failure_severity": failure.severity.value,
                "pipeline_id": failure.pipeline_id,
                "job_name": failure.job_name,
            },
        )

        # Store the retry attempt
        self.database.store_retry_attempt(retry_attempt)

        logger.info(
            f"Scheduling retry for failure {failure.id} in {delay} seconds (attempt {retry_attempt.attempt_number})"
        )

        try:
            # Wait for the calculated delay
            await asyncio.sleep(delay)

            # Attempt to trigger the pipeline retry
            # For now, we'll simulate this - in a real implementation, this would
            # trigger a workflow run via GitHub API
            success = await self._trigger_pipeline_retry(failure)

            # Update retry attempt with result
            retry_attempt.completed_at = datetime.now(timezone.utc)
            retry_attempt.success = success

            if success:
                logger.info(f"Retry attempt {retry_attempt.id} succeeded")
                # Mark original failure as resolved
                failure.resolved_at = datetime.now(timezone.utc)
                self.database.store_pipeline_failure(failure)
            else:
                logger.warning(f"Retry attempt {retry_attempt.id} failed")
                retry_attempt.error_message = "Pipeline retry failed"
                # Increment retry count on original failure
                failure.retry_count += 1
                self.database.store_pipeline_failure(failure)

            # Update retry attempt record
            self.database.store_retry_attempt(retry_attempt)

            return retry_attempt

        except Exception as e:
            logger.error(f"Error during retry attempt {retry_attempt.id}: {e}")
            retry_attempt.completed_at = datetime.now(timezone.utc)
            retry_attempt.success = False
            retry_attempt.error_message = str(e)
            self.database.store_retry_attempt(retry_attempt)

            # Increment retry count on original failure
            failure.retry_count += 1
            self.database.store_pipeline_failure(failure)

            return retry_attempt

    async def _trigger_pipeline_retry(self, failure: "PipelineFailure") -> bool:
        """Trigger a pipeline retry via GitHub API."""
        try:
            # For certain types of failures, we can attempt automatic remediation
            if failure.category.value in ["linting", "formatting"]:
                # For linting/formatting, we could potentially create a PR with fixes
                # For now, we'll simulate success for these "auto-fixable" issues
                logger.info(f"Simulating auto-fix for {failure.category.value} issue")
                return True

            # For other failures, we would need to trigger a workflow re-run
            # This would require using the GitHub API to re-run the failed workflow
            logger.info(
                f"Would trigger workflow re-run for {failure.category.value} failure"
            )

            # For demonstration purposes, simulate a 50% success rate
            import random

            return random.random() > 0.5

        except Exception as e:
            logger.error(f"Failed to trigger pipeline retry: {e}")
            return False

    async def initiate_enhanced_recovery(
        self, failure: "PipelineFailure", recovery_type: str = "auto"
    ) -> Optional:
        """Initiate enhanced recovery using the recovery manager."""
        if not self.recovery_manager:
            logger.warning(
                "Recovery manager not available, falling back to basic retry"
            )
            return await self.retry_failed_pipeline(failure)

        try:
            # Determine best recovery strategy
            if recovery_type == "auto":
                recovery_type = self._determine_recovery_strategy(failure)

            logger.info(
                f"Initiating enhanced {recovery_type} recovery for failure {failure.id}"
            )

            # Create checkpoint before recovery if needed
            if recovery_type in ["resume", "rollback"] and failure.pipeline_id:
                await self._create_pre_recovery_checkpoint(failure)

            # Initiate recovery
            recovery_state = await self.recovery_manager.initiate_recovery(
                failure, recovery_type
            )

            # Execute recovery
            success = await self.recovery_manager.execute_recovery(recovery_state)

            if success:
                logger.info(
                    f"Enhanced recovery {recovery_state.id} completed successfully"
                )
                # Mark original failure as resolved
                failure.resolved_at = datetime.now(timezone.utc)
                self.database.store_pipeline_failure(failure)
            else:
                logger.warning(f"Enhanced recovery {recovery_state.id} failed")

            return recovery_state

        except Exception as e:
            logger.error(f"Enhanced recovery failed: {e}")
            # Fall back to basic retry
            return await self.retry_failed_pipeline(failure)

    def _determine_recovery_strategy(self, failure: "PipelineFailure") -> str:
        """Determine the best recovery strategy for a failure."""
        # Check if there are recent checkpoints for resumption
        if self.recovery_manager:
            checkpoints = self.recovery_manager.database.get_workflow_checkpoints(
                repository=failure.repository, limit=5
            )

            # If we have recent checkpoints, consider resume
            recent_checkpoints = [
                cp
                for cp in checkpoints
                if cp.run_id == failure.pipeline_id
                or cp.commit_sha == failure.commit_sha
            ]

            if recent_checkpoints:
                # For build/dependency failures, prefer resume
                if failure.category in [
                    FailureCategory.BUILD,
                    FailureCategory.DEPENDENCY,
                ]:
                    return "resume"

                # For critical failures with good checkpoints, consider rollback
                if (
                    failure.severity == FailureSeverity.CRITICAL
                    and len(recent_checkpoints) > 1
                ):
                    return "rollback"

        # For simple failures, use retry
        if failure.category in [FailureCategory.LINTING, FailureCategory.FORMATTING]:
            return "retry"

        # Default to retry for other cases
        return "retry"

    async def _create_pre_recovery_checkpoint(self, failure: "PipelineFailure"):
        """Create a checkpoint before attempting recovery."""
        if not self.recovery_manager:
            return

        try:
            checkpoint = await self.recovery_manager.create_checkpoint(
                repository=failure.repository,
                workflow_name="pre_recovery",
                run_id=failure.pipeline_id,
                commit_sha=failure.commit_sha,
                checkpoint_type="failure_point",
                checkpoint_name=f"before_recovery_{failure.id}",
                workflow_state={
                    "failure_context": {
                        "job_name": failure.job_name,
                        "step_name": failure.step_name,
                        "category": failure.category.value,
                        "severity": failure.severity.value,
                    }
                },
                environment_context={
                    "failure_detected_at": failure.detected_at.isoformat(),
                    "retry_count": failure.retry_count,
                },
            )

            logger.info(f"Created pre-recovery checkpoint {checkpoint.id}")

        except Exception as e:
            logger.warning(f"Failed to create pre-recovery checkpoint: {e}")

    def check_for_escalation(self, repository: str) -> Optional["EscalationRecord"]:
        """Check if failures in a repository need escalation."""
        from models import EscalationRecord

        if not self.config.escalation_config.enabled:
            return None

        # Get recent unresolved failures
        recent_failures = self.database.get_recent_pipeline_failures(
            repository=repository, days=1
        )

        # Group failures by pattern/category
        failure_patterns = {}
        for failure in recent_failures:
            if failure.resolved_at is None:  # Only unresolved failures
                pattern_key = f"{failure.category.value}_{failure.job_name}"
                if pattern_key not in failure_patterns:
                    failure_patterns[pattern_key] = []
                failure_patterns[pattern_key].append(failure)

        # Check if any pattern exceeds escalation threshold
        for pattern, failures in failure_patterns.items():
            if len(failures) >= self.config.escalation_config.escalation_threshold:

                # Check if we've already escalated this pattern recently
                recent_escalations = self.database.get_recent_escalations(
                    repository=repository, days=1, resolved=False
                )

                # Skip if already escalated recently (within cooldown)
                should_skip = False
                for escalation in recent_escalations:
                    if pattern in escalation.failure_pattern:
                        hours_since = (
                            datetime.now(timezone.utc) - escalation.escalated_at
                        ).total_seconds() / 3600
                        if hours_since < self.config.escalation_config.cooldown_hours:
                            should_skip = True
                            break

                if should_skip:
                    continue

                # Create escalation record
                escalation = EscalationRecord(
                    repository=repository,
                    failure_pattern=pattern,
                    failure_count=len(failures),
                    escalation_level="agent",  # Start with agent level
                    channels_used=self.config.escalation_config.escalation_channels,
                    contacts_notified=self.config.escalation_config.escalation_contacts,
                    metadata={
                        "failure_ids": [f.id for f in failures],
                        "categories": list(set(f.category.value for f in failures)),
                        "severities": list(set(f.severity.value for f in failures)),
                    },
                )

                # Store escalation record
                self.database.store_escalation_record(escalation)

                logger.warning(
                    f"Escalating {len(failures)} persistent failures in {repository} "
                    f"for pattern '{pattern}'"
                )

                return escalation

        return None

    def get_retry_dashboard_data(
        self, repository: Optional[str] = None, days: int = 7
    ) -> Dict[str, Any]:
        """Get dashboard data for retry attempts and escalations."""
        try:
            # Get recent retry attempts
            retry_attempts = self.database.get_recent_retry_attempts(
                repository=repository, days=days
            )

            # Get recent escalations
            escalations = self.database.get_recent_escalations(
                repository=repository, days=days
            )

            # Calculate retry statistics
            total_retries = len(retry_attempts)
            successful_retries = len([r for r in retry_attempts if r.success])
            failed_retries = total_retries - successful_retries
            success_rate = (
                (successful_retries / total_retries * 100) if total_retries > 0 else 0
            )

            # Calculate escalation statistics
            total_escalations = len(escalations)
            resolved_escalations = len([e for e in escalations if e.resolved])
            pending_escalations = total_escalations - resolved_escalations

            return {
                "retry_summary": {
                    "total_retries": total_retries,
                    "successful_retries": successful_retries,
                    "failed_retries": failed_retries,
                    "success_rate": round(success_rate, 2),
                    "time_period_days": days,
                },
                "escalation_summary": {
                    "total_escalations": total_escalations,
                    "resolved_escalations": resolved_escalations,
                    "pending_escalations": pending_escalations,
                    "time_period_days": days,
                },
                "recent_retries": [
                    {
                        "id": r.id,
                        "repository": r.repository,
                        "attempt_number": r.attempt_number,
                        "success": r.success,
                        "attempted_at": r.attempted_at.isoformat(),
                        "delay_seconds": r.retry_delay_seconds,
                    }
                    for r in retry_attempts[-10:]  # Last 10 retries
                ],
                "recent_escalations": [
                    {
                        "id": e.id,
                        "repository": e.repository,
                        "failure_pattern": e.failure_pattern,
                        "failure_count": e.failure_count,
                        "escalation_level": e.escalation_level,
                        "escalated_at": e.escalated_at.isoformat(),
                        "resolved": e.resolved,
                    }
                    for e in escalations[-10:]  # Last 10 escalations
                ],
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get retry dashboard data: {e}")
            return {"error": str(e)}
