#!/usr/bin/env python3
"""Migration script for setting up hierarchical story management database."""

import argparse
import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager, run_migrations
from models import Epic, StoryStatus, SubStory, UserStory


def create_sample_data(db_manager: DatabaseManager):
    """Create sample data to demonstrate the hierarchical structure."""
    print("\nCreating sample data...")

    # Create a sample epic
    epic = Epic(
        title="User Authentication System",
        description="Implement a comprehensive user authentication system with OAuth support",
        business_value="Enable user accounts and personalized experiences across the platform",
        acceptance_criteria=[
            "Users can register with email and password",
            "Users can login with OAuth providers (Google, GitHub)",
            "User sessions are secure and properly managed",
            "Password reset functionality is available",
        ],
        target_repositories=["backend", "frontend"],
        estimated_duration_weeks=4,
    )

    epic_id = db_manager.save_story(epic)
    print(f"✓ Created epic: {epic.title} (ID: {epic_id})")

    # Create user stories for the epic
    user_stories = [
        UserStory(
            epic_id=epic_id,
            title="User Registration",
            description="As a new user, I want to create an account so that I can access personalized features",
            user_persona="New User",
            user_goal="Create an account to access the platform",
            acceptance_criteria=[
                "User can enter email and password",
                "Email validation is performed",
                "Password strength requirements are enforced",
                "Confirmation email is sent",
            ],
            target_repositories=["backend", "frontend"],
            story_points=5,
        ),
        UserStory(
            epic_id=epic_id,
            title="OAuth Login",
            description="As a user, I want to login with my Google or GitHub account for convenience",
            user_persona="Existing User",
            user_goal="Quick and secure login without remembering passwords",
            acceptance_criteria=[
                "Google OAuth integration works",
                "GitHub OAuth integration works",
                "User profile is created from OAuth data",
                "Existing accounts can be linked",
            ],
            target_repositories=["backend", "frontend"],
            story_points=8,
        ),
    ]

    user_story_ids = []
    for user_story in user_stories:
        story_id = db_manager.save_story(user_story)
        user_story_ids.append(story_id)
        print(f"✓ Created user story: {user_story.title} (ID: {story_id})")

    # Create sub-stories for the first user story
    sub_stories = [
        SubStory(
            user_story_id=user_story_ids[0],
            title="Backend API for User Registration",
            description="Implement REST API endpoints for user registration",
            department="backend",
            technical_requirements=[
                "Create User model with validations",
                "Implement registration endpoint",
                "Add email verification system",
                "Set up password hashing",
            ],
            target_repository="backend",
            estimated_hours=16,
        ),
        SubStory(
            user_story_id=user_story_ids[0],
            title="Frontend Registration Form",
            description="Create user interface for registration",
            department="frontend",
            technical_requirements=[
                "Design registration form UI",
                "Add form validation",
                "Integrate with backend API",
                "Add loading and error states",
            ],
            dependencies=[],
            target_repository="frontend",
            estimated_hours=12,
        ),
    ]

    for sub_story in sub_stories:
        story_id = db_manager.save_story(sub_story)
        print(f"✓ Created sub-story: {sub_story.title} (ID: {story_id})")

    print(f"\nSample data created successfully!")

    # Demonstrate hierarchy retrieval
    hierarchy = db_manager.get_epic_hierarchy(epic_id)
    if hierarchy:
        epic_progress = hierarchy.get_epic_progress()
        print(
            f"\nEpic Progress: {epic_progress['completed']}/{epic_progress['total']} user stories completed ({epic_progress['percentage']}%)"
        )

        for us in hierarchy.user_stories:
            us_progress = hierarchy.get_user_story_progress(us.id)
            print(
                f"  User Story '{us.title}': {us_progress['completed']}/{us_progress['total']} sub-stories completed ({us_progress['percentage']}%)"
            )


def main():
    """Main migration script entry point."""
    parser = argparse.ArgumentParser(description="Storyteller Database Migration")
    parser.add_argument(
        "--db-path",
        default="storyteller.db",
        help="Path to the SQLite database file (default: storyteller.db)",
    )
    parser.add_argument(
        "--sample-data", action="store_true", help="Create sample data after migration"
    )
    parser.add_argument(
        "--reset", action="store_true", help="Reset database by removing existing file"
    )

    args = parser.parse_args()

    # Remove existing database if reset requested
    if args.reset:
        db_path = Path(args.db_path)
        if db_path.exists():
            db_path.unlink()
            print(f"✓ Removed existing database: {db_path}")

    try:
        # Run migrations
        db_manager = run_migrations(args.db_path)

        # Create sample data if requested
        if args.sample_data:
            create_sample_data(db_manager)

        print(f"\n🎉 Migration completed successfully!")
        print(f"Database created at: {Path(args.db_path).absolute()}")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
