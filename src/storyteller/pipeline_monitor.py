"""Pipeline failure monitoring system for automated agent workflow."""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from database import DatabaseManager
from github_handler import GitHubHandler
from models import (
    FailureCategory,
    FailurePattern,
    FailureSeverity,
    PipelineFailure,
    PipelineRun,
    PipelineStatus,
)

logger = logging.getLogger(__name__)


class PipelineMonitor:
    """Monitor pipeline failures across repositories with classification and analysis."""

    def __init__(self, config: Config):
        self.config = config
        self.database = DatabaseManager()
        self.github_handler = GitHubHandler(config)

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
