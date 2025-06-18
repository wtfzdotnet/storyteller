"""Integration tests for cross-repository conversation system and multi-repository context."""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock

import pytest

from config import get_config
from conversation_manager import ConversationManager
from database import DatabaseManager
from mcp_server import MCPRequest, MCPStoryServer
from multi_repo_context import MultiRepositoryContextReader

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


@pytest.mark.asyncio
async def test_conversation_manager_integration():
    """Test ConversationManager with full workflow integration."""
    # Use temporary file database for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        manager = ConversationManager()
        manager.database = DatabaseManager(tmp_db_path)
        # Mock the context reader to avoid GitHub API calls
        manager.context_reader.get_repository_context = AsyncMock(
            return_value={
                "type": "backend",
                "description": "Backend API service",
                "key_files": ["app.py", "requirements.txt"],
                "languages": ["Python"],
                "structure": {"src": ["models", "api", "tests"]},
            }
        )

        # Create cross-repository conversation
        conversation = await manager.create_conversation(
            title="API Versioning Strategy",
            description="Planning API versioning across all services",
            repositories=["backend", "frontend", "mobile"],
            initial_participants=[
                {"name": "System Architect", "role": "system-architect"},
                {
                    "name": "Lead Developer",
                    "role": "lead-developer",
                    "repository": "backend",
                },
            ],
        )

        assert conversation.title == "API Versioning Strategy"
        assert len(conversation.repositories) == 3
        assert len(conversation.participants) == 2

        # Add additional participant
        participant = await manager.add_participant(
            conversation_id=conversation.id,
            name="Frontend Lead",
            role="lead-developer",
            repository="frontend",
        )

        # Add regular message
        message = await manager.add_message(
            conversation_id=conversation.id,
            participant_id=participant.id,
            content="We need to ensure backward compatibility for at least 2 versions.",
            message_type="text",
        )

        # Add context message (should trigger context enrichment)
        context_msg = await manager.add_context_message(
            conversation_id=conversation.id,
            participant_id=participant.id,
            repository="frontend",
            context_summary="Current frontend uses React 18 with TypeScript. API calls are centralized in a service layer.",
        )

        # Add decision message (should update conversation status)
        decision_msg = await manager.add_decision_message(
            conversation_id=conversation.id,
            participant_id=conversation.participants[0].id,  # System Architect
            decision="We will implement semantic versioning with a 2-version backward compatibility policy.",
            repositories_affected=["backend", "frontend", "mobile"],
        )

        # Verify conversation status changed to resolved
        updated_conversation = manager.get_conversation(conversation.id)
        assert updated_conversation.status == "resolved"

        # Get conversation history
        history = manager.get_conversation_history(conversation.id)
        assert len(history["messages"]) >= 3
        assert any(msg["message_type"] == "decision" for msg in history["messages"])

        # Get cross-repository insights
        insights = await manager.get_cross_repository_insights(conversation.id)
        assert "key_decisions" in insights
        assert "repository_impacts" in insights
        assert len(insights["repository_impacts"]) == 3

        # Test repository filtering
        frontend_conversations = manager.list_conversations(repository="frontend")
        assert len(frontend_conversations) >= 1

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_db_path):
            os.unlink(tmp_db_path)


