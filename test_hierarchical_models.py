"""Tests for hierarchical story management system."""

import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from models import Epic, StoryHierarchy, StoryStatus, StoryType, SubStory, UserStory


class TestHierarchicalModels(unittest.TestCase):
    """Test the hierarchical data models."""

    def test_epic_creation(self):
        """Test Epic creation and serialization."""
        epic = Epic(
            title="Test Epic",
            description="Test epic description",
            business_value="High business value",
            acceptance_criteria=["Criteria 1", "Criteria 2"],
            target_repositories=["backend", "frontend"],
            estimated_duration_weeks=4,
        )

        self.assertEqual(epic.title, "Test Epic")
        self.assertEqual(epic.status, StoryStatus.DRAFT)
        self.assertEqual(len(epic.acceptance_criteria), 2)

        # Test serialization
        epic_dict = epic.to_dict()
        self.assertEqual(epic_dict["story_type"], StoryType.EPIC.value)
        self.assertIsNone(epic_dict["parent_id"])
        self.assertEqual(epic_dict["business_value"], "High business value")

    def test_user_story_creation(self):
        """Test UserStory creation and relationship."""
        epic_id = "epic_123"
        user_story = UserStory(
            epic_id=epic_id,
            title="Test User Story",
            description="As a user, I want...",
            user_persona="Test User",
            user_goal="Achieve something",
            acceptance_criteria=["AC 1", "AC 2"],
            target_repositories=["backend"],
            story_points=5,
        )

        self.assertEqual(user_story.epic_id, epic_id)
        self.assertEqual(user_story.story_points, 5)

        # Test serialization
        story_dict = user_story.to_dict()
        self.assertEqual(story_dict["story_type"], StoryType.USER_STORY.value)
        self.assertEqual(story_dict["parent_id"], epic_id)
        self.assertEqual(story_dict["story_points"], 5)

    def test_sub_story_creation(self):
        """Test SubStory creation and relationship."""
        user_story_id = "user_story_123"
        sub_story = SubStory(
            user_story_id=user_story_id,
            title="Backend API Implementation",
            description="Implement REST API",
            department="backend",
            technical_requirements=["Req 1", "Req 2"],
            dependencies=["sub_story_456"],
            target_repository="backend",
            estimated_hours=16.5,
        )

        self.assertEqual(sub_story.user_story_id, user_story_id)
        self.assertEqual(sub_story.department, "backend")
        self.assertEqual(sub_story.estimated_hours, 16.5)

        # Test serialization
        story_dict = sub_story.to_dict()
        self.assertEqual(story_dict["story_type"], StoryType.SUB_STORY.value)
        self.assertEqual(story_dict["parent_id"], user_story_id)
        self.assertEqual(story_dict["department"], "backend")

    def test_story_hierarchy_progress(self):
        """Test progress calculation in StoryHierarchy."""
        epic = Epic(title="Test Epic")

        # Create user stories with different statuses
        user_story_1 = UserStory(epic_id=epic.id, title="US 1", status=StoryStatus.DONE)
        user_story_2 = UserStory(
            epic_id=epic.id, title="US 2", status=StoryStatus.IN_PROGRESS
        )

        # Create sub-stories
        sub_story_1 = SubStory(
            user_story_id=user_story_1.id, title="SS 1", status=StoryStatus.DONE
        )
        sub_story_2 = SubStory(
            user_story_id=user_story_1.id, title="SS 2", status=StoryStatus.DONE
        )
        sub_story_3 = SubStory(
            user_story_id=user_story_2.id, title="SS 3", status=StoryStatus.IN_PROGRESS
        )

        hierarchy = StoryHierarchy(
            epic=epic,
            user_stories=[user_story_1, user_story_2],
            sub_stories={
                user_story_1.id: [sub_story_1, sub_story_2],
                user_story_2.id: [sub_story_3],
            },
        )

        # Test epic progress (1 of 2 user stories done = 50%)
        epic_progress = hierarchy.get_epic_progress()
        self.assertEqual(epic_progress["total"], 2)
        self.assertEqual(epic_progress["completed"], 1)
        self.assertEqual(epic_progress["percentage"], 50.0)

        # Test user story 1 progress (2 of 2 sub-stories done = 100%)
        us1_progress = hierarchy.get_user_story_progress(user_story_1.id)
        self.assertEqual(us1_progress["total"], 2)
        self.assertEqual(us1_progress["completed"], 2)
        self.assertEqual(us1_progress["percentage"], 100.0)

        # Test user story 2 progress (0 of 1 sub-stories done = 0%)
        us2_progress = hierarchy.get_user_story_progress(user_story_2.id)
        self.assertEqual(us2_progress["total"], 1)
        self.assertEqual(us2_progress["completed"], 0)
        self.assertEqual(us2_progress["percentage"], 0.0)


