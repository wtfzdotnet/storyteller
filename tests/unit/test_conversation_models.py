"""Basic unit tests for conversation system models and core functionality."""

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


def test_conversation_participant_model():
    """Test ConversationParticipant data model."""
    participant = ConversationParticipant(
        name="Alice Developer", role="lead-developer", repository="backend"
    )

    assert participant.name == "Alice Developer"
    assert participant.role == "lead-developer"
    assert participant.repository == "backend"
    assert participant.id is not None


def test_message_model():
    """Test Message data model."""
    participant = ConversationParticipant(
        name="Bob Designer", role="ux-designer", repository="frontend"
    )

    message = Message(
        conversation_id="test_conv",
        participant_id=participant.id,
        content="This is a test message about UI design.",
        message_type="text",
        repository_context="frontend",
    )

    assert message.conversation_id == "test_conv"
    assert message.participant_id == participant.id
    assert message.content == "This is a test message about UI design."
    assert message.message_type == "text"
    assert message.repository_context == "frontend"
    assert message.id is not None


def test_conversation_model():
    """Test Conversation data model."""
    participant = ConversationParticipant(
        name="Charlie Architect", role="system-architect"
    )

    message = Message(
        conversation_id="test_conv",
        participant_id=participant.id,
        content="Let's discuss the system architecture.",
        message_type="text",
    )

    conversation = Conversation(
        title="System Architecture Discussion",
        description="Planning system-wide architectural decisions",
        repositories=["backend", "frontend", "mobile"],
        participants=[participant],
        messages=[message],
    )

    assert conversation.title == "System Architecture Discussion"
    assert conversation.repositories == ["backend", "frontend", "mobile"]
    assert len(conversation.participants) == 1
    assert len(conversation.messages) == 1
    assert conversation.status == "active"


def test_conversation_repository_filtering():
    """Test repository-specific filtering methods."""
    # Create participants for different repositories
    backend_participant = ConversationParticipant(
        name="Backend Dev", role="lead-developer", repository="backend"
    )
    frontend_participant = ConversationParticipant(
        name="Frontend Dev", role="lead-developer", repository="frontend"
    )
    general_participant = ConversationParticipant(
        name="Product Manager", role="product-manager"
    )

    # Create messages for different repositories
    backend_message = Message(
        conversation_id="test_conv",
        participant_id=backend_participant.id,
        content="Backend API considerations",
        repository_context="backend",
    )
    frontend_message = Message(
        conversation_id="test_conv",
        participant_id=frontend_participant.id,
        content="Frontend UI concerns",
        repository_context="frontend",
    )
    general_message = Message(
        conversation_id="test_conv",
        participant_id=general_participant.id,
        content="General product requirements",
    )

    conversation = Conversation(
        title="Feature Planning",
        repositories=["backend", "frontend"],
        participants=[backend_participant, frontend_participant, general_participant],
        messages=[backend_message, frontend_message, general_message],
    )

    # Test participant filtering
    backend_participants = conversation.get_participants_by_repository("backend")
    assert len(backend_participants) == 1
    assert backend_participants[0].name == "Backend Dev"

    frontend_participants = conversation.get_participants_by_repository("frontend")
    assert len(frontend_participants) == 1
    assert frontend_participants[0].name == "Frontend Dev"

    # Test message filtering
    backend_messages = conversation.get_messages_by_repository("backend")
    assert len(backend_messages) == 1
    assert "Backend API" in backend_messages[0].content

    frontend_messages = conversation.get_messages_by_repository("frontend")
    assert len(frontend_messages) == 1
    assert "Frontend UI" in frontend_messages[0].content


@pytest.mark.asyncio
async def test_conversation_manager_basic_operations():
    """Test basic ConversationManager operations with mocked dependencies."""
    # Use temporary file database for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        # Create manager with mocked context reader
        manager = ConversationManager()
        manager.database = DatabaseManager(tmp_db_path)
        manager.context_reader = MagicMock()
        manager.context_reader.get_repository_context = AsyncMock(return_value=None)

        # Test conversation creation
        conversation = await manager.create_conversation(
            title="Test Conversation",
            description="Testing basic operations",
            repositories=["backend"],
            initial_participants=[
                {"name": "Test User", "role": "developer", "repository": "backend"}
            ],
        )

        assert conversation.title == "Test Conversation"
        assert len(conversation.participants) == 1
        assert conversation.participants[0].name == "Test User"

        # Test participant addition
        participant = await manager.add_participant(
            conversation_id=conversation.id,
            name="Second User",
            role="tester",
            repository="backend",
        )

        assert participant.name == "Second User"
        assert participant.role == "tester"

        # Test message addition
        message = await manager.add_message(
            conversation_id=conversation.id,
            participant_id=participant.id,
            content="Test message content",
            message_type="text",
        )

        assert message.content == "Test message content"
        assert message.message_type == "text"

        # Test conversation retrieval
        retrieved_conversation = manager.get_conversation(conversation.id)
        assert retrieved_conversation is not None
        assert retrieved_conversation.title == "Test Conversation"

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_db_path):
            os.unlink(tmp_db_path)


def test_message_types():
    """Test different message types."""
    participant = ConversationParticipant(name="Test User", role="developer")

    # Test text message
    text_message = Message(
        conversation_id="test",
        participant_id=participant.id,
        content="Regular text message",
        message_type="text",
    )
    assert text_message.message_type == "text"

    # Test context share message
    context_message = Message(
        conversation_id="test",
        participant_id=participant.id,
        content="Sharing repository context",
        message_type="context_share",
        repository_context="backend",
    )
    assert context_message.message_type == "context_share"
    assert context_message.repository_context == "backend"

    # Test decision message
    decision_message = Message(
        conversation_id="test",
        participant_id=participant.id,
        content="Final decision on architecture",
        message_type="decision",
    )
    assert decision_message.message_type == "decision"

    # Test system message
    system_message = Message(
        conversation_id="test",
        participant_id=participant.id,
        content="System notification",
        message_type="system",
    )
    assert system_message.message_type == "system"
