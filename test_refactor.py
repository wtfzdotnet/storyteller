#!/usr/bin/env python3
"""
Test script for refactor functionality without requiring GitHub connectivity.
"""

import asyncio
import unittest
from unittest.mock import Mock, patch
from story_manager import StoryOrchestrator, UserStory
from config import Config


class TestRefactorMode(unittest.TestCase):
    def setUp(self):
        # Mock services to avoid network calls
        self.mock_llm_service = Mock()
        self.mock_github_service = Mock()
        self.mock_config = Mock(spec=Config)
        
        # Configure mock config for multi-repository mode
        self.mock_config.is_multi_repository_mode.return_value = True
        self.mock_config.get_repository_list.return_value = ['backend', 'frontend']
        
        # Mock repository configs
        backend_config = Mock()
        backend_config.name = "test/backend"
        backend_config.type = "backend"
        backend_config.description = "Backend API and services"
        backend_config.story_labels = ["backend", "api"]
        
        frontend_config = Mock()
        frontend_config.name = "test/frontend"
        frontend_config.type = "frontend"
        frontend_config.description = "Frontend UI application"
        frontend_config.story_labels = ["frontend", "ui"]
        
        self.mock_config.multi_repository_config.get_repository.side_effect = lambda key: {
            'backend': backend_config,
            'frontend': frontend_config
        }.get(key)
        
        self.orchestrator = StoryOrchestrator(
            self.mock_llm_service, 
            self.mock_github_service, 
            self.mock_config
        )

    def test_get_refactor_roles(self):
        """Test that appropriate roles are returned for different refactor types."""
        # Test extract refactor
        roles = self.orchestrator._get_refactor_roles("extract")
        self.assertEqual(roles, ["Senior Developer", "Software Architect", "Code Reviewer"])
        
        # Test optimize refactor
        roles = self.orchestrator._get_refactor_roles("optimize")
        self.assertEqual(roles, ["Performance Engineer", "Senior Developer", "DevOps Engineer"])
        
        # Test unknown refactor type defaults to general
        roles = self.orchestrator._get_refactor_roles("unknown")
        self.assertEqual(roles, ["Senior Developer", "Tech Lead", "Code Reviewer"])

    def test_get_default_file_patterns(self):
        """Test default file patterns for different refactor types and repositories."""
        # Test extract patterns for backend
        patterns = self.orchestrator._get_default_file_patterns("extract", "backend")
        self.assertEqual(patterns, ["**/*.py", "**/*.sql", "**/*.yml", "**/*.json"])
        
        # Test extract patterns for frontend
        patterns = self.orchestrator._get_default_file_patterns("extract", "frontend")
        self.assertEqual(patterns, ["**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx", "**/*.css", "**/*.scss"])
        
        # Test optimize patterns for general repository
        patterns = self.orchestrator._get_default_file_patterns("optimize", None)
        self.assertEqual(patterns, ["**/*.py", "**/*.js", "**/*.ts", "**/*.sql"])

    def test_create_refactor_prompt(self):
        """Test refactor prompt creation with context."""
        refactor_request = "Extract authentication logic into a service"
        refactor_type = "extract"
        repo_key = "backend"
        relevant_files = ["auth/models.py", "auth/views.py", "auth/utils.py"]
        
        prompt = self.orchestrator._create_refactor_prompt(
            refactor_request, refactor_type, repo_key, relevant_files
        )
        
        # Check that key elements are in the prompt
        self.assertIn("Extract authentication logic into a service", prompt)
        self.assertIn("Refactor Type: Extract", prompt)
        self.assertIn("auth/models.py", prompt)
        self.assertIn("Acceptance Criteria", prompt)
        self.assertIn("Code is refactored according to the specified requirements", prompt)

    async def test_discover_relevant_files_with_ai_async(self):
        """Test file discovery using AI suggestions."""
        # Mock AI response as a coroutine
        ai_response = "auth/models.py\nauth/views.py\nauth/services.py\ntests/test_auth.py"
        async def mock_query(*args, **kwargs):
            return ai_response
        self.mock_llm_service.query_llm = mock_query
        
        files = await self.orchestrator._discover_relevant_files(
            "Extract authentication logic", "extract", "backend", None
        )
        
        expected_files = ["auth/models.py", "auth/views.py", "auth/services.py", "tests/test_auth.py"]
        self.assertEqual(files, expected_files)

    async def test_discover_relevant_files_with_specific_files_async(self):
        """Test file discovery when specific files are provided."""
        specific_files = ["custom/auth.py", "custom/models.py"]
        
        files = await self.orchestrator._discover_relevant_files(
            "Extract authentication logic", "extract", "backend", specific_files
        )
        
        # Should return provided files without calling AI
        self.assertEqual(files, specific_files)
        self.mock_llm_service.query_llm.assert_not_called()

    async def test_discover_relevant_files_fallback_async(self):
        """Test file discovery fallback when AI fails."""
        # Mock AI failure
        async def mock_query_fail(*args, **kwargs):
            raise Exception("AI service unavailable")
        self.mock_llm_service.query_llm = mock_query_fail
        
        files = await self.orchestrator._discover_relevant_files(
            "Extract authentication logic", "extract", "backend", None
        )
        
        # Should fallback to default patterns
        expected_files = ["**/*.py", "**/*.sql", "**/*.yml", "**/*.json"]
        self.assertEqual(files, expected_files)


async def run_async_tests():
    """Run async test methods"""
    test = TestRefactorMode()
    test.setUp()
    
    print("Testing file discovery with AI...")
    await test.test_discover_relevant_files_with_ai_async()
    print("✓ File discovery with AI works")
    
    print("Testing file discovery with specific files...")
    await test.test_discover_relevant_files_with_specific_files_async()
    print("✓ File discovery with specific files works")
    
    print("Testing file discovery fallback...")
    await test.test_discover_relevant_files_fallback_async()
    print("✓ File discovery fallback works")


def main():
    print("Running refactor mode tests...")
    
    # Run synchronous tests
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestRefactorMode)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Run async tests
    print("\nRunning async tests...")
    asyncio.run(run_async_tests())
    
    if result.wasSuccessful():
        print("\n✅ All refactor mode tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())