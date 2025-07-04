import json
import unittest
from datetime import datetime, timezone

from src.storyteller.models import UserStory  # For testing BaseStory inheritance
from src.storyteller.models import (
    AcceptanceCriterionContribution,
    BaseStory,
    ConsensusResult,
    ConsensusStatus,
    EffortEstimate,
    TestingRequirement,
)


class TestNewModels(unittest.TestCase):

    def test_acceptance_criterion_contribution(self):
        now = datetime.now(timezone.utc)
        ac_contrib = AcceptanceCriterionContribution(
            story_id="story123",
            role_name="product-owner",
            contribution_text="User should be able to log in.",
            rationale="Core functionality.",
            created_at=now,
            metadata={"source": "llm"},
        )
        self.assertEqual(ac_contrib.story_id, "story123")
        self.assertEqual(ac_contrib.role_name, "product-owner")

        ac_dict = ac_contrib.to_dict()
        self.assertEqual(ac_dict["story_id"], "story123")
        self.assertEqual(ac_dict["role_name"], "product-owner")
        self.assertEqual(ac_dict["contribution_text"], "User should be able to log in.")
        self.assertEqual(ac_dict["rationale"], "Core functionality.")
        self.assertEqual(datetime.fromisoformat(ac_dict["created_at"]), now)
        self.assertEqual(json.loads(ac_dict["metadata"]), {"source": "llm"})

    def test_testing_requirement(self):
        now = datetime.now(timezone.utc)
        test_req = TestingRequirement(
            story_id="story123",
            role_name="qa-engineer",
            requirement_text="Test login with 100 concurrent users.",
            priority=1,
            created_at=now,
            metadata={"test_type": "performance"},
        )
        self.assertEqual(test_req.priority, 1)

        tr_dict = test_req.to_dict()
        self.assertEqual(tr_dict["story_id"], "story123")
        self.assertEqual(tr_dict["role_name"], "qa-engineer")
        self.assertEqual(
            tr_dict["requirement_text"], "Test login with 100 concurrent users."
        )
        self.assertEqual(tr_dict["priority"], 1)
        self.assertEqual(datetime.fromisoformat(tr_dict["created_at"]), now)
        self.assertEqual(json.loads(tr_dict["metadata"]), {"test_type": "performance"})

    def test_effort_estimate(self):
        now = datetime.now(timezone.utc)
        effort_est = EffortEstimate(
            story_id="story123",
            role_name="lead-developer",
            estimate_value=5.0,
            estimate_unit="points",
            confidence=0.8,
            notes="Medium complexity, involves DB changes.",
            created_at=now,
            metadata={"tool": "planning_poker_app"},
        )
        self.assertEqual(effort_est.estimate_unit, "points")

        ee_dict = effort_est.to_dict()
        self.assertEqual(ee_dict["story_id"], "story123")
        self.assertEqual(ee_dict["role_name"], "lead-developer")
        self.assertEqual(ee_dict["estimate_value"], 5.0)
        self.assertEqual(ee_dict["estimate_unit"], "points")
        self.assertEqual(ee_dict["confidence"], 0.8)
        self.assertEqual(ee_dict["notes"], "Medium complexity, involves DB changes.")
        self.assertEqual(datetime.fromisoformat(ee_dict["created_at"]), now)
        self.assertEqual(
            json.loads(ee_dict["metadata"]), {"tool": "planning_poker_app"}
        )

    def test_base_story_with_contributions(self):
        story = UserStory(
            title="Test Story with Contributions"
        )  # Using UserStory to test BaseStory fields

        ac_contrib_data = {"role_name": "PO", "contribution_text": "AC1"}
        test_req_data = {"role_name": "QA", "requirement_text": "TR1"}
        effort_est_data = {"role_name": "Dev", "estimate_value": 3.0}

        story.acceptance_criteria_contributions.append(ac_contrib_data)
        story.testing_requirements_contributions.append(test_req_data)
        story.effort_estimates_contributions.append(effort_est_data)

        story_dict = story.to_dict()

        self.assertEqual(
            json.loads(story_dict["acceptance_criteria_contributions"]),
            [ac_contrib_data],
        )
        self.assertEqual(
            json.loads(story_dict["testing_requirements_contributions"]),
            [test_req_data],
        )
        self.assertEqual(
            json.loads(story_dict["effort_estimates_contributions"]), [effort_est_data]
        )

        # Test default empty lists
        empty_story = UserStory(title="Empty Contributions")
        empty_story_dict = empty_story.to_dict()
        self.assertEqual(
            json.loads(empty_story_dict["acceptance_criteria_contributions"]), []
        )
        self.assertEqual(
            json.loads(empty_story_dict["testing_requirements_contributions"]), []
        )
        self.assertEqual(
            json.loads(empty_story_dict["effort_estimates_contributions"]), []
        )

    def test_consensus_result_with_requirements_context(self):
        req_context = {
            "acceptance_criteria_contributions": [{"text": "AC1"}],
            "testing_requirements_contributions": [{"text": "TR1"}],
        }
        consensus = ConsensusResult(
            conversation_id="conv1",
            decision="Consensus on requirements",
            requirements_context=req_context,
        )
        self.assertEqual(consensus.requirements_context, req_context)

        cr_dict = consensus.to_dict()
        self.assertEqual(json.loads(cr_dict["requirements_context"]), req_context)

        # Test from_dict
        rehydrated_cr = ConsensusResult.from_dict(cr_dict)
        self.assertEqual(rehydrated_cr.requirements_context, req_context)

        # Test from_dict with None requirements_context
        cr_dict_no_req = consensus.to_dict()
        cr_dict_no_req["requirements_context"] = None
        rehydrated_cr_no_req = ConsensusResult.from_dict(cr_dict_no_req)
        self.assertIsNone(rehydrated_cr_no_req.requirements_context)

        # Test from_dict with missing requirements_context key
        cr_dict_missing_key = consensus.to_dict()
        del cr_dict_missing_key["requirements_context"]  # Simulate it not being in DB
        rehydrated_cr_missing_key = ConsensusResult.from_dict(cr_dict_missing_key)
        self.assertIsNone(rehydrated_cr_missing_key.requirements_context)


if __name__ == "__main__":
    unittest.main()
