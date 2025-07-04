import json
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.storyteller.config import Config, LLMConfig, RepositoryConfig, StorageConfig
from src.storyteller.consensus_engine import ConsensusEngine
from src.storyteller.database import DatabaseManager
from src.storyteller.llm_handler import LLMResponse
from src.storyteller.models import (
    ConsensusStatus,
    RoleVote,
    StoryStatus,
    UserStory,
    VotingPosition,
)
from src.storyteller.role_analyzer import RoleAssignment, RoleAssignmentResult

# Adjust these imports based on your project structure
from src.storyteller.story_manager import StoryManager, StoryProcessor


# Minimal Config for Integration Testing
class IntegrationTestConfig(Config):
    def __init__(self, db_path="test_integration_storyteller.db"):
        super().__init__()  # Ensure parent class defaults are set if any
        self.database_url = db_path  # Used by DatabaseManager if not overridden
        self.repositories = {
            "test_backend": RepositoryConfig(
                name="org/backend", type="backend", description="Backend service"
            ),
            "test_frontend": RepositoryConfig(
                name="org/frontend", type="frontend", description="Frontend app"
            ),
        }
        self.default_repository = "test_backend"
        self.llm = LLMConfig(
            provider="mock", model="mock_model", api_key="test_key", temperature=0.1
        )
        self.storage = StorageConfig(primary="sqlite", params={"db_path": db_path})
        self.role_files_path = (
            "src/storyteller/.storyteller/roles"  # Path to actual roles
        )
        self.templates_path = (
            "src/storyteller/.storyteller/templates"  # Path to actual templates
        )
        self.auto_consensus_threshold = 70
        self.auto_consensus_max_iterations = 3
        # Add any other config values your system might need during this flow


