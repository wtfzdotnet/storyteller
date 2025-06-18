"""Test cross-repository conversation system functionality."""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from conversation_manager import ConversationManager
from database import DatabaseManager
from models import Conversation, ConversationParticipant, Message

from mcp_server import MCPRequest, MCPStoryServer

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


@pytest.mark.asyncio
async def test_conversation_models():
    """Test conversation data models."""

    print("\n=== Testing Conversation Models ===")

    # Test ConversationParticipant
    participant = ConversationParticipant(
        name="Alice Developer", role="lead-developer", repository="backend"
    )
    print(f"✓ Created participant: {participant.name} ({participant.role})")

    # Test Message
    message = Message(
        conversation_id="test_conv",
        participant_id=participant.id,
        content="This is a test message about backend architecture.",
        message_type="text",
        repository_context="backend",
    )
    print(f"✓ Created message: {message.id} by {participant.name}")

    # Test Conversation
    conversation = Conversation(
        title="Backend API Design Discussion",
        description="Discussing API design across frontend and backend repositories",
        repositories=["backend", "frontend"],
        participants=[participant],
        messages=[message],
    )
    print(f"✓ Created conversation: {conversation.title}")

    # Test conversation methods
    new_message = conversation.add_message(
        participant_id=participant.id,
        content="Let's also consider the frontend implications.",
        message_type="text",
        repository_context="frontend",
    )
    print(f"✓ Added message to conversation: {new_message.content[:50]}...")

    # Test filtering methods
    backend_messages = conversation.get_messages_by_repository("backend")
    frontend_messages = conversation.get_messages_by_repository("frontend")
    print(
        f"✓ Backend messages: {len(backend_messages)}, Frontend messages: {len(frontend_messages)}"
    )

    # Test conversation summary
    summary = conversation.get_conversation_summary()
    print(
        f"✓ Conversation summary: {summary['message_count']} messages, {summary['participant_count']} participants"
    )


@pytest.mark.asyncio
async def test_conversation_database():
    """Test conversation database functionality."""

    print("\n=== Testing Conversation Database ===")

    # Use temporary file database for testing to avoid in-memory connection issues
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        db = DatabaseManager(tmp_db_path)

        # Create test conversation
        conversation = Conversation(
            title="Cross-repo Testing Strategy",
            description="Discussing testing approaches for frontend and backend",
            repositories=["frontend", "backend"],
        )

        # Add participants
        frontend_dev = ConversationParticipant(
            name="Bob Frontend", role="frontend-developer", repository="frontend"
        )
        backend_dev = ConversationParticipant(
            name="Carol Backend", role="backend-developer", repository="backend"
        )
        conversation.participants = [frontend_dev, backend_dev]

        # Add messages
        conversation.add_message(
            participant_id=frontend_dev.id,
            content="We need to ensure our testing strategy covers integration points.",
            message_type="text",
            repository_context="frontend",
        )

        conversation.add_message(
            participant_id=backend_dev.id,
            content="Agreed. Let's define clear API contracts for testing.",
            message_type="text",
            repository_context="backend",
        )

        # Save to database
        saved_id = db.save_conversation(conversation)
        print(f"✓ Saved conversation to database: {saved_id}")

        # Retrieve from database
        retrieved_conv = db.get_conversation(saved_id)
        assert retrieved_conv is not None
        print(f"✓ Retrieved conversation: {retrieved_conv.title}")
        print(f"  - Participants: {len(retrieved_conv.participants)}")
        print(f"  - Messages: {len(retrieved_conv.messages)}")

        # Test listing conversations
        conversations = db.list_conversations()
        print(f"✓ Listed conversations: {len(conversations)} found")

        # Test filtering by repository
        backend_conversations = db.get_conversations_by_repository("backend")
        print(f"✓ Backend conversations: {len(backend_conversations)} found")

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_db_path):
            os.unlink(tmp_db_path)