class TestDatabaseManager(unittest.TestCase):
    """Test the database manager functionality."""

    def setUp(self):
        """Set up test database."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.db_manager = DatabaseManager(self.temp_file.name)

    def tearDown(self):
        """Clean up test database."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_database_initialization(self):
        """Test database schema creation."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = ["stories", "story_relationships", "github_issues"]
            for table in expected_tables:
                self.assertIn(table, tables)

    def test_save_and_retrieve_epic(self):
        """Test saving and retrieving an epic."""
        epic = Epic(
            title="Test Epic",
            description="Test description",
            business_value="High value",
            acceptance_criteria=["AC1", "AC2"],
            estimated_duration_weeks=3,
        )

        # Save epic
        saved_id = self.db_manager.save_story(epic)
        self.assertEqual(saved_id, epic.id)

        # Retrieve epic
        retrieved_epic = self.db_manager.get_story(epic.id)
        self.assertIsInstance(retrieved_epic, Epic)
        self.assertEqual(retrieved_epic.title, "Test Epic")
        self.assertEqual(retrieved_epic.business_value, "High value")
        self.assertEqual(len(retrieved_epic.acceptance_criteria), 2)
        self.assertEqual(retrieved_epic.estimated_duration_weeks, 3)

    def test_save_and_retrieve_user_story(self):
        """Test saving and retrieving a user story."""
        # First create an epic
        epic = Epic(title="Parent Epic")
        self.db_manager.save_story(epic)

        user_story = UserStory(
            epic_id=epic.id,
            title="Test User Story",
            description="Test description",
            user_persona="Test User",
            user_goal="Test goal",
            story_points=5,
        )

        # Save user story
        saved_id = self.db_manager.save_story(user_story)
        self.assertEqual(saved_id, user_story.id)

        # Retrieve user story
        retrieved_story = self.db_manager.get_story(user_story.id)
        self.assertIsInstance(retrieved_story, UserStory)
        self.assertEqual(retrieved_story.epic_id, epic.id)
        self.assertEqual(retrieved_story.story_points, 5)

    def test_save_and_retrieve_sub_story(self):
        """Test saving and retrieving a sub-story."""
        # Create epic and user story first
        epic = Epic(title="Parent Epic")
        self.db_manager.save_story(epic)

        user_story = UserStory(epic_id=epic.id, title="Parent User Story")
        self.db_manager.save_story(user_story)

        sub_story = SubStory(
            user_story_id=user_story.id,
            title="Test Sub Story",
            description="Test description",
            department="backend",
            technical_requirements=["Req1", "Req2"],
            target_repository="backend",
            estimated_hours=8.5,
        )

        # Save sub-story
        saved_id = self.db_manager.save_story(sub_story)
        self.assertEqual(saved_id, sub_story.id)

        # Retrieve sub-story
        retrieved_story = self.db_manager.get_story(sub_story.id)
        self.assertIsInstance(retrieved_story, SubStory)
        self.assertEqual(retrieved_story.user_story_id, user_story.id)
        self.assertEqual(retrieved_story.department, "backend")
        self.assertEqual(retrieved_story.estimated_hours, 8.5)
        self.assertEqual(len(retrieved_story.technical_requirements), 2)

    def test_epic_hierarchy_retrieval(self):
        """Test retrieving complete epic hierarchy."""
        # Create epic
        epic = Epic(title="Test Epic")
        self.db_manager.save_story(epic)

        # Create user stories
        user_story_1 = UserStory(epic_id=epic.id, title="US 1")
        user_story_2 = UserStory(epic_id=epic.id, title="US 2")
        self.db_manager.save_story(user_story_1)
        self.db_manager.save_story(user_story_2)

        # Create sub-stories
        sub_story_1 = SubStory(user_story_id=user_story_1.id, title="SS 1")
        sub_story_2 = SubStory(user_story_id=user_story_1.id, title="SS 2")
        sub_story_3 = SubStory(user_story_id=user_story_2.id, title="SS 3")
        self.db_manager.save_story(sub_story_1)
        self.db_manager.save_story(sub_story_2)
        self.db_manager.save_story(sub_story_3)

        # Retrieve hierarchy
        hierarchy = self.db_manager.get_epic_hierarchy(epic.id)

        self.assertIsNotNone(hierarchy)
        self.assertEqual(hierarchy.epic.id, epic.id)
        self.assertEqual(len(hierarchy.user_stories), 2)

        # Check sub-stories
        self.assertEqual(len(hierarchy.sub_stories[user_story_1.id]), 2)
        self.assertEqual(len(hierarchy.sub_stories[user_story_2.id]), 1)

    def test_children_stories_retrieval(self):
        """Test retrieving child stories."""
        # Create epic
        epic = Epic(title="Test Epic")
        self.db_manager.save_story(epic)

        # Create user stories
        user_story_1 = UserStory(epic_id=epic.id, title="US 1")
        user_story_2 = UserStory(epic_id=epic.id, title="US 2")
        self.db_manager.save_story(user_story_1)
        self.db_manager.save_story(user_story_2)

        # Get children
        children = self.db_manager.get_children_stories(epic.id, StoryType.USER_STORY)

        self.assertEqual(len(children), 2)
        self.assertIsInstance(children[0], UserStory)
        self.assertIsInstance(children[1], UserStory)

    def test_status_update(self):
        """Test updating story status."""
        epic = Epic(title="Test Epic", status=StoryStatus.DRAFT)
        self.db_manager.save_story(epic)

        # Update status
        result = self.db_manager.update_story_status(epic.id, StoryStatus.IN_PROGRESS)
        self.assertTrue(result)

        # Verify update
        retrieved_epic = self.db_manager.get_story(epic.id)
        self.assertEqual(retrieved_epic.status, StoryStatus.IN_PROGRESS)

    def test_story_relationships(self):
        """Test story relationships functionality."""
        epic = Epic(title="Epic 1")
        user_story = UserStory(epic_id=epic.id, title="US 1")

        self.db_manager.save_story(epic)
        self.db_manager.save_story(user_story)

        # Add relationship
        self.db_manager.add_story_relationship(
            epic.id, user_story.id, "depends_on", {"priority": "high"}
        )

        # Get relationships
        relationships = self.db_manager.get_story_relationships(epic.id)

        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]["relationship_type"], "depends_on")

    def test_github_issue_linking(self):
        """Test GitHub issue linking functionality."""
        epic = Epic(title="Test Epic")
        self.db_manager.save_story(epic)

        # Link GitHub issue
        self.db_manager.link_github_issue(
            epic.id, "test/repo", 123, "https://github.com/test/repo/issues/123"
        )

        # Get linked issues
        issues = self.db_manager.get_github_issues(epic.id)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue_number"], 123)
        self.assertEqual(issues[0]["repository_name"], "test/repo")

    def test_story_deletion_cascade(self):
        """Test that deleting a parent story cascades to children."""
        # Create hierarchy
        epic = Epic(title="Test Epic")
        user_story = UserStory(epic_id=epic.id, title="US 1")
        sub_story = SubStory(user_story_id=user_story.id, title="SS 1")

        self.db_manager.save_story(epic)
        self.db_manager.save_story(user_story)
        self.db_manager.save_story(sub_story)

        # Delete epic (should cascade)
        result = self.db_manager.delete_story(epic.id)
        self.assertTrue(result)

        # Verify cascade deletion
        self.assertIsNone(self.db_manager.get_story(epic.id))
        self.assertIsNone(self.db_manager.get_story(user_story.id))
        self.assertIsNone(self.db_manager.get_story(sub_story.id))


class TestDatabaseIntegration(unittest.TestCase):
    """Integration tests for the complete database system."""

    def setUp(self):
        """Set up test database."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.db_manager = DatabaseManager(self.temp_file.name)

    def tearDown(self):
        """Clean up test database."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_complete_workflow(self):
        """Test complete workflow from epic creation to progress tracking."""
        # 1. Create epic
        epic = Epic(
            title="User Authentication System",
            description="Complete auth system",
            business_value="Enable user accounts",
            estimated_duration_weeks=4,
        )
        self.db_manager.save_story(epic)

        # 2. Create user stories
        user_story_1 = UserStory(
            epic_id=epic.id,
            title="User Registration",
            story_points=5,
            status=StoryStatus.DONE,
        )
        user_story_2 = UserStory(
            epic_id=epic.id,
            title="User Login",
            story_points=3,
            status=StoryStatus.IN_PROGRESS,
        )

        self.db_manager.save_story(user_story_1)
        self.db_manager.save_story(user_story_2)

        # 3. Create sub-stories
        sub_story_1 = SubStory(
            user_story_id=user_story_1.id,
            title="Backend Registration API",
            department="backend",
            status=StoryStatus.DONE,
        )
        sub_story_2 = SubStory(
            user_story_id=user_story_1.id,
            title="Frontend Registration Form",
            department="frontend",
            status=StoryStatus.DONE,
        )
        sub_story_3 = SubStory(
            user_story_id=user_story_2.id,
            title="Login API",
            department="backend",
            status=StoryStatus.IN_PROGRESS,
        )

        self.db_manager.save_story(sub_story_1)
        self.db_manager.save_story(sub_story_2)
        self.db_manager.save_story(sub_story_3)

        # 4. Test hierarchy retrieval and progress
        hierarchy = self.db_manager.get_epic_hierarchy(epic.id)

        self.assertIsNotNone(hierarchy)
        self.assertEqual(len(hierarchy.user_stories), 2)

        # Test progress calculations
        epic_progress = hierarchy.get_epic_progress()
        self.assertEqual(epic_progress["completed"], 1)  # 1 user story done
        self.assertEqual(epic_progress["total"], 2)
        self.assertEqual(epic_progress["percentage"], 50.0)

        us1_progress = hierarchy.get_user_story_progress(user_story_1.id)
        self.assertEqual(us1_progress["percentage"], 100.0)  # All sub-stories done

        us2_progress = hierarchy.get_user_story_progress(user_story_2.id)
        self.assertEqual(us2_progress["percentage"], 0.0)  # Sub-story in progress


if __name__ == "__main__":
    unittest.main(verbosity=2)
