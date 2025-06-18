"""Tests for context-aware story generation functionality."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"

from story_manager import StoryProcessor, StoryRequest  # noqa: E402
from multi_repo_context import RepositoryContext, FileContext, MultiRepositoryContext  # noqa: E402


class TestContextAwareStoryGeneration(unittest.TestCase):
    """Test context-aware story generation functionality."""

    def setUp(self):
        """Set up test dependencies."""
        # Use temporary database for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()

        self.story_processor = StoryProcessor()
        self.story_processor.database.db_path = Path(self.temp_file.name)
        self.story_processor.database.init_database()

    def tearDown(self):
        """Clean up test dependencies."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_story_generation_includes_repository_context(self):
        """Test that story generation includes multi-repository context."""
        
        # Mock repository context
        mock_backend_context = RepositoryContext(
            repository="wtfzdotnet/recipeer",
            repo_type="backend", 
            description="Backend API services",
            structure={"src": ["main.py", "models.py", "api.py"]},
            key_files=[
                FileContext(
                    repository="wtfzdotnet/recipeer",
                    path="src/api.py",
                    content="from fastapi import FastAPI\napp = FastAPI()",
                    file_type=".py",
                    language="python",
                    size=50,
                    importance_score=0.9
                )
            ],
            languages={"python": 0.8, "yaml": 0.2},
            dependencies=["fastapi", "pydantic"],
            file_count=10
        )

        mock_frontend_context = RepositoryContext(
            repository="wtfzdotnet/recipes-frontend",
            repo_type="frontend",
            description="React frontend application", 
            structure={"src": ["App.js", "components"]},
            key_files=[
                FileContext(
                    repository="wtfzdotnet/recipes-frontend",
                    path="src/App.js",
                    content="import React from 'react';\nfunction App() { return <div>Hello</div>; }",
                    file_type=".js",
                    language="javascript",
                    size=75,
                    importance_score=0.8
                )
            ],
            languages={"javascript": 0.9, "css": 0.1},
            dependencies=["react", "axios"],
            file_count=25
        )

        with (
            patch.object(self.story_processor, "analyze_story_content") as mock_analyze_content,
            patch.object(self.story_processor.context_reader, "get_repository_context") as mock_get_repo_context,
            patch.object(self.story_processor.context_reader, "get_multi_repository_context") as mock_get_multi_context,
            patch.object(self.story_processor.llm_handler, "analyze_story_with_role") as mock_analyze,
            patch.object(self.story_processor.llm_handler, "synthesize_expert_analyses") as mock_synthesize,
        ):
            
            # Setup mocks
            mock_analyze_content.return_value = {
                "recommended_roles": ["system-architect", "lead-developer"],
                "target_repositories": ["backend", "frontend"],
                "complexity": "medium",
                "themes": ["search", "recipes"],
                "reasoning": "Multi-repository search feature"
            }
            
            mock_get_repo_context.side_effect = [mock_backend_context, mock_frontend_context]
            
            mock_get_multi_context.return_value = MultiRepositoryContext(
                repositories=[mock_backend_context, mock_frontend_context],
                cross_repository_insights={
                    "shared_languages": ["javascript"],
                    "common_patterns": ["RESTful API"],
                    "integration_points": ["API endpoints"]
                },
                dependency_graph={"frontend": ["backend"]},
                total_files_analyzed=35,
                context_quality_score=0.85
            )
            
            mock_analyze.return_value = MagicMock(
                content="Analysis with technical details from FastAPI backend and React frontend",
                model="test",
                provider="test",
                usage={}
            )
            
            mock_synthesize.return_value = MagicMock(
                content="Synthesized analysis including cross-repository dependencies and technical implementation details"
            )

            # Test story processing
            async def run_test():
                story_request = StoryRequest(
                    content="As a user, I want to search for recipes so that I can find meals to cook",
                    target_repositories=["backend", "frontend"]
                )
                
                result = await self.story_processor.process_story(story_request)
                
                # Verify repository context was gathered
                self.assertEqual(mock_get_repo_context.call_count, 2)
                
                # Verify context was passed to expert analysis
                for call in mock_analyze.call_args_list:
                    context = call[1]["context"]
                    self.assertIsNotNone(context)
                    self.assertIn("repository_contexts", context)
                    
                # Verify result includes repository information
                self.assertIn("backend", result.target_repositories)
                self.assertIn("frontend", result.target_repositories)
                self.assertIn("repository_contexts", result.metadata)

            asyncio.run(run_test())

    def test_cross_repository_impact_analysis(self):
        """Test that cross-repository impact analysis is included."""
        
        with (
            patch.object(self.story_processor, "analyze_story_content") as mock_analyze_content,
            patch.object(self.story_processor.context_reader, "get_repository_context") as mock_get_repo_context,
            patch.object(self.story_processor.context_reader, "get_multi_repository_context") as mock_multi_context,
            patch.object(self.story_processor.llm_handler, "analyze_story_with_role") as mock_analyze,
            patch.object(self.story_processor.llm_handler, "synthesize_expert_analyses") as mock_synthesize,
        ):
            
            # Setup content analysis mock
            mock_analyze_content.return_value = {
                "recommended_roles": ["system-architect", "lead-developer"],
                "target_repositories": ["backend", "frontend"],
                "complexity": "high",
                "themes": ["rating", "social"],
                "reasoning": "Multi-repository rating feature"
            }
            
            # Mock repository contexts
            mock_get_repo_context.return_value = RepositoryContext(
                repository="test",
                repo_type="backend",
                description="Test repo",
                structure={},
                key_files=[],
                languages={},
                dependencies=[],
                file_count=5
            )
            
            # Mock multi-repository context with cross-repo insights
            mock_multi_context.return_value = MultiRepositoryContext(
                repositories=[],  # Mock repositories
                cross_repository_insights={
                    "shared_languages": ["javascript", "python"],
                    "common_patterns": ["RESTful API", "React components"],
                    "dependency_conflicts": [],
                    "integration_points": ["API endpoints", "authentication"]
                },
                dependency_graph={"frontend": ["backend"]},
                total_files_analyzed=35,
                context_quality_score=0.85
            )
            
            mock_analyze.return_value = MagicMock(
                content="Analysis considering cross-repository dependencies",
                model="test",
                provider="test", 
                usage={}
            )
            
            mock_synthesize.return_value = MagicMock(
                content="Synthesis including cross-repository impact analysis and integration considerations"
            )

            async def run_test():
                story_request = StoryRequest(
                    content="As a user, I want to rate recipes so that other users can see quality ratings",
                    target_repositories=["backend", "frontend"]
                )
                
                result = await self.story_processor.process_story(story_request)
                
                # Verify cross-repository analysis was performed
                mock_multi_context.assert_called_once()
                
                # Verify metadata includes cross-repo insights
                self.assertIn("cross_repository_insights", result.metadata)
                
                # Verify synthesis includes cross-repo considerations
                self.assertIn("cross-repository", result.synthesized_analysis.lower())

            asyncio.run(run_test())

    def test_context_aware_acceptance_criteria_generation(self):
        """Test that acceptance criteria include repository-specific technical details."""
        
        with (
            patch.object(self.story_processor, "analyze_story_content") as mock_analyze_content,
            patch.object(self.story_processor.context_reader, "get_repository_context") as mock_get_repo_context,
            patch.object(self.story_processor.llm_handler, "analyze_story_with_role") as mock_analyze,
            patch.object(self.story_processor.llm_handler, "synthesize_expert_analyses") as mock_synthesize,
        ):
            
            # Setup content analysis mock
            mock_analyze_content.return_value = {
                "recommended_roles": ["lead-developer"],
                "target_repositories": ["backend"],
                "complexity": "medium",
                "themes": ["rating", "database"],
                "reasoning": "Backend rating implementation"
            }
            
            # Mock repository context with specific technical stack
            mock_context = RepositoryContext(
                repository="wtfzdotnet/recipeer",
                repo_type="backend",
                description="FastAPI backend with PostgreSQL",
                structure={},
                key_files=[
                    FileContext(
                        repository="wtfzdotnet/recipeer",
                        path="requirements.txt",
                        content="fastapi==0.68.0\npsycopg2==2.9.1\nalembic==1.7.1",
                        file_type=".txt",
                        language="text",
                        size=100,
                        importance_score=0.7
                    )
                ],
                languages={"python": 1.0},
                dependencies=["fastapi", "psycopg2", "alembic"],
                file_count=15
            )
            
            mock_get_repo_context.return_value = mock_context
            
            # Mock analysis to include technical requirements
            mock_analyze.return_value = MagicMock(
                content="""
                Technical Analysis:
                - Implement FastAPI endpoint for recipe rating
                - Add PostgreSQL table for ratings with proper indexing
                - Use Alembic for database migration
                - Implement rating aggregation logic
                
                Acceptance Criteria:
                - [ ] POST /api/recipes/{id}/ratings endpoint accepts rating (1-5 stars)
                - [ ] Ratings stored in PostgreSQL with user_id, recipe_id, rating, timestamp
                - [ ] Database migration creates ratings table with proper constraints
                - [ ] GET /api/recipes/{id}/ratings returns average rating and count
                """,
                model="test",
                provider="test",
                usage={}
            )
            
            mock_synthesize.return_value = MagicMock(
                content="Synthesized analysis with technical details",
                model="test",
                provider="test",
                usage={}
            )

            async def run_test():
                story_request = StoryRequest(
                    content="As a user, I want to rate recipes",
                    target_repositories=["backend"]
                )
                
                result = await self.story_processor.process_story(story_request)
                
                # Find the backend analysis
                backend_analysis = next(
                    (a for a in result.expert_analyses if "fastapi" in a.analysis.lower()),
                    None
                )
                
                self.assertIsNotNone(backend_analysis)
                self.assertIn("PostgreSQL", backend_analysis.analysis)
                self.assertIn("Alembic", backend_analysis.analysis)
                self.assertIn("POST /api/recipes", backend_analysis.analysis)

            asyncio.run(run_test())


    def test_repository_specific_sub_story_creation(self):
        """Test that repository-specific sub-stories are created with context awareness."""
        
        with (
            patch.object(self.story_processor, "analyze_story_content") as mock_analyze_content,
            patch.object(self.story_processor.context_reader, "get_repository_context") as mock_get_repo_context,
            patch.object(self.story_processor.llm_handler, "analyze_story_with_role") as mock_analyze,
            patch.object(self.story_processor.llm_handler, "synthesize_expert_analyses") as mock_synthesize,
        ):
            
            # Setup content analysis mock
            mock_analyze_content.return_value = {
                "recommended_roles": ["system-architect", "lead-developer"],
                "target_repositories": ["backend", "frontend"],
                "complexity": "medium",
                "themes": ["user-interface", "data-management"],
                "reasoning": "Multi-repository feature with UI and data components"
            }
            
            # Mock repository context with specific technical details
            mock_backend_context = RepositoryContext(
                repository="wtfzdotnet/recipeer",
                repo_type="backend",
                description="FastAPI backend with PostgreSQL",
                structure={"src": ["main.py", "models.py"]},
                key_files=[
                    FileContext(
                        repository="wtfzdotnet/recipeer",
                        path="requirements.txt",
                        content="fastapi==0.68.0\npsycopg2==2.9.1\npytest==6.2.0",
                        file_type=".txt",
                        language="text",
                        size=100,
                        importance_score=0.7
                    )
                ],
                languages={"python": 1.0},
                dependencies=["fastapi", "psycopg2", "pytest"],
                file_count=15
            )
            
            mock_frontend_context = RepositoryContext(
                repository="wtfzdotnet/recipes-frontend",
                repo_type="frontend",
                description="React frontend with Material-UI",
                structure={"src": ["App.js", "components"]},
                key_files=[
                    FileContext(
                        repository="wtfzdotnet/recipes-frontend",
                        path="package.json",
                        content='{"dependencies": {"react": "^17.0.0", "@material-ui/core": "^4.12.0", "jest": "^26.0.0"}}',
                        file_type=".json",
                        language="json",
                        size=200,
                        importance_score=0.8
                    )
                ],
                languages={"javascript": 0.9, "css": 0.1},
                dependencies=["react", "@material-ui/core", "jest"],
                file_count=25
            )
            
            mock_get_repo_context.side_effect = [mock_backend_context, mock_frontend_context]
            
            # Mock expert analysis that should include repository-specific details
            mock_analyze.return_value = MagicMock(
                content="""
                ## Repository-Specific Analysis
                
                **Backend (FastAPI + PostgreSQL):**
                - Implement FastAPI endpoints with proper typing
                - Create PostgreSQL schema with proper constraints
                - Use pytest for comprehensive testing
                
                **Frontend (React + Material-UI):**
                - Create React components using Material-UI design system
                - Implement proper state management with hooks
                - Write Jest tests for component behavior
                
                **Acceptance Criteria:**
                - [ ] Backend API endpoints follow FastAPI patterns
                - [ ] Frontend components use Material-UI components
                - [ ] Database operations use PostgreSQL features
                - [ ] Testing covers both pytest and Jest frameworks
                """,
                model="test",
                provider="test",
                usage={}
            )
            
            mock_synthesize.return_value = MagicMock(
                content="Synthesized analysis with repository-specific technical details and framework-specific recommendations",
                model="test",
                provider="test",
                usage={}
            )

            async def run_test():
                story_request = StoryRequest(
                    content="As a user, I want to manage my profile so that I can update my personal information",
                    target_repositories=["backend", "frontend"]
                )
                
                result = await self.story_processor.process_story(story_request)
                
                # Verify that repository contexts were gathered and used
                self.assertGreaterEqual(mock_get_repo_context.call_count, 2)
                
                # Verify metadata includes repository-specific context
                self.assertIn("repository_contexts", result.metadata)
                repo_contexts = result.metadata["repository_contexts"]
                self.assertEqual(len(repo_contexts), 2)
                
                # Verify backend context
                backend_ctx = next(ctx for ctx in repo_contexts if ctx["repo_type"] == "backend")
                self.assertIn("python", backend_ctx.get("languages", {}))
                
                # Verify frontend context  
                frontend_ctx = next(ctx for ctx in repo_contexts if ctx["repo_type"] == "frontend")
                self.assertIn("javascript", frontend_ctx.get("languages", {}))
                
                # Verify that analysis includes framework-specific details
                backend_analysis = next(
                    (a for a in result.expert_analyses if "fastapi" in a.analysis.lower()),
                    None
                )
                self.assertIsNotNone(backend_analysis)
                self.assertIn("FastAPI", backend_analysis.analysis)
                self.assertIn("PostgreSQL", backend_analysis.analysis)

            asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()