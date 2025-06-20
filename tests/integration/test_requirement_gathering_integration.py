"""Integration tests for role-based requirement gathering."""

import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from config import Config
from multi_repo_context import RepositoryContext
from requirement_gatherer import GatheredRequirements, RequirementSet
from story_manager import StoryProcessor, StoryRequest


class TestRequirementGatheringIntegration(unittest.TestCase):
    """Test integration of requirement gathering with story processing."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Config(
            github_token="test_token",
            github_repository="wtfzdotnet/storyteller",
            default_llm_provider="github",
        )

        # Mock all external dependencies
        with (
            patch("story_manager.LLMHandler") as mock_llm_class,
            patch("story_manager.GitHubHandler") as mock_github_class,
            patch("story_manager.DatabaseManager") as mock_db_class,
            patch("story_manager.load_role_files") as mock_load_roles,
            patch("story_manager.RoleAssignmentEngine") as mock_role_engine_class,
            patch(
                "story_manager.MultiRepositoryContextReader"
            ) as mock_context_reader_class,
        ):

            # Setup mock instances
            self.mock_llm_handler = Mock()
            mock_llm_class.return_value = self.mock_llm_handler

            self.mock_github_handler = Mock()
            mock_github_class.return_value = self.mock_github_handler

            self.mock_database = Mock()
            mock_db_class.return_value = self.mock_database

            mock_load_roles.return_value = {
                "qa-engineer": "QA Engineer role definition",
                "system-architect": "System Architect role definition",
                "lead-developer": "Lead Developer role definition",
            }

            self.mock_role_engine = Mock()
            mock_role_engine_class.return_value = self.mock_role_engine

            self.mock_context_reader = Mock()
            mock_context_reader_class.return_value = self.mock_context_reader

            # Create story processor
            self.story_processor = StoryProcessor(self.config)

    @pytest.mark.asyncio
    async def test_requirement_gathering_workflow_integration(self):
        """Test the complete requirement gathering workflow integration."""

        # Setup mock responses for role assignment
        from role_analyzer import RoleAssignment, RoleAssignmentResult

        mock_assignment_result = RoleAssignmentResult(
            story_id="test_story_123",
            primary_roles=[
                RoleAssignment("qa-engineer", 0.9, "Testing expertise"),
                RoleAssignment("system-architect", 0.8, "Architecture analysis"),
            ],
            secondary_roles=[
                RoleAssignment("lead-developer", 0.7, "Implementation guidance"),
            ],
            suggested_roles=[],
        )

        self.mock_role_engine.assign_roles.return_value = mock_assignment_result

        # Setup mock repository context
        mock_repo_context = RepositoryContext(
            repository="backend",
            repo_type="backend",
            description="Backend API services",
            languages={"python": 0.8, "javascript": 0.2},
            key_files=[],
        )

        self.mock_context_reader.get_repository_context = AsyncMock(
            return_value=mock_repo_context
        )

        # Setup mock LLM responses for requirement gathering
        def mock_generate_response(prompt, **kwargs):
            response = Mock()
            if "acceptance criteria" in prompt.lower():
                response.content = """
                - The system shall validate recipe rating inputs (1-5 stars)
                - The user can submit only one rating per recipe
                - The system shall display average rating on recipe pages
                """
            elif "testing requirements" in prompt.lower():
                response.content = """
                - Unit tests for rating validation logic
                - Integration tests for rating API endpoints
                - End-to-end tests for rating display functionality
                """
            elif "effort estimation" in prompt.lower():
                response.content = """
                {
                    "story_points": 5,
                    "complexity": 3,
                    "time_estimate_hours": 20,
                    "risk_factors": ["Database schema changes", "API versioning"],
                    "confidence": "medium",
                    "reasoning": "Moderate complexity due to new database table"
                }
                """
            elif "synthesize" in prompt.lower() or "synthesis" in prompt.lower():
                response.content = """
                {
                    "acceptance_criteria": [
                        "The system shall validate recipe rating inputs (1-5 stars)",
                        "Users can submit only one rating per recipe",
                        "The system shall display average rating on recipe pages",
                        "The system shall store rating timestamps for audit purposes"
                    ],
                    "testing_requirements": [
                        "Unit tests for rating validation and business logic",
                        "Integration tests for rating API endpoints with database",
                        "End-to-end tests for complete rating workflow",
                        "Performance tests for rating aggregation queries"
                    ]
                }
                """
            else:
                response.content = "Default response"

            return response

        self.mock_llm_handler.generate_response = AsyncMock(
            side_effect=mock_generate_response
        )

        # Test the requirement gathering workflow
        story_content = "As a user, I want to rate recipes so that I can share my opinion with other users"

        gathered_requirements = await self.story_processor.gather_requirements(
            story_content=story_content,
            target_repositories=["backend"],
        )

        # Verify the results
        self.assertIsInstance(gathered_requirements, GatheredRequirements)
        self.assertEqual(gathered_requirements.story_content, story_content)

        # Check that requirements were gathered from all roles
        self.assertEqual(
            len(gathered_requirements.role_requirements), 3
        )  # qa-engineer, system-architect, lead-developer

        role_names = [req.role_name for req in gathered_requirements.role_requirements]
        self.assertIn("qa-engineer", role_names)
        self.assertIn("system-architect", role_names)
        self.assertIn("lead-developer", role_names)

        # Check synthesized acceptance criteria
        self.assertGreater(
            len(gathered_requirements.synthesized_acceptance_criteria), 0
        )
        self.assertIn(
            "validate recipe rating inputs",
            gathered_requirements.synthesized_acceptance_criteria[0],
        )

        # Check synthesized testing requirements
        self.assertGreater(
            len(gathered_requirements.synthesized_testing_requirements), 0
        )
        self.assertIn(
            "Unit tests", gathered_requirements.synthesized_testing_requirements[0]
        )

        # Check story points estimation
        self.assertIsNotNone(gathered_requirements.estimated_story_points)
        self.assertGreater(gathered_requirements.estimated_story_points, 0)

        # Check confidence score
        self.assertGreater(gathered_requirements.confidence_score, 0)
        self.assertLessEqual(gathered_requirements.confidence_score, 1.0)

    @pytest.mark.asyncio
    async def test_analyze_story_workflow_with_requirements(self):
        """Test the enhanced story analysis workflow that includes requirement gathering."""

        # Setup mocks for story processing
        self.mock_llm_handler.analyze_story_with_role = AsyncMock()
        self.mock_llm_handler.synthesize_expert_analyses = AsyncMock()

        # Mock story content analysis
        mock_analysis_response = Mock()
        mock_analysis_response.content = """
        {
            "recommended_roles": ["qa-engineer", "system-architect"],
            "target_repositories": ["backend"],
            "complexity": "medium",
            "themes": ["rating", "user interaction"],
            "reasoning": "Recipe rating requires database changes and API development"
        }
        """

        # Mock expert role analysis
        mock_expert_response = Mock()
        mock_expert_response.content = (
            "Expert analysis of the story from role perspective"
        )
        mock_expert_response.model = "test-model"
        mock_expert_response.provider = "test-provider"
        mock_expert_response.usage = {}

        self.mock_llm_handler.analyze_story_with_role.return_value = (
            mock_expert_response
        )

        # Mock synthesis
        mock_synthesis_response = Mock()
        mock_synthesis_response.content = "Synthesized analysis from all expert roles"

        self.mock_llm_handler.synthesize_expert_analyses.return_value = (
            mock_synthesis_response
        )

        # Setup requirement gathering mocks (similar to previous test)
        from role_analyzer import RoleAssignment, RoleAssignmentResult

        mock_assignment_result = RoleAssignmentResult(
            story_id="test_story_456",
            primary_roles=[
                RoleAssignment("qa-engineer", 0.9, "Testing expertise"),
                RoleAssignment("system-architect", 0.8, "Architecture analysis"),
            ],
            secondary_roles=[],
            suggested_roles=[],
        )

        self.mock_role_engine.assign_roles.return_value = mock_assignment_result

        # Setup mock repository context
        mock_repo_context = RepositoryContext(
            repository="backend",
            repo_type="backend",
            description="Backend API services",
            languages={"python": 0.8},
            key_files=[],
        )

        self.mock_context_reader.get_repository_context = AsyncMock(
            return_value=mock_repo_context
        )

        # Setup requirement gathering response
        def mock_generate_response(prompt, **kwargs):
            response = Mock()
            if "Analyze this user story" in prompt:
                response.content = mock_analysis_response.content
            elif "acceptance criteria" in prompt.lower():
                response.content = "- Acceptance criterion from role analysis"
            elif "testing requirements" in prompt.lower():
                response.content = "- Testing requirement from role analysis"
            elif "effort estimation" in prompt.lower():
                response.content = (
                    '{"story_points": 3, "complexity": 2, "confidence": "high"}'
                )
            elif "synthesize" in prompt.lower():
                response.content = '{"acceptance_criteria": ["Synthesized criterion"], "testing_requirements": ["Synthesized test"]}'
            else:
                response.content = "Default response"

            return response

        self.mock_llm_handler.generate_response = AsyncMock(
            side_effect=mock_generate_response
        )

        # Test the enhanced workflow
        result = await self.story_processor.analyze_story_workflow(
            content="As a user, I want to rate recipes",
            roles=["qa-engineer", "system-architect"],
            context={"target_repositories": ["backend"]},
        )

        # Verify the workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIn(
            "Story analysis and requirement gathering completed", result["message"]
        )

        # Verify data structure
        data = result["data"]
        self.assertIn("story_id", data)
        self.assertIn("processed_story", data)
        self.assertIn("gathered_requirements", data)
        self.assertIn("acceptance_criteria", data)
        self.assertIn("testing_requirements", data)
        self.assertIn("estimated_story_points", data)
        self.assertIn("confidence_score", data)

        # Verify requirement gathering results are included
        self.assertIsInstance(data["gathered_requirements"], GatheredRequirements)
        self.assertIsInstance(data["acceptance_criteria"], list)
        self.assertIsInstance(data["testing_requirements"], list)
        self.assertIsInstance(data["estimated_story_points"], int)
        self.assertIsInstance(data["confidence_score"], float)

    @pytest.mark.asyncio
    async def test_requirement_gathering_with_multiple_repositories(self):
        """Test requirement gathering when multiple repositories are involved."""

        # Setup multiple repository contexts
        backend_context = RepositoryContext(
            repository="backend",
            repo_type="backend",
            description="Backend API services",
            languages={"python": 0.9},
            key_files=[],
        )

        frontend_context = RepositoryContext(
            repository="frontend",
            repo_type="frontend",
            description="Frontend user interface",
            languages={"javascript": 0.7, "typescript": 0.3},
            key_files=[],
        )

        def mock_get_repo_context(repo_name):
            if repo_name == "backend":
                return backend_context
            elif repo_name == "frontend":
                return frontend_context
            else:
                raise ValueError(f"Unknown repository: {repo_name}")

        self.mock_context_reader.get_repository_context = AsyncMock(
            side_effect=mock_get_repo_context
        )

        # Setup role assignment for multiple repositories
        from role_analyzer import RoleAssignment, RoleAssignmentResult

        mock_assignment_result = RoleAssignmentResult(
            story_id="test_story_multi",
            primary_roles=[
                RoleAssignment("system-architect", 0.9, "Multi-repo architecture"),
                RoleAssignment("lead-developer", 0.8, "Cross-repo implementation"),
                RoleAssignment("ux-ui-designer", 0.7, "Frontend design"),
            ],
            secondary_roles=[
                RoleAssignment("qa-engineer", 0.6, "Cross-repo testing"),
            ],
            suggested_roles=[],
        )

        self.mock_role_engine.assign_roles.return_value = mock_assignment_result

        # Setup requirement gathering responses
        def mock_generate_response(prompt, **kwargs):
            response = Mock()
            role_context = kwargs.get("role_context", "")

            if "acceptance criteria" in prompt.lower():
                if "ux-ui-designer" in role_context:
                    response.content = (
                        "- Frontend UI shall be responsive and accessible"
                    )
                elif "system-architect" in role_context:
                    response.content = (
                        "- System shall maintain data consistency across repositories"
                    )
                else:
                    response.content = "- Generic acceptance criterion"
            elif "testing requirements" in prompt.lower():
                response.content = "- Cross-repository integration tests required"
            elif "effort estimation" in prompt.lower():
                response.content = (
                    '{"story_points": 8, "complexity": 4, "confidence": "medium"}'
                )
            elif "synthesize" in prompt.lower():
                response.content = """
                {
                    "acceptance_criteria": [
                        "Frontend UI shall be responsive and accessible",
                        "System shall maintain data consistency across repositories",
                        "API endpoints shall follow consistent patterns"
                    ],
                    "testing_requirements": [
                        "Cross-repository integration tests required",
                        "Frontend component tests for UI elements",
                        "Backend API tests for data consistency"
                    ]
                }
                """
            else:
                response.content = "Default response"

            return response

        self.mock_llm_handler.generate_response = AsyncMock(
            side_effect=mock_generate_response
        )

        # Test requirement gathering with multiple repositories
        gathered_requirements = await self.story_processor.gather_requirements(
            story_content="As a user, I want to manage my recipe collection across devices",
            target_repositories=["backend", "frontend"],
        )

        # Verify multi-repository requirements
        self.assertEqual(
            len(gathered_requirements.role_requirements), 4
        )  # 3 primary + 1 secondary

        # Check that repository-specific requirements are captured
        metadata = gathered_requirements.metadata
        self.assertIn("repository_contexts", metadata)
        self.assertEqual(len(metadata["repository_contexts"]), 2)

        # Verify synthesized requirements consider multiple repositories
        self.assertGreater(
            len(gathered_requirements.synthesized_acceptance_criteria), 1
        )
        self.assertGreater(
            len(gathered_requirements.synthesized_testing_requirements), 1
        )

        # Check that cross-repository considerations are included
        acceptance_criteria_text = " ".join(
            gathered_requirements.synthesized_acceptance_criteria
        )
        self.assertIn("data consistency", acceptance_criteria_text.lower())


if __name__ == "__main__":
    unittest.main()
