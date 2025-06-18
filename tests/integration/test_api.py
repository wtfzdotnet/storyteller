"""Test cases for the Epic Management API."""

import json
import tempfile
import unittest
from pathlib import Path

import requests
from api import app
from fastapi.testclient import TestClient
from models import Epic, StoryStatus
from story_manager import StoryManager


class TestEpicAPI(unittest.TestCase):
    """Test cases for Epic API endpoints."""

    def setUp(self):
        """Set up test environment."""
        self.client = TestClient(app)

        # Use temporary database for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()

        # Initialize StoryManager with temporary database
        self.story_manager = StoryManager()
        self.story_manager.database.db_path = Path(self.temp_file.name)
        self.story_manager.database.init_database()

        # Patch the API's get_story_manager function to use our test instance
        import api

        api.story_manager = self.story_manager

    def tearDown(self):
        """Clean up test environment."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_create_epic(self):
        """Test creating an epic."""
        epic_data = {
            "title": "Test Epic",
            "description": "Test epic description",
            "business_value": "High test value",
            "acceptance_criteria": ["AC1", "AC2"],
            "target_repositories": ["test-repo"],
            "estimated_duration_weeks": 3,
        }

        response = self.client.post("/epics", json=epic_data)
        self.assertEqual(response.status_code, 201)

        created_epic = response.json()
        self.assertEqual(created_epic["title"], "Test Epic")
        self.assertEqual(created_epic["description"], "Test epic description")
        self.assertEqual(created_epic["business_value"], "High test value")
        self.assertEqual(created_epic["acceptance_criteria"], ["AC1", "AC2"])
        self.assertEqual(created_epic["target_repositories"], ["test-repo"])
        self.assertEqual(created_epic["estimated_duration_weeks"], 3)
        self.assertEqual(created_epic["status"], "draft")
        self.assertIn("id", created_epic)

    def test_create_epic_minimal(self):
        """Test creating an epic with minimal data."""
        epic_data = {"title": "Minimal Epic", "description": "Minimal description"}

        response = self.client.post("/epics", json=epic_data)
        self.assertEqual(response.status_code, 201)

        created_epic = response.json()
        self.assertEqual(created_epic["title"], "Minimal Epic")
        self.assertEqual(created_epic["business_value"], "")
        self.assertEqual(created_epic["acceptance_criteria"], [])
        self.assertEqual(created_epic["target_repositories"], [])
        self.assertIsNone(created_epic["estimated_duration_weeks"])

    def test_create_epic_validation_error(self):
        """Test epic creation with invalid data."""
        # Missing required title
        epic_data = {"description": "Test description"}

        response = self.client.post("/epics", json=epic_data)
        self.assertEqual(response.status_code, 422)  # Validation error

    def test_get_epic(self):
        """Test retrieving an epic."""
        # Create epic first
        epic = self.story_manager.create_epic(
            title="Test Epic", description="Test description"
        )

        response = self.client.get(f"/epics/{epic.id}")
        self.assertEqual(response.status_code, 200)

        retrieved_epic = response.json()
        self.assertEqual(retrieved_epic["id"], epic.id)
        self.assertEqual(retrieved_epic["title"], "Test Epic")

    def test_get_epic_not_found(self):
        """Test retrieving a non-existent epic."""
        response = self.client.get("/epics/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_list_epics(self):
        """Test listing epics."""
        # Create multiple epics
        epic1 = self.story_manager.create_epic(title="Epic 1", description="Desc 1")
        epic2 = self.story_manager.create_epic(title="Epic 2", description="Desc 2")

        response = self.client.get("/epics")
        self.assertEqual(response.status_code, 200)

        epics_data = response.json()
        self.assertEqual(epics_data["total"], 2)
        self.assertEqual(len(epics_data["epics"]), 2)

        epic_ids = [epic["id"] for epic in epics_data["epics"]]
        self.assertIn(epic1.id, epic_ids)
        self.assertIn(epic2.id, epic_ids)

    def test_list_epics_with_status_filter(self):
        """Test listing epics with status filter."""
        # Create epic and change status
        epic = self.story_manager.create_epic(title="Test Epic", description="Desc")
        self.story_manager.update_story_status(epic.id, StoryStatus.IN_PROGRESS)

        # Filter by status
        response = self.client.get("/epics?status=in_progress")
        self.assertEqual(response.status_code, 200)

        epics_data = response.json()
        self.assertEqual(epics_data["total"], 1)
        self.assertEqual(epics_data["epics"][0]["status"], "in_progress")

    def test_list_epics_with_pagination(self):
        """Test listing epics with pagination."""
        # Create multiple epics
        for i in range(5):
            self.story_manager.create_epic(title=f"Epic {i}", description=f"Desc {i}")

        # Test pagination
        response = self.client.get("/epics?limit=2&offset=1")
        self.assertEqual(response.status_code, 200)

        epics_data = response.json()
        self.assertEqual(epics_data["total"], 5)
        self.assertEqual(len(epics_data["epics"]), 2)

    def test_update_epic(self):
        """Test updating an epic."""
        # Create epic first
        epic = self.story_manager.create_epic(
            title="Original Title", description="Original description"
        )

        # Update epic
        update_data = {"title": "Updated Title", "status": "in_progress"}

        response = self.client.put(f"/epics/{epic.id}", json=update_data)
        self.assertEqual(response.status_code, 200)

        updated_epic = response.json()
        self.assertEqual(updated_epic["title"], "Updated Title")
        self.assertEqual(updated_epic["status"], "in_progress")
        # Original description should remain unchanged
        self.assertEqual(updated_epic["description"], "Original description")

    def test_update_epic_not_found(self):
        """Test updating a non-existent epic."""
        update_data = {"title": "New Title"}

        response = self.client.put("/epics/nonexistent", json=update_data)
        self.assertEqual(response.status_code, 404)

    def test_update_epic_invalid_status(self):
        """Test updating epic with invalid status."""
        epic = self.story_manager.create_epic(title="Test Epic", description="Desc")

        update_data = {"status": "invalid_status"}

        response = self.client.put(f"/epics/{epic.id}", json=update_data)
        self.assertEqual(response.status_code, 400)

    def test_delete_epic(self):
        """Test deleting an epic."""
        # Create epic
        epic = self.story_manager.create_epic(title="Test Epic", description="Desc")

        # Delete epic
        response = self.client.delete(f"/epics/{epic.id}")
        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])

        # Verify epic is deleted
        response = self.client.get(f"/epics/{epic.id}")
        self.assertEqual(response.status_code, 404)

    def test_delete_epic_not_found(self):
        """Test deleting a non-existent epic."""
        response = self.client.delete("/epics/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_get_epic_hierarchy(self):
        """Test retrieving epic hierarchy."""
        # Create epic
        epic = self.story_manager.create_epic(title="Test Epic", description="Desc")

        # Create user story under epic
        user_story = self.story_manager.create_user_story(
            epic_id=epic.id,
            title="Test User Story",
            description="User story description",
        )

        # Get hierarchy
        response = self.client.get(f"/epics/{epic.id}/hierarchy")
        self.assertEqual(response.status_code, 200)

        hierarchy = response.json()
        self.assertEqual(hierarchy["epic"]["id"], epic.id)
        self.assertEqual(len(hierarchy["user_stories"]), 1)
        self.assertEqual(hierarchy["user_stories"][0]["id"], user_story.id)
        self.assertIn("progress", hierarchy)

    def test_get_epic_hierarchy_not_found(self):
        """Test retrieving hierarchy for non-existent epic."""
        response = self.client.get("/epics/nonexistent/hierarchy")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    # Set minimal environment variables for testing
    import os

    os.environ["GITHUB_TOKEN"] = "test_token"
    os.environ["DEFAULT_LLM_PROVIDER"] = "github"

    unittest.main()
