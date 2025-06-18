"""Tests for intelligent role assignment functionality."""

import unittest
from unittest.mock import Mock

from config import Config
from multi_repo_context import FileContext, RepositoryContext
from role_analyzer import RoleAssignmentEngine, RoleAssignmentResult


class TestRoleAssignmentEngine(unittest.TestCase):
    """Test the RoleAssignmentEngine class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock(spec=Config)
        self.engine = RoleAssignmentEngine(self.config)

    def test_assign_roles_with_frontend_repository(self):
        """Test role assignment for frontend repository context."""
        # Create frontend repository context
        repo_context = RepositoryContext(
            repository="test-frontend",
            repo_type="frontend",
            description="React frontend application",
            languages={"javascript": 10, "typescript": 5},
            key_files=[
                FileContext(
                    repository="test-frontend",
                    path="package.json",
                    content='{"dependencies": {"react": "^17.0.0"}}',
                    file_type="json",
                )
            ],
        )

        story_content = "As a user, I want a responsive user interface design for the recipe search page"

        result = self.engine.assign_roles(
            story_content=story_content,
            repository_contexts=[repo_context],
            story_id="test-story-1",
        )

        # Check that we get expected roles
        self.assertIsInstance(result, RoleAssignmentResult)
        self.assertEqual(result.story_id, "test-story-1")

        # Check that UX/UI designer is assigned due to frontend + UI keywords
        role_names = [
            r.role_name for r in result.primary_roles + result.secondary_roles
        ]
        self.assertIn("ux-ui-designer", role_names)
        self.assertIn("product-owner", role_names)  # Default role
        self.assertIn("system-architect", role_names)  # Default role

    def test_assign_roles_with_backend_repository(self):
        """Test role assignment for backend repository context."""
        repo_context = RepositoryContext(
            repository="test-backend",
            repo_type="backend",
            description="Python API backend",
            languages={"python": 15},
            key_files=[
                FileContext(
                    repository="test-backend",
                    path="requirements.txt",
                    content="fastapi\npsycopg2",
                    file_type="text",
                )
            ],
        )

        story_content = (
            "Implement secure API authentication with PostgreSQL database integration"
        )

        result = self.engine.assign_roles(
            story_content=story_content,
            repository_contexts=[repo_context],
            story_id="test-story-2",
        )

        role_names = [
            r.role_name for r in result.primary_roles + result.secondary_roles
        ]
        self.assertIn("system-architect", role_names)
        self.assertIn("lead-developer", role_names)
        self.assertIn("security-expert", role_names)  # Due to "secure" keyword

    def test_assign_roles_with_manual_overrides(self):
        """Test role assignment with manual overrides."""
        repo_context = RepositoryContext(
            repository="test-repo",
            repo_type="backend",
            description="Test repository",
            languages={"python": 5},
        )

        manual_roles = ["qa-engineer", "devops-engineer"]

        result = self.engine.assign_roles(
            story_content="Test story content",
            repository_contexts=[repo_context],
            story_id="test-story-3",
            manual_overrides=manual_roles,
        )

        # Check manual overrides are in primary roles
        manual_role_names = [
            r.role_name for r in result.primary_roles if r.assigned_by == "manual"
        ]
        self.assertEqual(set(manual_role_names), set(manual_roles))

        # Check confidence scores for manual overrides
        for role in result.primary_roles:
            if role.assigned_by == "manual":
                self.assertEqual(role.confidence_score, 1.0)
                self.assertEqual(role.assignment_reason, "Manual override")

    def test_content_keyword_analysis(self):
        """Test that story content keywords are properly analyzed."""
        repo_context = RepositoryContext(
            repository="test-repo",
            repo_type="storyteller",
            description="Test repository",
            languages={},
        )

        # Test different content scenarios
        test_cases = [
            ("Create AI-powered recipe recommendations", ["ai-expert"]),
            ("Implement user authentication and security", ["security-expert"]),
            ("Design responsive UI for mobile devices", ["ux-ui-designer"]),
            ("Set up monitoring and deployment pipeline", ["devops-engineer"]),
            ("Write comprehensive documentation", ["documentation-hoarder"]),
            ("Add unit tests and quality assurance", ["qa-engineer"]),
        ]

        for content, expected_roles in test_cases:
            result = self.engine.assign_roles(
                story_content=content,
                repository_contexts=[repo_context],
                story_id="test-content",
            )

            all_role_names = [
                r.role_name
                for r in result.primary_roles
                + result.secondary_roles
                + result.suggested_roles
            ]

            for expected_role in expected_roles:
                self.assertIn(
                    expected_role,
                    all_role_names,
                    f"Expected role '{expected_role}' not found for content: '{content}'",
                )

    def test_technology_mapping(self):
        """Test that technology detection properly maps to roles."""
        # Test React frontend
        repo_context = RepositoryContext(
            repository="react-app",
            repo_type="frontend",
            description="React application",
            languages={"javascript": 10},
            key_files=[
                FileContext(
                    repository="react-app",
                    path="src/App.jsx",
                    content="import React from 'react';",
                    file_type="javascript",
                )
            ],
        )

        result = self.engine.assign_roles(
            story_content="Update the main application component",
            repository_contexts=[repo_context],
            story_id="test-tech",
        )

        role_names = [
            r.role_name for r in result.primary_roles + result.secondary_roles
        ]
        self.assertIn("ux-ui-designer", role_names)
        self.assertIn("lead-developer", role_names)

    def test_multiple_repositories(self):
        """Test role assignment with multiple repository contexts."""
        frontend_context = RepositoryContext(
            repository="frontend-app",
            repo_type="frontend",
            description="Frontend application",
            languages={"javascript": 10},
        )

        backend_context = RepositoryContext(
            repository="backend-api",
            repo_type="backend",
            description="Backend API",
            languages={"python": 8},
        )

        result = self.engine.assign_roles(
            story_content="Integrate frontend and backend for user authentication",
            repository_contexts=[frontend_context, backend_context],
            story_id="test-multi",
        )

        # Should get roles for both frontend and backend
        role_names = [
            r.role_name for r in result.primary_roles + result.secondary_roles
        ]
        self.assertIn("ux-ui-designer", role_names)  # Frontend
        self.assertIn("system-architect", role_names)  # Backend + Default
        self.assertIn("security-expert", role_names)  # Authentication keyword

        # Check metadata includes both repositories
        self.assertEqual(
            set(result.assignment_metadata["repositories"]),
            {"frontend-app", "backend-api"},
        )
        self.assertEqual(
            set(result.assignment_metadata["repository_types"]), {"frontend", "backend"}
        )

    def test_confidence_scoring(self):
        """Test that confidence scores are calculated correctly."""
        repo_context = RepositoryContext(
            repository="test-repo",
            repo_type="backend",
            description="Backend with strong Python focus",
            languages={"python": 20},  # High count
        )

        result = self.engine.assign_roles(
            story_content="Implement Python API with machine learning features",
            repository_contexts=[repo_context],
            story_id="test-confidence",
        )

        # Find AI expert role (should have high confidence due to multiple signals)
        ai_expert_role = None
        for role in result.primary_roles + result.secondary_roles:
            if role.role_name == "ai-expert":
                ai_expert_role = role
                break

        self.assertIsNotNone(ai_expert_role)
        self.assertGreater(ai_expert_role.confidence_score, 0.5)

    def test_assignment_reason_generation(self):
        """Test that assignment reasons are generated correctly."""
        repo_context = RepositoryContext(
            repository="security-app",
            repo_type="backend",
            description="Security-focused backend",
            languages={"python": 10},
        )

        result = self.engine.assign_roles(
            story_content="Implement authentication and authorization system",
            repository_contexts=[repo_context],
            story_id="test-reasons",
        )

        # Find security expert role
        security_expert = None
        for role in result.primary_roles + result.secondary_roles:
            if role.role_name == "security-expert":
                security_expert = role
                break

        self.assertIsNotNone(security_expert)
        self.assertIn("Repository type 'backend'", security_expert.assignment_reason)

    def test_validate_role_exists(self):
        """Test role validation functionality."""
        # This test depends on actual role files existing
        # Test with a role that should exist
        self.assertTrue(self.engine.validate_role_exists("ai-expert"))

        # Test with a role that shouldn't exist
        self.assertFalse(self.engine.validate_role_exists("nonexistent-role"))

    def test_get_available_roles(self):
        """Test getting list of available roles."""
        roles = self.engine.get_available_roles()

        # Should return a list of role names
        self.assertIsInstance(roles, list)

        # Should include some expected roles (if they exist)
        expected_roles = ["ai-expert", "system-architect", "ux-ui-designer"]
        for role in expected_roles:
            if self.engine.validate_role_exists(role):
                self.assertIn(role, roles)

    def test_default_roles_always_included(self):
        """Test that default roles are always included."""
        repo_context = RepositoryContext(
            repository="minimal-repo",
            repo_type="unknown",
            description="Minimal repository",
            languages={},
        )

        result = self.engine.assign_roles(
            story_content="Simple story with no specific keywords",
            repository_contexts=[repo_context],
            story_id="test-defaults",
        )

        default_role_names = [
            r.role_name
            for r in result.primary_roles
            if r.assignment_reason == "Default strategic role"
        ]

        for default_role in self.engine.DEFAULT_ROLES:
            self.assertIn(default_role, default_role_names)

    def test_role_assignment_metadata(self):
        """Test that assignment metadata is properly populated."""
        repo_context = RepositoryContext(
            repository="test-repo",
            repo_type="frontend",
            description="Test repository",
            languages={"javascript": 5},
        )

        result = self.engine.assign_roles(
            story_content="Test story",
            repository_contexts=[repo_context],
            story_id="test-metadata",
        )

        metadata = result.assignment_metadata

        # Check required metadata fields
        self.assertIn("repository_types", metadata)
        self.assertIn("repositories", metadata)
        self.assertIn("assignment_timestamp", metadata)
        self.assertIn("total_roles_considered", metadata)

        # Check metadata values
        self.assertEqual(metadata["repository_types"], ["frontend"])
        self.assertEqual(metadata["repositories"], ["test-repo"])
        self.assertIsInstance(metadata["total_roles_considered"], int)


if __name__ == "__main__":
    unittest.main()
