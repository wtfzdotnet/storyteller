"""Integration tests for role assignment with story management."""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from config import Config
from story_manager import StoryProcessor
from multi_repo_context import RepositoryContext
from role_analyzer import RoleAssignmentResult, RoleAssignment


class TestRoleAssignmentIntegration(unittest.TestCase):
    """Test integration of role assignment with story management."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config with all required attributes
        self.config = Mock(spec=Config)
        self.config.repositories = {
            "backend": Mock(type="backend", description="Backend API"),
            "frontend": Mock(type="frontend", description="Frontend app")
        }
        self.config.default_repository = "backend"
        self.config.github_token = "fake_token"
        
        # Create story processor with mocked dependencies
        with patch('story_manager.LLMHandler'), \
             patch('story_manager.GitHubHandler'), \
             patch('story_manager.DatabaseManager'), \
             patch('story_manager.load_role_files', return_value={}), \
             patch('story_manager.MultiRepositoryContextReader'):
            self.processor = StoryProcessor(self.config)
    
    def test_assign_roles_intelligently_basic(self):
        """Test basic intelligent role assignment."""
        async def run_test():
            # Mock the context reader to return empty contexts
            mock_context = RepositoryContext(
                repository="backend",
                repo_type="backend",
                description="Backend API",
                languages={"python": 10},
                key_files=[]
            )
            
            self.processor.context_reader.get_repository_context = AsyncMock(return_value=mock_context)
            result = await self.processor.assign_roles_intelligently(
                story_content="Implement secure API authentication",
                target_repositories=["backend"]
            )
            
            # Check result structure
            self.assertIn("story_id", result)
            self.assertIn("recommended_roles", result)
            self.assertIn("primary_roles", result)
            self.assertIn("assignment_details", result)
            
            # Check that appropriate roles were assigned
            recommended_roles = result["recommended_roles"]
            self.assertIn("product-owner", recommended_roles)  # Default role
            self.assertIn("system-architect", recommended_roles)  # Default role
            
            # Security expert should be assigned due to "secure" keyword
            self.assertIn("security-expert", recommended_roles)
        
        # Run the async test
        asyncio.run(run_test())
    
    def test_assign_roles_with_manual_overrides(self):
        """Test role assignment with manual overrides."""
        async def run_test():
            mock_context = RepositoryContext(
                repository="frontend",
                repo_type="frontend", 
                description="Frontend app",
                languages={"javascript": 8},
                key_files=[]
            )
            
            self.processor.context_reader.get_repository_context = AsyncMock(return_value=mock_context)
            result = await self.processor.assign_roles_intelligently(
                story_content="Update the user interface",
                target_repositories=["frontend"],
                manual_role_overrides=["qa-engineer", "devops-engineer"]
            )
            
            # Manual overrides should be in primary roles
            self.assertIn("qa-engineer", result["primary_roles"])
            self.assertIn("devops-engineer", result["primary_roles"])
            
            # Check assignment details
            assignment_details = result["assignment_details"]
            self.assertIsInstance(assignment_details, RoleAssignmentResult)
            
            # Find manual assignments
            manual_assignments = [r for r in assignment_details.primary_roles 
                                if r.assigned_by == "manual"]
            self.assertEqual(len(manual_assignments), 2)
            
            for assignment in manual_assignments:
                self.assertEqual(assignment.confidence_score, 1.0)
                self.assertEqual(assignment.assignment_reason, "Manual override")
        
        asyncio.run(run_test())
    
    def test_assign_roles_context_failure_fallback(self):
        """Test fallback when repository context cannot be retrieved."""
        async def run_test():
            # Mock context reader to raise an exception
            self.processor.context_reader.get_repository_context = AsyncMock(
                side_effect=Exception("Context retrieval failed"))
            result = await self.processor.assign_roles_intelligently(
                story_content="Basic story content",
                target_repositories=["backend"]
            )
            
            # Should still work with minimal context from config
            self.assertIn("story_id", result)
            self.assertIn("recommended_roles", result)
            
            # Default roles should still be assigned
            self.assertIn("product-owner", result["recommended_roles"])
            self.assertIn("system-architect", result["recommended_roles"])
        
        asyncio.run(run_test())
    
    def test_assign_roles_no_target_repositories(self):
        """Test role assignment when no target repositories specified."""
        async def run_test():
            result = await self.processor.assign_roles_intelligently(
                story_content="Generic story content without specific targets"
            )
            
            # Should work with all configured repositories
            self.assertIn("story_id", result)
            self.assertIn("recommended_roles", result)
            self.assertIn("target_repositories", result)
            
            # Should have created contexts for all configured repositories
            expected_repos = set(self.config.repositories.keys())
            actual_repos = set(result["target_repositories"])
            self.assertEqual(expected_repos, actual_repos)
        
        asyncio.run(run_test())
    
    def test_role_assignment_with_multiple_repositories(self):
        """Test role assignment with multiple repository contexts."""
        async def run_test():
            # Mock contexts for multiple repositories
            backend_context = RepositoryContext(
                repository="backend",
                repo_type="backend",
                description="Backend API",
                languages={"python": 15},
                key_files=[]
            )
            
            frontend_context = RepositoryContext(
                repository="frontend", 
                repo_type="frontend",
                description="Frontend app",
                languages={"javascript": 12, "typescript": 5},
                key_files=[]
            )
            
            def mock_get_context(repo_name):
                if repo_name == "backend":
                    return backend_context
                elif repo_name == "frontend":
                    return frontend_context
                else:
                    raise ValueError(f"Unknown repo: {repo_name}")
            
            self.processor.context_reader.get_repository_context = AsyncMock(side_effect=mock_get_context)
            result = await self.processor.assign_roles_intelligently(
                story_content="Implement full-stack user authentication with UI and API",
                target_repositories=["backend", "frontend"]
            )
            
            # Should get roles appropriate for both backend and frontend
            recommended_roles = result["recommended_roles"]
            
            # Backend roles
            self.assertIn("system-architect", recommended_roles)
            self.assertIn("lead-developer", recommended_roles)
            
            # Frontend roles  
            self.assertIn("ux-ui-designer", recommended_roles)
            
            # Security expert due to "authentication" keyword
            self.assertIn("security-expert", recommended_roles)
            
            # Check metadata includes both repositories
            assignment_details = result["assignment_details"]
            self.assertEqual(set(assignment_details.assignment_metadata["repositories"]),
                           {"backend", "frontend"})
            self.assertEqual(set(assignment_details.assignment_metadata["repository_types"]),
                           {"backend", "frontend"})
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()