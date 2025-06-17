"""Tests for Epic breakdown functionality."""

import asyncio
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from database import DatabaseManager
from models import Epic, StoryStatus, UserStory
from story_manager import StoryManager


class TestEpicBreakdown(unittest.TestCase):
    """Test the epic breakdown functionality."""

    def setUp(self):
        """Set up test environment."""
        # Use temporary database for tests
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
        # Create test database manager
        self.database = DatabaseManager(db_path=self.temp_db.name)
        
        # Create test epic
        self.test_epic = Epic(
            title="User Authentication System",
            description="Implement comprehensive user authentication including login, registration, and password recovery",
            business_value="Enable secure user access and improve platform security",
            acceptance_criteria=[
                "Users can register with email and password",
                "Users can login with valid credentials",
                "Users can recover forgotten passwords",
                "User sessions are managed securely"
            ],
            target_repositories=["backend", "frontend"],
            estimated_duration_weeks=4,
        )
        
        # Save test epic to database
        self.database.save_story(self.test_epic)
    
    def tearDown(self):
        """Clean up test environment."""
        import os
        os.unlink(self.temp_db.name)

    @patch('story_manager.StoryProcessor')
    def test_breakdown_epic_to_user_stories_success(self, mock_processor_class):
        """Test successful epic breakdown."""
        
        # Mock the LLM response
        mock_llm_response = Mock()
        mock_llm_response.content = """{
            "user_stories": [
                {
                    "title": "User Registration",
                    "description": "As a new user, I want to register an account so that I can access the platform",
                    "user_persona": "new user",
                    "user_goal": "register an account",
                    "acceptance_criteria": [
                        "User can enter email and password",
                        "System validates email format",
                        "Account is created successfully"
                    ],
                    "target_repositories": ["backend", "frontend"],
                    "story_points": 5,
                    "rationale": "Core registration functionality"
                },
                {
                    "title": "User Login",
                    "description": "As a registered user, I want to login so that I can access my account",
                    "user_persona": "registered user",
                    "user_goal": "login to account",
                    "acceptance_criteria": [
                        "User can enter credentials",
                        "System validates credentials",
                        "User is redirected to dashboard"
                    ],
                    "target_repositories": ["backend", "frontend"],
                    "story_points": 3,
                    "rationale": "Essential login functionality"
                }
            ],
            "breakdown_rationale": "Split authentication into core components"
        }"""
        
        # Mock the processor and LLM handler
        mock_processor = Mock()
        mock_llm_handler = AsyncMock()
        mock_llm_handler.generate_response.return_value = mock_llm_response
        mock_processor.llm_handler = mock_llm_handler
        
        # Mock the config with repositories
        mock_config = Mock()
        mock_config.repositories = {"backend": {"name": "backend"}, "frontend": {"name": "frontend"}}
        mock_processor.config = mock_config
        mock_processor_class.return_value = mock_processor
        
        # Create story manager with mocked database
        story_manager = StoryManager()
        story_manager.database = self.database
        story_manager.processor = mock_processor
        
        # Run the breakdown
        async def run_test():
            user_stories = await story_manager.breakdown_epic_to_user_stories(
                epic_id=self.test_epic.id,
                max_user_stories=5,
                target_repositories=["backend", "frontend"]
            )
            
            # Assertions
            self.assertEqual(len(user_stories), 2)
            
            # Check first user story
            story1 = user_stories[0]
            self.assertEqual(story1.title, "User Registration")
            self.assertEqual(story1.epic_id, self.test_epic.id)
            self.assertEqual(story1.user_persona, "new user")
            self.assertEqual(story1.story_points, 5)
            self.assertEqual(len(story1.acceptance_criteria), 3)
            
            # Check second user story
            story2 = user_stories[1]
            self.assertEqual(story2.title, "User Login")
            self.assertEqual(story2.epic_id, self.test_epic.id)
            self.assertEqual(story2.user_persona, "registered user")
            self.assertEqual(story2.story_points, 3)
            
            # Verify both stories are in the database
            hierarchy = self.database.get_epic_hierarchy(self.test_epic.id)
            self.assertIsNotNone(hierarchy)
            self.assertEqual(len(hierarchy.user_stories), 2)
            
        asyncio.run(run_test())

    @patch('story_manager.StoryProcessor')
    def test_breakdown_epic_to_user_stories_llm_parsing_error(self, mock_processor_class):
        """Test epic breakdown with LLM parsing error (fallback)."""
        
        # Mock the LLM response with invalid JSON
        mock_llm_response = Mock()
        mock_llm_response.content = "Invalid JSON response"
        
        # Mock the processor and LLM handler
        mock_processor = Mock()
        mock_llm_handler = AsyncMock()
        mock_llm_handler.generate_response.return_value = mock_llm_response
        mock_processor.llm_handler = mock_llm_handler
        
        # Mock the config with repositories
        mock_config = Mock()
        mock_config.repositories = {"backend": {"name": "backend"}, "frontend": {"name": "frontend"}}
        mock_processor.config = mock_config
        mock_processor_class.return_value = mock_processor
        
        # Create story manager with mocked database
        story_manager = StoryManager()
        story_manager.database = self.database
        story_manager.processor = mock_processor
        
        # Run the breakdown
        async def run_test():
            user_stories = await story_manager.breakdown_epic_to_user_stories(
                epic_id=self.test_epic.id,
                max_user_stories=3,
            )
            
            # Should create fallback user story
            self.assertEqual(len(user_stories), 1)
            
            fallback_story = user_stories[0]
            self.assertEqual(fallback_story.title, f"Implement {self.test_epic.title}")
            self.assertEqual(fallback_story.epic_id, self.test_epic.id)
            self.assertEqual(fallback_story.story_points, 5)
            
        asyncio.run(run_test())

    @patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token'})
    @patch('story_manager.get_config')
    def test_breakdown_epic_invalid_epic_id(self, mock_get_config):
        """Test breakdown with invalid epic ID."""
        
        # Mock config with proper string values
        mock_config = Mock()
        mock_config.repositories = {"backend": {"name": "backend"}}
        mock_config.default_repository = "backend"
        mock_config.github_token = "test_token"
        mock_config.default_llm_provider = "github"
        mock_config.openai_api_key = None
        mock_config.ollama_api_host = "http://localhost:11434"  # Provide default value
        mock_get_config.return_value = mock_config
        
        story_manager = StoryManager()
        story_manager.database = self.database
        
        async def run_test():
            with self.assertRaises(ValueError) as context:
                await story_manager.breakdown_epic_to_user_stories(
                    epic_id="invalid_id",
                    max_user_stories=3,
                )
            
            self.assertIn("Epic not found", str(context.exception))
            
        asyncio.run(run_test())

    def test_parent_child_linking(self):
        """Test that user stories are properly linked to their parent epic."""
        
        # Create a user story manually
        user_story = UserStory(
            epic_id=self.test_epic.id,
            title="Test User Story",
            description="Test description",
            user_persona="test user",
            user_goal="test goal",
        )
        
        self.database.save_story(user_story)
        
        # Verify the hierarchy
        hierarchy = self.database.get_epic_hierarchy(self.test_epic.id)
        self.assertIsNotNone(hierarchy)
        self.assertEqual(hierarchy.epic.id, self.test_epic.id)
        self.assertEqual(len(hierarchy.user_stories), 1)
        self.assertEqual(hierarchy.user_stories[0].epic_id, self.test_epic.id)

    def test_progress_tracking(self):
        """Test progress tracking from epic to user stories."""
        
        # Create multiple user stories with different statuses
        user_story1 = UserStory(
            epic_id=self.test_epic.id,
            title="Completed Story",
            description="A completed story",
            status=StoryStatus.DONE,
        )
        
        user_story2 = UserStory(
            epic_id=self.test_epic.id,
            title="In Progress Story",
            description="A story in progress",
            status=StoryStatus.IN_PROGRESS,
        )
        
        user_story3 = UserStory(
            epic_id=self.test_epic.id,
            title="Draft Story",
            description="A draft story",
            status=StoryStatus.DRAFT,
        )
        
        # Save all stories
        for story in [user_story1, user_story2, user_story3]:
            self.database.save_story(story)
        
        # Check progress
        hierarchy = self.database.get_epic_hierarchy(self.test_epic.id)
        progress = hierarchy.get_epic_progress()
        
        # Should have 1 completed out of 3 total
        self.assertEqual(progress['total'], 3)
        self.assertEqual(progress['completed'], 1)
        self.assertEqual(progress['percentage'], 33.3)


if __name__ == '__main__':
    unittest.main()