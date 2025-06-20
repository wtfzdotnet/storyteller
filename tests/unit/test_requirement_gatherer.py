"""Tests for role-based requirement gathering functionality."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from config import Config
from multi_repo_context import RepositoryContext
from requirement_gatherer import (
    GatheredRequirements,
    RequirementGatherer,
    RequirementSet,
)
from role_analyzer import RoleAssignment


class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """Clean up after tests."""
        self.loop.close()
        super().tearDown()

    def run_async(self, coro):
        """Run an async coroutine in the test loop."""
        return self.loop.run_until_complete(coro)


class TestRequirementGatherer(AsyncTestCase):
    """Test the RequirementGatherer class."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.config = Config(
            github_token="test_token",
            github_repository="wtfzdotnet/storyteller",
            default_llm_provider="github",
        )

        # Mock LLM handler
        self.mock_llm_handler = Mock()
        self.requirement_gatherer = RequirementGatherer(
            self.config, self.mock_llm_handler
        )

    def test_requirement_gatherer_initialization(self):
        """Test that RequirementGatherer initializes correctly."""
        self.assertIsNotNone(self.requirement_gatherer.config)
        self.assertIsNotNone(self.requirement_gatherer.llm_handler)
        self.assertIsNotNone(self.requirement_gatherer.templates_dir)

    def test_gather_acceptance_criteria(self):
        """Test gathering acceptance criteria from a role."""

        async def async_test():
            # Setup mock response
            mock_response = Mock()
            mock_response.content = """
            - The system shall validate user input for recipe ratings
            - The user can submit ratings from 1-5 stars
            - The system shall display average ratings on recipe pages
            """
            self.mock_llm_handler.generate_response = AsyncMock(
                return_value=mock_response
            )

            # Create test role assignment
            role_assignment = RoleAssignment(
                role_name="qa-engineer",
                confidence_score=0.9,
                assignment_reason="Testing expertise required",
            )

            context = {
                "story_content": "As a user, I want to rate recipes",
                "role_name": "qa-engineer",
                "repository_context": "backend",
                "assignment_reason": "Testing expertise required",
            }

            # Test gathering acceptance criteria
            criteria = await self.requirement_gatherer._gather_acceptance_criteria(
                role_assignment, context
            )

            # Verify results
            self.assertEqual(len(criteria), 3)
            self.assertIn("validate user input", criteria[0])
            self.assertIn("submit ratings", criteria[1])
            self.assertIn("display average ratings", criteria[2])

        self.run_async(async_test())

    def test_gather_testing_requirements(self):
        """Test gathering testing requirements from a role."""

        async def async_test():
            # Setup mock response
            mock_response = Mock()
            mock_response.content = """
            - Unit tests for rating validation logic
            - Integration tests for rating submission API
            - End-to-end tests for rating display functionality
            - Performance tests for rating aggregation
            """
            self.mock_llm_handler.generate_response = AsyncMock(
                return_value=mock_response
            )

            # Create test role assignment
            role_assignment = RoleAssignment(
                role_name="qa-engineer",
                confidence_score=0.9,
                assignment_reason="Testing expertise required",
            )

            context = {
                "story_content": "As a user, I want to rate recipes",
                "role_name": "qa-engineer",
                "repository_context": "backend",
            }

            # Test gathering testing requirements
            requirements = await self.requirement_gatherer._gather_testing_requirements(
                role_assignment, context
            )

            # Verify results
            self.assertEqual(len(requirements), 4)
            self.assertIn("Unit tests", requirements[0])
            self.assertIn("Integration tests", requirements[1])
            self.assertIn("End-to-end tests", requirements[2])
            self.assertIn("Performance tests", requirements[3])

        self.run_async(async_test())

    def test_gather_effort_estimation(self):
        """Test gathering effort estimation from a role."""

        async def async_test():
            # Setup mock response with JSON
            mock_response = Mock()
            mock_response.content = """
            {
                "story_points": 5,
                "complexity": 3,
                "time_estimate_hours": 16,
                "risk_factors": ["Database migration complexity", "Integration testing"],
                "confidence": "medium",
                "reasoning": "Moderate complexity due to database changes"
            }
            """
            self.mock_llm_handler.generate_response = AsyncMock(
                return_value=mock_response
            )

            # Create test role assignment
            role_assignment = RoleAssignment(
                role_name="system-architect",
                confidence_score=0.9,
                assignment_reason="Architecture analysis required",
            )

            context = {
                "story_content": "As a user, I want to rate recipes",
                "role_name": "system-architect",
                "repository_context": "backend",
            }

            # Test gathering effort estimation
            estimate = await self.requirement_gatherer._gather_effort_estimation(
                role_assignment, context
            )

            # Verify results
            self.assertEqual(estimate["story_points"], 5)
            self.assertEqual(estimate["complexity"], 3)
            self.assertEqual(estimate["time_estimate_hours"], 16)
            self.assertEqual(estimate["confidence"], "medium")
            self.assertIn("Database migration", estimate["risk_factors"][0])

        self.run_async(async_test())

    def test_gather_effort_estimation_fallback_parsing(self):
        """Test effort estimation with fallback parsing when JSON fails."""

        async def async_test():
            # Setup mock response with non-JSON content
            mock_response = Mock()
            mock_response.content = """
            Story Points: 8
            Complexity: 4 out of 5
            This is a high complexity story due to multiple integrations.
            Confidence level is low due to uncertainty.
            """
            self.mock_llm_handler.generate_response = AsyncMock(
                return_value=mock_response
            )

            # Create test role assignment
            role_assignment = RoleAssignment(
                role_name="lead-developer",
                confidence_score=0.8,
                assignment_reason="Development expertise required",
            )

            context = {
                "story_content": "Complex integration story",
                "role_name": "lead-developer",
                "repository_context": "backend, frontend",
            }

            # Test gathering effort estimation
            estimate = await self.requirement_gatherer._gather_effort_estimation(
                role_assignment, context
            )

            # Verify fallback parsing worked
            self.assertEqual(estimate["story_points"], 8)
            self.assertEqual(estimate["complexity"], 4)
            self.assertEqual(estimate["confidence"], "low")

        self.run_async(async_test())

    def test_gather_requirements_full_workflow(self):
        """Test the complete requirement gathering workflow."""

        async def async_test():
            # Setup mock responses for all gathering methods
            mock_acceptance_response = Mock()
            mock_acceptance_response.content = (
                "- Acceptance criterion 1\n- Acceptance criterion 2"
            )

            mock_testing_response = Mock()
            mock_testing_response.content = (
                "- Testing requirement 1\n- Testing requirement 2"
            )

            mock_effort_response = Mock()
            mock_effort_response.content = (
                '{"story_points": 3, "complexity": 2, "confidence": "high"}'
            )

            mock_synthesis_response = Mock()
            mock_synthesis_response.content = '{"acceptance_criteria": ["Synthesized criterion 1"], "testing_requirements": ["Synthesized test 1"]}'

            # Configure mock to return different responses based on call
            def mock_generate_response(prompt, **kwargs):
                if "acceptance criteria" in prompt.lower():
                    return mock_acceptance_response
                elif "testing requirements" in prompt.lower():
                    return mock_testing_response
                elif "effort estimation" in prompt.lower():
                    return mock_effort_response
                else:
                    return mock_synthesis_response

            self.mock_llm_handler.generate_response = AsyncMock(
                side_effect=mock_generate_response
            )

            # Create test data
            story_content = "As a user, I want to rate recipes"
            story_id = "test_story_123"

            assigned_roles = [
                RoleAssignment(
                    role_name="qa-engineer",
                    confidence_score=0.9,
                    assignment_reason="Testing expertise",
                ),
                RoleAssignment(
                    role_name="system-architect",
                    confidence_score=0.8,
                    assignment_reason="Architecture analysis",
                ),
            ]

            repository_contexts = [
                RepositoryContext(
                    repository="backend",
                    repo_type="backend",
                    description="Backend API",
                    languages={"python": 0.8},
                    key_files=[],
                )
            ]

            # Test full gathering workflow
            result = await self.requirement_gatherer.gather_requirements(
                story_content=story_content,
                story_id=story_id,
                assigned_roles=assigned_roles,
                repository_contexts=repository_contexts,
            )

            # Verify result structure
            self.assertIsInstance(result, GatheredRequirements)
            self.assertEqual(result.story_id, story_id)
            self.assertEqual(result.story_content, story_content)
            self.assertEqual(len(result.role_requirements), 2)

            # Verify role requirements
            qa_requirements = next(
                r for r in result.role_requirements if r.role_name == "qa-engineer"
            )
            self.assertEqual(len(qa_requirements.acceptance_criteria), 2)
            self.assertEqual(len(qa_requirements.testing_requirements), 2)

            # Verify synthesized results
            self.assertIsNotNone(result.synthesized_acceptance_criteria)
            self.assertIsNotNone(result.synthesized_testing_requirements)
            self.assertIsNotNone(result.estimated_story_points)

        self.run_async(async_test())

    def test_calculate_consensus_story_points(self):
        """Test story points consensus calculation."""
        # Test median calculation with odd number of estimates
        estimates = [2, 3, 5, 8, 5]
        result = self.requirement_gatherer._calculate_consensus_story_points(estimates)
        self.assertEqual(result, 5)  # Median is 5, which is in Fibonacci sequence

        # Test median calculation with even number of estimates
        estimates = [3, 5, 8, 13]
        result = self.requirement_gatherer._calculate_consensus_story_points(estimates)
        # Median is 6.5, closest Fibonacci is 5 (diff=1.5) vs 8 (diff=1.5), should choose smaller
        self.assertEqual(result, 5)

        # Test empty estimates
        estimates = []
        result = self.requirement_gatherer._calculate_consensus_story_points(estimates)
        self.assertEqual(result, 3)  # Default value

    def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        role_requirements = [
            RequirementSet(role_name="role1", confidence_level="high"),
            RequirementSet(role_name="role2", confidence_level="medium"),
            RequirementSet(role_name="role3", confidence_level="low"),
        ]

        score = self.requirement_gatherer._calculate_confidence_score(role_requirements)

        # Expected: (1.0 + 0.6 + 0.3) / 3 = 0.63333...
        self.assertAlmostEqual(score, 0.633, places=2)

    def test_parse_bulleted_list(self):
        """Test parsing of bulleted lists from LLM responses."""
        content = """
        - First item
        - Second item
        * Third item with asterisk
        • Fourth item with bullet
        1. Numbered item
        2. Another numbered item
        Regular line without bullet
        """

        items = self.requirement_gatherer._parse_bulleted_list(content)

        expected_items = [
            "First item",
            "Second item",
            "Third item with asterisk",
            "Fourth item with bullet",
            "Numbered item",
            "Another numbered item",
        ]

        self.assertEqual(items, expected_items)

    def test_format_repository_context(self):
        """Test repository context formatting."""
        contexts = [
            RepositoryContext(
                repository="backend",
                repo_type="backend",
                description="Backend API",
                languages={},
                key_files=[],
            ),
            RepositoryContext(
                repository="frontend",
                repo_type="frontend",
                description="Frontend UI",
                languages={},
                key_files=[],
            ),
        ]

        formatted = self.requirement_gatherer._format_repository_context(contexts)

        self.assertEqual(formatted, "backend (backend), frontend (frontend)")

    def test_determine_confidence_level(self):
        """Test confidence level determination from role assignment scores."""
        # High confidence
        high_role = RoleAssignment("role1", 0.9, "reason")
        self.assertEqual(
            self.requirement_gatherer._determine_confidence_level(high_role), "high"
        )

        # Medium confidence
        medium_role = RoleAssignment("role2", 0.6, "reason")
        self.assertEqual(
            self.requirement_gatherer._determine_confidence_level(medium_role), "medium"
        )

        # Low confidence
        low_role = RoleAssignment("role3", 0.3, "reason")
        self.assertEqual(
            self.requirement_gatherer._determine_confidence_level(low_role), "low"
        )


if __name__ == "__main__":
    unittest.main()
