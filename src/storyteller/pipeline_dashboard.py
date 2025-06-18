"""Real-time monitoring dashboard for pipeline failures."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import Config
from database import DatabaseManager
from models import FailureCategory, FailureSeverity
from pipeline_monitor import PipelineMonitor

logger = logging.getLogger(__name__)


class PipelineDashboard:
    """Dashboard for real-time pipeline monitoring and visualization."""

    def __init__(self, config: Config):
        self.config = config
        self.database = DatabaseManager()
        self.pipeline_monitor = PipelineMonitor(config)

    def get_dashboard_data(
        self, repository: Optional[str] = None, time_range: str = "24h"
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard data for pipeline monitoring."""
        try:
            # Parse time range
            days = self._parse_time_range(time_range)

            # Get core monitoring data
            base_data = self.pipeline_monitor.get_failure_dashboard_data(
                repository=repository, days=days
            )

            # Add dashboard-specific enhancements
            dashboard_data = {
                **base_data,
                "health_metrics": self._calculate_health_metrics(repository, days),
                "trending_data": self._get_trending_data(repository, days),
                "repository_health": self._get_repository_health_scores(days),
                "alert_summary": self._get_alert_summary(repository, days),
                "recommendations": self._get_improvement_recommendations(
                    repository, days
                ),
            }

            return dashboard_data

        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {"error": str(e)}

    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to days."""
        time_range = time_range.lower()
        if time_range.endswith("h"):
            hours = int(time_range[:-1])
            return max(1, hours // 24)  # Convert to days, minimum 1
        elif time_range.endswith("d"):
            return int(time_range[:-1])
        elif time_range.endswith("w"):
            return int(time_range[:-1]) * 7
        else:
            return 1  # Default to 1 day

    def _calculate_health_metrics(
        self, repository: Optional[str], days: int
    ) -> Dict[str, Any]:
        """Calculate overall health metrics for pipelines."""
        try:
            # Get all pipeline runs in the time period
            pipeline_runs = self.database.get_recent_pipeline_runs(
                repository=repository, days=days
            )

            if not pipeline_runs:
                return {
                    "success_rate": 100.0,
                    "total_runs": 0,
                    "successful_runs": 0,
                    "failed_runs": 0,
                    "average_duration": 0,
                    "health_score": "unknown",
                }

            successful_runs = [r for r in pipeline_runs if r.status.value == "success"]
            failed_runs = [r for r in pipeline_runs if r.status.value == "failure"]

            success_rate = (len(successful_runs) / len(pipeline_runs)) * 100

            # Calculate average duration for completed runs
            completed_runs = [r for r in pipeline_runs if r.completed_at]
            avg_duration = 0
            if completed_runs:
                durations = []
                for run in completed_runs:
                    duration = (
                        run.completed_at - run.started_at
                    ).total_seconds() / 60  # minutes
                    durations.append(duration)
                avg_duration = sum(durations) / len(durations)

            # Calculate health score
            health_score = self._calculate_health_score(
                success_rate, avg_duration, len(failed_runs)
            )

            return {
                "success_rate": round(success_rate, 1),
                "total_runs": len(pipeline_runs),
                "successful_runs": len(successful_runs),
                "failed_runs": len(failed_runs),
                "average_duration": round(avg_duration, 1),
                "health_score": health_score,
            }

        except Exception as e:
            logger.error(f"Failed to calculate health metrics: {e}")
            return {"error": str(e)}

    def _calculate_health_score(
        self, success_rate: float, avg_duration: float, failed_count: int
    ) -> str:
        """Calculate overall health score based on metrics."""
        if success_rate >= 95 and failed_count <= 2:
            return "excellent"
        elif success_rate >= 85 and failed_count <= 5:
            return "good"
        elif success_rate >= 70 and failed_count <= 10:
            return "fair"
        else:
            return "poor"

    def _get_trending_data(
        self, repository: Optional[str], days: int
    ) -> Dict[str, Any]:
        """Get trending data for pipeline failures over time."""
        try:
            # Get failures grouped by day
            failures = self.database.get_recent_pipeline_failures(
                repository=repository, days=days
            )

            # Group by day
            daily_failures = {}
            daily_categories = {}

            end_date = datetime.now(timezone.utc)
            for i in range(days):
                date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
                daily_failures[date] = 0
                daily_categories[date] = {}

            for failure in failures:
                date = failure.detected_at.strftime("%Y-%m-%d")
                if date in daily_failures:
                    daily_failures[date] += 1
                    category = failure.category.value
                    daily_categories[date][category] = (
                        daily_categories[date].get(category, 0) + 1
                    )

            # Calculate trend direction
            recent_avg = sum(list(daily_failures.values())[:3]) / 3 if days >= 3 else 0
            older_avg = (
                sum(list(daily_failures.values())[-3:]) / 3 if days >= 6 else recent_avg
            )

            if recent_avg > older_avg * 1.2:
                trend = "increasing"
            elif recent_avg < older_avg * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"

            return {
                "daily_failures": daily_failures,
                "daily_categories": daily_categories,
                "trend_direction": trend,
                "trend_percentage": round(
                    ((recent_avg - older_avg) / (older_avg or 1)) * 100, 1
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get trending data: {e}")
            return {"error": str(e)}

    def _get_repository_health_scores(self, days: int) -> Dict[str, Any]:
        """Get health scores for all repositories."""
        try:
            # Get unique repositories from recent failures
            all_failures = self.database.get_recent_pipeline_failures(days=days)
            repositories = set(f.repository for f in all_failures)

            repo_scores = {}
            for repo in repositories:
                repo_data = self._calculate_health_metrics(repository=repo, days=days)
                repo_scores[repo] = {
                    "health_score": repo_data.get("health_score", "unknown"),
                    "success_rate": repo_data.get("success_rate", 0),
                    "failed_runs": repo_data.get("failed_runs", 0),
                }

            return repo_scores

        except Exception as e:
            logger.error(f"Failed to get repository health scores: {e}")
            return {"error": str(e)}

    def _get_alert_summary(
        self, repository: Optional[str], days: int
    ) -> Dict[str, Any]:
        """Get summary of current alerts and issues."""
        try:
            failures = self.database.get_recent_pipeline_failures(
                repository=repository, days=days
            )

            # Count alerts by severity
            alert_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

            active_alerts = []
            for failure in failures:
                severity = failure.severity.value
                alert_counts[severity] += 1

                # Consider unresolved failures as active alerts
                if not failure.resolved_at:
                    active_alerts.append(
                        {
                            "id": failure.id,
                            "repository": failure.repository,
                            "category": failure.category.value,
                            "severity": severity,
                            "message": failure.failure_message[:100],
                            "detected_at": failure.detected_at.isoformat(),
                        }
                    )

            # Sort by severity and time
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            active_alerts.sort(
                key=lambda x: (severity_order[x["severity"]], x["detected_at"]),
                reverse=True,
            )

            return {
                "total_alerts": len(active_alerts),
                "by_severity": alert_counts,
                "active_alerts": active_alerts[:10],  # Top 10 most critical
                "critical_count": alert_counts["critical"],
                "requires_attention": alert_counts["critical"] + alert_counts["high"]
                > 0,
            }

        except Exception as e:
            logger.error(f"Failed to get alert summary: {e}")
            return {"error": str(e)}

    def _get_improvement_recommendations(
        self, repository: Optional[str], days: int
    ) -> List[Dict[str, Any]]:
        """Get recommendations for improving pipeline health."""
        try:
            recommendations = []

            # Get failure patterns for analysis
            patterns = self.database.get_failure_patterns(days=days)

            # Repository-specific patterns if requested
            if repository:
                patterns = [p for p in patterns if repository in p.repositories]

            # Generate recommendations based on patterns
            for pattern in patterns[:5]:  # Top 5 patterns
                if pattern.failure_count >= 3:  # Significant pattern
                    recommendation = {
                        "type": "pattern_fix",
                        "priority": self._get_recommendation_priority(pattern),
                        "title": f"Address recurring {pattern.category.value} issues",
                        "description": pattern.description,
                        "failure_count": pattern.failure_count,
                        "affected_repositories": pattern.repositories,
                        "suggestions": pattern.resolution_suggestions[:3],
                    }
                    recommendations.append(recommendation)

            # Add general recommendations based on metrics
            health_metrics = self._calculate_health_metrics(repository, days)
            if health_metrics.get("success_rate", 100) < 80:
                recommendations.append(
                    {
                        "type": "general_improvement",
                        "priority": "high",
                        "title": "Improve overall pipeline success rate",
                        "description": f"Current success rate is {health_metrics.get('success_rate', 0)}%",
                        "suggestions": [
                            "Review and fix the most common failure causes",
                            "Implement better error handling in build scripts",
                            "Add pre-commit hooks to catch issues early",
                        ],
                    }
                )

            # Sort by priority
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))

            return recommendations

        except Exception as e:
            logger.error(f"Failed to get improvement recommendations: {e}")
            return []

    def _get_recommendation_priority(self, pattern) -> str:
        """Determine recommendation priority based on pattern characteristics."""
        if pattern.failure_count >= 10:
            return "critical"
        elif pattern.failure_count >= 5:
            return "high"
        elif pattern.failure_count >= 3:
            return "medium"
        else:
            return "low"

    def get_live_status(self) -> Dict[str, Any]:
        """Get current live status of all monitored pipelines."""
        try:
            # Get recent pipeline runs (last few hours)
            recent_runs = self.database.get_recent_pipeline_runs(days=1)

            # Filter to runs from last 4 hours
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=4)
            recent_runs = [r for r in recent_runs if r.started_at >= cutoff_time]

            running_pipelines = [
                r for r in recent_runs if r.status.value == "in_progress"
            ]
            failed_pipelines = [r for r in recent_runs if r.status.value == "failure"]

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_active": len(running_pipelines),
                "recent_failures": len(failed_pipelines),
                "running_pipelines": [
                    {
                        "id": r.id,
                        "repository": r.repository,
                        "branch": r.branch,
                        "workflow": r.workflow_name,
                        "started_at": r.started_at.isoformat(),
                    }
                    for r in running_pipelines
                ],
                "recent_failed": [
                    {
                        "id": r.id,
                        "repository": r.repository,
                        "branch": r.branch,
                        "workflow": r.workflow_name,
                        "failure_count": len(r.failures),
                    }
                    for r in failed_pipelines[-5:]  # Last 5 failures
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get live status: {e}")
            return {"error": str(e)}

    def export_dashboard_data(
        self,
        repository: Optional[str] = None,
        time_range: str = "7d",
        format: str = "json",
    ) -> Dict[str, Any]:
        """Export dashboard data for external systems or reporting."""
        try:
            data = self.get_dashboard_data(repository, time_range)

            # Add export metadata
            export_data = {
                "export_info": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "repository_filter": repository,
                    "time_range": time_range,
                    "format": format,
                },
                "dashboard_data": data,
            }

            return export_data

        except Exception as e:
            logger.error(f"Failed to export dashboard data: {e}")
            return {"error": str(e)}
