import asyncio
import json
import os
import sys  # Added import for sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from typer.testing import CliRunner

# Adjust sys.path to ensure main and src modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from main import app  # Typer app

# Mock StoryManager for CLI tests to avoid actual DB operations / API calls during CLI command tests
# We want to test the CLI's argument parsing, flow, and output formatting.
# The underlying StoryManager.import_roadmap logic is tested in its own unit/integration tests.


class TestCliRoadmapImport(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = Path(self.test_dir.name)

        # Mock the StoryManager that the CLI command would instantiate
        self.mock_story_manager_instance = MagicMock()
        # The import_roadmap method is async, so use AsyncMock for its return
        self.mock_story_manager_instance.import_roadmap = AsyncMock()

        # Patch the StoryManager class within the main module where the CLI command uses it.
        # The CLI command is `import_roadmap_cli` inside `main.py`.
        # It does `from src.storyteller.story_manager import StoryManager`
        # then `story_manager = StoryManager()`
        # So we need to patch `src.storyteller.story_manager.StoryManager`
        self.story_manager_patcher = patch(
            "src.storyteller.story_manager.StoryManager",
            return_value=self.mock_story_manager_instance,
        )
        self.mock_story_manager_class = self.story_manager_patcher.start()

    def tearDown(self):
        self.test_dir.cleanup()
        self.story_manager_patcher.stop()  # Important to stop the patch

    def _create_temp_file(self, filename: str, content: str = ""):
        file_path = self.test_dir_path / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def test_import_roadmap_csv_success(self):
        """Test CLI roadmap import for CSV successfully."""
        csv_file = self._create_temp_file("test.csv", "header1,header2\nval1,val2")

        # Define what the mocked import_roadmap should return
        self.mock_story_manager_instance.import_roadmap.return_value = {
            "message": "Roadmap imported successfully from CSV.",
            "epics_created": 1,
            "user_stories_created": 2,
            "sub_stories_created": 3,
        }

        result = self.runner.invoke(
            app, ["story", "import-roadmap", str(csv_file), "--format", "csv"]
        )

        self.assertEqual(result.exit_code, 0, result.stdout)
        self.assertIn("Importing roadmap from", result.stdout)
        self.assertIn("Roadmap Import Complete", result.stdout)
        self.assertIn("Roadmap imported successfully from CSV.", result.stdout)
        self.assertIn(
            "Epics                               1", result.stdout
        )  # Typer/Rich table format
        self.mock_story_manager_instance.import_roadmap.assert_called_once_with(
            file_path=str(csv_file), file_format="csv", preview=False
        )

    def test_import_roadmap_json_preview(self):
        """Test CLI roadmap import for JSON in preview mode."""
        json_file = self._create_temp_file("test.json", "[]")  # Empty JSON array

        self.mock_story_manager_instance.import_roadmap.return_value = {
            "file_path": str(json_file),
            "file_format": "json",
            "status": "preview",
            "epics_to_be_created": 2,
            "user_stories_to_be_created": 5,
            "sub_stories_to_be_created": 10,
            "details": [
                {
                    "epic_title": "Preview Epic",
                    "user_stories_count": 2,
                    "sub_stories_count": 3,
                }
            ],
        }

        result = self.runner.invoke(
            app, ["story", "import-roadmap", str(json_file), "-f", "json", "--preview"]
        )

        self.assertEqual(result.exit_code, 0, result.stdout)
        self.assertIn("Roadmap Import Preview", result.stdout)
        self.assertIn("Epics to be created             2", result.stdout)
        self.assertIn("Preview Epic", result.stdout)
        self.mock_story_manager_instance.import_roadmap.assert_called_once_with(
            file_path=str(json_file), file_format="json", preview=True
        )

    def test_import_roadmap_excel_file_not_found(self):
        """Test CLI roadmap import when Excel file does not exist."""
        # No need to mock StoryManager's method here as Typer should catch file existence first
        result = self.runner.invoke(
            app, ["story", "import-roadmap", "nonexistent.xlsx", "-f", "excel"]
        )

        self.assertNotEqual(
            result.exit_code, 0, "CLI should exit with non-zero for missing file"
        )
        self.assertIn(
            "Error: Invalid value for 'FILE_PATH'", result.stdout
        )  # Typer's error message
        self.assertIn("does not exist", result.stdout)

    def test_import_roadmap_unsupported_format_error_from_sm(self):
        """Test CLI when StoryManager returns a ValueError for unsupported format."""
        dummy_file = self._create_temp_file("dummy.txt")

        self.mock_story_manager_instance.import_roadmap.side_effect = ValueError(
            "Unsupported file format: txt"
        )

        result = self.runner.invoke(
            app, ["story", "import-roadmap", str(dummy_file), "-f", "txt"]
        )

        self.assertNotEqual(result.exit_code, 0, result.stdout)
        self.assertIn("Error: Unsupported file format: txt", result.stdout)
        self.mock_story_manager_instance.import_roadmap.assert_called_once_with(
            file_path=str(dummy_file), file_format="txt", preview=False
        )

    def test_import_roadmap_general_error_from_sm(self):
        """Test CLI when StoryManager raises a general exception."""
        dummy_file = self._create_temp_file("dummy.csv")

        self.mock_story_manager_instance.import_roadmap.side_effect = Exception(
            "Something broke badly"
        )

        result = self.runner.invoke(
            app, ["story", "import-roadmap", str(dummy_file), "-f", "csv", "--debug"]
        )  # Enable debug for more output

        self.assertNotEqual(result.exit_code, 0, result.stdout)
        self.assertIn(
            "An unexpected error occurred during roadmap import", result.stdout
        )
        self.assertIn("Something broke badly", result.stdout)  # The exception message
        # If using --debug, the actual traceback might be printed by Typer/Rich, which is fine.

    def test_import_roadmap_missing_format_option(self):
        """Test CLI roadmap import when --format option is missing."""
        dummy_file = self._create_temp_file("dummy.csv")
        result = self.runner.invoke(app, ["story", "import-roadmap", str(dummy_file)])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Error: Missing option '--format' / '-f'", result.stdout
        )  # Typer's error for missing option


if __name__ == "__main__":
    unittest.main()
