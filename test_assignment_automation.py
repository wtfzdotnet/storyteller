"""Tests for assignment automation engine."""

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from assignment_engine import (
    AssignmentDecision,
    AssignmentEngine,
    AssignmentReason,
    StoryComplexity,
    WorkloadInfo,
)
from config import Config


class TestAssignmentEngine(unittest.TestCase):
    """Test the AssignmentEngine class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock(spec=Config)
        self.engine = AssignmentEngine(self.config)

    def test_determine_story_complexity_low(self):
        """Test story complexity determination for low complexity."""
        story_content = "Update button text on login page"
        
        complexity = self.engine.determine_story_complexity(story_content)
        
        self.assertEqual(complexity, StoryComplexity.LOW)

    def test_determine_story_complexity_medium(self):
        """Test story complexity determination for medium complexity."""
        story_content = "Implement user authentication API endpoint"
        
        complexity = self.engine.determine_story_complexity(story_content)
        
        self.assertEqual(complexity, StoryComplexity.MEDIUM)

    def test_determine_story_complexity_high(self):
        """Test story complexity determination for high complexity."""
        story_content = "Design new system architecture for performance optimization across multiple repositories"
        
        complexity = self.engine.determine_story_complexity(story_content)
        
        self.assertEqual(complexity, StoryComplexity.HIGH)

    def test_determine_story_complexity_with_metadata(self):
        """Test story complexity with metadata hints."""
        story_content = "Update user profile"
        metadata = {
            "estimated_hours": 25,
            "target_repositories": ["backend", "frontend"],
            "story_points": 10
        }
        
        complexity = self.engine.determine_story_complexity(story_content, metadata)
        
        self.assertEqual(complexity, StoryComplexity.HIGH)

    def test_check_assignment_eligibility_manual_override(self):
        """Test assignment eligibility with manual override."""
        story_content = "Complex architecture changes requiring manual review"
        
        decision = self.engine.check_assignment_eligibility(
            story_content=story_content,
            manual_override=True
        )
        
        self.assertTrue(decision.should_assign)
        self.assertEqual(decision.assignee, "copilot-sve-agent")
        self.assertEqual(decision.reason, AssignmentReason.MANUAL_OVERRIDE)

    def test_check_assignment_eligibility_high_complexity_blocked(self):
        """Test that high complexity stories are not auto-assigned."""
        story_content = "Redesign entire system architecture for security and performance"
        
        decision = self.engine.check_assignment_eligibility(story_content=story_content)
        
        self.assertFalse(decision.should_assign)
        self.assertEqual(decision.reason, AssignmentReason.COMPLEXITY_THRESHOLD)
        self.assertIn("complexity", decision.metadata)

    def test_check_assignment_eligibility_low_complexity_approved(self):
        """Test that low complexity stories are auto-assigned."""
        story_content = "Fix typo in error message"
        
        decision = self.engine.check_assignment_eligibility(story_content=story_content)
        
        self.assertTrue(decision.should_assign)
        self.assertEqual(decision.assignee, "copilot-sve-agent")
        self.assertEqual(decision.reason, AssignmentReason.AUTO_ELIGIBLE)

    def test_check_assignment_eligibility_medium_complexity_approved(self):
        """Test that medium complexity stories are auto-assigned."""
        story_content = "Add new API endpoint for user preferences"
        
        decision = self.engine.check_assignment_eligibility(story_content=story_content)
        
        self.assertTrue(decision.should_assign)
        self.assertEqual(decision.assignee, "copilot-sve-agent")
        self.assertEqual(decision.reason, AssignmentReason.AUTO_ELIGIBLE)

    def test_workload_constraint_at_capacity(self):
        """Test workload constraint when agent is at capacity."""
        # Mock workload to show agent at capacity
        self.engine.assignment_history = [
            {"assignee": "copilot-sve-agent", "story_id": f"story_{i}"} 
            for i in range(5)
        ]
        
        story_content = "Simple task"
        
        decision = self.engine.check_assignment_eligibility(story_content=story_content)
        
        self.assertFalse(decision.should_assign)
        self.assertEqual(decision.reason, AssignmentReason.WORKLOAD_LIMIT)

    def test_process_assignment_records_history(self):
        """Test that assignment processing records history."""
        story_id = "test_story_001"
        story_content = "Update documentation"
        
        decision = self.engine.process_assignment(story_id, story_content)
        
        self.assertEqual(len(self.engine.assignment_history), 1)
        
        record = self.engine.assignment_history[0]
        self.assertEqual(record["story_id"], story_id)
        self.assertEqual(record["decision"], decision.should_assign)
        self.assertIn("timestamp", record)

    def test_get_assignment_queue_chronological_order(self):
        """Test that assignment queue returns chronologically ordered assignments."""
        # Process multiple assignments
        assignments = [
            ("story_001", "Task 1"),
            ("story_002", "Task 2"),
            ("story_003", "Task 3"),
        ]
        
        for story_id, content in assignments:
            self.engine.process_assignment(story_id, content)
        
        queue = self.engine.get_assignment_queue()
        
        # Should have all assigned stories
        assigned_count = len([h for h in self.engine.assignment_history if h["decision"]])
        self.assertEqual(len(queue), assigned_count)
        
        # Should be in chronological order
        timestamps = [item["timestamp"] for item in queue]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_get_assignment_statistics(self):
        """Test assignment statistics calculation."""
        # Process a mix of assignments
        assignments = [
            ("story_001", "Simple task"),  # Should be assigned
            ("story_002", "Complex architecture changes"),  # Should be blocked
            ("story_003", "Another simple task"),  # Should be assigned
        ]
        
        for story_id, content in assignments:
            self.engine.process_assignment(story_id, content)
        
        stats = self.engine.get_assignment_statistics()
        
        self.assertEqual(stats["total_processed"], 3)
        self.assertGreater(stats["assigned"], 0)
        self.assertLess(stats["assigned"], 3)  # Some should be blocked
        self.assertIn("assignment_rate", stats)
        self.assertIn("reasons", stats)

    def test_get_current_workload(self):
        """Test current workload calculation."""
        # Add some assignment history
        self.engine.assignment_history = [
            {"assignee": "copilot-sve-agent", "story_id": "story_1"},
            {"assignee": "copilot-sve-agent", "story_id": "story_2"},
            {"assignee": "other-user", "story_id": "story_3"},
        ]
        
        workload = self.engine._get_current_workload("copilot-sve-agent")
        
        self.assertEqual(workload.assignee, "copilot-sve-agent")
        self.assertEqual(workload.active_stories, 2)
        self.assertIsNotNone(workload.last_assignment)

    def test_assignment_decision_dataclass(self):
        """Test AssignmentDecision dataclass functionality."""
        decision = AssignmentDecision(
            should_assign=True,
            assignee="test-agent",
            reason=AssignmentReason.AUTO_ELIGIBLE,
            explanation="Test explanation",
            metadata={"test": "data"}
        )
        
        self.assertTrue(decision.should_assign)
        self.assertEqual(decision.assignee, "test-agent")
        self.assertEqual(decision.reason, AssignmentReason.AUTO_ELIGIBLE)
        self.assertEqual(decision.metadata["test"], "data")

    def test_workload_info_dataclass(self):
        """Test WorkloadInfo dataclass functionality."""
        workload = WorkloadInfo(
            assignee="test-agent",
            active_stories=3,
            pending_stories=1,
            blocked_stories=0
        )
        
        self.assertEqual(workload.assignee, "test-agent")
        self.assertEqual(workload.active_stories, 3)
        self.assertEqual(workload.pending_stories, 1)
        self.assertIsNone(workload.last_assignment)


class TestAssignmentEngineIntegration(unittest.TestCase):
    """Integration tests for assignment engine with workflow components."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock(spec=Config)
        self.engine = AssignmentEngine(self.config)

    def test_end_to_end_assignment_workflow(self):
        """Test complete assignment workflow from story to decision."""
        story_scenarios = [
            {
                "story_id": "epic_001_us_001",
                "content": "As a user, I want to update my profile picture",
                "metadata": {"story_points": 3, "estimated_hours": 4},
                "expected_assigned": True,
            },
            {
                "story_id": "epic_001_us_002",
                "content": "Redesign entire authentication system with multi-factor authentication",
                "metadata": {"story_points": 13, "estimated_hours": 40},
                "expected_assigned": False,
            },
            {
                "story_id": "epic_002_us_001",
                "content": "Add validation to contact form",
                "metadata": {"story_points": 2, "estimated_hours": 3},
                "expected_assigned": True,
            },
        ]
        
        results = []
        for scenario in story_scenarios:
            decision = self.engine.process_assignment(
                story_id=scenario["story_id"],
                story_content=scenario["content"],
                story_metadata=scenario["metadata"]
            )
            results.append({
                "scenario": scenario,
                "decision": decision,
            })
        
        # Verify assignment decisions
        for result in results:
            scenario = result["scenario"]
            decision = result["decision"]
            
            self.assertEqual(
                decision.should_assign,
                scenario["expected_assigned"],
                f"Assignment decision mismatch for {scenario['story_id']}"
            )
            
            if decision.should_assign:
                self.assertEqual(decision.assignee, "copilot-sve-agent")
        
        # Verify assignment queue is in chronological order
        queue = self.engine.get_assignment_queue()
        assigned_stories = [s for s in story_scenarios if s["expected_assigned"]]
        self.assertEqual(len(queue), len(assigned_stories))
        
        # Verify statistics
        stats = self.engine.get_assignment_statistics()
        self.assertEqual(stats["total_processed"], len(story_scenarios))
        self.assertEqual(stats["assigned"], len(assigned_stories))

    def test_manual_override_bypasses_complexity_check(self):
        """Test that manual override allows assignment of high complexity stories."""
        high_complexity_story = "Migrate entire database to new architecture with zero downtime"
        
        # Normal assignment should be blocked
        normal_decision = self.engine.process_assignment(
            story_id="story_normal",
            story_content=high_complexity_story
        )
        self.assertFalse(normal_decision.should_assign)
        
        # Manual override should allow assignment
        override_decision = self.engine.process_assignment(
            story_id="story_override",
            story_content=high_complexity_story,
            manual_override=True
        )
        self.assertTrue(override_decision.should_assign)
        self.assertEqual(override_decision.reason, AssignmentReason.MANUAL_OVERRIDE)

    def test_workload_balancing_prevents_overload(self):
        """Test that workload balancing prevents agent overload."""
        # Fill up the agent's capacity
        for i in range(self.engine.max_concurrent_assignments):
            decision = self.engine.process_assignment(
                story_id=f"story_{i}",
                story_content="Simple task"
            )
            self.assertTrue(decision.should_assign, f"Story {i} should be assigned")
        
        # Next assignment should be blocked due to capacity
        decision = self.engine.process_assignment(
            story_id="story_overflow",
            story_content="Another simple task"
        )
        self.assertFalse(decision.should_assign)
        self.assertEqual(decision.reason, AssignmentReason.WORKLOAD_LIMIT)


if __name__ == "__main__":
    unittest.main()