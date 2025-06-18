"""Test webhook API endpoints."""

import os

# Set required environment variables for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"

from fastapi.testclient import TestClient

from api import app


def test_webhook_endpoints():
    """Test webhook-related API endpoints."""
    client = TestClient(app)

    print("Testing webhook status endpoint...")
    response = client.get("/webhooks/status")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert "webhook_enabled" in response.json()

    print("\nTesting health endpoint...")
    response = client.get("/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    print("\nTesting transitions endpoint...")
    response = client.get("/transitions")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert "transitions" in response.json()

    print("\n✓ All webhook API endpoints work correctly")


if __name__ == "__main__":
    test_webhook_endpoints()
