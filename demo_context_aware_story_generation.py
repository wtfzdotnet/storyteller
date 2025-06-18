#!/usr/bin/env python3
"""Demonstration of context-aware story generation."""

import asyncio
import os
from unittest.mock import MagicMock

from multi_repo_context import FileContext, RepositoryContext
from story_manager import StoryProcessor, StoryRequest

# Set environment for demo
os.environ["GITHUB_TOKEN"] = "demo_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


async def demo_context_aware_story_generation():
    """Demonstrate context-aware story generation capabilities."""

    print("🎯 Storyteller Context-Aware Story Generation Demo")
    print("=" * 60)

    # Create a story processor
    processor = StoryProcessor()

    # Create mock repository contexts to simulate real environments
    backend_context = RepositoryContext(
        repository="wtfzdotnet/recipeer",
        repo_type="backend",
        description="FastAPI backend service with PostgreSQL database",
        structure={"src": ["main.py", "models.py", "api/"], "tests": ["test_api.py"]},
        key_files=[
            FileContext(
                repository="wtfzdotnet/recipeer",
                path="requirements.txt",
                content="fastapi==0.68.0\npsycopg2-binary==2.9.1\npydantic==1.8.0\nuvicorn==0.15.0",
                file_type=".txt",
                language="text",
                size=120,
                importance_score=0.9,
            ),
            FileContext(
                repository="wtfzdotnet/recipeer",
                path="src/main.py",
                content="from fastapi import FastAPI\nfrom src.models import Recipe\n\napp = FastAPI(title='Recipe API')",
                file_type=".py",
                language="python",
                size=200,
                importance_score=0.95,
            ),
        ],
        languages={"python": 0.85, "yaml": 0.15},
        dependencies=["fastapi", "psycopg2-binary", "pydantic", "uvicorn"],
        file_count=25,
    )

    frontend_context = RepositoryContext(
        repository="wtfzdotnet/recipes-frontend",
        repo_type="frontend",
        description="React-based frontend application with Material-UI",
        structure={
            "src": ["App.js", "components/", "pages/"],
            "public": ["index.html"],
        },
        key_files=[
            FileContext(
                repository="wtfzdotnet/recipes-frontend",
                path="package.json",
                content='{"dependencies": {"react": "^17.0.2", "@mui/material": "^5.0.0", "axios": "^0.24.0"}}',
                file_type=".json",
                language="json",
                size=300,
                importance_score=0.85,
            ),
            FileContext(
                repository="wtfzdotnet/recipes-frontend",
                path="src/App.js",
                content=(
                    "import React from 'react';\n"
                    "import { ThemeProvider } from '@mui/material';\n"
                    "\nfunction App() { return <div>Recipe App</div>; }"
                ),
                file_type=".js",
                language="javascript",
                size=150,
                importance_score=0.9,
            ),
        ],
        languages={"javascript": 0.75, "css": 0.20, "html": 0.05},
        dependencies=["react", "@mui/material", "axios"],
        file_count=45,
    )

    # Mock the context reader to return our demo contexts
    async def mock_get_repo_context(repo_key, max_files=20, use_cache=True):
        if repo_key == "backend":
            return backend_context
        elif repo_key == "frontend":
            return frontend_context
        return None

    async def mock_get_multi_repo_context(repository_keys=None, max_files_per_repo=15):
        from multi_repo_context import MultiRepositoryContext

        return MultiRepositoryContext(
            repositories=[backend_context, frontend_context],
            cross_repository_insights={
                "shared_languages": ["json", "yaml"],
                "common_patterns": ["RESTful API", "Component architecture"],
                "integration_points": ["API endpoints", "HTTP requests"],
                "dependency_conflicts": [],
            },
            dependency_graph={"frontend": ["backend"]},
            total_files_analyzed=70,
            context_quality_score=0.88,
        )

    # Mock LLM responses for demo
    def mock_llm_response(content):
        return MagicMock(content=content, model="demo", provider="demo", usage={})

    # Replace real methods with mocks for demo
    processor.context_reader.get_repository_context = mock_get_repo_context
    processor.context_reader.get_multi_repository_context = mock_get_multi_repo_context

    # Mock analyze_story_content
    async def mock_analyze_story_content(story_content):
        return {
            "recommended_roles": [
                "system-architect",
                "lead-developer",
                "ux-ui-designer",
            ],
            "target_repositories": ["backend", "frontend"],
            "complexity": "medium",
            "themes": ["user-management", "authentication", "profile"],
            "reasoning": "Multi-repository user profile feature requiring both API and UI changes",
        }

    processor.analyze_story_content = mock_analyze_story_content

    # Mock expert analysis
    async def mock_analyze_with_role(
        story_content, role_definition, role_name, context=None
    ):
        repo_contexts = context.get("repository_contexts", []) if context else []
        tech_stack = []
        for repo_ctx in repo_contexts:
            tech_stack.extend(repo_ctx.get("key_technologies", []))
            tech_stack.extend(repo_ctx.get("dependencies", [])[:3])

        repo_list = ", ".join(
            [ctx.get("repository", "unknown") for ctx in repo_contexts]
        )
        tech_list = ", ".join(set(tech_stack))
        integration_list = ", ".join(
            context.get("cross_repository_insights", {}).get("integration_points", [])
            if context
            else []
        )

        analysis_content = f"""
## {role_name.title()} Analysis

**Story Assessment:**
{story_content}

**Technical Context Analysis:**
- Target Repositories: {repo_list}
- Technology Stack: {tech_list}
- Integration Points: {integration_list}

**Context-Aware Acceptance Criteria:**
- [ ] Backend API implements profile endpoints using FastAPI patterns
- [ ] Frontend uses Material-UI components for consistent design
- [ ] Database operations use PostgreSQL features for data persistence
- [ ] React components manage profile state with proper hooks
- [ ] API integration uses axios for HTTP requests
- [ ] Cross-repository authentication flow works seamlessly

**Implementation Recommendations:**
- Leverage FastAPI's automatic OpenAPI documentation for API endpoints
- Use Material-UI's form components for profile editing interface
- Implement proper error handling for both frontend and backend
- Consider caching strategies for profile data access
- Ensure proper validation on both client and server sides

**Repository-Specific Considerations:**
- Backend: Utilize existing PostgreSQL schema and FastAPI route patterns
- Frontend: Follow established React component structure and Material-UI theming
"""
        return mock_llm_response(analysis_content)

    processor.llm_handler.analyze_story_with_role = mock_analyze_with_role

    # Mock synthesis
    async def mock_synthesize_analyses(story_content, expert_analyses, context=None):
        return mock_llm_response(
            """
# Comprehensive Context-Aware Story Analysis

## Executive Summary
This user profile management feature requires coordinated development across
backend and frontend repositories, leveraging existing technology stacks and
architectural patterns.

## Technical Stack Integration
- **Backend (FastAPI + PostgreSQL)**: Leverage existing API patterns and database schema
- **Frontend (React + Material-UI)**: Build upon established component library and state management
- **Cross-Repository**: Coordinate authentication and data flow between systems

## Context-Driven Implementation Plan

### Repository-Specific Tasks
**Backend Repository (FastAPI):**
- Implement profile CRUD endpoints following existing API conventions
- Add database migrations for profile schema updates
- Include comprehensive API documentation via FastAPI's automatic OpenAPI

**Frontend Repository (React + Material-UI):**
- Create profile management components using Material-UI design system
- Implement form validation and state management with React hooks
- Integrate with backend APIs using existing axios service layer

### Cross-Repository Considerations
- Authentication flow must work seamlessly across both applications
- Data validation rules should be consistent between frontend and
  backend
- Error handling patterns should provide consistent user experience

## Quality Assurance Strategy
- Unit tests for both FastAPI endpoints and React components
- Integration tests for cross-repository authentication flow
- End-to-end testing of complete profile management
  workflow

This analysis leverages repository context including technology dependencies,
existing code patterns, and architectural decisions to provide implementable
recommendations.
"""
        )

    processor.llm_handler.synthesize_expert_analyses = mock_synthesize_analyses

    # Create a story request
    story_request = StoryRequest(
        content=(
            "As a user, I want to manage my profile information so that I can keep "
            "my account details up to date and personalize my experience"
        ),
        target_repositories=["backend", "frontend"],
    )

    print(f"📋 Processing Story: {story_request.content}")
    print(f"🎯 Target Repositories: {story_request.target_repositories}")
    print()

    # Process the story with context awareness
    result = await processor.process_story(story_request)

    print("✅ Context-Aware Story Processing Complete!")
    print()

    # Display results
    print("📊 **Processing Results:**")
    print(f"   Story ID: {result.story_id}")
    print(f"   Target Repositories: {result.target_repositories}")
    print(f"   Expert Analyses: {len(result.expert_analyses)}")
    print(f"   Context Quality: {result.metadata.get('context_quality', 0):.2%}")
    print()

    print("🏗️ **Repository Contexts Analyzed:**")
    for repo_ctx in result.metadata.get("repository_contexts", []):
        print(f"   • {repo_ctx['repository']} ({repo_ctx['repo_type']})")
        print(f"     Languages: {', '.join(repo_ctx['languages'].keys())}")
        print(f"     Files: {repo_ctx['file_count']} analyzed")
        print()

    print("🔗 **Cross-Repository Insights:**")
    insights = result.metadata.get("cross_repository_insights", {})
    if insights:
        shared_langs = insights.get("shared_languages", [])
        if shared_langs:
            print(f"   • Shared Technologies: {', '.join(shared_langs)}")
        common_patterns = insights.get("common_patterns", [])
        if common_patterns:
            print(f"   • Common Patterns: {', '.join(common_patterns)}")

        integration_points = insights.get("integration_points", [])
        if integration_points:
            print(f"   • Integration Points: {', '.join(integration_points)}")
    print()

    print("🧠 **Expert Analysis Summary:**")
    for analysis in result.expert_analyses:
        print(f"   • {analysis.role_name}: Generated context-aware recommendations")
        if "FastAPI" in analysis.analysis:
            print("     ✓ Includes FastAPI-specific guidance")
        if "Material-UI" in analysis.analysis:
            print("     ✓ Includes Material-UI design considerations")
        if "PostgreSQL" in analysis.analysis:
            print("     ✓ Includes database-specific recommendations")
    print()

    print("📄 **Synthesized Analysis Preview:**")
    synthesis_preview = (
        result.synthesized_analysis[:300] + "..."
        if len(result.synthesized_analysis) > 300
        else result.synthesized_analysis
    )
    print(f"   {synthesis_preview}")
    print()

    print("🎉 **Context-Aware Features Demonstrated:**")
    print("   ✅ Multi-repository context gathering")
    print("   ✅ Technology stack-aware analysis")
    print("   ✅ Cross-repository impact consideration")
    print("   ✅ Framework-specific acceptance criteria")
    print("   ✅ Repository-specific implementation guidance")
    print("   ✅ Integration point identification")

    return result


if __name__ == "__main__":
    asyncio.run(demo_context_aware_story_generation())
