"""Tests for sub-story generation functionality."""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"

from models import UserStory  # noqa: E402
from story_manager import StoryManager  # noqa: E402


class TestSubStoryGeneration(unittest.TestCase):
    """Test sub-story generation for different departments."""

    def setUp(self):
        """Set up test dependencies."""
        # Use temporary database for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()

        self.story_manager = StoryManager()
        self.story_manager.database.db_path = Path(self.temp_file.name)
        self.story_manager.database.init_database()

    def tearDown(self):
        """Clean up test dependencies."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_get_department_dependencies(self):
        """Test department dependency mapping."""
        dependencies = self.story_manager._get_department_dependencies()

        # Verify expected dependencies
        self.assertIn("frontend", dependencies)
        self.assertIn("backend", dependencies["frontend"])

        self.assertIn("testing", dependencies)
        self.assertEqual(set(dependencies["testing"]), {"backend", "frontend"})

        self.assertIn("devops", dependencies)
        self.assertEqual(
            set(dependencies["devops"]), {"backend", "frontend", "testing"}
        )

    def test_analyze_user_story_for_departments_success(self):
        """Test successful LLM analysis of user story for departments."""

        with patch.object(
            self.story_manager.processor.llm_handler, "generate_response"
        ) as mock_llm:
            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = json.dumps(
                [
                    {
                        "department": "backend",
                        "title": "Backend API Implementation",
                        "description": "Implement backend API endpoints",
                        "tasks": [
                            "Create API endpoint",
                            "Add validation",
                            "Write tests",
                        ],
                        "dependencies": [],
                        "target_repository": "backend",
                        "estimated_hours": 8,
                    },
                    {
                        "department": "frontend",
                        "title": "Frontend UI Implementation",
                        "description": "Implement frontend user interface",
                        "tasks": [
                            "Create UI components",
                            "Integrate with API",
                            "Add styling",
                        ],
                        "dependencies": ["backend"],
                        "target_repository": "frontend",
                        "estimated_hours": 12,
                    },
                ]
            )
            mock_llm.return_value = mock_response

            # Create test user story
            user_story = UserStory(
                epic_id="test_epic",
                title="User Login Feature",
                description="As a user, I want to log in to access my account",
                user_persona="registered user",
                user_goal="log in to my account",
                acceptance_criteria=[
                    "Valid credentials accepted",
                    "Invalid credentials rejected",
                ],
                target_repositories=["backend", "frontend"],
                story_points=8,
            )

            # Test the analysis
            async def run_test():
                departments = (
                    await self.story_manager._analyze_user_story_for_departments(
                        user_story, ["backend", "frontend", "testing", "devops"]
                    )
                )

                # Verify results
                self.assertEqual(len(departments), 2)

                backend_dept = next(
                    d for d in departments if d["department"] == "backend"
                )
                self.assertEqual(backend_dept["title"], "Backend API Implementation")
                self.assertEqual(backend_dept["estimated_hours"], 8)

                frontend_dept = next(
                    d for d in departments if d["department"] == "frontend"
                )
                self.assertEqual(frontend_dept["dependencies"], ["backend"])

            asyncio.run(run_test())

    def test_analyze_user_story_for_departments_fallback(self):
        """Test fallback when LLM analysis fails."""

        with patch.object(
            self.story_manager.processor.llm_handler, "generate_response"
        ) as mock_llm:
            # Mock LLM to raise exception
            mock_llm.side_effect = json.JSONDecodeError("Test error", "", 0)

            # Create test user story
            user_story = UserStory(
                epic_id="test_epic",
                title="User Login Feature",
                description="As a user, I want to log in",
                target_repositories=["backend", "frontend"],
            )

            # Test the analysis fallback
            async def run_test():
                departments = (
                    await self.story_manager._analyze_user_story_for_departments(
                        user_story, ["backend", "frontend", "testing", "devops"]
                    )
                )

                # Verify fallback creates expected departments
                self.assertGreaterEqual(
                    len(departments), 2
                )  # backend, frontend, testing

                dept_names = [d["department"] for d in departments]
                self.assertIn("backend", dept_names)
                self.assertIn("frontend", dept_names)
                self.assertIn("testing", dept_names)

            asyncio.run(run_test())

    def test_generate_sub_stories_for_departments_success(self):
        """Test successful sub-story generation."""

        with (
            patch.object(self.story_manager.database, "get_story") as mock_get,
            patch.object(self.story_manager.database, "save_story") as mock_save,
            patch.object(
                self.story_manager.database, "add_story_relationship"
            ) as mock_add_rel,
            patch.object(
                self.story_manager, "_analyze_user_story_for_departments"
            ) as mock_analyze,
        ):

            # Mock database operations
            user_story = UserStory(
                id="user_story_123",
                epic_id="epic_123",
                title="User Authentication",
                description="Implement user authentication system",
                target_repositories=["backend", "frontend"],
            )
            mock_get.return_value = user_story
            mock_save.return_value = True
            mock_add_rel.return_value = True

            # Mock analysis result
            mock_analyze.return_value = [
                {
                    "department": "backend",
                    "title": "Backend Authentication API",
                    "description": "Implement authentication endpoints",
                    "tasks": ["JWT implementation", "Password validation"],
                    "dependencies": [],
                    "target_repository": "backend",
                    "estimated_hours": 8,
                },
                {
                    "department": "testing",
                    "title": "Authentication Testing",
                    "description": "Test authentication functionality",
                    "tasks": ["Unit tests", "Integration tests"],
                    "dependencies": ["backend"],
                    "target_repository": "backend",
                    "estimated_hours": 6,
                },
            ]

            # Test sub-story generation
            async def run_test():
                sub_stories = (
                    await self.story_manager.generate_sub_stories_for_departments(
                        "user_story_123", ["backend", "testing"]
                    )
                )

                # Verify results
                self.assertEqual(len(sub_stories), 2)

                backend_story = next(
                    s for s in sub_stories if s.department == "backend"
                )
                self.assertEqual(backend_story.title, "Backend Authentication API")
                self.assertEqual(backend_story.estimated_hours, 8)

                testing_story = next(
                    s for s in sub_stories if s.department == "testing"
                )
                self.assertEqual(testing_story.department, "testing")
                self.assertEqual(testing_story.estimated_hours, 6)

                # Verify that dependency was added
                mock_add_rel.assert_called_once()

            asyncio.run(run_test())

    def test_generate_sub_stories_invalid_user_story(self):
        """Test error handling for invalid user story ID."""

        with patch.object(self.story_manager.database, "get_story") as mock_get:
            mock_get.return_value = None

            async def run_test():
                with self.assertRaises(ValueError) as context:
                    await self.story_manager.generate_sub_stories_for_departments(
                        "invalid_id"
                    )

                self.assertIn(
                    "User story not found: invalid_id", str(context.exception)
                )

            asyncio.run(run_test())


# Async test runner
class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def run_async(self, coro):
        return self.loop.run_until_complete(coro)


class TestSubStoryGenerationAsync(AsyncTestCase):
    """Async tests for sub-story generation."""

    def setUp(self):
        super().setUp()
        # Use temporary database for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()

        self.story_manager = StoryManager()
        self.story_manager.database.db_path = Path(self.temp_file.name)
        self.story_manager.database.init_database()

    def tearDown(self):
        super().tearDown()
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_analyze_user_story_for_departments_success(self):
        """Test successful department analysis."""

        async def run_test():
            with patch.object(
                self.story_manager.processor.llm_handler, "generate_response"
            ) as mock_llm:
                mock_response = MagicMock()
                mock_response.content = json.dumps(
                    [
                        {
                            "department": "backend",
                            "title": "Backend Implementation",
                            "description": "Backend work",
                            "tasks": ["API", "Database"],
                            "dependencies": [],
                            "target_repository": "backend",
                            "estimated_hours": 8,
                        }
                    ]
                )
                mock_llm.return_value = mock_response

                user_story = UserStory(
                    epic_id="test", title="Test Story", target_repositories=["backend"]
                )

                result = await self.story_manager._analyze_user_story_for_departments(
                    user_story, ["backend", "frontend"]
                )

                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["department"], "backend")

        self.run_async(run_test())

    def test_generate_sub_stories_success(self):
        """Test successful sub-story generation end-to-end."""

        async def run_test():
            with (
                patch.object(self.story_manager.database, "get_story") as mock_get,
                patch.object(self.story_manager.database, "save_story") as mock_save,
                patch.object(
                    self.story_manager, "_analyze_user_story_for_departments"
                ) as mock_analyze,
            ):

                user_story = UserStory(
                    id="test_story", epic_id="test_epic", title="Test"
                )
                mock_get.return_value = user_story
                mock_save.return_value = True
                mock_analyze.return_value = [
                    {
                        "department": "backend",
                        "title": "Backend Task",
                        "description": "Backend implementation",
                        "tasks": ["API development"],
                        "dependencies": [],
                        "target_repository": "backend",
                        "estimated_hours": 8,
                    }
                ]

                result = await self.story_manager.generate_sub_stories_for_departments(
                    "test_story"
                )

                self.assertEqual(len(result), 1)
                self.assertEqual(result[0].department, "backend")

        self.run_async(run_test())


if __name__ == "__main__":
    unittest.main()
