"""Unit tests for conversation system core functionality without external dependencies."""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from conversation_manager import ConversationManager
from database import DatabaseManager
from models import Conversation, ConversationParticipant, Message

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


@pytest.mark.asyncio
async def test_conversation_models():
    """Test conversation data models."""

    # Test ConversationParticipant
    participant = ConversationParticipant(
        name="Alice Developer", role="lead-developer", repository="backend"
    )
    assert participant.name == "Alice Developer"
    assert participant.role == "lead-developer"

    # Test Message
    message = Message(
        conversation_id="test_conv",
        participant_id=participant.id,
        content="This is a test message about backend architecture.",
        message_type="text",
        repository_context="backend",
    )
    assert message.conversation_id == "test_conv"
    assert message.content == "This is a test message about backend architecture."

    # Test Conversation
    conversation = Conversation(
        title="Backend API Design Discussion",
        description="Discussing API design across frontend and backend repositories",
        repositories=["backend", "frontend"],
        participants=[participant],
        messages=[message],
    )
    assert conversation.title == "Backend API Design Discussion"
    assert len(conversation.repositories) == 2


@pytest.mark.asyncio
async def test_conversation_manager_basic():
    """Test ConversationManager basic operations with mocked dependencies."""
    # Use temporary file database for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        manager = ConversationManager()
        manager.database = DatabaseManager(tmp_db_path)
        # Mock the context reader to avoid external API calls
        manager.context_reader = MagicMock()
        manager.context_reader.get_repository_context = AsyncMock(return_value=None)

        # Test conversation creation
        conversation = await manager.create_conversation(
            title="Test Discussion",
            description="Testing conversation creation",
            repositories=["backend"],
            initial_participants=[
                {"name": "Test Developer", "role": "developer", "repository": "backend"}
            ],
        )

        assert conversation.title == "Test Discussion"
        assert len(conversation.participants) == 1
        assert conversation.participants[0].name == "Test Developer"

        # Test message addition
        participant = conversation.participants[0]
        message = await manager.add_message(
            conversation_id=conversation.id,
            participant_id=participant.id,
            content="Test message",
            message_type="text",
        )

        assert message.content == "Test message"
        assert message.message_type == "text"

        # Test conversation retrieval
        retrieved = manager.get_conversation(conversation.id)
        assert retrieved is not None
        assert retrieved.title == "Test Discussion"

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_db_path):
            os.unlink(tmp_db_path)


def test_conversation_filtering():
    """Test conversation repository filtering methods."""
    # Create participants for different repositories
    backend_participant = ConversationParticipant(
        name="Backend Dev", role="lead-developer", repository="backend"
    )
    frontend_participant = ConversationParticipant(
        name="Frontend Dev", role="lead-developer", repository="frontend"
    )

    # Create messages for different repositories
    backend_message = Message(
        conversation_id="test_conv",
        participant_id=backend_participant.id,
        content="Backend considerations",
        repository_context="backend",
    )
    frontend_message = Message(
        conversation_id="test_conv",
        participant_id=frontend_participant.id,
        content="Frontend requirements",
        repository_context="frontend",
    )

    conversation = Conversation(
        title="Feature Planning",
        repositories=["backend", "frontend"],
        participants=[backend_participant, frontend_participant],
        messages=[backend_message, frontend_message],
    )

    # Test participant filtering
    backend_participants = conversation.get_participants_by_repository("backend")
    assert len(backend_participants) == 1
    assert backend_participants[0].name == "Backend Dev"

    # Test message filtering
    backend_messages = conversation.get_messages_by_repository("backend")
    assert len(backend_messages) == 1
    assert "Backend considerations" in backend_messages[0].content