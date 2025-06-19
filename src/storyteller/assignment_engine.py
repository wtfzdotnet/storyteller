"""Assignment automation engine for copilot-sve-agent with workload balancing."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)


class AssignmentReason(Enum):
    """Reason for assignment decision."""

    AUTO_ELIGIBLE = "auto_eligible"
    MANUAL_OVERRIDE = "manual_override"
    WORKLOAD_LIMIT = "workload_limit"
    BLOCKED_DEPENDENCY = "blocked_dependency"
    COMPLEXITY_THRESHOLD = "complexity_threshold"


class StoryComplexity(Enum):
    """Story complexity levels for assignment decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskPriority(Enum):
    """Task priority levels for workload distribution."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AssignmentDecision:
    """Decision result for story assignment."""

    should_assign: bool
    assignee: Optional[str] = None
    reason: AssignmentReason = AssignmentReason.AUTO_ELIGIBLE
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    estimated_effort: float = 1.0  # Effort multiplier based on complexity


@dataclass
class WorkloadInfo:
    """Information about current assignee workload."""

    assignee: str
    active_stories: int
    pending_stories: int
    last_assignment: Optional[datetime] = None
    blocked_stories: int = 0
    weighted_workload: float = 0.0  # Complexity-weighted workload
    average_completion_time: Optional[float] = None  # Hours
    success_rate: float = 100.0  # Percentage


class AssignmentEngine:
    """Engine for automated agent assignment with workload balancing."""

    def __init__(self, config: Config):
        self.config = config
        self.max_concurrent_assignments = 5  # Prevent overwhelming agents
        self.assignment_history: List[Dict[str, Any]] = []
        # Multi-agent support - start with primary agent for backward compatibility
        self.available_agents = ["copilot-sve-agent"]
        # Extended agent list for load balancing (can be enabled later)
        self.extended_agents = [
            "copilot-sve-agent",
            "copilot-dev-agent",
            "copilot-qa-agent",
        ]
        # Effort multipliers for complexity levels
        self.complexity_effort_multipliers = {
            StoryComplexity.LOW: 1.0,
            StoryComplexity.MEDIUM: 2.0,
            StoryComplexity.HIGH: 4.0,
        }
        self.enable_multi_agent = False  # Feature flag for multi-agent support

    def enable_multi_agent_support(self, enabled: bool = True):
        """Enable or disable multi-agent workload distribution."""
        self.enable_multi_agent = enabled
        if enabled:
            self.available_agents = self.extended_agents
        else:
            self.available_agents = ["copilot-sve-agent"]

    def determine_story_complexity(
        self, story_content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> StoryComplexity:
        """Determine story complexity based on content and metadata."""

        content_lower = story_content.lower()

        # High complexity indicators
        high_complexity_keywords = [
            "architecture",
            "migration",
            "migrate",
            "security",
            "performance",
            "integration",
            "complex",
            "multiple repositories",
            "system-wide",
            "redesign",
            "entire",
            "zero downtime",
            "refactor",
            "overhaul",
        ]

        # Medium complexity indicators
        medium_complexity_keywords = [
            "api",
            "database",
            "authentication",
            "workflow",
            "business logic",
        ]

        high_score = sum(
            1 for keyword in high_complexity_keywords if keyword in content_lower
        )
        medium_score = sum(
            1 for keyword in medium_complexity_keywords if keyword in content_lower
        )

        # Check metadata for complexity hints
        if metadata:
            estimated_hours = metadata.get("estimated_hours", 0)
            story_points = metadata.get("story_points", 0)
            target_repos = metadata.get("target_repositories", [])

            # Multiple repositories increase complexity
            if len(target_repos) > 1:
                high_score += 1

            # High time estimates indicate complexity
            if estimated_hours and estimated_hours > 20:
                high_score += 1
            elif estimated_hours and estimated_hours > 8:
                medium_score += 1

            if story_points and story_points > 8:
                high_score += 1
            elif story_points and story_points > 3:
                medium_score += 1

        # Determine complexity level
        if high_score >= 2:
            return StoryComplexity.HIGH
        elif high_score >= 1 or medium_score >= 2:
            return StoryComplexity.MEDIUM
        else:
            return StoryComplexity.LOW

    def determine_task_priority(
        self, story_content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> TaskPriority:
        """Determine task priority based on content and metadata."""

        content_lower = story_content.lower()

        # Critical priority indicators
        critical_keywords = [
            "critical",
            "urgent",
            "hotfix",
            "security vulnerability",
            "production down",
            "outage",
            "emergency",
        ]

        # High priority indicators
        high_keywords = [
            "important",
            "high priority",
            "blocker",
            "deadline",
            "customer impact",
            "revenue impact",
        ]

        # Check content for priority indicators
        if any(keyword in content_lower for keyword in critical_keywords):
            return TaskPriority.CRITICAL
        elif any(keyword in content_lower for keyword in high_keywords):
            return TaskPriority.HIGH

        # Check metadata for priority
        if metadata:
            priority = metadata.get("priority", "").lower()
            if priority in ["critical", "urgent"]:
                return TaskPriority.CRITICAL
            elif priority in ["high", "important"]:
                return TaskPriority.HIGH
            elif priority in ["low"]:
                return TaskPriority.LOW

        return TaskPriority.NORMAL

    def check_assignment_eligibility(
        self,
        story_content: str,
        story_metadata: Optional[Dict[str, Any]] = None,
        manual_override: bool = False,
    ) -> AssignmentDecision:
        """Check if a story should be assigned to an agent."""

        if manual_override:
            # For manual override, still use load balancing to pick best agent
            best_agent = self._select_best_agent()
            return AssignmentDecision(
                should_assign=True,
                assignee=best_agent,
                reason=AssignmentReason.MANUAL_OVERRIDE,
                explanation="Manual override requested",
                priority=TaskPriority.HIGH,
                estimated_effort=2.0,
            )

        # Check story complexity and priority
        complexity = self.determine_story_complexity(story_content, story_metadata)
        priority = self.determine_task_priority(story_content, story_metadata)
        estimated_effort = self.complexity_effort_multipliers[complexity]

        # For now, auto-assign low and medium complexity stories
        # High complexity requires manual review unless it's critical priority
        if complexity == StoryComplexity.HIGH and priority != TaskPriority.CRITICAL:
            return AssignmentDecision(
                should_assign=False,
                reason=AssignmentReason.COMPLEXITY_THRESHOLD,
                explanation=f"Story complexity ({complexity.value}) exceeds auto-assignment threshold",
                metadata={"complexity": complexity.value, "priority": priority.value},
                priority=priority,
                estimated_effort=estimated_effort,
            )

        # Find best agent using load balancing
        best_agent = self._select_best_agent(estimated_effort, priority)
        if not best_agent:
            return AssignmentDecision(
                should_assign=False,
                reason=AssignmentReason.WORKLOAD_LIMIT,
                explanation="All agents at capacity",
                metadata={"complexity": complexity.value, "priority": priority.value},
                priority=priority,
                estimated_effort=estimated_effort,
            )

        # Check for blocking dependencies
        if story_metadata:
            dependencies = story_metadata.get("dependencies", [])
            if dependencies:
                # For now, assume dependencies are handled elsewhere
                # This could be expanded to check actual dependency status
                pass

        return AssignmentDecision(
            should_assign=True,
            assignee=best_agent,
            reason=AssignmentReason.AUTO_ELIGIBLE,
            explanation=f"Story eligible for auto-assignment (complexity: {complexity.value}, priority: {priority.value})",
            metadata={"complexity": complexity.value, "priority": priority.value},
            priority=priority,
            estimated_effort=estimated_effort,
        )

    def _select_best_agent(
        self,
        estimated_effort: float = 1.0,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> Optional[str]:
        """Select the best available agent using load balancing."""

        # Get workload info for all agents
        agent_workloads = []
        for agent in self.available_agents:
            workload = self._get_current_workload(agent)
            # Check if agent has capacity (use active_stories for backward compatibility)
            if workload.active_stories < self.max_concurrent_assignments:
                agent_workloads.append((agent, workload))

        if not agent_workloads:
            return None

        # Sort agents by workload (ascending) and success rate (descending)
        agent_workloads.sort(key=lambda x: (x[1].active_stories, -x[1].success_rate))

        # For critical tasks, prefer agents with higher success rates
        if priority == TaskPriority.CRITICAL and len(agent_workloads) > 1:
            # Sort by success rate first for critical tasks
            agent_workloads.sort(
                key=lambda x: (-x[1].success_rate, x[1].active_stories)
            )

        # Prefer copilot-sve-agent if it has capacity (for backward compatibility)
        preferred_agents = [
            agent for agent, workload in agent_workloads if agent == "copilot-sve-agent"
        ]
        if preferred_agents:
            return preferred_agents[0]

        return agent_workloads[0][0]

    def _check_workload_constraints(self) -> AssignmentDecision:
        """Check if any agent has capacity for new assignments."""

        # Check if any agent has capacity
        for agent in self.available_agents:
            workload = self._get_current_workload(agent)
            if workload.active_stories < self.max_concurrent_assignments:
                return AssignmentDecision(
                    should_assign=True,
                    assignee=agent,
                    reason=AssignmentReason.AUTO_ELIGIBLE,
                    explanation=f"Workload capacity available for {agent}",
                )

        # All agents at capacity
        return AssignmentDecision(
            should_assign=False,
            reason=AssignmentReason.WORKLOAD_LIMIT,
            explanation=f"All agents at capacity",
            metadata={"total_agents": len(self.available_agents)},
        )

    def _get_current_workload(self, assignee: str) -> WorkloadInfo:
        """Get current workload information for an assignee."""

        # Get assignments for this agent - include both old and new format for backward compatibility
        agent_assignments = [
            h for h in self.assignment_history if h.get("assignee") == assignee
        ]

        # Count assignments that were actually assigned (have decision=True or no decision field for old records)
        assigned_count = len(
            [
                h
                for h in agent_assignments
                if h.get("decision", True)  # Default to True for backward compatibility
            ]
        )

        # Calculate weighted workload based on complexity
        weighted_workload = 0.0
        for assignment in agent_assignments:
            if assignment.get("decision", True):  # Only count assigned stories
                effort = assignment.get("metadata", {}).get("estimated_effort", 1.0)
                weighted_workload += effort

        # Calculate performance metrics
        total_assignments = assigned_count
        completed_assignments = len(
            [
                a
                for a in agent_assignments
                if a.get("metadata", {}).get("completed", False)
            ]
        )

        success_rate = 100.0
        if total_assignments > 0:
            success_rate = (completed_assignments / total_assignments) * 100

        # Calculate average completion time (mock implementation)
        average_completion_time = None
        if completed_assignments > 0:
            # In real implementation, this would calculate from actual completion data
            average_completion_time = 24.0  # Mock: 24 hours average

        return WorkloadInfo(
            assignee=assignee,
            active_stories=assigned_count,
            pending_stories=0,
            last_assignment=(datetime.now(timezone.utc) if agent_assignments else None),
            blocked_stories=0,
            weighted_workload=weighted_workload,
            average_completion_time=average_completion_time,
            success_rate=success_rate,
        )

    def process_assignment(
        self,
        story_id: str,
        story_content: str,
        story_metadata: Optional[Dict[str, Any]] = None,
        manual_override: bool = False,
    ) -> AssignmentDecision:
        """Process assignment decision for a story."""

        logger.info(f"Processing assignment for story {story_id}")

        decision = self.check_assignment_eligibility(
            story_content=story_content,
            story_metadata=story_metadata,
            manual_override=manual_override,
        )

        # Record assignment decision in history with enhanced metadata
        assignment_record = {
            "story_id": story_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision.should_assign,
            "assignee": decision.assignee,
            "reason": decision.reason.value,
            "explanation": decision.explanation,
            "metadata": {
                **decision.metadata,
                "estimated_effort": decision.estimated_effort,
                "priority": decision.priority.value,
                "completed": False,  # Will be updated when story is completed
            },
        }

        self.assignment_history.append(assignment_record)

        logger.info(
            f"Assignment decision for {story_id}: "
            f"{'ASSIGN to ' + decision.assignee if decision.should_assign else 'SKIP'} "
            f"({decision.reason.value}) - {decision.explanation}"
        )

        return decision

    def get_assignment_queue(self) -> List[Dict[str, Any]]:
        """Get chronologically ordered assignment queue."""

        # Return assignments sorted by timestamp (chronological order)
        return sorted(
            [h for h in self.assignment_history if h["decision"]],
            key=lambda x: x["timestamp"],
        )

    def get_assignment_statistics(self) -> Dict[str, Any]:
        """Get assignment statistics for monitoring."""

        total_assignments = len(self.assignment_history)
        successful_assignments = len(
            [h for h in self.assignment_history if h["decision"]]
        )

        if total_assignments == 0:
            return {
                "total_processed": 0,
                "assigned": 0,
                "assignment_rate": 0.0,
                "reasons": {},
                "agent_workloads": {},
                "priority_distribution": {},
                "complexity_distribution": {},
            }

        # Count assignment reasons
        reason_counts = {}
        priority_counts = {}
        complexity_counts = {}

        for record in self.assignment_history:
            reason = record["reason"]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

            # Count priority and complexity distribution
            metadata = record.get("metadata", {})
            priority = metadata.get("priority", "normal")
            complexity = metadata.get("complexity", "low")

            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1

        # Get current workload for all agents
        agent_workloads = {}
        for agent in self.available_agents:
            workload = self._get_current_workload(agent)
            agent_workloads[agent] = {
                "active_stories": workload.active_stories,
                "weighted_workload": workload.weighted_workload,
                "success_rate": workload.success_rate,
                "average_completion_time": workload.average_completion_time,
            }

        return {
            "total_processed": total_assignments,
            "assigned": successful_assignments,
            "assignment_rate": round(
                successful_assignments / total_assignments * 100, 2
            ),
            "reasons": reason_counts,
            "agent_workloads": agent_workloads,
            "priority_distribution": priority_counts,
            "complexity_distribution": complexity_counts,
            "total_agents": len(self.available_agents),
        }

    def mark_assignment_completed(self, story_id: str, success: bool = True) -> bool:
        """Mark an assignment as completed for performance tracking."""

        for record in self.assignment_history:
            if record["story_id"] == story_id:
                record["metadata"]["completed"] = True
                record["metadata"]["success"] = success
                record["metadata"]["completion_time"] = datetime.now(
                    timezone.utc
                ).isoformat()
                return True
        return False

    def get_agent_performance_metrics(self, agent: str) -> Dict[str, Any]:
        """Get detailed performance metrics for a specific agent."""

        workload = self._get_current_workload(agent)
        agent_assignments = [
            h
            for h in self.assignment_history
            if h.get("assignee") == agent and h.get("decision", False)
        ]

        # Calculate workload distribution by priority and complexity
        priority_workload = {}
        complexity_workload = {}

        for assignment in agent_assignments:
            metadata = assignment.get("metadata", {})
            priority = metadata.get("priority", "normal")
            complexity = metadata.get("complexity", "low")
            effort = metadata.get("estimated_effort", 1.0)

            priority_workload[priority] = priority_workload.get(priority, 0) + effort
            complexity_workload[complexity] = (
                complexity_workload.get(complexity, 0) + effort
            )

        return {
            "agent": agent,
            "active_stories": workload.active_stories,
            "weighted_workload": workload.weighted_workload,
            "success_rate": workload.success_rate,
            "average_completion_time": workload.average_completion_time,
            "priority_workload_distribution": priority_workload,
            "complexity_workload_distribution": complexity_workload,
            "capacity_utilization": (
                round(
                    (workload.weighted_workload / (self.max_concurrent_assignments * 2))
                    * 100,
                    2,
                )
                if self.max_concurrent_assignments > 0
                else 0
            ),
        }

    def get_workload_distribution_recommendation(self) -> Dict[str, Any]:
        """Get recommendations for optimal workload distribution."""

        agent_metrics = []
        for agent in self.available_agents:
            metrics = self.get_agent_performance_metrics(agent)
            agent_metrics.append(metrics)

        # Sort by capacity utilization
        agent_metrics.sort(key=lambda x: x["capacity_utilization"])

        recommendations = []

        # Check for overloaded agents
        overloaded_agents = [m for m in agent_metrics if m["capacity_utilization"] > 80]
        underutilized_agents = [
            m for m in agent_metrics if m["capacity_utilization"] < 50
        ]

        if overloaded_agents:
            recommendations.append(
                {
                    "type": "rebalance",
                    "message": f"Agents {[a['agent'] for a in overloaded_agents]} are overloaded",
                    "suggestion": "Consider redistributing work or reducing assignment limits",
                }
            )

        if underutilized_agents and overloaded_agents:
            recommendations.append(
                {
                    "type": "redistribute",
                    "message": "Workload imbalance detected",
                    "suggestion": f"Redistribute work from {[a['agent'] for a in overloaded_agents]} to {[a['agent'] for a in underutilized_agents]}",
                }
            )

        return {
            "agent_metrics": agent_metrics,
            "recommendations": recommendations,
            "overall_utilization": (
                round(
                    sum(m["capacity_utilization"] for m in agent_metrics)
                    / len(agent_metrics),
                    2,
                )
                if agent_metrics
                else 0
            ),
        }
