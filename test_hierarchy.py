"""Test the hierarchical story data model."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.base import get_db_session, init_database
from database.repository import StoryRepository
from database.models import Epic, Story, SubStory


def test_hierarchical_model():
    """Test the hierarchical story model functionality."""
    print("Testing hierarchical story data model...")
    
    # Initialize database (creates tables if needed)
    init_database()
    
    # Get database session
    db_gen = get_db_session()
    db = next(db_gen)
    repo = StoryRepository(db)
    
    try:
        # Create an epic
        epic = repo.create_epic(
            title="User Authentication System",
            description="Implement comprehensive user authentication with security features",
            story_id="epic_auth_001",
            status="planning",
            priority="high",
            labels=["security", "authentication", "backend"],
            github_repository="backend"
        )
        print(f"✓ Created Epic: {epic.title} (ID: {epic.id})")
        
        # Create stories under the epic
        story1 = repo.create_story(
            title="User Registration Flow",
            description="As a user, I want to register for an account",
            story_id="story_reg_001",
            epic_id=epic.id,
            status="backlog",
            priority="high",
            story_points=8,
            original_content="Implement user registration with email verification",
            target_repositories=["backend", "frontend"],
            labels=["registration", "email"]
        )
        print(f"✓ Created Story: {story1.title} (ID: {story1.id})")
        
        story2 = repo.create_story(
            title="User Login Flow",
            description="As a user, I want to login to my account",
            story_id="story_login_001",
            epic_id=epic.id,
            status="backlog",
            priority="medium",
            story_points=5,
            original_content="Implement secure login with password validation",
            target_repositories=["backend", "frontend"],
            labels=["login", "security"]
        )
        print(f"✓ Created Story: {story2.title} (ID: {story2.id})")
        
        # Create sub-stories under story1
        sub_story1 = repo.create_sub_story(
            title="Email Validation API",
            description="Create API endpoint for email validation",
            story_id="substory_email_001",
            parent_story_id=story1.id,
            status="open",
            priority="high",
            story_points=3,
            acceptance_criteria=[
                "API validates email format",
                "API checks for existing emails",
                "Returns appropriate error messages"
            ],
            technical_requirements="FastAPI endpoint with Pydantic validation",
            estimated_hours=8,
            assigned_role="lead-developer"
        )
        print(f"✓ Created Sub-story: {sub_story1.title} (ID: {sub_story1.id})")
        
        sub_story2 = repo.create_sub_story(
            title="Registration Form UI",
            description="Create user registration form interface",
            story_id="substory_regform_001",
            parent_story_id=story1.id,
            status="open",
            priority="medium",
            story_points=5,
            acceptance_criteria=[
                "Form has all required fields",
                "Real-time validation feedback",
                "Responsive design"
            ],
            technical_requirements="React form with validation",
            estimated_hours=12,
            assigned_role="ux-ui-designer"
        )
        print(f"✓ Created Sub-story: {sub_story2.title} (ID: {sub_story2.id})")
        
        # Test hierarchy queries
        print("\n--- Testing Hierarchy Queries ---")
        
        # Get complete hierarchy
        full_epic = repo.get_full_hierarchy(epic.id)
        print(f"Epic '{full_epic.title}' has {len(full_epic.stories)} stories")
        for story in full_epic.stories:
            print(f"  Story '{story.title}' has {len(story.sub_stories)} sub-stories")
            for sub_story in story.sub_stories:
                print(f"    Sub-story: '{sub_story.title}'")
        
        # Test statistics
        stats = repo.get_hierarchy_stats()
        print(f"\nHierarchy Statistics:")
        print(f"  Epics: {stats['epics']}")
        print(f"  Stories: {stats['stories']}")
        print(f"  Sub-stories: {stats['sub_stories']}")
        print(f"  Total items: {stats['total_items']}")
        
        # Test search
        search_results = repo.search_by_title("user")
        print(f"\nSearch results for 'user':")
        print(f"  Epics: {len(search_results['epics'])}")
        print(f"  Stories: {len(search_results['stories'])}")
        print(f"  Sub-stories: {len(search_results['sub_stories'])}")
        
        # Test status updates
        repo.update_status("story", story1.id, "in_progress")
        updated_story = repo.get_story(story1.id)
        print(f"\n✓ Updated story status to: {updated_story.status}")
        
        print("\n✅ All hierarchical model tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_hierarchical_model()
    if not success:
        sys.exit(1)