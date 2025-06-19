"""Integration test for manual intervention system."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.storyteller.models import (
    ManualIntervention, 
    ConsensusResult, 
    ConsensusStatus,
    Conversation,
    ConversationParticipant
)
from src.storyteller.database import DatabaseManager
from src.storyteller.consensus_engine import ConsensusEngine


class TestManualInterventionIntegration(unittest.TestCase):
    """Integration test for complete manual intervention workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.mktemp(suffix='.db')
        self.db = DatabaseManager(self.temp_db)
        self.db.init_database()

    def tearDown(self):
        """Clean up test fixtures."""
        if Path(self.temp_db).exists():
            Path(self.temp_db).unlink()

    def test_full_manual_intervention_workflow(self):
        """Test the complete manual intervention workflow."""
        
        # Mock config to avoid environment dependencies
        from src.storyteller.config import Config
        mock_config = Config(
            github_token="test",
            auto_consensus_threshold=70,
            auto_consensus_max_iterations=5
        )
        
        # Initialize consensus engine
        engine = ConsensusEngine(mock_config)
        
        # Create a consensus process that fails
        consensus = engine.create_consensus_process(
            conversation_id="conv_integration_test",
            decision_topic="Should we implement feature X with approach Y?",
            threshold=0.8
        )
        
        # Simulate consensus failure
        consensus.status = ConsensusStatus.FAILED
        consensus.iterations = 5
        
        # Step 1: Check if intervention is needed
        requires_intervention, reason = engine.check_consensus_requires_intervention(consensus)
        self.assertTrue(requires_intervention)
        self.assertEqual(reason, "failed_consensus")
        
        # Step 2: Trigger manual intervention
        intervention_id = engine.trigger_manual_intervention(
            consensus=consensus,
            conversation_id="conv_integration_test",
            trigger_reason=reason,
            intervention_type="decision",
            metadata={"urgency": "high", "deadline": "2024-01-15"},
            db=self.db
        )
        
        self.assertIsNotNone(intervention_id)
        self.assertTrue(intervention_id.startswith("intervention_"))
        
        # Step 3: Verify intervention was stored
        stored_intervention = self.db.get_manual_intervention(intervention_id)
        self.assertIsNotNone(stored_intervention)
        self.assertEqual(stored_intervention.conversation_id, "conv_integration_test")
        self.assertEqual(stored_intervention.consensus_id, consensus.id)
        self.assertEqual(stored_intervention.trigger_reason, "failed_consensus")
        self.assertEqual(stored_intervention.status, "pending")
        self.assertEqual(stored_intervention.metadata["urgency"], "high")
        
        # Step 4: Check intervention appears in pending list
        pending_interventions = self.db.get_pending_interventions()
        self.assertEqual(len(pending_interventions), 1)
        self.assertEqual(pending_interventions[0].id, intervention_id)
        
        # Step 5: Simulate human review and decision
        human_decision = "Approved with modifications: implement feature X with approach Z instead"
        human_rationale = """
        After reviewing the consensus failure, I've decided to:
        1. Approve the feature implementation
        2. Change approach from Y to Z for better performance
        3. Add additional security requirements
        4. Extend timeline by 1 week for proper testing
        """
        
        # Step 6: Resolve the intervention
        success = engine.resolve_manual_intervention(
            intervention_id=intervention_id,
            human_decision=human_decision,
            human_rationale=human_rationale,
            intervener_id="pm_alice_smith",
            intervener_role="project-manager",
            override_data={
                "approach_changed": True,
                "new_approach": "Z",
                "timeline_extension": "1 week",
                "additional_requirements": ["security_review", "performance_testing"]
            },
            db=self.db
        )
        
        self.assertTrue(success)
        
        # Step 7: Verify intervention is resolved
        resolved_intervention = self.db.get_manual_intervention(intervention_id)
        self.assertEqual(resolved_intervention.status, "resolved")
        self.assertEqual(resolved_intervention.human_decision, human_decision)
        self.assertEqual(resolved_intervention.human_rationale, human_rationale)
        self.assertEqual(resolved_intervention.intervener_id, "pm_alice_smith")
        self.assertEqual(resolved_intervention.intervener_role, "project-manager")
        self.assertIsNotNone(resolved_intervention.resolved_at)
        
        # Step 8: Verify override data was stored
        self.assertEqual(resolved_intervention.override_data["approach_changed"], True)
        self.assertEqual(resolved_intervention.override_data["new_approach"], "Z")
        
        # Step 9: Verify audit trail
        self.assertGreaterEqual(len(resolved_intervention.audit_trail), 2)
        
        # Check intervention_triggered entry
        trigger_entry = resolved_intervention.audit_trail[0]
        self.assertEqual(trigger_entry["action"], "intervention_triggered")
        self.assertEqual(trigger_entry["actor"], "system")
        
        # Check intervention_resolved entry
        resolve_entry = resolved_intervention.audit_trail[1]
        self.assertEqual(resolve_entry["action"], "intervention_resolved")
        self.assertEqual(resolve_entry["actor"], "project-manager:pm_alice_smith")
        
        # Step 10: Verify no longer appears in pending list
        pending_after_resolve = self.db.get_pending_interventions()
        self.assertEqual(len(pending_after_resolve), 0)
        
        print("✓ Full manual intervention workflow test passed!")

    def test_multiple_interventions_workflow(self):
        """Test handling multiple interventions simultaneously."""
        
        from src.storyteller.config import Config
        mock_config = Config(
            github_token="test",
            auto_consensus_threshold=70,
            auto_consensus_max_iterations=5
        )
        
        engine = ConsensusEngine(mock_config)
        
        # Create multiple failed consensus processes
        interventions = []
        for i in range(3):
            consensus = engine.create_consensus_process(
                conversation_id=f"conv_multi_test_{i}",
                decision_topic=f"Decision topic {i}",
                threshold=0.8
            )
            consensus.status = ConsensusStatus.TIMEOUT
            
            intervention_id = engine.trigger_manual_intervention(
                consensus=consensus,
                conversation_id=f"conv_multi_test_{i}",
                trigger_reason="timeout",
                intervention_type="decision",
                db=self.db
            )
            interventions.append(intervention_id)
        
        # Verify all interventions are pending
        pending = self.db.get_pending_interventions()
        self.assertEqual(len(pending), 3)
        
        # Resolve interventions in different ways
        # 1. Approve first intervention
        engine.resolve_manual_intervention(
            intervention_id=interventions[0],
            human_decision="Approved as-is",
            human_rationale="Original decision is acceptable",
            intervener_id="pm_001",
            intervener_role="project-manager",
            db=self.db
        )
        
        # 2. Reject second intervention
        engine.resolve_manual_intervention(
            intervention_id=interventions[1],
            human_decision="Rejected",
            human_rationale="Requires further analysis",
            intervener_id="director_002",
            intervener_role="technical-director",
            db=self.db
        )
        
        # 3. Modify third intervention
        engine.resolve_manual_intervention(
            intervention_id=interventions[2],
            human_decision="Approved with major modifications",
            human_rationale="Concept good but implementation needs rework",
            intervener_id="architect_003",
            intervener_role="chief-architect",
            override_data={"requires_redesign": True},
            db=self.db
        )
        
        # Verify all interventions are resolved
        pending_final = self.db.get_pending_interventions()
        self.assertEqual(len(pending_final), 0)
        
        # Verify different resolution statuses
        intervention_1 = self.db.get_manual_intervention(interventions[0])
        intervention_2 = self.db.get_manual_intervention(interventions[1])
        intervention_3 = self.db.get_manual_intervention(interventions[2])
        
        self.assertEqual(intervention_1.human_decision, "Approved as-is")
        self.assertEqual(intervention_2.human_decision, "Rejected")
        self.assertEqual(intervention_3.human_decision, "Approved with major modifications")
        
        self.assertEqual(intervention_1.intervener_role, "project-manager")
        self.assertEqual(intervention_2.intervener_role, "technical-director")
        self.assertEqual(intervention_3.intervener_role, "chief-architect")
        
        print("✓ Multiple interventions workflow test passed!")

    def test_intervention_automatic_detection(self):
        """Test automatic detection of when interventions are needed."""
        
        from src.storyteller.config import Config
        mock_config = Config(
            github_token="test",
            auto_consensus_threshold=70,
            auto_consensus_max_iterations=5
        )
        
        engine = ConsensusEngine(mock_config)
        
        # Test different scenarios that should trigger intervention
        test_cases = [
            {
                "status": ConsensusStatus.FAILED,
                "expected_intervention": True,
                "expected_reason": "failed_consensus"
            },
            {
                "status": ConsensusStatus.TIMEOUT,
                "expected_intervention": True,
                "expected_reason": "timeout"
            },
            {
                "status": ConsensusStatus.REACHED,
                "expected_intervention": False,
                "expected_reason": ""
            },
            {
                "status": ConsensusStatus.PENDING,
                "expected_intervention": False,
                "expected_reason": ""
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            consensus = engine.create_consensus_process(
                conversation_id=f"conv_detection_test_{i}",
                decision_topic=f"Test decision {i}",
                threshold=0.7
            )
            
            consensus.status = test_case["status"]
            
            requires_intervention, reason = engine.check_consensus_requires_intervention(consensus)
            
            self.assertEqual(
                requires_intervention, 
                test_case["expected_intervention"],
                f"Case {i}: Expected intervention={test_case['expected_intervention']}, got {requires_intervention}"
            )
            self.assertEqual(
                reason, 
                test_case["expected_reason"],
                f"Case {i}: Expected reason='{test_case['expected_reason']}', got '{reason}'"
            )
        
        print("✓ Intervention automatic detection test passed!")


if __name__ == "__main__":
    unittest.main()