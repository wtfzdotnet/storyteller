"""Integration tests for GitHub storage manager workflow."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from config import Config
from github_storage import GitHubStorageManager, StorageConfig
from models import Epic, UserStory, SubStory, StoryStatus
from story_manager import StoryAnalysis


class TestGitHubStorageIntegration:
    """Integration tests for complete GitHub storage workflows."""

    def setup_method(self):
        """Set up test environment."""
        self.config = Config(
            github_token="test_token",
            github_repository="test/repo",
            storage=StorageConfig(
                primary="github",
                cache_enabled=False,
                deployment_context="pipeline"
            )
        )

    @patch('github_storage.GitHubHandler')
    @pytest.mark.asyncio
    async def test_complete_story_hierarchy_workflow(self, mock_github_handler_class):
        """Test complete workflow: Epic -> User Stories -> Sub-Stories -> Expert Analysis."""
        
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler
        
        # Mock GitHub issues for each story type
        mock_epic_issue = MagicMock()
        mock_epic_issue.number = 100
        mock_epic_issue.repository.full_name = "test/repo"
        
        mock_user_story_issue = MagicMock()
        mock_user_story_issue.number = 101
        mock_user_story_issue.repository.full_name = "test/repo"
        
        mock_sub_story_issue = MagicMock()
        mock_sub_story_issue.number = 102
        mock_sub_story_issue.repository.full_name = "test/repo"
        
        mock_handler.create_issue.side_effect = [
            mock_epic_issue,
            mock_user_story_issue, 
            mock_sub_story_issue
        ]
        
        # Create storage manager
        storage = GitHubStorageManager(self.config)
        
        # 1. Create Epic
        epic = Epic(
            id="epic_001",
            title="User Authentication System",
            description="Implement complete user authentication with OAuth support",
            business_value="Enable secure user access and personalization",
            target_repositories=["backend", "frontend"],
            acceptance_criteria=[
                "Users can register with email/password",
                "OAuth integration with Google/GitHub",
                "Secure session management",
                "Password reset functionality"
            ]
        )
        
        epic_issue = await storage.save_epic(epic)
        assert epic_issue.number == 100
        
        # 2. Create User Story
        user_story = UserStory(
            id="story_001",
            epic_id="epic_001",
            title="OAuth Integration",
            description="As a user, I want to login with my Google account so that I don't need to remember another password",
            user_persona="Busy Professional",
            user_goal="Quick and secure login",
            target_repositories=["backend", "frontend"],
            acceptance_criteria=[
                "Google OAuth button on login page",
                "Successful authentication redirects to dashboard",
                "User profile populated from OAuth data"
            ]
        )
        
        user_story_issue = await storage.save_user_story(user_story)
        assert user_story_issue.number == 101
        
        # 3. Create Sub-Story
        sub_story = SubStory(
            id="substory_001",
            user_story_id="story_001",
            title="Backend OAuth API",
            description="Implement OAuth endpoints and session management",
            department="backend",
            target_repository="backend",
            technical_requirements=[
                "OAuth 2.0 implementation",
                "JWT token management",
                "User session storage"
            ],
            estimated_hours=8.0
        )
        
        sub_story_issue = await storage.save_sub_story(sub_story)
        assert sub_story_issue.number == 102
        
        # 4. Add Expert Analysis
        analysis = StoryAnalysis(
            role_name="security-expert",
            analysis="OAuth implementation looks solid. Need to ensure proper token validation and secure session management.",
            recommendations=[
                "Use industry-standard OAuth libraries",
                "Implement proper CSRF protection",
                "Add rate limiting to auth endpoints"
            ],
            concerns=[
                "Token storage security",
                "Session timeout handling"
            ],
            metadata={
                "security_score": 8,
                "complexity": "medium",
                "estimated_hours": 8
            }
        )
        
        await storage.save_expert_analysis(101, analysis, "test/repo")
        
        # Verify all create_issue calls were made with correct data
        assert mock_handler.create_issue.call_count == 3
        assert mock_handler.add_issue_comment.call_count == 1
        
        # Verify Epic issue creation
        epic_call = mock_handler.create_issue.call_args_list[0][0][0]
        assert epic_call.title == "Epic: User Authentication System"
        assert "epic_id: epic_001" in epic_call.body
        assert "storyteller" in epic_call.labels
        assert "epic" in epic_call.labels
        
        # Verify User Story issue creation  
        user_story_call = mock_handler.create_issue.call_args_list[1][0][0]
        assert user_story_call.title == "User Story: OAuth Integration"
        assert "user_story_id: story_001" in user_story_call.body
        assert "epic_id: epic_001" in user_story_call.body
        assert "user-story" in user_story_call.labels
        
        # Verify Sub-Story issue creation
        sub_story_call = mock_handler.create_issue.call_args_list[2][0][0]
        assert sub_story_call.title == "Sub-Story (backend): Backend OAuth API"
        assert "sub_story_id: substory_001" in sub_story_call.body
        assert "user_story_id: story_001" in sub_story_call.body
        assert "sub-story" in sub_story_call.labels
        assert "department:backend" in sub_story_call.labels
        
        # Verify Expert Analysis comment
        comment_call = mock_handler.add_issue_comment.call_args
        assert comment_call[0][1] == 101  # issue number
        comment_body = comment_call[0][2]
        assert "Expert Analysis: security-expert" in comment_body
        assert "OAuth implementation looks solid" in comment_body
        assert "Use industry-standard OAuth libraries" in comment_body

    @patch('github_storage.GitHubHandler')
    @pytest.mark.asyncio
    async def test_cross_repository_story_creation(self, mock_github_handler_class):
        """Test creating stories across multiple repositories."""
        
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler
        
        # Mock different repository contexts
        mock_backend_issue = MagicMock()
        mock_backend_issue.number = 201
        mock_backend_issue.repository.full_name = "test/backend"
        
        mock_frontend_issue = MagicMock()
        mock_frontend_issue.number = 202
        mock_frontend_issue.repository.full_name = "test/frontend"
        
        mock_handler.create_issue.side_effect = [mock_backend_issue, mock_frontend_issue]
        
        # Create storage manager
        storage = GitHubStorageManager(self.config)
        
        # Create backend sub-story
        backend_story = SubStory(
            id="backend_001",
            user_story_id="story_001",
            title="API Authentication Service",
            description="Backend API for user authentication",
            department="backend",
            target_repository="backend",
            technical_requirements=["JWT implementation", "Database integration"]
        )
        
        # Create frontend sub-story  
        frontend_story = SubStory(
            id="frontend_001", 
            user_story_id="story_001",
            title="Login UI Components",
            description="Frontend login form and OAuth buttons",
            department="frontend",
            target_repository="frontend",
            technical_requirements=["React components", "OAuth client integration"]
        )
        
        # Save to different repositories
        backend_issue = await storage.save_sub_story(backend_story, "test/backend")
        frontend_issue = await storage.save_sub_story(frontend_story, "test/frontend")
        
        # Verify issues created in correct repositories
        assert backend_issue.number == 201
        assert frontend_issue.number == 202
        
        # Verify repository-specific content
        backend_call = mock_handler.create_issue.call_args_list[0][0][0]
        assert "API Authentication Service" in backend_call.title
        assert "department:backend" in backend_call.labels
        
        frontend_call = mock_handler.create_issue.call_args_list[1][0][0]
        assert "Login UI Components" in frontend_call.title
        assert "department:frontend" in frontend_call.labels

    @patch('github_storage.GitHubHandler')
    @pytest.mark.asyncio
    async def test_issue_reconstruction_workflow(self, mock_github_handler_class):
        """Test reconstructing story objects from GitHub issues."""
        
        # Setup mocks
        mock_handler = AsyncMock()
        mock_github_handler_class.return_value = mock_handler
        
        # Create mock issue with frontmatter
        mock_issue = MagicMock()
        mock_issue.number = 300
        mock_issue.title = "Epic: API Modernization"
        mock_issue.body = """---