@pytest.mark.asyncio
async def test_mcp_conversation_endpoints_integration():
    """Test MCP server conversation endpoints with full workflow."""
    # Use temporary file database for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        server = MCPStoryServer()
        server.conversation_manager.database = DatabaseManager(tmp_db_path)
        # Mock the context reader
        server.conversation_manager.context_reader.get_repository_context = AsyncMock(
            return_value={
                "type": "backend",
                "description": "Database service",
                "key_files": ["schema.sql", "migrations/"],
                "languages": ["SQL", "Python"],
            }
        )

        # Test conversation creation
        create_request = MCPRequest(
            id="test1",
            method="conversation/create",
            params={
                "title": "Database Migration Strategy",
                "description": "Planning database changes across services",
                "repositories": ["backend", "data-service"],
                "participants": [
                    {"name": "DBA", "role": "database-administrator"},
                    {
                        "name": "Backend Lead",
                        "role": "lead-developer",
                        "repository": "backend",
                    },
                ],
            },
        )

        response = await server.handle_request(create_request)
        assert response.result["success"]
        conversation_id = response.result["conversation_id"]

        # Test adding participant
        add_participant_request = MCPRequest(
            id="test2",
            method="conversation/add_participant",
            params={
                "conversation_id": conversation_id,
                "name": "Data Engineer",
                "role": "data-engineer",
                "repository": "data-service",
            },
        )

        response = await server.handle_request(add_participant_request)
        assert response.result["success"]

        # Test adding message
        add_message_request = MCPRequest(
            id="test3",
            method="conversation/add_message",
            params={
                "conversation_id": conversation_id,
                "participant_name": "DBA",
                "content": "We should plan the migration in phases to minimize downtime.",
                "message_type": "text",
            },
        )

        response = await server.handle_request(add_message_request)
        assert response.result["success"]

        # Test adding context
        add_context_request = MCPRequest(
            id="test4",
            method="conversation/add_context",
            params={
                "conversation_id": conversation_id,
                "participant_name": "Backend Lead",
                "repository": "backend",
                "context_summary": "Current schema has 15 tables with complex relationships.",
            },
        )

        response = await server.handle_request(add_context_request)
        assert response.result["success"]

        # Test adding decision
        add_decision_request = MCPRequest(
            id="test5",
            method="conversation/add_decision",
            params={
                "conversation_id": conversation_id,
                "participant_name": "DBA",
                "decision": "Implement blue-green deployment strategy for zero-downtime migrations.",
                "repositories_affected": ["backend", "data-service"],
            },
        )

        response = await server.handle_request(add_decision_request)
        assert response.result["success"]

        # Test getting conversation
        get_request = MCPRequest(
            id="test6",
            method="conversation/get",
            params={"conversation_id": conversation_id},
        )

        response = await server.handle_request(get_request)
        assert response.result["success"]
        conversation_data = response.result["conversation"]
        assert conversation_data["title"] == "Database Migration Strategy"
        assert conversation_data["status"] == "resolved"  # Should be resolved after decision

        # Test getting history
        history_request = MCPRequest(
            id="test7",
            method="conversation/history",
            params={"conversation_id": conversation_id},
        )

        response = await server.handle_request(history_request)
        assert response.result["success"]
        history = response.result["history"]
        assert len(history["messages"]) >= 3

        # Test getting insights
        insights_request = MCPRequest(
            id="test8",
            method="conversation/insights",
            params={"conversation_id": conversation_id},
        )

        response = await server.handle_request(insights_request)
        assert response.result["success"]
        insights = response.result["insights"]
        assert "key_decisions" in insights
        assert "repository_impacts" in insights

        # Test listing conversations
        list_request = MCPRequest(
            id="test9",
            method="conversation/list",
            params={"repository": "backend"},
        )

        response = await server.handle_request(list_request)
        assert response.result["success"]
        conversations = response.result["conversations"]
        assert len(conversations) >= 1

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_db_path):
            os.unlink(tmp_db_path)


@pytest.mark.asyncio
async def test_mcp_context_endpoints_integration():
    """Test MCP context endpoints that would normally make GitHub API calls."""
    server = MCPStoryServer()

    # Test context/repository_structure endpoint
    request = MCPRequest(
        id="test1",
        method="context/repository_structure",
        params={"repository": "storyteller"},
    )
    response = await server.handle_request(request)

    # Note: This will fail with GitHub API since we have a fake token
    # but the endpoint structure is validated
    assert response.result is not None
    if response.result.get("success"):
        # If somehow it works (shouldn't with fake token)
        assert "structure" in response.result
    else:
        # Expected case - should handle auth errors gracefully
        assert "error" in response.result

    # Test context/file_content endpoint
    request = MCPRequest(
        id="test2",
        method="context/file_content",
        params={"repository": "storyteller", "file_path": "README.md"},
    )
    response = await server.handle_request(request)

    assert response.result is not None
    # Should handle the request gracefully even with auth errors

    # Test context/repository endpoint
    request = MCPRequest(
        id="test3",
        method="context/repository",
        params={"repository": "storyteller", "max_files": 5, "use_cache": False},
    )
    response = await server.handle_request(request)

    assert response.result is not None
    # Should handle the request gracefully even with auth errors

    # Test context/multi_repository endpoint
    request = MCPRequest(
        id="test4",
        method="context/multi_repository",
        params={"repositories": ["storyteller", "backend"], "max_files_per_repo": 3},
    )
    response = await server.handle_request(request)

    assert response.result is not None
    # Should handle the request gracefully even with auth errors

    # Test invalid parameters - this should work regardless of auth
    request = MCPRequest(
        id="test5",
        method="context/repository",
        params={},  # Missing required repository parameter
    )
    response = await server.handle_request(request)

    assert response.result is not None
    assert not response.result.get("success")
    assert "error" in response.result


