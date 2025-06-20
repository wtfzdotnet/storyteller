"""Tests for manual intervention system."""

import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storyteller.consensus_engine import ConsensusEngine
from src.storyteller.conversation_manager import ConversationManager
from src.storyteller.database import DatabaseManager
from src.storyteller.models import ConsensusResult, ConsensusStatus, ManualIntervention


class TestManualIntervention(unittest.TestCase):
    """Test manual intervention functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.mktemp(suffix=".db")
        self.db = DatabaseManager(self.temp_db)
        self.db.init_database()

    def tearDown(self):
        """Clean up test fixtures."""
        if Path(self.temp_db).exists():
            Path(self.temp_db).unlink()

    def test_manual_intervention_model_creation(self):
        """Test ManualIntervention model creation and serialization."""
        intervention = ManualIntervention(
            conversation_id="conv_123",
            consensus_id="consensus_456",
            trigger_reason="failed_consensus",
            intervention_type="decision",
            original_decision="Implement feature X",
            human_decision="",
            human_rationale="",
            intervener_id="",
            intervener_role="",
            status="pending",
            affected_roles=["frontend-developer", "backend-developer"],
            metadata={"priority": "high"},
        )

        self.assertIsNotNone(intervention.id)
        self.assertTrue(intervention.id.startswith("intervention_"))
        self.assertEqual(intervention.conversation_id, "conv_123")
        self.assertEqual(intervention.consensus_id, "consensus_456")
        self.assertEqual(intervention.trigger_reason, "failed_consensus")
        self.assertEqual(intervention.status, "pending")
        self.assertEqual(len(intervention.affected_roles), 2)

    def test_manual_intervention_audit_trail(self):
        """Test audit trail functionality."""
        intervention = ManualIntervention(
            conversation_id="conv_123",
            consensus_id="consensus_456",
            trigger_reason="timeout",
            original_decision="Test decision",
        )

        # Test adding audit entries
        intervention.add_audit_entry(
            action="intervention_triggered",
            details="Triggered due to timeout",
            actor="system",
        )

        intervention.add_audit_entry(
            action="human_review",
            details="Under review by project manager",
            actor="project-manager:john_doe",
        )

        self.assertEqual(len(intervention.audit_trail), 2)
        self.assertEqual(
            intervention.audit_trail[0]["action"], "intervention_triggered"
        )
        self.assertEqual(
            intervention.audit_trail[1]["actor"], "project-manager:john_doe"
        )

    def test_manual_intervention_serialization(self):
        """Test ManualIntervention to_dict and from_dict."""
        original = ManualIntervention(
            conversation_id="conv_123",
            consensus_id="consensus_456",
            trigger_reason="manual_request",
            original_decision="Test decision",
            affected_roles=["qa-engineer"],
            metadata={"urgency": "medium"},
        )

        # Test serialization
        data = original.to_dict()
        self.assertIn("id", data)
        self.assertIn("conversation_id", data)
        self.assertIn("consensus_id", data)

        # Test deserialization
        restored = ManualIntervention.from_dict(data)
        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.conversation_id, original.conversation_id)
        self.assertEqual(restored.consensus_id, original.consensus_id)
        self.assertEqual(restored.trigger_reason, original.trigger_reason)
        self.assertEqual(restored.affected_roles, original.affected_roles)
        self.assertEqual(restored.metadata, original.metadata)

    def test_database_store_and_retrieve_intervention(self):
        """Test storing and retrieving manual interventions."""
        intervention = ManualIntervention(
            conversation_id="conv_123",
            consensus_id="consensus_456",
            trigger_reason="failed_consensus",
            original_decision="Implement new API",
        )

        # Test storing
        success = self.db.store_manual_intervention(intervention)
        self.assertTrue(success)

        # Test retrieving by ID
        retrieved = self.db.get_manual_intervention(intervention.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, intervention.id)
        self.assertEqual(retrieved.conversation_id, intervention.conversation_id)

        # Test retrieving non-existent intervention
        non_existent = self.db.get_manual_intervention("non_existent_id")
        self.assertIsNone(non_existent)

    def test_database_get_interventions_by_conversation(self):
        """Test retrieving interventions by conversation."""
        # Create multiple interventions
        intervention1 = ManualIntervention(
            conversation_id="conv_123",
            consensus_id="consensus_456",
            trigger_reason="failed_consensus",
            original_decision="Decision 1",
            status="pending",
        )

        intervention2 = ManualIntervention(
            conversation_id="conv_123",
            consensus_id="consensus_789",
            trigger_reason="timeout",
            original_decision="Decision 2",
            status="resolved",
        )

        intervention3 = ManualIntervention(
            conversation_id="conv_456",
            consensus_id="consensus_999",
            trigger_reason="manual_request",
            original_decision="Decision 3",
            status="pending",
        )

        # Store all interventions
        self.db.store_manual_intervention(intervention1)
        self.db.store_manual_intervention(intervention2)
        self.db.store_manual_intervention(intervention3)

        # Test retrieving all interventions for conversation
        conv_123_interventions = self.db.get_interventions_by_conversation("conv_123")
        self.assertEqual(len(conv_123_interventions), 2)

        # Test retrieving with status filter
        pending_interventions = self.db.get_interventions_by_conversation(
            "conv_123", status="pending"
        )
        self.assertEqual(len(pending_interventions), 1)
        self.assertEqual(pending_interventions[0].status, "pending")

    def test_database_get_pending_interventions(self):
        """Test retrieving pending interventions."""
        # Create interventions with different statuses
        pending1 = ManualIntervention(
            conversation_id="conv_123",
            consensus_id="consensus_456",
            trigger_reason="failed_consensus",
            status="pending",
            original_decision="Decision 1",
        )

        pending2 = ManualIntervention(
            conversation_id="conv_456",
            consensus_id="consensus_789",
            trigger_reason="timeout",
            status="pending",
            original_decision="Decision 2",
        )

        resolved = ManualIntervention(
            conversation_id="conv_789",
            consensus_id="consensus_999",
            trigger_reason="manual_request",
            status="resolved",
            original_decision="Decision 3",
        )

        # Store all interventions
        self.db.store_manual_intervention(pending1)
        self.db.store_manual_intervention(pending2)
        self.db.store_manual_intervention(resolved)

        # Test retrieving pending interventions
        pending_interventions = self.db.get_pending_interventions()
        self.assertEqual(len(pending_interventions), 2)
        for intervention in pending_interventions:
            self.assertEqual(intervention.status, "pending")

    def test_consensus_engine_check_requires_intervention(self):
        """Test consensus engine intervention detection."""
        from src.storyteller.config import Config

        # Create mock config to avoid environment variable requirements
        mock_config = Config(
            github_token="test",
            auto_consensus_threshold=70,
            auto_consensus_max_iterations=5,
        )

        engine = ConsensusEngine(mock_config)

        # Test failed consensus
        consensus = engine.create_consensus_process(
            conversation_id="conv_123", decision_topic="Test decision"
        )
        consensus.status = ConsensusStatus.FAILED

        requires_intervention, reason = engine.check_consensus_requires_intervention(
            consensus
        )
        self.assertTrue(requires_intervention)
        self.assertEqual(reason, "failed_consensus")

        # Test timeout
        consensus.status = ConsensusStatus.TIMEOUT
        requires_intervention, reason = engine.check_consensus_requires_intervention(
            consensus
        )
        self.assertTrue(requires_intervention)
        self.assertEqual(reason, "timeout")

        # Test reached consensus (should not require intervention)
        consensus.status = ConsensusStatus.REACHED
        requires_intervention, reason = engine.check_consensus_requires_intervention(
            consensus
        )
        self.assertFalse(requires_intervention)
        self.assertEqual(reason, "")


class TestConversationManagerIntervention(unittest.TestCase):
    """Test conversation manager manual intervention methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.mktemp(suffix=".db")

    def tearDown(self):
        """Clean up test fixtures."""
        if Path(self.temp_db).exists():
            Path(self.temp_db).unlink()

    async def test_conversation_manager_intervention_workflow(self):
        """Test full intervention workflow through conversation manager."""
        # This test requires environment variables, so we'll mock them
        import os

        os.environ["GITHUB_TOKEN"] = "test_token"
        os.environ["DEFAULT_LLM_PROVIDER"] = "github"

        try:
            from src.storyteller.conversation_manager import ConversationManager
            from src.storyteller.models import Conversation, ConversationParticipant

            manager = ConversationManager()

            # Create a conversation
            conversation = await manager.create_conversation(
                title="Test Consensus Conversation",
                description="Testing manual intervention workflow",
                repositories=["test-repo"],
                initial_participants=[{"name": "System", "role": "system"}],
            )

            # Test triggering intervention
            intervention_id = await manager.trigger_manual_intervention(
                conversation_id=conversation.id,
                consensus_id="test_consensus_123",
                trigger_reason="manual_request",
                intervention_type="decision",
            )

            self.assertIsNotNone(intervention_id)
            self.assertTrue(intervention_id.startswith("intervention_"))

            # Test getting intervention status
            status = manager.get_intervention_status(intervention_id)
            self.assertIsNotNone(status)
            self.assertEqual(status["status"], "pending")
            self.assertEqual(status["trigger_reason"], "manual_request")

            # Test resolving intervention
            success = await manager.resolve_manual_intervention(
                intervention_id=intervention_id,
                human_decision="Approved with conditions",
                human_rationale="Approved but requires additional testing",
                intervener_id="pm_001",
                intervener_role="project-manager",
            )

            self.assertTrue(success)

            # Check intervention is now resolved
            updated_status = manager.get_intervention_status(intervention_id)
            self.assertEqual(updated_status["status"], "resolved")
            self.assertEqual(
                updated_status["human_decision"], "Approved with conditions"
            )
            self.assertEqual(updated_status["intervener_id"], "pm_001")

        finally:
            # Clean up environment variables
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("DEFAULT_LLM_PROVIDER", None)

    def test_conversation_manager_intervention_workflow_sync(self):
        """Test conversation manager intervention workflow (synchronous parts)."""
        # Test the synchronous parts that don't require full setup
        import os
        import tempfile
        from pathlib import Path

        os.environ["GITHUB_TOKEN"] = "test_token"
        os.environ["DEFAULT_LLM_PROVIDER"] = "github"

        # Use a temporary database for this test
        temp_db = tempfile.mktemp(suffix=".db")
        try:
            from unittest.mock import patch

            from src.storyteller.conversation_manager import ConversationManager

            # Mock the database to use our temporary database
            with patch(
                "src.storyteller.conversation_manager.DatabaseManager"
            ) as mock_db_class:
                from src.storyteller.database import DatabaseManager

                test_db = DatabaseManager(temp_db)
                test_db.init_database()
                mock_db_class.return_value = test_db

                manager = ConversationManager()

                # Test getting pending interventions (should be empty initially)
                pending = manager.get_pending_interventions()
                self.assertEqual(len(pending), 0)

                # Test getting non-existent intervention status
                status = manager.get_intervention_status("non_existent_id")
                self.assertIsNone(status)

        finally:
            # Clean up environment variables and temp db
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("DEFAULT_LLM_PROVIDER", None)
            if Path(temp_db).exists():
                Path(temp_db).unlink()


def run_async_test(test_func):
    """Helper to run async test functions."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(test_func())
    finally:
        loop.close()


if __name__ == "__main__":
    unittest.main()
