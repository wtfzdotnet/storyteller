"""Test cases for the Epic Management API."""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd  # Added import for pandas
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

    # --- Roadmap Import API Tests ---

    def _create_temp_file_for_upload(self, content: str, filename: str) -> Path:
        """Helper to create a temporary file with content."""
        # Use the same temp directory as the database for consistency, or a new one
        temp_dir = Path(self.temp_file.name).parent
        file_path = temp_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def test_import_roadmap_csv_success(self):
        """Test successful roadmap import from CSV."""
        csv_content = (
            "type,id,parent_id,title,description\n"
            "epic,E1,,Epic CSV,First epic from CSV\n"
            "user_story,US1,E1,User Story CSV,First US for E1 from CSV"
        )
        csv_file_path = self._create_temp_file_for_upload(csv_content, "roadmap.csv")

        with open(csv_file_path, "rb") as f:
            response = self.client.post(
                "/roadmap/import?file_format=csv",
                files={"file": ("roadmap.csv", f, "text/csv")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Roadmap imported successfully", data["message"])
        self.assertEqual(
            data["epics_created"], 1
        )  # This depends on the actual parsing logic of _parse_row and _build_hierarchies
        self.assertEqual(data["user_stories_created"], 1)  # Same as above

        # Cleanup temp file
        csv_file_path.unlink(missing_ok=True)

    def test_import_roadmap_json_success(self):
        """Test successful roadmap import from JSON."""
        json_content = json.dumps(
            [
                {
                    "id": "EPJ1",
                    "title": "Epic JSON",
                    "description": "Epic from JSON",
                    "user_stories": [
                        {
                            "id": "USJ1",
                            "title": "User Story JSON",
                            "description": "US for EPJ1 from JSON",
                        }
                    ],
                }
            ]
        )
        json_file_path = self._create_temp_file_for_upload(json_content, "roadmap.json")

        with open(json_file_path, "rb") as f:
            response = self.client.post(
                "/roadmap/import?file_format=json",
                files={"file": ("roadmap.json", f, "application/json")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Roadmap imported successfully", data["message"])
        self.assertEqual(data["epics_created"], 1)
        self.assertEqual(data["user_stories_created"], 1)

        json_file_path.unlink(missing_ok=True)

    def test_import_roadmap_excel_success(self):
        """Test successful roadmap import from Excel."""
        # Create a dummy Excel file using pandas
        excel_data = pd.DataFrame(
            [
                {
                    "type": "epic",
                    "id": "EX1",
                    "parent_id": None,
                    "title": "Epic Excel",
                    "description": "Epic from Excel",
                },
                {
                    "type": "user_story",
                    "id": "USX1",
                    "parent_id": "EX1",
                    "title": "User Story Excel",
                    "description": "US for EX1 from Excel",
                },
            ]
        )
        excel_file_path = Path(self.temp_file.name).parent / "roadmap.xlsx"

        with pd.ExcelWriter(str(excel_file_path), engine="openpyxl") as writer:
            excel_data.to_excel(writer, index=False, sheet_name="Sheet1")

        with open(excel_file_path, "rb") as f:
            response = self.client.post(
                "/roadmap/import?file_format=excel",
                files={
                    "file": (
                        "roadmap.xlsx",
                        f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Roadmap imported successfully", data["message"])
        # These counts depend on the full implementation of _parse_row_to_story and _build_story_hierarchies
        self.assertEqual(data["epics_created"], 1)
        self.assertEqual(data["user_stories_created"], 1)

        excel_file_path.unlink(missing_ok=True)

    def test_import_roadmap_preview_mode(self):
        """Test roadmap import in preview mode."""
        json_content = json.dumps(
            [{"id": "EPP1", "title": "Epic Preview"}]
        )  # Minimal valid JSON
        json_file_path = self._create_temp_file_for_upload(json_content, "preview.json")

        with open(json_file_path, "rb") as f:
            response = self.client.post(
                "/roadmap/import?file_format=json&preview=true",
                files={"file": ("preview.json", f, "application/json")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Roadmap import preview generated successfully", data["message"])
        self.assertIsNotNone(data["preview_data"])
        self.assertEqual(
            data["preview_data"]["epics_to_be_created"], 1
        )  # Based on import_from_json logic

        # Verify no epics were actually created in the DB
        db_epics = self.story_manager.get_all_epics()
        self.assertEqual(len(db_epics), 0)

        json_file_path.unlink(missing_ok=True)

    def test_import_roadmap_unsupported_format(self):
        """Test roadmap import with an unsupported file format."""
        txt_content = "This is not a valid roadmap format."
        txt_file_path = self._create_temp_file_for_upload(txt_content, "roadmap.txt")

        with open(txt_file_path, "rb") as f:
            response = self.client.post(
                "/roadmap/import?file_format=txt",
                files={"file": ("roadmap.txt", f, "text/plain")},
            )

        self.assertEqual(
            response.status_code, 400
        )  # Expecting ValueError to be caught by API
        data = response.json()
        self.assertIn("Unsupported file format: txt", data["detail"])

        txt_file_path.unlink(missing_ok=True)

    def test_import_roadmap_file_parse_error(self):
        """Test roadmap import with a file that causes a parsing error (e.g., malformed JSON)."""
        malformed_json_content = "{'id': 'EPError', 'title': 'Malformed JSON"  # Missing closing brace and quotes
        json_file_path = self._create_temp_file_for_upload(
            malformed_json_content, "malformed.json"
        )

        with open(json_file_path, "rb") as f:
            response = self.client.post(
                "/roadmap/import?file_format=json",
                files={"file": ("malformed.json", f, "application/json")},
            )

        self.assertEqual(
            response.status_code, 400
        )  # From JSONDecodeError in importer, caught by StoryManager
        data = response.json()
        self.assertIn(
            "Failed to import roadmap", data["detail"]
        )  # Generic message from StoryManager
        self.assertIn("Error decoding JSON", data["detail"])  # Specific error part

        json_file_path.unlink(missing_ok=True)


if __name__ == "__main__":
    # Set minimal environment variables for testing
    import os

    os.environ["GITHUB_TOKEN"] = "test_token"
    os.environ["DEFAULT_LLM_PROVIDER"] = "github"

    # Need openpyxl for Excel tests if pandas is used in main code
    try:
        import openpyxl
    except ImportError:
        print(
            "WARNING: openpyxl not found, Excel import tests might be affected or main code might fail."
        )
        print("Install with: pip install openpyxl")

    unittest.main()
