"""Test integration of hierarchical models with existing story manager."""

import tempfile
from pathlib import Path

from models import StoryStatus
from story_manager import StoryManager


def test_hierarchical_integration():
    """Test that StoryManager works with hierarchical models."""

    # Use temporary database for testing
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()

    try:
        # Initialize StoryManager with temporary database
        story_manager = StoryManager()
        story_manager.database.db_path = Path(temp_file.name)
        story_manager.database.init_database()

        # Test creating an epic
        epic = story_manager.create_epic(
            title="Test Epic",
            description="Test epic for integration",
            business_value="High test value",
            estimated_duration_weeks=2,
        )

        assert epic.title == "Test Epic"
        assert epic.id is not None

        # Test creating user story
        user_story = story_manager.create_user_story(
            epic_id=epic.id,
            title="Test User Story",
            description="As a tester, I want to verify integration",
            user_persona="Tester",
            user_goal="Verify system works",
            story_points=3,
        )

        assert user_story.title == "Test User Story"
        assert user_story.epic_id == epic.id

        # Test creating sub-story
        sub_story = story_manager.create_sub_story(
            user_story_id=user_story.id,
            title="Integration Test Implementation",
            description="Write tests to verify integration",
            department="testing",
            target_repository="storyteller",
            estimated_hours=4.0,
        )

        assert sub_story.title == "Integration Test Implementation"
        assert sub_story.user_story_id == user_story.id

        # Test retrieving hierarchy
        hierarchy = story_manager.get_epic_hierarchy(epic.id)
        assert hierarchy is not None
        assert hierarchy.epic.id == epic.id
        assert len(hierarchy.user_stories) == 1
        assert hierarchy.user_stories[0].id == user_story.id
        assert len(hierarchy.sub_stories[user_story.id]) == 1
        assert hierarchy.sub_stories[user_story.id][0].id == sub_story.id

        # Test progress calculation
        epic_progress = hierarchy.get_epic_progress()
        assert epic_progress["total"] == 1
        assert epic_progress["completed"] == 0  # Nothing done yet
        assert epic_progress["percentage"] == 0.0

        # Test status update
        success = story_manager.update_story_status(sub_story.id, StoryStatus.DONE)
        assert success

        # Re-retrieve and check progress
        updated_hierarchy = story_manager.get_epic_hierarchy(epic.id)
        us_progress = updated_hierarchy.get_user_story_progress(user_story.id)
        assert us_progress["completed"] == 1
        assert us_progress["percentage"] == 100.0

        # Test story retrieval
        retrieved_epic = story_manager.get_story(epic.id)
        assert retrieved_epic.title == "Test Epic"
        assert retrieved_epic.business_value == "High test value"

        # Test get all epics
        all_epics = story_manager.get_all_epics()
        assert len(all_epics) == 1
        assert all_epics[0].id == epic.id

    finally:
        # Clean up
        Path(temp_file.name).unlink(missing_ok=True)


def test_story_manager_database_operations():
    """Test StoryManager database operations."""
    
    # Use temporary database for testing
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()

    try:
        story_manager = StoryManager()
        story_manager.database.db_path = Path(temp_file.name)
        story_manager.database.init_database()

        # Test epic creation with validation
        epic = story_manager.create_epic(
            title="Database Test Epic",
            description="Testing database operations",
            business_value="Ensure data persistence",
            estimated_duration_weeks=1,
        )

        # Verify epic was saved to database
        retrieved_epic = story_manager.get_story(epic.id)
        assert retrieved_epic is not None
        assert retrieved_epic.title == "Database Test Epic"
        
        # Test epic listing
        epics = story_manager.get_all_epics()
        assert len(epics) == 1
        assert epics[0].id == epic.id

        # Test epic update
        success = story_manager.update_story_status(epic.id, StoryStatus.IN_PROGRESS)
        assert success
        
        updated_epic = story_manager.get_story(epic.id)
        assert updated_epic.status == StoryStatus.IN_PROGRESS

    finally:
        # Clean up
        Path(temp_file.name).unlink(missing_ok=True)


def test_story_manager_github_integration():
    """Test StoryManager GitHub integration capabilities."""
    
    # Use temporary database for testing
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()

    try:
        story_manager = StoryManager()
        story_manager.database.db_path = Path(temp_file.name)
        story_manager.database.init_database()

        # Create test epic
        epic = story_manager.create_epic(
            title="GitHub Integration Epic",
            description="Testing GitHub integration features",
            business_value="Enable GitHub workflow",
            target_repositories=["storyteller"],
            estimated_duration_weeks=2,
        )

        # Test that epic was created with GitHub-compatible data
        assert epic.target_repositories == ["storyteller"]
        assert epic.id is not None
        
        # Test retrieving epic with GitHub data
        retrieved_epic = story_manager.get_story(epic.id)
        assert retrieved_epic.target_repositories == ["storyteller"]

    finally:
        # Clean up
        Path(temp_file.name).unlink(missing_ok=True)