class TestRoleBasedRequirementsWorkflow(unittest.IsolatedAsyncioTestCase):
    DB_PATH = "test_integration_storyteller_workflow.db"

    @classmethod
    def setUpClass(cls):
        # Ensure template files exist for roles we'll use
        # This assumes the test is run from the repository root
        roles_template_dir = Path("src/storyteller/.storyteller/templates/roles")
        if not roles_template_dir.exists():
            roles_template_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy templates if they don't exist (or ensure they do)
        # These should match the ones created in the plan
        cls.ensure_template_exists(
            roles_template_dir / "product-owner_requirements.md",
            "PO Template: {{ story_title }}",
        )
        cls.ensure_template_exists(
            roles_template_dir / "qa-engineer_requirements.md",
            "QA Template: {{ story_title }}",
        )
        cls.ensure_template_exists(
            roles_template_dir / "lead-developer_requirements.md",
            "Dev Template: {{ story_title }}",
        )

    @classmethod
    def ensure_template_exists(cls, path: Path, content: str):
        if not path.exists():
            with open(path, "w") as f:
                f.write(content)

    def setUp(self):
        if os.path.exists(self.DB_PATH):
            os.remove(self.DB_PATH)

        self.config = IntegrationTestConfig(db_path=self.DB_PATH)
        self.db_manager = DatabaseManager(
            db_path=self.DB_PATH
        )  # StoryProcessor will make its own

        # We will let StoryProcessor initialize its own components based on config,
        # but we'll need to mock LLMHandler responses.
        # The RoleAssignmentEngine will use actual role files if path is correct.

        # StoryManager uses StoryProcessor, so testing via StoryManager might be good.
        # For this test, let's instantiate StoryProcessor directly to focus the test.
        self.story_processor = StoryProcessor(config=self.config)
        # self.story_processor.database is already initialized by its __init__

        self.consensus_engine = ConsensusEngine(
            config=self.config
        )  # For consensus part

        # Mock LLM Handler at the class level used by StoryProcessor
        self.mock_llm_handler_patch = patch(
            "src.storyteller.story_manager.LLMHandler", autospec=True
        )
        self.MockLLMHandlerClass = self.mock_llm_handler_patch.start()
        self.mock_llm_instance = self.MockLLMHandlerClass.return_value
        self.story_processor.llm_handler = (
            self.mock_llm_instance
        )  # Ensure processor uses this mock

        # Mock RoleAssignmentEngine if needed to control roles, or let it run
        # For integration, let's try to let it run if it's not too heavy
        # self.mock_role_analyzer_patch = patch('src.storyteller.story_manager.RoleAssignmentEngine', autospec=True)
        # self.MockRoleAnalyzerClass = self.mock_role_analyzer_patch.start()
        # self.mock_role_analyzer_instance = self.MockRoleAnalyzerClass.return_value
        # self.story_processor.role_assignment_engine = self.mock_role_analyzer_instance

    def tearDown(self):
        self.mock_llm_handler_patch.stop()
        # if hasattr(self, 'mock_role_analyzer_patch'):
        #     self.mock_role_analyzer_patch.stop()
        if os.path.exists(self.DB_PATH):
            os.remove(self.DB_PATH)

    async def test_full_requirement_gathering_and_consensus_flow(self):
        # 1. Create a story (directly in DB for this test, or use StoryManager)
        story_id = "integ_story_001"
        story_title = "Full Workflow Test Story"
        story_description = (
            "As a user, I want a feature, so I can benefit. Involves UI and API."
        )

        test_story = UserStory(
            id=story_id,
            title=story_title,
            description=story_description,
            status=StoryStatus.DRAFT,
            epic_id="integ_epic_001",
            target_repositories=[
                "test_backend",
                "test_frontend",
            ],  # For RoleAnalyzer context
        )
        self.story_processor.database.save_story(test_story)

        # --- Configure Mocks ---
        # Mock RoleAssignmentEngine to return specific roles for predictability
        # Or, ensure your actual RoleAnalyzer identifies PO, QA, Dev based on story_description
        # For this test, let's mock it to ensure these roles are picked.
        mock_role_analyzer = MagicMock()  # Replacing the instance on story_processor
        role_po = RoleAssignment(
            role_name="product-owner",
            confidence_score=0.9,
            assignment_reason="integ_test",
        )
        role_qa = RoleAssignment(
            role_name="qa-engineer",
            confidence_score=0.9,
            assignment_reason="integ_test",
        )
        role_dev = RoleAssignment(
            role_name="lead-developer",
            confidence_score=0.9,
            assignment_reason="integ_test",
        )
        mock_role_analyzer.assign_roles.return_value = RoleAssignmentResult(
            story_id=story_id,
            primary_roles=[role_po, role_qa, role_dev],
            secondary_roles=[],
            suggested_roles=[],
        )
        self.story_processor.role_assignment_engine = mock_role_analyzer

        # Mock LLM responses for requirement gathering
        # Order: PO, QA, Dev (based on primary_roles order above)
        po_ac_response = "AC from PO: Final system must do X. User can achieve Y."
        qa_test_req_response = (
            "Testing Req from QA: Test X thoroughly. Test Y under load."
        )
        dev_effort_response = (
            "Effort: 8 points. Confidence: Medium. Notes: API changes needed."
        )

        self.mock_llm_instance.generate_response = AsyncMock(
            side_effect=[
                LLMResponse(
                    content=po_ac_response, model="mock", provider="mock", usage={}
                ),
                LLMResponse(
                    content=qa_test_req_response,
                    model="mock",
                    provider="mock",
                    usage={},
                ),
                LLMResponse(
                    content=dev_effort_response, model="mock", provider="mock", usage={}
                ),
            ]
        )

        # --- 2. Call gather_role_based_requirements ---
        updated_story = await self.story_processor.gather_role_based_requirements(
            story_id
        )
        self.assertIsNotNone(updated_story)

        # --- 3. Verify contributions and synthesis ---
        self.assertIn(
            "Final system must do X", updated_story.acceptance_criteria
        )  # Check synthesized AC
        self.assertIn("User can achieve Y", updated_story.acceptance_criteria)

        self.assertEqual(len(updated_story.acceptance_criteria_contributions), 1)
        self.assertEqual(
            updated_story.acceptance_criteria_contributions[0]["role_name"],
            "product-owner",
        )
        self.assertEqual(
            updated_story.acceptance_criteria_contributions[0]["contribution_text"],
            po_ac_response,
        )

        self.assertEqual(len(updated_story.testing_requirements_contributions), 1)
        self.assertEqual(
            updated_story.testing_requirements_contributions[0]["role_name"],
            "qa-engineer",
        )
        # Basic parsing in gather_role_based_requirements currently stores whole response
        self.assertEqual(
            updated_story.testing_requirements_contributions[0]["requirement_text"],
            qa_test_req_response,
        )

        self.assertEqual(len(updated_story.effort_estimates_contributions), 1)
        self.assertEqual(
            updated_story.effort_estimates_contributions[0]["role_name"],
            "lead-developer",
        )
        # Basic parsing stores whole response in notes, placeholder for value/unit
        self.assertEqual(
            updated_story.effort_estimates_contributions[0]["notes"],
            dev_effort_response,
        )
        self.assertEqual(
            updated_story.effort_estimates_contributions[0]["estimate_value"], 5
        )  # Current placeholder

        # --- 4. Initiate Consensus Process ---
        requirements_context_for_consensus = {
            "story_title": updated_story.title,
            "story_description": updated_story.description,
            "acceptance_criteria": updated_story.acceptance_criteria,  # The synthesized list
            "testing_requirements_contributions": updated_story.testing_requirements_contributions,
            "effort_estimates_contributions": updated_story.effort_estimates_contributions,
        }

        consensus_process = self.consensus_engine.create_consensus_process(
            conversation_id=f"conv_{story_id}",
            decision_topic=f"Consensus on requirements for story {story_id}",
            required_roles=["product-owner", "qa-engineer", "lead-developer"],
            requirements_context=requirements_context_for_consensus,
        )
        self.assertIsNotNone(consensus_process)
        self.assertEqual(
            consensus_process.requirements_context, requirements_context_for_consensus
        )

        # --- 5. Simulate Votes ---
        # Mock LLM responses for voting (simplified: assume roles agree for this test)
        # In a real scenario, the LLM would be prompted with the requirements_context

        vote_po = self.consensus_engine.add_role_vote(
            consensus_process,
            "product-owner",
            "po_participant",
            VotingPosition.AGREE,
            confidence=0.9,
            rationale="ACs look good.",
        )
        vote_qa = self.consensus_engine.add_role_vote(
            consensus_process,
            "qa-engineer",
            "qa_participant",
            VotingPosition.AGREE,
            confidence=0.8,
            rationale="Testing reqs cover main areas.",
        )
        vote_dev = self.consensus_engine.add_role_vote(
            consensus_process,
            "lead-developer",
            "dev_participant",
            VotingPosition.AGREE,
            confidence=0.85,
            rationale="Effort estimate seems reasonable.",
        )

        # --- 6. Check Consensus Status ---
        status = self.consensus_engine.check_consensus_status(consensus_process)
        self.assertEqual(
            status, ConsensusStatus.REACHED
        )  # Assuming threshold is met by 3 agreements

        report = self.consensus_engine.generate_consensus_report(consensus_process)
        self.assertTrue(report["metrics"]["consensus_reached"])
        self.assertEqual(
            report["requirements_context_summary"]["num_ac_contributions"], 0
        )  # This is from requirements_context, not direct ACs
        # The summary in consensus engine counts items in the *passed* context
        self.assertEqual(
            len(report["requirements_context_summary"]), 4
        )  # has_context, num_ac, num_test, num_effort
        self.assertTrue(report["requirements_context_summary"]["has_context"])
        # The summary in consensus engine counts items in the *passed* context's lists
        # The passed context has "acceptance_criteria" as a flat list, not "acceptance_criteria_contributions"
        # Let's adjust what we pass or what we assert.
        # For this test, it's easier to adjust the assertion to match the structure.
        # The `requirements_context_summary` looks for specific keys:
        # `acceptance_criteria_contributions`, `testing_requirements_contributions`, `effort_estimates_contributions`
        # My `requirements_context_for_consensus` has these keys, but `acceptance_criteria` is a flat list.
        # This means num_ac_contributions should be 0 if that specific key is not a list of contributions.

        # Let's refine the requirements_context_for_consensus to match what the report expects for counts
        refined_req_context = {
            "story_title": updated_story.title,
            "story_description": updated_story.description,
            "direct_acceptance_criteria": updated_story.acceptance_criteria,  # For LLM prompt to roles
            "acceptance_criteria_contributions": updated_story.acceptance_criteria_contributions,  # For report count
            "testing_requirements_contributions": updated_story.testing_requirements_contributions,  # For report count
            "effort_estimates_contributions": updated_story.effort_estimates_contributions,  # For report count
        }
        consensus_process_refined = self.consensus_engine.create_consensus_process(
            conversation_id=f"conv_{story_id}_refined",
            decision_topic=f"Consensus on requirements for story {story_id} (refined context)",
            required_roles=["product-owner", "qa-engineer", "lead-developer"],
            requirements_context=refined_req_context,
        )
        report_refined = self.consensus_engine.generate_consensus_report(
            consensus_process_refined
        )
        self.assertEqual(
            report_refined["requirements_context_summary"]["num_ac_contributions"], 1
        )
        self.assertEqual(
            report_refined["requirements_context_summary"]["num_testing_requirements"],
            1,
        )
        self.assertEqual(
            report_refined["requirements_context_summary"]["num_effort_estimates"], 1
        )


if __name__ == "__main__":
    unittest.main()
