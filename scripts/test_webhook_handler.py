"""Tests for webhook handler functionality."""

import os
from unittest.mock import patch

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


def test_webhook_handler_import():
    """Test that webhook handler can be imported."""
    from config import get_config
    from webhook_handler import WebhookHandler

    config = get_config()
    handler = WebhookHandler(config)
    assert handler is not None
    print("✓ WebhookHandler imports and initializes correctly")


def test_webhook_signature_verification():
    """Test webhook signature verification."""
    import hashlib
    import hmac

    from config import get_config
    from webhook_handler import WebhookHandler

    config = get_config()
    config.webhook_secret = "test_secret"
    handler = WebhookHandler(config)

    # Test payload
    payload = b'{"test": "data"}'

    # Create valid signature
    signature = hmac.new(b"test_secret", payload, hashlib.sha256).hexdigest()
    signature_header = f"sha256={signature}"

    # Test valid signature
    assert handler.verify_signature(payload, signature_header)

    # Test invalid signature
    assert not handler.verify_signature(payload, "sha256=invalid")

    # Test no secret configured
    config.webhook_secret = None
    handler = WebhookHandler(config)
    assert handler.verify_signature(
        payload, signature_header
    )  # Should pass when no secret

    print("✓ Webhook signature verification works correctly")


def test_story_reference_extraction():
    """Test extraction of story references from text."""
    from config import get_config
    from webhook_handler import WebhookHandler

    config = get_config()
    handler = WebhookHandler(config)

    # Test various formats
    text1 = "This fixes story_abc12345"
    assert handler._extract_story_references(text1) == ["story_abc12345"]

    text2 = "Closes #story_def67890 and relates to story_ghi13579"
    refs = handler._extract_story_references(text2)
    assert "story_def67890" in refs
    assert "story_ghi13579" in refs

    text3 = "No story references here"
    assert handler._extract_story_references(text3) == []

    print("✓ Story reference extraction works correctly")


def test_status_mapping_configuration():
    """Test custom status mapping configuration."""
    from config import get_config
    from models import StoryStatus
    from webhook_handler import WebhookHandler

    config = get_config()

    # Add custom status mappings
    config.webhook_config.status_mappings = {
        "pull_request.opened": "in_progress",
        "issues.closed": "done",
    }

    handler = WebhookHandler(config)

    # Check that custom mappings are loaded
    assert handler.status_rules["pull_request.opened"] == StoryStatus.IN_PROGRESS
    assert handler.status_rules["issues.closed"] == StoryStatus.DONE

    print("✓ Custom status mapping configuration works correctly")


async def test_webhook_payload_processing():
    """Test processing of GitHub webhook payloads."""
    from config import get_config
    from models import Epic, StoryStatus
    from webhook_handler import WebhookHandler

    config = get_config()
    handler = WebhookHandler(config)

    # Create a test story first
    epic = Epic(
        id="story_abc12345",
        title="Test Epic",
        description="Test epic for webhook testing",
        status=StoryStatus.DRAFT,
    )
    handler.database.save_story(epic)

    # Mock database methods
    with patch.object(
        handler.database, "get_stories_by_github_issue", return_value=[epic]
    ):

        # Test pull request opened payload
        pr_payload = {
            "action": "opened",
            "pull_request": {
                "number": 123,
                "title": "Fix issue with story_abc12345",
                "body": "This PR fixes story_abc12345",
                "merged": False,
            },
            "repository": {"full_name": "test/repo"},
        }

        result = await handler.handle_webhook(pr_payload)
        assert result["status"] in ["processed", "ignored"]

        print("✓ Webhook payload processing works correctly")


if __name__ == "__main__":
    print("Running webhook handler tests...")
    print("=" * 50)

    try:
        test_webhook_handler_import()
        test_webhook_signature_verification()
        test_story_reference_extraction()
        test_status_mapping_configuration()

        # Run async test
        import asyncio

        asyncio.run(test_webhook_payload_processing())

        print("=" * 50)
        print("✓ All webhook handler tests passed!")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
