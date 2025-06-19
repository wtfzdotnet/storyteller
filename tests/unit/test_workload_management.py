"""Unit tests for enhanced workload management features."""

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from assignment_engine import (
    AssignmentDecision,
    AssignmentEngine,
    AssignmentReason,
    StoryComplexity,
    TaskPriority,
    WorkloadInfo,
)
from config import Config


class TestWorkloadManagement(unittest.TestCase):
    """Test enhanced workload management features."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock(spec=Config)
        self.engine = AssignmentEngine(self.config)

    def test_task_priority_determination(self):
        """Test task priority determination based on content and metadata."""
        # Test critical priority
        critical_content = "CRITICAL: Security vulnerability in production"
        priority = self.engine.determine_task_priority(critical_content)
        self.assertEqual(priority, TaskPriority.CRITICAL)

        # Test high priority
        high_content = "Important customer deadline approaching"
        priority = self.engine.determine_task_priority(high_content)
        self.assertEqual(priority, TaskPriority.HIGH)

        # Test normal priority (default)
        normal_content = "Add new feature to user profile"
        priority = self.engine.determine_task_priority(normal_content)
        self.assertEqual(priority, TaskPriority.NORMAL)

        # Test metadata priority
        metadata_priority = {"priority": "critical"}
        priority = self.engine.determine_task_priority("Simple task", metadata_priority)
        self.assertEqual(priority, TaskPriority.CRITICAL)

    def test_multi_agent_support_disabled_by_default(self):
        """Test that multi-agent support is disabled by default for backward compatibility."""
        self.assertFalse(self.engine.enable_multi_agent)
        self.assertEqual(self.engine.available_agents, ["copilot-sve-agent"])

    def test_enable_multi_agent_support(self):
        """Test enabling multi-agent support."""
        # Enable multi-agent support
        self.engine.enable_multi_agent_support(True)

        self.assertTrue(self.engine.enable_multi_agent)
        self.assertEqual(len(self.engine.available_agents), 3)
        self.assertIn("copilot-sve-agent", self.engine.available_agents)
        self.assertIn("copilot-dev-agent", self.engine.available_agents)
        self.assertIn("copilot-qa-agent", self.engine.available_agents)

        # Disable multi-agent support
        self.engine.enable_multi_agent_support(False)

        self.assertFalse(self.engine.enable_multi_agent)
        self.assertEqual(self.engine.available_agents, ["copilot-sve-agent"])

    def test_weighted_workload_calculation(self):
        """Test weighted workload calculation based on complexity."""
        # Add assignments with different complexity levels
        self.engine.assignment_history = [
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_1",
                "decision": True,
                "metadata": {"estimated_effort": 1.0},  # Low complexity
            },
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_2",
                "decision": True,
                "metadata": {"estimated_effort": 2.0},  # Medium complexity
            },
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_3",
                "decision": True,
                "metadata": {"estimated_effort": 4.0},  # High complexity
            },
        ]

        workload = self.engine._get_current_workload("copilot-sve-agent")

        self.assertEqual(workload.assignee, "copilot-sve-agent")
        self.assertEqual(workload.active_stories, 3)
        self.assertEqual(workload.weighted_workload, 7.0)  # 1.0 + 2.0 + 4.0

    def test_assignment_decision_with_priority_and_effort(self):
        """Test that assignment decisions include priority and estimated effort."""
        story_content = "CRITICAL: Fix security vulnerability in authentication system"
        metadata = {"priority": "critical", "estimated_hours": 40}

        decision = self.engine.check_assignment_eligibility(
            story_content=story_content, story_metadata=metadata
        )

        self.assertTrue(decision.should_assign)
        self.assertEqual(decision.priority, TaskPriority.CRITICAL)
        self.assertEqual(
            decision.estimated_effort, 4.0
        )  # High complexity due to "security" + hours > 20
        self.assertIn("critical", decision.metadata["priority"])

    def test_mark_assignment_completed(self):
        """Test marking assignments as completed for performance tracking."""
        # Add an assignment
        decision = self.engine.process_assignment(
            story_id="test_story", story_content="Simple task"
        )

        self.assertTrue(decision.should_assign)

        # Mark as completed
        success = self.engine.mark_assignment_completed("test_story", success=True)
        self.assertTrue(success)

        # Check that completion was recorded
        assignment = next(
            (
                h
                for h in self.engine.assignment_history
                if h["story_id"] == "test_story"
            ),
            None,
        )
        self.assertIsNotNone(assignment)
        self.assertTrue(assignment["metadata"]["completed"])
        self.assertTrue(assignment["metadata"]["success"])
        self.assertIn("completion_time", assignment["metadata"])

    def test_agent_performance_metrics(self):
        """Test agent performance metrics calculation."""
        # Enable multi-agent support for this test
        self.engine.enable_multi_agent_support(True)

        # Add some assignment history
        self.engine.assignment_history = [
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_1",
                "decision": True,
                "metadata": {
                    "estimated_effort": 2.0,
                    "priority": "high",
                    "complexity": "medium",
                    "completed": True,
                    "success": True,
                },
            },
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_2",
                "decision": True,
                "metadata": {
                    "estimated_effort": 1.0,
                    "priority": "normal",
                    "complexity": "low",
                    "completed": False,
                },
            },
        ]

        metrics = self.engine.get_agent_performance_metrics("copilot-sve-agent")

        self.assertEqual(metrics["agent"], "copilot-sve-agent")
        self.assertEqual(metrics["active_stories"], 2)
        self.assertEqual(metrics["weighted_workload"], 3.0)
        self.assertEqual(metrics["success_rate"], 50.0)  # 1 completed out of 2
        self.assertEqual(metrics["priority_workload_distribution"]["high"], 2.0)
        self.assertEqual(metrics["priority_workload_distribution"]["normal"], 1.0)
        self.assertEqual(metrics["complexity_workload_distribution"]["medium"], 2.0)
        self.assertEqual(metrics["complexity_workload_distribution"]["low"], 1.0)

    def test_workload_distribution_recommendation(self):
        """Test workload distribution recommendations."""
        # Enable multi-agent support
        self.engine.enable_multi_agent_support(True)

        # Create imbalanced workload - overload one agent
        overloaded_assignments = [
            {
                "assignee": "copilot-sve-agent",
                "story_id": f"story_{i}",
                "decision": True,
                "metadata": {"estimated_effort": 2.0},
            }
            for i in range(6)  # 12.0 total effort - high utilization
        ]

        self.engine.assignment_history = overloaded_assignments

        recommendations = self.engine.get_workload_distribution_recommendation()

        # Check that metrics are calculated correctly
        self.assertEqual(len(recommendations["agent_metrics"]), 3)

        # Check that overloaded agent is identified
        overloaded_metric = next(
            (
                m
                for m in recommendations["agent_metrics"]
                if m["agent"] == "copilot-sve-agent"
            ),
            None,
        )
        self.assertIsNotNone(overloaded_metric)
        self.assertGreater(overloaded_metric["capacity_utilization"], 80)

        # Check that recommendations are provided
        self.assertGreater(len(recommendations["recommendations"]), 0)

        # Should suggest rebalancing
        rebalance_rec = next(
            (r for r in recommendations["recommendations"] if r["type"] == "rebalance"),
            None,
        )
        self.assertIsNotNone(rebalance_rec)

    def test_enhanced_assignment_statistics(self):
        """Test enhanced assignment statistics with priority and complexity distribution."""
        # Add varied assignments
        assignments = [
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_1",
                "decision": True,
                "reason": "auto_eligible",
                "metadata": {"priority": "critical", "complexity": "high"},
            },
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_2",
                "decision": True,
                "reason": "auto_eligible",
                "metadata": {"priority": "normal", "complexity": "medium"},
            },
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_3",
                "decision": False,
                "reason": "workload_limit",
                "metadata": {"priority": "low", "complexity": "low"},
            },
        ]

        self.engine.assignment_history = assignments

        stats = self.engine.get_assignment_statistics()

        self.assertEqual(stats["total_processed"], 3)
        self.assertEqual(stats["assigned"], 2)
        self.assertEqual(stats["assignment_rate"], 66.67)

        # Check priority distribution
        self.assertEqual(stats["priority_distribution"]["critical"], 1)
        self.assertEqual(stats["priority_distribution"]["normal"], 1)
        self.assertEqual(stats["priority_distribution"]["low"], 1)

        # Check complexity distribution
        self.assertEqual(stats["complexity_distribution"]["high"], 1)
        self.assertEqual(stats["complexity_distribution"]["medium"], 1)
        self.assertEqual(stats["complexity_distribution"]["low"], 1)

        # Check agent workloads
        self.assertIn("agent_workloads", stats)
        self.assertIn("copilot-sve-agent", stats["agent_workloads"])

    def test_load_balancing_with_critical_priority(self):
        """Test that critical priority tasks prefer agents with higher success rates."""
        # Enable multi-agent support
        self.engine.enable_multi_agent_support(True)

        # Set up different success rates for agents through assignment history
        self.engine.assignment_history = [
            # copilot-sve-agent: 100% success rate (1/1)
            {
                "assignee": "copilot-sve-agent",
                "story_id": "story_1",
                "decision": True,
                "metadata": {
                    "completed": True,
                    "success": True,
                    "estimated_effort": 1.0,
                },
            },
            # copilot-dev-agent: 50% success rate (1/2)
            {
                "assignee": "copilot-dev-agent",
                "story_id": "story_2",
                "decision": True,
                "metadata": {
                    "completed": True,
                    "success": True,
                    "estimated_effort": 1.0,
                },
            },
            {
                "assignee": "copilot-dev-agent",
                "story_id": "story_3",
                "decision": True,
                "metadata": {
                    "completed": True,
                    "success": False,
                    "estimated_effort": 1.0,
                },
            },
        ]

        # Test critical priority assignment
        critical_content = "CRITICAL: Production system down"
        decision = self.engine.check_assignment_eligibility(critical_content)

        self.assertTrue(decision.should_assign)
        self.assertEqual(decision.priority, TaskPriority.CRITICAL)
        # Should prefer agent with higher success rate for critical tasks
        self.assertEqual(decision.assignee, "copilot-sve-agent")


if __name__ == "__main__":
    unittest.main()
