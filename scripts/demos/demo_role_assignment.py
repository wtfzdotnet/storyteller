#!/usr/bin/env python3
"""Demo script showing intelligent role assignment functionality."""

import asyncio
from typing import List
from unittest.mock import Mock

from config import Config
from multi_repo_context import FileContext, RepositoryContext
from role_analyzer import RoleAssignmentEngine


def create_demo_config() -> Config:
    """Create a demo configuration."""
    config = Mock(spec=Config)
    config.repositories = {
        "backend": Mock(type="backend", description="Python API backend"),
        "frontend": Mock(type="frontend", description="React frontend app"),
        "mobile": Mock(type="mobile", description="React Native mobile app"),
    }
    config.default_repository = "backend"
    return config


def create_demo_contexts() -> List[RepositoryContext]:
    """Create demo repository contexts."""
    return [
        # Backend context
        RepositoryContext(
            repository="backend",
            repo_type="backend",
            description="Python FastAPI backend with PostgreSQL",
            languages={"python": 25, "sql": 8},
            key_files=[
                FileContext(
                    repository="backend",
                    path="requirements.txt",
                    content="fastapi\npsycopg2-binary\nsqlalchemy\nalembic",
                    file_type="text",
                ),
                FileContext(
                    repository="backend",
                    path="main.py",
                    content=(
                        "from fastapi import FastAPI\n"
                        "from auth import router as auth_router"
                    ),
                    file_type="python",
                ),
            ],
        ),
        # Frontend context
        RepositoryContext(
            repository="frontend",
            repo_type="frontend",
            description="React TypeScript frontend application",
            languages={"javascript": 15, "typescript": 20},
            key_files=[
                FileContext(
                    repository="frontend",
                    path="package.json",
                    content=(
                        '{"dependencies": {"react": "^18.0.0", '
                        '"@types/react": "^18.0.0"}}'
                    ),
                    file_type="json",
                ),
                FileContext(
                    repository="frontend",
                    path="src/App.tsx",
                    content=(
                        "import React from 'react';\n" "export default function App() {"
                    ),
                    file_type="typescript",
                ),
            ],
        ),
    ]


def demo_scenario(
    engine: RoleAssignmentEngine,
    scenario_name: str,
    story_content: str,
    contexts: List[RepositoryContext],
    manual_overrides: List[str] = None,
):
    """Run a demo scenario and display results."""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'='*60}")
    print(f"Story: {story_content}")
    print(f"Repositories: {[c.repository for c in contexts]}")
    if manual_overrides:
        print(f"Manual overrides: {manual_overrides}")

    result = engine.assign_roles(
        story_content=story_content,
        repository_contexts=contexts,
        story_id=f"demo-{scenario_name.lower().replace(' ', '-')}",
        manual_overrides=manual_overrides,
    )

    print(f"\nPRIMARY ROLES ({len(result.primary_roles)}):")
    for role in result.primary_roles:
        print(f"  • {role.role_name}")
        print(f"    Confidence: {role.confidence_score:.2f}")
        print(f"    Reason: {role.assignment_reason}")
        print(f"    Assigned by: {role.assigned_by}")
        print()

    if result.secondary_roles:
        print(f"SECONDARY ROLES ({len(result.secondary_roles)}):")
        for role in result.secondary_roles:
            print(f"  • {role.role_name} (confidence: {role.confidence_score:.2f})")
        print()

    if result.suggested_roles:
        print(f"SUGGESTED ROLES ({len(result.suggested_roles)}):")
        for role in result.suggested_roles:
            print(f"  • {role.role_name} (confidence: {role.confidence_score:.2f})")
        print()

    print("Assignment metadata:")
    metadata = result.assignment_metadata
    print(f"  Repository types: {metadata['repository_types']}")
    print(f"  Total roles considered: {metadata['total_roles_considered']}")


async def main():
    """Run the demo scenarios."""
    print("INTELLIGENT ROLE ASSIGNMENT DEMO")
    print(
        "This demo shows how the role assignment engine works with different scenarios."
    )

    # Setup
    config = create_demo_config()
    engine = RoleAssignmentEngine(config)
    contexts = create_demo_contexts()

    # Scenario 1: API Security Story
    demo_scenario(
        engine=engine,
        scenario_name="API Security Implementation",
        story_content=(
            "Implement secure user authentication and authorization system "
            "with JWT tokens and role-based access control"
        ),
        contexts=[ctx for ctx in contexts if ctx.repository == "backend"],
    )

    # Scenario 2: Frontend UX Story
    demo_scenario(
        engine=engine,
        scenario_name="User Interface Design",
        story_content=(
            "Design responsive user interface for recipe discovery "
            "with accessibility features and mobile-first approach"
        ),
        contexts=[ctx for ctx in contexts if ctx.repository == "frontend"],
    )

    # Scenario 3: Full-stack Story
    demo_scenario(
        engine=engine,
        scenario_name="Full-Stack Feature",
        story_content="Implement real-time recipe recommendations using machine learning with live UI updates",
        contexts=contexts,
    )

    # Scenario 4: Manual Override Example
    demo_scenario(
        engine=engine,
        scenario_name="Manual Override",
        story_content="Add comprehensive testing and quality assurance for the payment system",
        contexts=[ctx for ctx in contexts if ctx.repository == "backend"],
        manual_overrides=["qa-engineer", "security-expert"],
    )

    # Scenario 5: Domain-specific Story
    demo_scenario(
        engine=engine,
        scenario_name="Domain Expertise",
        story_content="Create nutrition analysis system with cultural food heritage tracking and dietary recommendations",
        contexts=contexts,
    )

    print(f"\n{'='*60}")
    print("AVAILABLE ROLES")
    print(f"{'='*60}")
    available_roles = engine.get_available_roles()
    print(f"Total available roles: {len(available_roles)}")
    for i, role in enumerate(sorted(available_roles), 1):
        print(f"{i:2d}. {role}")
        if i % 5 == 0:  # Group every 5 roles
            print()


if __name__ == "__main__":
    asyncio.run(main())
