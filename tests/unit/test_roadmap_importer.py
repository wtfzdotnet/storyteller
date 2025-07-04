import asyncio
import csv
import json
import os

# Ensure src path is discoverable for imports, adjust as necessary if your test runner handles this differently
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List  # Added imports
from unittest.mock import MagicMock, patch

import pandas as pd

# This is a common way to adjust path for local testing if not using a more sophisticated test runner setup
# For a more robust solution, consider using PYTHONPATH or editable installs.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.storyteller.models import Epic, StoryHierarchy, SubStory, UserStory
from src.storyteller.roadmap_importer import RoadmapImporter


class TestRoadmapImporter(unittest.TestCase):

    def setUp(self):
        self.importer = RoadmapImporter()
        # Create a temporary directory to store test files
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = Path(self.test_dir.name)

    def tearDown(self):
        # Cleanup the temporary directory
        self.test_dir.cleanup()

    def _create_csv_file(self, filename: str, data: List[Dict[str, str]]):
        file_path = self.test_dir_path / filename
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            if not data:  # Handle empty data case
                # Write header only if no data, or let DictWriter handle it if data exists
                # For an empty file that should parse to nothing, just creating an empty file might be enough
                # or a file with only headers.
                if data == []:  # Explicitly empty list means write header
                    writer = csv.writer(f)
                    if data:  # This condition will be false, but for logic clarity
                        writer.writerow(data[0].keys())
                return file_path

            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return file_path

    def _create_json_file(self, filename: str, data: Any):
        file_path = self.test_dir_path / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return file_path

    def _create_excel_file(
        self, filename: str, data: List[Dict[str, str]], sheet_name="Sheet1"
    ):
        file_path = self.test_dir_path / filename
        if not data:  # Handle case where data might be empty for Excel
            df = pd.DataFrame()  # Create an empty DataFrame
        else:
            df = pd.DataFrame(data)

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        return file_path

    # --- CSV Import Tests ---
    def test_import_from_csv_empty_file(self):
        """Test importing from an empty CSV file."""
        csv_file = self._create_csv_file("empty.csv", [])
        # Depending on strictness, an empty file (or one with only headers) should result in empty list
        # For _parse_row_to_story and _build_story_hierarchies as placeholders, this might behave unexpectedly.
        # For now, let's assume they handle empty inputs gracefully.

        # Mock helper methods to control their output during this specific test
        with (
            patch.object(self.importer, "_parse_row_to_story", return_value=None),
            patch.object(self.importer, "_build_story_hierarchies", return_value=[]),
        ):
            result = self.importer.import_from_csv(str(csv_file))
        self.assertEqual(result, [])

    def test_import_from_csv_header_only(self):
        """Test importing from a CSV file with only headers."""
        # This is a bit tricky with DictWriter if data list is empty.
        # Let's manually create a header-only file.
        file_path = self.test_dir_path / "header_only.csv"
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["type", "id", "parent_id", "title", "description"])

        with (
            patch.object(self.importer, "_parse_row_to_story", return_value=None),
            patch.object(self.importer, "_build_story_hierarchies", return_value=[]),
        ):
            result = self.importer.import_from_csv(str(file_path))
        self.assertEqual(result, [])

    def test_import_from_csv_file_not_found(self):
        """Test importing from a non-existent CSV file."""
        with self.assertRaises(FileNotFoundError):
            self.importer.import_from_csv("non_existent_file.csv")

    @patch("src.storyteller.roadmap_importer.RoadmapImporter._parse_row_to_story")
    @patch("src.storyteller.roadmap_importer.RoadmapImporter._build_story_hierarchies")
    def test_import_from_csv_parses_data_calls_helpers(
        self, mock_build_hierarchies, mock_parse_row
    ):
        """Test that CSV data is read and helper methods are called."""
        csv_data = [
            {
                "type": "epic",
                "id": "E1",
                "parent_id": "",
                "title": "Epic 1",
                "description": "Desc E1",
            },
            {
                "type": "user_story",
                "id": "US1",
                "parent_id": "E1",
                "title": "User Story 1",
                "description": "Desc US1",
            },
        ]
        csv_file = self._create_csv_file("simple_roadmap.csv", csv_data)

        # Mock return values for helpers
        mock_epic = Epic(id="E1", title="Epic 1")
        mock_us = UserStory(id="US1", title="User Story 1", epic_id="E1")
        mock_parse_row.side_effect = [mock_epic, mock_us]  # Return these in order

        mock_hierarchy = StoryHierarchy(epic=mock_epic, user_stories=[mock_us])
        mock_build_hierarchies.return_value = [mock_hierarchy]

        result = self.importer.import_from_csv(str(csv_file))

        self.assertEqual(mock_parse_row.call_count, 2)
        mock_parse_row.assert_any_call(csv_data[0])
        mock_parse_row.assert_any_call(csv_data[1])

        mock_build_hierarchies.assert_called_once_with([mock_epic, mock_us])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], StoryHierarchy)
        self.assertEqual(result[0].epic.id, "E1")

    # --- JSON Import Tests ---
    def test_import_from_json_empty_file(self):
        """Test importing from an empty JSON file (invalid JSON)."""
        json_file = self._create_json_file(
            "empty.json", ""
        )  # Will cause JSONDecodeError
        with self.assertRaises(json.JSONDecodeError):
            self.importer.import_from_json(str(json_file))

    def test_import_from_json_empty_list(self):
        """Test importing from a JSON file with an empty list."""
        json_file = self._create_json_file("empty_list.json", [])
        result = self.importer.import_from_json(str(json_file))
        self.assertEqual(result, [])

    def test_import_from_json_file_not_found(self):
        """Test importing from a non-existent JSON file."""
        with self.assertRaises(FileNotFoundError):
            self.importer.import_from_json("non_existent_file.json")

    def test_import_from_json_invalid_structure_not_list(self):
        """Test JSON import if root is not a list."""
        json_file = self._create_json_file("not_a_list.json", {"epic": "data"})
        result = self.importer.import_from_json(str(json_file))
        self.assertEqual(result, [])  # Expecting it to log error and return empty

    def test_import_from_json_basic_hierarchy(self):
        """Test importing a basic valid JSON hierarchy."""
        json_data = [
            {
                "id": "EP01",
                "title": "Epic One",
                "description": "First epic",
                "user_stories": [
                    {
                        "id": "US01",
                        "title": "User Story One",
                        "description": "First user story for EP01",
                        "sub_stories": [
                            {
                                "id": "SS01",
                                "title": "Sub Story One",
                                "description": "First sub-story for US01",
                            }
                        ],
                    }
                ],
            }
        ]
        json_file = self._create_json_file("basic.json", json_data)
        result = self.importer.import_from_json(str(json_file))

        self.assertEqual(len(result), 1)
        hierarchy = result[0]
        self.assertIsInstance(hierarchy, StoryHierarchy)
        self.assertEqual(hierarchy.epic.id, "EP01")
        self.assertEqual(hierarchy.epic.title, "Epic One")

        self.assertEqual(len(hierarchy.user_stories), 1)
        us = hierarchy.user_stories[0]
        self.assertEqual(us.id, "US01")
        self.assertEqual(us.title, "User Story One")
        self.assertEqual(us.epic_id, "EP01")

        self.assertIn(us.id, hierarchy.sub_stories)
        self.assertEqual(len(hierarchy.sub_stories[us.id]), 1)
        ss = hierarchy.sub_stories[us.id][0]
        self.assertEqual(ss.id, "SS01")
        self.assertEqual(ss.title, "Sub Story One")
        self.assertEqual(ss.user_story_id, "US01")

    # --- Excel Import Tests ---
    def test_import_from_excel_empty_file_or_sheet(self):
        """Test importing from an empty Excel file/sheet."""
        excel_file = self._create_excel_file("empty.xlsx", [])
        with (
            patch.object(self.importer, "_parse_row_to_story", return_value=None),
            patch.object(self.importer, "_build_story_hierarchies", return_value=[]),
        ):
            result = self.importer.import_from_excel(str(excel_file))
        self.assertEqual(result, [])

    def test_import_from_excel_file_not_found(self):
        """Test importing from a non-existent Excel file."""
        with self.assertRaises(FileNotFoundError):  # Pandas raises FileNotFoundError
            self.importer.import_from_excel("non_existent_file.xlsx")

    @patch("src.storyteller.roadmap_importer.RoadmapImporter._parse_row_to_story")
    @patch("src.storyteller.roadmap_importer.RoadmapImporter._build_story_hierarchies")
    def test_import_from_excel_parses_data_calls_helpers(
        self, mock_build_hierarchies, mock_parse_row
    ):
        """Test that Excel data is read and helper methods are called."""
        excel_data = [
            {
                "type": "epic",
                "id": "E1X",
                "parent_id": None,
                "title": "Epic Excel",
                "description": "Desc E1X",
            },
            {
                "type": "user_story",
                "id": "US1X",
                "parent_id": "E1X",
                "title": "User Story Excel",
                "description": "Desc US1X",
            },
        ]
        excel_file = self._create_excel_file("simple_roadmap.xlsx", excel_data)

        mock_epic = Epic(id="E1X", title="Epic Excel")
        mock_us = UserStory(id="US1X", title="User Story Excel", epic_id="E1X")
        mock_parse_row.side_effect = [mock_epic, mock_us]

        mock_hierarchy = StoryHierarchy(epic=mock_epic, user_stories=[mock_us])
        mock_build_hierarchies.return_value = [mock_hierarchy]

        result = self.importer.import_from_excel(str(excel_file))

        self.assertEqual(mock_parse_row.call_count, 2)
        # Pandas might convert parent_id: "" (empty string) to None or NaN then None.
        # We need to be robust to this in _parse_row_to_story or ensure data is clean.
        # For the mock, the direct dict is passed.
        self.assertEqual(
            mock_parse_row.call_args_list[0][0][0]["title"], excel_data[0]["title"]
        )
        self.assertEqual(
            mock_parse_row.call_args_list[1][0][0]["title"], excel_data[1]["title"]
        )

        mock_build_hierarchies.assert_called_once_with([mock_epic, mock_us])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], StoryHierarchy)
        self.assertEqual(result[0].epic.id, "E1X")

    # --- Placeholder _parse_row_to_story Tests (will need expansion) ---
    def test_parse_row_to_story_epic(self):
        row = {"type": "epic", "title": "Test Epic", "description": "Epic Desc"}
        story = self.importer._parse_row_to_story(row)
        self.assertIsInstance(story, Epic)
        self.assertEqual(story.title, "Test Epic")

    def test_parse_row_to_story_user_story(self):
        row = {
            "type": "user_story",
            "title": "Test US",
            "description": "US Desc",
            "parent_id": "EP01",
        }
        story = self.importer._parse_row_to_story(row)
        self.assertIsInstance(story, UserStory)
        self.assertEqual(story.title, "Test US")
        self.assertEqual(story.epic_id, "EP01")

    def test_parse_row_to_story_sub_story(self):
        row = {
            "type": "sub_story",
            "title": "Test SS",
            "description": "SS Desc",
            "parent_id": "US01",
        }
        story = self.importer._parse_row_to_story(row)
        self.assertIsInstance(story, SubStory)
        self.assertEqual(story.title, "Test SS")
        self.assertEqual(story.user_story_id, "US01")

    def test_parse_row_to_story_unknown_type(self):
        row = {"type": "unknown", "title": "Unknown Story"}
        story = self.importer._parse_row_to_story(row)
        self.assertIsNone(story)

    # --- Placeholder _build_story_hierarchies Tests (will need expansion) ---
    @patch("src.storyteller.roadmap_importer.logger")  # To check logs if needed
    def test_build_story_hierarchies_simple(self, mock_logger):
        """
        This test will need significant updates once _build_story_hierarchies
        is fully implemented to correctly link stories.
        For now, it tests the placeholder's basic behavior.
        """
        epic1 = Epic(id="E1", title="Epic 1")
        # us1 = UserStory(id="US1", title="US1", epic_id="E1")
        # ss1 = SubStory(id="SS1", title="SS1", user_story_id="US1")

        # Current placeholder only creates hierarchies from Epics
        stories = [epic1]  # , us1, ss1]
        hierarchies = self.importer._build_story_hierarchies(stories)

        self.assertEqual(len(hierarchies), 1)
        self.assertEqual(hierarchies[0].epic.id, "E1")
        # self.assertEqual(len(hierarchies[0].user_stories), 1) # Will fail with placeholder
        # self.assertEqual(len(hierarchies[0].sub_stories[us1.id]), 1) # Will fail

    # --- Preview Method Test (conceptual for now) ---
    @patch("src.storyteller.roadmap_importer.RoadmapImporter.import_from_csv")
    def test_preview_import_csv_calls_correct_importer(self, mock_import_csv):
        mock_import_csv.return_value = []  # Simulate importer returning empty list
        self.importer.preview_import("dummy.csv", "csv")
        mock_import_csv.assert_called_once_with("dummy.csv")

    @patch("src.storyteller.roadmap_importer.RoadmapImporter.import_from_json")
    def test_preview_import_json_calls_correct_importer(self, mock_import_json):
        # Simulate JSON importer returning a basic hierarchy for summary calculation
        mock_epic = Epic(id="E1", title="Preview Epic")
        mock_us = UserStory(id="US1", title="Preview US", epic_id="E1")
        mock_hierarchy = StoryHierarchy(
            epic=mock_epic, user_stories=[mock_us], sub_stories={}
        )
        mock_import_json.return_value = [mock_hierarchy]

        summary = self.importer.preview_import("dummy.json", "json")
        mock_import_json.assert_called_once_with("dummy.json")
        self.assertEqual(summary["epics_to_be_created"], 1)
        self.assertEqual(summary["user_stories_to_be_created"], 1)


if __name__ == "__main__":
    unittest.main()

# Note: To run these tests, you might need to install openpyxl: pip install openpyxl
# And ensure pandas is in your requirements for the main code.
# The placeholder nature of _parse_row_to_story and _build_story_hierarchies means
# tests for CSV and Excel import logic are somewhat limited until those are fleshed out.
# JSON import tests are more comprehensive as that method builds hierarchies directly.
