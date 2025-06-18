"""Basic unit tests to ensure core functionality works."""


def test_imports():
    """Test that core modules can be imported without errors."""
    try:
        from config import get_config
        from models import ConversationParticipant
        from multi_repo_context import (
            ContextCache,
            IntelligentFileSelector,
            RepositoryTypeDetector,
        )
        from webhook_handler import WebhookHandler

        # Test instantiation of basic classes
        participant = ConversationParticipant(name="Test", role="developer")
        assert participant.name == "Test"

        detector = RepositoryTypeDetector()
        assert detector is not None

        selector = IntelligentFileSelector()
        assert selector is not None

        cache = ContextCache()
        assert cache is not None

        # Test webhook handler
        config = get_config()
        webhook_handler = WebhookHandler(config)
        assert webhook_handler is not None

    except Exception as e:
        raise AssertionError(f"Import test failed: {e}")


def test_conversation_participant_basic():
    """Test basic ConversationParticipant functionality."""
    from models import ConversationParticipant

    # Test basic creation
    participant = ConversationParticipant(
        name="John Developer", role="lead-developer", repository="backend"
    )

    assert participant.name == "John Developer"
    assert participant.role == "lead-developer"
    assert participant.repository == "backend"
    assert participant.id is not None
    assert len(participant.id) > 0


def test_message_basic():
    """Test basic Message functionality."""
    from models import ConversationParticipant, Message

    participant = ConversationParticipant(name="Test User", role="tester")

    message = Message(
        conversation_id="test_conv_123",
        participant_id=participant.id,
        content="This is a test message",
        message_type="text",
    )

    assert message.conversation_id == "test_conv_123"
    assert message.participant_id == participant.id
    assert message.content == "This is a test message"
    assert message.message_type == "text"
    assert message.id is not None


def test_repository_type_detection_basic():
    """Test basic repository type detection."""
    from multi_repo_context import RepositoryTypeDetector

    detector = RepositoryTypeDetector()

    # Test frontend detection
    frontend_files = ["package.json", "src/App.js", "public/index.html"]
    result = detector.detect_repository_type({}, frontend_files)
    assert result == "frontend"

    # Test backend detection
    backend_files = ["requirements.txt", "app.py", "src/models/user.py"]
    result = detector.detect_repository_type({}, backend_files)
    assert result == "backend"


def test_file_selector_basic():
    """Test basic file selector functionality."""
    from multi_repo_context import IntelligentFileSelector

    selector = IntelligentFileSelector()

    files = [
        ("package.json", "file"),
        ("src/App.js", "file"),
        ("node_modules/react/index.js", "file"),
        ("README.md", "file"),
    ]

    selected = selector.select_important_files("frontend", files, 2)

    # Should select important files and exclude dependencies
    assert "package.json" in selected
    assert "node_modules/react/index.js" not in selected
    assert len(selected) <= 2


def test_cache_basic():
    """Test basic cache functionality."""
    from multi_repo_context import ContextCache

    cache = ContextCache(max_size=2)

    # Test basic set/get
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    # Test eviction
    cache.set("key2", "value2")
    cache.set("key3", "value3")  # Should evict key1

    assert cache.get("key1") is None
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"
