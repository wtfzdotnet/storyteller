import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.storyteller.config import Config, RepositoryConfig
from src.storyteller.llm_handler import LLMResponse
from src.storyteller.models import (
    AcceptanceCriterionContribution,
    EffortEstimate,
    StoryStatus,
    TestingRequirement,
    UserStory,
)
from src.storyteller.role_analyzer import RoleAssignment, RoleAssignmentResult

# Adjust imports based on your project structure
from src.storyteller.story_manager import StoryProcessor


# A minimal config for testing
class MinimalTestConfig(Config):
    def __init__(self):
        super().__init__()  # Call parent __init__ if it sets up defaults
        self.repositories = {
            "test_repo": RepositoryConfig(
                name="test_owner/test_repo", type="backend", description="Test repo"
            )
        }
        self.default_repository = "test_repo"
        self.llm_provider = "mock"  # Ensure LLM handler doesn't try to make real calls
        # Add other minimal required config fields if StoryProcessor depends on them


class TestStoryProcessorRoleGathering(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.test_config = MinimalTestConfig()
        # Patch get_config if StoryProcessor calls it globally
        # For now, assume config is passed to constructor

        self.mock_db_manager = MagicMock()
        self.mock_llm_handler = MagicMock()
        self.mock_role_analyzer = MagicMock()
        self.mock_context_reader = MagicMock()
        self.mock_template_manager = MagicMock()  # If used, else mock file reads

        self.story_processor = StoryProcessor(config=self.test_config)
        self.story_processor.database = self.mock_db_manager
        self.story_processor.llm_handler = self.mock_llm_handler
        self.story_processor.role_assignment_engine = self.mock_role_analyzer
        self.story_processor.context_reader = self.mock_context_reader
        self.story_processor.template_manager = self.mock_template_manager

    async def test_gather_role_based_requirements_happy_path(self):
        story_id = "story_gather_001"
        story_title = "Test Story for Gathering"
        story_content = "This is the story description."

        mock_story = UserStory(
            id=story_id,
            title=story_title,
            description=story_content,
            status=StoryStatus.DRAFT,
        )
        self.mock_db_manager.get_story.return_value = mock_story

        # Mock RoleAssignmentEngine
        role_po = RoleAssignment(
            role_name="product-owner", confidence_score=0.9, assignment_reason="test"
        )
        role_qa = RoleAssignment(
            role_name="qa-engineer", confidence_score=0.9, assignment_reason="test"
        )
        self.mock_role_analyzer.assign_roles.return_value = RoleAssignmentResult(
            story_id=story_id,
            primary_roles=[role_po],
            secondary_roles=[role_qa],
            suggested_roles=[],
        )

        # Mock LLMHandler responses for each role
        # Product Owner LLM Response (e.g. contributing ACs)
        po_response_content = "AC from PO: User can see dashboard."
        # QA Engineer LLM Response (e.g. contributing Test Reqs)
        qa_response_content = "Test Req from QA: Verify dashboard loads in <1s."

        # This needs to be an AsyncMock if generate_response is async
        self.mock_llm_handler.generate_response = AsyncMock()
        self.mock_llm_handler.generate_response.side_effect = [
            LLMResponse(
                content=po_response_content, model="mock", provider="mock", usage={}
            ),
            LLMResponse(
                content=qa_response_content, model="mock", provider="mock", usage={}
            ),
        ]

        # Mock template reading
        # This path needs to be correct relative to where the tests are run or use absolute paths/fixtures
        # For simplicity, mocking direct file read if template_manager isn't heavily used for this.
        # If TemplateManager is used, mock its methods instead.

        # Using patch for Path.exists and Path.read_text
        # This assumes templates are named like 'src/storyteller/.storyteller/templates/roles/product-owner_requirements.md'
        # Adjust the path structure if it's different in your actual implementation.
        # The key is that these paths match what `gather_role_based_requirements` tries to open.

        mock_po_template_content = "PO Template: {{ story_title }} {{ story_id }}"
        mock_qa_template_content = "QA Template: {{ story_title }} {{ story_id }}"

        def mock_path_exists(path_arg):
            path_str = str(path_arg)
            if "product-owner_requirements.md" in path_str:
                return True
            if "qa-engineer_requirements.md" in path_str:
                return True
            return False

        def mock_read_text(path_arg):
            path_str = str(path_arg)  # Convert Path object to string for comparison
            if "product-owner_requirements.md" in path_str:
                return mock_po_template_content
            if "qa-engineer_requirements.md" in path_str:
                return mock_qa_template_content
            raise FileNotFoundError(f"Mocked file not found: {path_str}")

        # We need to patch 'pathlib.Path' within the module where it's used.
        # If 'story_manager.py' does 'from pathlib import Path', then patch 'src.storyteller.story_manager.Path'
        with patch("src.storyteller.story_manager.Path") as MockPath:
            # Configure the behavior of the MockPath instance
            mock_path_instance = MockPath.return_value  # This is what Path(...) returns
            mock_path_instance.exists.side_effect = mock_path_exists
            # This is a bit tricky: Path(...).read_text()
            # We need the instance returned by Path(...) to have a read_text method

            # Create a new MagicMock for the instance that Path() returns
            path_instance_mock = MagicMock()
            path_instance_mock.exists.side_effect = mock_path_exists

            # path_instance_mock.read_text needs to be a regular method, not AsyncMock
            # if the actual read_text is synchronous.
            # We need to get the path string to decide which content to return.
            # The instance itself will be passed as `self` to read_text.
            # So, we need a callable that can access the path from the instance.

            # A simpler way if the path string is directly used in read_text:
            # If Path(some_path_str).read_text() is called.
            # The path_instance_mock here represents Path(some_path_str)

            # Let's make the mock return different content based on its own string representation
            # This is a common pattern for mocking file system interactions.
            def dynamic_read_text(*args, **kwargs):
                # 'self' here is the mock_path_instance
                # We need to know what path this instance represents
                # This can be tricky if the path isn't stored on the mock easily
                # A simpler approach is to have Path() return different mocks for different paths,
                # or have exists and read_text be more intelligent based on the path string.

                # Let's assume the path string is implicitly part of the mock_path_instance's identity
                # For this specific side_effect, we might not have it directly.
                # The side_effect on MockPath.return_value.read_text is better.

                # Let's try to make the instance itself behave like a Path object for the sake of the test
                if "product-owner_requirements.md" in str(
                    path_instance_mock
                ):  # This comparison is speculative
                    return mock_po_template_content
                elif "qa-engineer_requirements.md" in str(path_instance_mock):
                    return mock_qa_template_content
                raise FileNotFoundError("Unknown path for mock read_text")

            # path_instance_mock.read_text.side_effect = dynamic_read_text
            # This is still not quite right. We need `read_text` to be a method on the instance.

            # Let's refine the patch for read_text
            # We are patching Path class. When Path(filename) is called, it returns an object.
            # That object has an exists() method and a read_text() method.

            def get_mock_path_object(path_str_arg):
                instance = MagicMock(spec=os.PathLike)  # Make it behave like a path
                instance.__str__ = lambda: path_str_arg  # So str(instance) works
                instance.exists.return_value = mock_path_exists(path_str_arg)
                instance.read_text.return_value = mock_read_text(path_str_arg)
                return instance

            MockPath.side_effect = get_mock_path_object

            updated_story = await self.story_processor.gather_role_based_requirements(
                story_id
            )

        # Assertions
        self.mock_db_manager.get_story.assert_called_once_with(story_id)
        self.mock_role_analyzer.assign_roles.assert_called_once()

        # Check LLM calls (2 roles = 2 calls)
        self.assertEqual(self.mock_llm_handler.generate_response.call_count, 2)

        # Check prompt for PO (first call)
        po_prompt_args = self.mock_llm_handler.generate_response.call_args_list[0]
        self.assertIn(story_title, po_prompt_args.kwargs["prompt"])  # Basic check
        self.assertIn("product-owner", po_prompt_args.kwargs["system_prompt"])

        # Check prompt for QA (second call)
        qa_prompt_args = self.mock_llm_handler.generate_response.call_args_list[1]
        self.assertIn(story_title, qa_prompt_args.kwargs["prompt"])
        self.assertIn("qa-engineer", qa_prompt_args.kwargs["system_prompt"])

        # Check contributions stored on the story object (before db save mock)
        self.assertTrue(hasattr(updated_story, "acceptance_criteria_contributions"))
        self.assertTrue(hasattr(updated_story, "testing_requirements_contributions"))

        self.assertEqual(len(updated_story.acceptance_criteria_contributions), 1)
        self.assertEqual(
            updated_story.acceptance_criteria_contributions[0]["role_name"],
            "product-owner",
        )
        self.assertEqual(
            updated_story.acceptance_criteria_contributions[0]["contribution_text"],
            po_response_content,
        )

        self.assertEqual(len(updated_story.testing_requirements_contributions), 1)
        self.assertEqual(
            updated_story.testing_requirements_contributions[0]["role_name"],
            "qa-engineer",
        )
        self.assertEqual(
            updated_story.testing_requirements_contributions[0]["requirement_text"],
            qa_response_content,
        )

        # Check that save_story was called (twice: once after gathering, once after synthesis)
        self.assertEqual(self.mock_db_manager.save_story.call_count, 2)
        self.mock_db_manager.save_story.assert_called_with(
            mock_story
        )  # or updated_story

    def test_synthesize_acceptance_criteria(self):
        story = UserStory(id="syn001", title="Synth Test")
        story.acceptance_criteria = ["Existing AC1"]
        story.acceptance_criteria_contributions = [
            AcceptanceCriterionContribution(
                story_id="syn001", role_name="PO", contribution_text="New AC from PO"
            ).to_dict(),
            AcceptanceCriterionContribution(
                story_id="syn001", role_name="Dev", contribution_text="Technical AC"
            ).to_dict(),
            AcceptanceCriterionContribution(
                story_id="syn001", role_name="QA", contribution_text="Existing AC1"
            ).to_dict(),  # Duplicate
            AcceptanceCriterionContribution(
                story_id="syn001", role_name="User", contribution_text="new ac from po"
            ).to_dict(),  # Duplicate case-insensitive
        ]

        self.story_processor._synthesize_acceptance_criteria(story)

        self.assertIn("Existing AC1", story.acceptance_criteria)
        self.assertIn("New AC from PO", story.acceptance_criteria)
        self.assertIn("Technical AC", story.acceptance_criteria)
        self.assertEqual(
            len(story.acceptance_criteria), 3
        )  # "Existing AC1", "New AC from PO", "Technical AC"

    def test_get_testing_requirements_for_story(self):
        story_id = "get_tr_001"
        now_iso = datetime.now(timezone.utc).isoformat()
        tr_dict_data = [
            {
                "id": "tr1",
                "story_id": story_id,
                "role_name": "QA",
                "requirement_text": "Test X",
                "created_at": now_iso,
                "metadata": json.dumps({"type": "functional"}),
            },
            {
                "id": "tr2",
                "story_id": story_id,
                "role_name": "Dev",
                "requirement_text": "Test Y",
                "priority": 1,
                "created_at": now_iso,
            },
        ]
        mock_story = UserStory(id=story_id, title="Get TR Test")
        mock_story.testing_requirements_contributions = tr_dict_data
        self.mock_db_manager.get_story.return_value = mock_story

        results = self.story_processor.get_testing_requirements_for_story(story_id)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], TestingRequirement)
        self.assertEqual(results[0].requirement_text, "Test X")
        self.assertEqual(
            results[0].metadata, {"type": "functional"}
        )  # Assuming metadata is parsed
        self.assertEqual(results[1].priority, 1)

    def test_get_effort_estimates_for_story(self):
        story_id = "get_ee_001"
        now_iso = datetime.now(timezone.utc).isoformat()
        ee_dict_data = [
            {
                "id": "ee1",
                "story_id": story_id,
                "role_name": "Dev",
                "estimate_value": 5.0,
                "estimate_unit": "points",
                "created_at": now_iso,
            },
            {
                "id": "ee2",
                "story_id": story_id,
                "role_name": "Architect",
                "estimate_value": 8.0,
                "estimate_unit": "points",
                "confidence": 0.7,
                "created_at": now_iso,
            },
        ]
        mock_story = UserStory(id=story_id, title="Get EE Test")
        mock_story.effort_estimates_contributions = ee_dict_data
        self.mock_db_manager.get_story.return_value = mock_story

        results = self.story_processor.get_effort_estimates_for_story(story_id)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], EffortEstimate)
        self.assertEqual(results[0].estimate_value, 5.0)
        self.assertEqual(results[1].role_name, "Architect")
        self.assertEqual(results[1].confidence, 0.7)


if __name__ == "__main__":
    unittest.main()