epic_id: epic_modernization
story_type: epic
status: in_progress
business_value: Improved performance and maintainability
target_repositories:
  - backend
  - infrastructure
acceptance_criteria:
  - RESTful API design
  - OpenAPI documentation
  - 95% test coverage
created_at: '2024-01-01T00:00:00+00:00'
updated_at: '2024-01-02T00:00:00+00:00'
metadata:
  priority: high
  complexity: high
---

# Epic: API Modernization

This epic focuses on modernizing our legacy API infrastructure to improve performance, maintainability, and developer experience.

## Goals
- Implement RESTful design principles
- Add comprehensive documentation
- Improve error handling and validation"""
        mock_issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_issue.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_issue.repository.full_name = "test/backend"
        mock_issue.html_url = "https://github.com/test/backend/issues/300"
        
        # Create storage manager
        storage = GitHubStorageManager(self.config)
        
        # Test parsing Epic from issue
        epic = await storage._parse_epic_from_issue(mock_issue)
        
        # Verify parsed Epic
        assert epic is not None
        assert epic.id == "epic_modernization"
        assert epic.title == "Epic: API Modernization"
        assert epic.status == StoryStatus.IN_PROGRESS
        assert epic.business_value == "Improved performance and maintainability"
        assert epic.target_repositories == ["backend", "infrastructure"]
        assert len(epic.acceptance_criteria) == 3
        assert "RESTful API design" in epic.acceptance_criteria
        assert epic.metadata["github_issue_number"] == 300
        assert epic.metadata["github_repository"] == "test/backend"
        assert epic.metadata["priority"] == "high"


if __name__ == '__main__':
    pytest.main([__file__, "-v"])