@pytest.mark.asyncio
async def test_conversation_manager():
    """Test conversation manager functionality."""

    print("\n=== Testing Conversation Manager ===")

    # Use temporary file database for testing
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        # Create manager with custom database
        manager = ConversationManager()
        manager.database = DatabaseManager(tmp_db_path)
        # Mock the context reader to avoid GitHub API calls
        manager.context_reader.get_repository_context = AsyncMock(return_value=None)

        # Create a conversation
        conversation = await manager.create_conversation(
            title="API Versioning Strategy",
            description="Discussing versioning strategy across all repositories",
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
        print(f"✓ Created conversation: {conversation.id}")

        # Add another participant
        participant = await manager.add_participant(
            conversation_id=conversation.id,
            name="Frontend Lead",
            role="frontend-lead",
            repository="frontend",
        )
        print(f"✓ Added participant: {participant.name}")

        # Add a regular message
        message = await manager.add_message(
            conversation_id=conversation.id,
            participant_id=participant.id,
            content="For the frontend, we should ensure backward compatibility for at least 2 versions.",
            message_type="text",
            repository_context="frontend",
        )
        print(f"✓ Added message: {message.id}")

        # Add a context message
        context_msg = await manager.add_context_message(
            conversation_id=conversation.id,
            participant_id=participant.id,
            repository="frontend",
            context_summary="Current frontend uses React 18 with TypeScript. API calls are centralized in a service layer.",
        )
        print(f"✓ Added context message: {context_msg.id}")

        # Add a decision message
        decision_msg = await manager.add_decision_message(
            conversation_id=conversation.id,
            participant_id=conversation.participants[0].id,  # System Architect
            decision="We will implement semantic versioning with a 2-version backward compatibility policy.",
            repositories_affected=["backend", "frontend", "mobile"],
        )
        print(f"✓ Added decision message: {decision_msg.id}")

        # Get conversation history
        history = manager.get_conversation_history(conversation.id)
        print(f"✓ Got conversation history: {len(history['messages'])} messages")

        # Get cross-repository insights
        insights = await manager.get_cross_repository_insights(conversation.id)
        print(
            f"✓ Generated insights: {len(insights['key_decisions'])} decisions, {len(insights['repository_impacts'])} repositories"
        )

        # List conversations
        all_conversations = manager.list_conversations()
        frontend_conversations = manager.list_conversations(repository="frontend")
        print(
            f"✓ Listed conversations: {len(all_conversations)} total, {len(frontend_conversations)} for frontend"
        )

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_db_path):
            os.unlink(tmp_db_path)


@pytest.mark.asyncio
async def test_mcp_conversation_endpoints():
    """Test MCP server conversation endpoints."""

    print("\n=== Testing MCP Conversation Endpoints ===")

    # Use temporary file database for testing
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        server = MCPStoryServer()
        server.conversation_manager.database = DatabaseManager(tmp_db_path)
        # Mock the context reader
        server.conversation_manager.context_reader.get_repository_context = AsyncMock(
            return_value=None
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
        print(f"✓ Created conversation via MCP: {conversation_id}")

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
        participant_id = response.result["participant_id"]
        print(f"✓ Added participant via MCP: {participant_id}")

        # Test adding message
        add_message_request = MCPRequest(
            id="test3",
            method="conversation/add_message",
            params={
                "conversation_id": conversation_id,
                "participant_id": participant_id,
                "content": "We should consider the impact on existing data pipelines.",
                "message_type": "text",
                "repository_context": "data-service",
            },
        )

        response = await server.handle_request(add_message_request)
        assert response.result["success"]
        print(f"✓ Added message via MCP: {response.result['message_id']}")

        # Test getting conversation
        get_request = MCPRequest(
            id="test4",
            method="conversation/get",
            params={"conversation_id": conversation_id},
        )

        response = await server.handle_request(get_request)
        assert response.result["success"]
        print(
            f"✓ Retrieved conversation via MCP: {response.result['conversation']['title']}"
        )

        # Test listing conversations
        list_request = MCPRequest(
            id="test5", method="conversation/list", params={"repository": "backend"}
        )

        response = await server.handle_request(list_request)
        assert response.result["success"]
        print(f"✓ Listed conversations via MCP: {response.result['total_count']} found")

        # Test getting history
        history_request = MCPRequest(
            id="test6",
            method="conversation/history",
            params={"conversation_id": conversation_id},
        )

        response = await server.handle_request(history_request)
        assert response.result["success"]
        print(
            f"✓ Got conversation history via MCP: {len(response.result['history']['messages'])} messages"
        )

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_db_path):
            os.unlink(tmp_db_path)


async def run_all_tests():
    """Run all conversation tests."""

    print("🧪 Running Cross-Repository Conversation System Tests")
    print("=" * 60)

    try:
        await test_conversation_models()
        await test_conversation_database()
        await test_conversation_manager()
        await test_mcp_conversation_endpoints()

        print("\n" + "=" * 60)
        print("✅ All conversation tests passed successfully!")
        print("\nImplemented Features:")
        print("- Cross-repository conversation data models")
        print("- Database schema and persistence for conversations")
        print("- Conversation management with context sharing")
        print("- MCP server endpoints for conversation operations")
        print("- Repository-specific conversation filtering")
        print("- Conversation history and cross-repository insights")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
