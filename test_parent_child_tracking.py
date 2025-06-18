"""Tests for parent-child relationship tracking functionality."""

import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from models import Epic, StoryStatus, SubStory, UserStory


class TestParentChildTracking(unittest.TestCase):
    """Test parent-child relationship tracking functionality."""

    def setUp(self):
        """Set up test database."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_manager = DatabaseManager(self.temp_file.name)

    def tearDown(self):
        """Clean up test database."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_automatic_status_propagation_user_story_to_epic(self):
        """Test that completing user stories updates epic status."""
        # Create epic
        epic = Epic(title="Test Epic", business_value="High value")
        self.db_manager.save_story(epic)

        # Create multiple user stories
        user_story1 = UserStory(epic_id=epic.id, title="US 1")
        user_story2 = UserStory(epic_id=epic.id, title="US 2")
        self.db_manager.save_story(user_story1)
        self.db_manager.save_story(user_story2)

        # Initially, epic should not be done
        hierarchy = self.db_manager.get_epic_hierarchy(epic.id)
        self.assertEqual(hierarchy.epic.status, StoryStatus.DRAFT)

        # Complete one user story
        self.db_manager.update_story_status(user_story1.id, StoryStatus.DONE)

        # Epic should now be in progress
        updated_epic = self.db_manager.get_story(epic.id)
        self.assertEqual(updated_epic.status, StoryStatus.IN_PROGRESS)

        # Complete second user story
        self.db_manager.update_story_status(user_story2.id, StoryStatus.DONE)

        # Epic should now be done
        updated_epic = self.db_manager.get_story(epic.id)
        self.assertEqual(updated_epic.status, StoryStatus.DONE)

    def test_automatic_status_propagation_sub_story_to_user_story(self):
        """Test that completing sub-stories updates user story status."""
        # Create hierarchy
        epic = Epic(title="Test Epic")
        self.db_manager.save_story(epic)

        user_story = UserStory(epic_id=epic.id, title="Test User Story")
        self.db_manager.save_story(user_story)

        sub_story1 = SubStory(user_story_id=user_story.id, title="Sub 1", department="backend")
        sub_story2 = SubStory(user_story_id=user_story.id, title="Sub 2", department="frontend")
        self.db_manager.save_story(sub_story1)
        self.db_manager.save_story(sub_story2)

        # Complete one sub-story
        self.db_manager.update_story_status(sub_story1.id, StoryStatus.DONE)

        # User story should be in progress
        updated_user_story = self.db_manager.get_story(user_story.id)
        self.assertEqual(updated_user_story.status, StoryStatus.IN_PROGRESS)

        # Complete second sub-story
        self.db_manager.update_story_status(sub_story2.id, StoryStatus.DONE)

        # User story should now be done
        updated_user_story = self.db_manager.get_story(user_story.id)
        self.assertEqual(updated_user_story.status, StoryStatus.DONE)

    def test_status_propagation_blocked_status(self):
        """Test that blocked children make parent blocked."""
        # Create hierarchy
        epic = Epic(title="Test Epic")
        self.db_manager.save_story(epic)

        user_story = UserStory(epic_id=epic.id, title="Test User Story")
        self.db_manager.save_story(user_story)

        sub_story = SubStory(user_story_id=user_story.id, title="Sub Story", department="backend")
        self.db_manager.save_story(sub_story)

        # Block the sub-story
        self.db_manager.update_story_status(sub_story.id, StoryStatus.BLOCKED)

        # User story should be blocked
        updated_user_story = self.db_manager.get_story(user_story.id)
        self.assertEqual(updated_user_story.status, StoryStatus.BLOCKED)

        # Epic should be blocked
        updated_epic = self.db_manager.get_story(epic.id)
        self.assertEqual(updated_epic.status, StoryStatus.BLOCKED)

    def test_relationship_validation_prevents_cycles(self):
        """Test that relationship validation prevents circular dependencies."""
        # Create stories
        story1 = Epic(title="Story 1")
        story2 = Epic(title="Story 2") 
        story3 = Epic(title="Story 3")
        
        self.db_manager.save_story(story1)
        self.db_manager.save_story(story2)
        self.db_manager.save_story(story3)

        # Create valid dependency chain: story1 -> story2 -> story3
        self.db_manager.add_story_relationship(story1.id, story2.id, "depends_on")
        self.db_manager.add_story_relationship(story2.id, story3.id, "depends_on")

        # Try to create circular dependency: story3 -> story1
        with self.assertRaises(ValueError):
            self.db_manager.add_story_relationship(story3.id, story1.id, "depends_on")

    def test_parent_child_validation(self):
        """Test validation of parent-child relationships."""
        story1 = Epic(title="Story 1")
        story2 = Epic(title="Story 2")
        
        self.db_manager.save_story(story1)
        self.db_manager.save_story(story2)

        # Valid relationship
        self.assertTrue(self.db_manager.validate_parent_child_relationship(story2.id, story1.id))

        # Invalid - self as parent
        self.assertFalse(self.db_manager.validate_parent_child_relationship(story1.id, story1.id))

    def test_dependency_chain_retrieval(self):
        """Test retrieving dependency chains."""
        # Create stories
        story1 = Epic(title="Story 1")
        story2 = Epic(title="Story 2")
        story3 = Epic(title="Story 3")
        
        self.db_manager.save_story(story1)
        self.db_manager.save_story(story2)
        self.db_manager.save_story(story3)

        # Create dependency chain
        self.db_manager.add_story_relationship(story1.id, story2.id, "depends_on")
        self.db_manager.add_story_relationship(story2.id, story3.id, "depends_on")

        # Get dependency chain
        dependencies = self.db_manager.get_dependency_chain(story1.id)
        
        self.assertEqual(len(dependencies), 2)
        self.assertEqual(dependencies[0]["target_story_id"], story2.id)
        self.assertEqual(dependencies[1]["target_story_id"], story3.id)

    def test_relationship_integrity_validation(self):
        """Test relationship integrity validation."""
        # Initially should have no issues
        issues = self.db_manager.validate_relationship_integrity()
        self.assertEqual(len(issues), 0)

        # Create a story and relationship
        story1 = Epic(title="Story 1")
        story2 = Epic(title="Story 2")
        
        self.db_manager.save_story(story1)
        self.db_manager.save_story(story2)
        
        self.db_manager.add_story_relationship(story1.id, story2.id, "depends_on")

        # Should still have no issues
        issues = self.db_manager.validate_relationship_integrity()
        self.assertEqual(len(issues), 0)

    def test_progress_calculation_with_mixed_statuses(self):
        """Test progress calculation with various status combinations."""
        # Create epic with user stories in different states
        epic = Epic(title="Test Epic")
        self.db_manager.save_story(epic)

        user_story1 = UserStory(epic_id=epic.id, title="US 1")  # Will be DONE
        user_story2 = UserStory(epic_id=epic.id, title="US 2")  # Will be IN_PROGRESS
        user_story3 = UserStory(epic_id=epic.id, title="US 3")  # Will stay DRAFT
        
        self.db_manager.save_story(user_story1)
        self.db_manager.save_story(user_story2)
        self.db_manager.save_story(user_story3)

        # Update statuses
        self.db_manager.update_story_status(user_story1.id, StoryStatus.DONE)
        self.db_manager.update_story_status(user_story2.id, StoryStatus.IN_PROGRESS)

        # Check epic progress
        hierarchy = self.db_manager.get_epic_hierarchy(epic.id)
        progress = hierarchy.get_epic_progress()
        
        self.assertEqual(progress["total"], 3)
        self.assertEqual(progress["completed"], 1)  # Only one is DONE
        self.assertEqual(progress["percentage"], 33.3)

        # Epic should be in progress due to mixed states
        updated_epic = self.db_manager.get_story(epic.id)
        self.assertEqual(updated_epic.status, StoryStatus.IN_PROGRESS)


if __name__ == "__main__":
    unittest.main()