def test_repository_configuration_integration():
    """Test repository configuration reading and validation."""
    config = get_config()

    # Basic configuration validation
    assert hasattr(config, "repositories")
    assert len(config.repositories) > 0

    # Test that our multi-repository configuration is properly structured
    assert "storyteller" in config.repositories
    storyteller_config = config.repositories["storyteller"]
    assert hasattr(storyteller_config, "name")
    assert hasattr(storyteller_config, "type")
    assert hasattr(storyteller_config, "description")

    # Test configuration has expected repositories for integration testing
    expected_repos = ["storyteller", "backend", "frontend"]
    for repo in expected_repos:
        if repo in config.repositories:
            repo_config = config.repositories[repo]
            assert repo_config.name is not None
            assert repo_config.type is not None


@pytest.mark.asyncio
async def test_context_reader_integration():
    """Test multi-repository context reader integration (with mocking)."""
    config = get_config()
    reader = MultiRepositoryContextReader(config)

    # Test that components are properly initialized
    assert reader.type_detector is not None
    assert reader.file_selector is not None
    assert reader.cache is not None

    # Test basic functionality without making actual API calls
    # This tests the integration of components without external dependencies

    # Test type detector integration
    files = ["src/App.js", "package.json", "public/index.html"]
    detected_type = reader.type_detector.detect_repository_type({}, files)
    assert detected_type == "frontend"

    # Test file selector integration
    file_list = [
        ("package.json", "file"),
        ("src/App.js", "file"),
        ("node_modules/react/index.js", "file"),
    ]
    selected = reader.file_selector.select_important_files("frontend", file_list, 2)
    assert "package.json" in selected
    assert "node_modules/react/index.js" not in selected

    # Test cache integration
    reader.cache.set("test_key", {"data": "test_value"})
    cached_value = reader.cache.get("test_key")
    assert cached_value == {"data": "test_value"}


@pytest.mark.asyncio
async def test_capabilities_integration():
    """Test that new capabilities are properly registered in MCP server."""
    server = MCPStoryServer()

    request = MCPRequest(id="caps", method="system/capabilities", params={})
    response = await server.handle_request(request)

    assert response.result["success"]
    capabilities = response.result["data"]["capabilities"]

    # Check that conversation capabilities are listed
    conversation_capabilities = [c for c in capabilities if "conversation/" in c]
    expected_conversation_capabilities = [
        "conversation/create",
        "conversation/add_participant",
        "conversation/add_message",
        "conversation/add_context",
        "conversation/add_decision",
        "conversation/get",
        "conversation/list",
        "conversation/history",
        "conversation/insights",
        "conversation/archive",
    ]

    for expected in expected_conversation_capabilities:
        assert expected in capabilities

    # Check that context capabilities are listed
    context_capabilities = [c for c in capabilities if "context/" in c]
    expected_context_capabilities = [
        "context/repository",
        "context/multi_repository",
        "context/file_content",
        "context/repository_structure",
    ]

    for expected in expected_context_capabilities:
        assert expected in capabilities

    # Check that features include multi-repository support
    features = response.result["data"]["features"]
    assert "multi_repository_context" in features
    assert "cross_repository_conversations" in features