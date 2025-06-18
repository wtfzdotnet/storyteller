"""
Demo script for GitHub Projects API integration.

This script demonstrates how to use the new GitHub Projects functionality
with the Storyteller system.
"""

import asyncio
import os
from config import Config
from github_handler import GitHubHandler
from models import ProjectData, Epic, UserStory, StoryStatus


async def demo_github_projects():
    """Demonstrate GitHub Projects integration."""
    
    print("🚀 GitHub Projects API Integration Demo")
    print("=" * 50)
    
    # Note: This is a demo script - actual GitHub token would be needed for live testing
    config = Config(github_token="demo_token")
    github_handler = GitHubHandler(config)
    
    # 1. Create a new project
    print("\n1. Creating a new GitHub Project...")
    project_data = ProjectData(
        title="Epic: User Authentication System",
        description="Project board for managing user authentication epic and its user stories",
        organization_login="myorg"  # or use repository_name for repo-level project
    )
    
    print(f"   Project Title: {project_data.title}")
    print(f"   Description: {project_data.description}")
    print("   ✓ Project data prepared")
    
    # 2. Demonstrate issue-to-project synchronization
    print("\n2. Synchronizing issues with project board...")
    
    # Simulate some issues that would be created from stories
    issue_list = [
        (1, "backend-repo"),  # Epic issue
        (2, "backend-repo"),  # User story: Login API
        (3, "frontend-repo"), # User story: Login UI
        (4, "backend-repo"),  # Sub-story: Password validation
        (5, "frontend-repo")  # Sub-story: Login form
    ]
    
    print(f"   Issues to sync: {len(issue_list)}")
    for issue_num, repo in issue_list:
        print(f"   - Issue #{issue_num} from {repo}")
    
    # 3. Demonstrate custom field mapping
    print("\n3. Custom field mapping configuration...")
    
    field_mappings = {
        "status": "PVTF_status_field_id",
        "priority": "PVTF_priority_field_id", 
        "story_points": "PVTF_points_field_id",
        "department": "PVTF_department_field_id"
    }
    
    print("   Field mappings:")
    for story_field, project_field in field_mappings.items():
        print(f"   - {story_field} → {project_field}")
    
    # 4. Show how story hierarchy would be synced
    print("\n4. Story hierarchy synchronization...")
    
    # Create sample epic and user stories to demonstrate sync
    epic = Epic(
        title="User Authentication System",
        description="Implement comprehensive user authentication",
        business_value="Enable secure user access to the platform",
        target_repositories=["backend-repo", "frontend-repo"]
    )
    
    user_story_1 = UserStory(
        epic_id=epic.id,
        title="User can log in with email and password",
        description="As a user, I want to log in with my email and password",
        user_persona="Registered User",
        user_goal="Access my account securely",
        target_repositories=["backend-repo", "frontend-repo"],
        story_points=5
    )
    
    user_story_2 = UserStory(
        epic_id=epic.id,
        title="User can reset forgotten password",
        description="As a user, I want to reset my password if I forget it",
        user_persona="Registered User", 
        user_goal="Regain access to my account",
        target_repositories=["backend-repo", "frontend-repo"],
        story_points=3
    )
    
    print(f"   Epic: {epic.title}")
    print(f"   User Stories: {len([user_story_1, user_story_2])}")
    print(f"   - {user_story_1.title} ({user_story_1.story_points} points)")
    print(f"   - {user_story_2.title} ({user_story_2.story_points} points)")
    
    # 5. Demonstrate bulk operations
    print("\n5. Bulk operations capability...")
    
    bulk_issues = [
        (10, "backend-repo"),
        (11, "frontend-repo"),
        (12, "testing-repo"),
        (13, "docs-repo")
    ]
    
    print(f"   Bulk adding {len(bulk_issues)} issues to project")
    print("   This allows efficient management of large story sets")
    
    # 6. Show project management workflow
    print("\n6. Project management workflow...")
    
    workflow_steps = [
        "Create GitHub Project for Epic",
        "Generate issues from story hierarchy", 
        "Add all issues to project board",
        "Set up custom fields (Status, Priority, Story Points)",
        "Map story metadata to project fields",
        "Synchronize status updates between issues and stories",
        "Track epic progress through project board"
    ]
    
    print("   Complete workflow:")
    for i, step in enumerate(workflow_steps, 1):
        print(f"   {i}. {step}")
    
    print("\n7. API Methods Available...")
    
    api_methods = [
        "create_project() - Create new GitHub Project",
        "add_issue_to_project() - Add single issue to project", 
        "bulk_add_issues_to_project() - Add multiple issues efficiently",
        "update_project_item_field() - Update custom field values",
        "get_project_fields() - Retrieve project's custom fields",
        "sync_story_to_project() - Sync entire story hierarchy",
        "create_project_for_epic() - Create project specifically for epic"
    ]
    
    print("   New GitHub Projects methods:")
    for method in api_methods:
        print(f"   - {method}")
    
    print("\n" + "=" * 50)
    print("✅ GitHub Projects API integration is ready!")
    print("\nKey Benefits:")
    print("- Automatic project board creation for epics")
    print("- Seamless issue-to-project synchronization") 
    print("- Custom field mapping for story metadata")
    print("- Bulk operations for efficient management")
    print("- Full story hierarchy support")
    print("\nNext steps:")
    print("- Configure GitHub token for your organization")
    print("- Set up project templates for consistent boards")
    print("- Configure custom field mappings in .storyteller/config.json")
    print("- Integrate with existing story creation workflow")


if __name__ == "__main__":
    asyncio.run(demo_github_projects())