"""Test integration of hierarchical models with existing story manager."""

import os
import tempfile
from pathlib import Path

# Setup paths for imports
import setup_path

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"

from models import StoryStatus  # noqa: E402
from story_manager import StoryManager  # noqa: E402


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

        print(f"✓ Created epic: {epic.title} (ID: {epic.id})")

        # Test creating user story
        user_story = story_manager.create_user_story(
            epic_id=epic.id,
            title="Test User Story",
            description="As a tester, I want to verify integration",
            user_persona="Tester",
            user_goal="Verify system works",
            story_points=3,
        )

        print(f"✓ Created user story: {user_story.title} (ID: {user_story.id})")

        # Test creating sub-story
        sub_story = story_manager.create_sub_story(
            user_story_id=user_story.id,
            title="Integration Test Implementation",
            description="Write tests to verify integration",
            department="testing",
            target_repository="storyteller",
            estimated_hours=4.0,
        )

        print(f"✓ Created sub-story: {sub_story.title} (ID: {sub_story.id})")

        # Test retrieving hierarchy
        hierarchy = story_manager.get_epic_hierarchy(epic.id)
        assert hierarchy is not None
        assert hierarchy.epic.id == epic.id
        assert len(hierarchy.user_stories) == 1
        assert hierarchy.user_stories[0].id == user_story.id
        assert len(hierarchy.sub_stories[user_story.id]) == 1
        assert hierarchy.sub_stories[user_story.id][0].id == sub_story.id

        print("✓ Retrieved complete hierarchy successfully")

        # Test progress calculation
        epic_progress = hierarchy.get_epic_progress()
        assert epic_progress["total"] == 1
        assert epic_progress["completed"] == 0  # Nothing done yet
        assert epic_progress["percentage"] == 0.0

        print(f"✓ Epic progress: {epic_progress}")

        # Test status update
        success = story_manager.update_story_status(sub_story.id, StoryStatus.DONE)
        assert success

        # Re-retrieve and check progress
        updated_hierarchy = story_manager.get_epic_hierarchy(epic.id)
        us_progress = updated_hierarchy.get_user_story_progress(user_story.id)
        assert us_progress["completed"] == 1
        assert us_progress["percentage"] == 100.0

        print(f"✓ Updated status and progress: {us_progress}")

        # Test story retrieval
        retrieved_epic = story_manager.get_story(epic.id)
        assert retrieved_epic.title == "Test Epic"
        assert retrieved_epic.business_value == "High test value"

        print("✓ Story retrieval works")

        # Test get all epics
        all_epics = story_manager.get_all_epics()
        assert len(all_epics) == 1
        assert all_epics[0].id == epic.id

        print("✓ Get all epics works")

        print("\n🎉 All integration tests passed!")

    finally:
        # Clean up
        Path(temp_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    test_hierarchical_integration()
