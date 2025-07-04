import json
import os
import unittest

from src.storyteller.database import DatabaseManager
from src.storyteller.models import StoryStatus, UserStory  # Using UserStory for testing


class TestDatabaseManagerExtensions(unittest.TestCase):
    DB_PATH = "test_storyteller_extensions.db"

    def setUp(self):
        # Ensure a clean database for each test
        if os.path.exists(self.DB_PATH):
            os.remove(self.DB_PATH)
        self.db_manager = DatabaseManager(db_path=self.DB_PATH)

    def tearDown(self):
        if os.path.exists(self.DB_PATH):
            os.remove(self.DB_PATH)

    def test_save_and_get_story_with_new_contribution_fields(self):
        story_id = "us_contrib_test_001"
        story = UserStory(
            id=story_id,
            title="Story with Contributions",
            description="Testing new contribution fields in DB",
            status=StoryStatus.DRAFT,
            epic_id="epic_contrib_001",
        )

        ac_contrib_data = [{"role_name": "PO", "contribution_text": "AC1 from PO"}]
        test_req_data = [{"role_name": "QA", "requirement_text": "TR1 from QA"}]
        effort_est_data = [
            {"role_name": "Dev", "estimate_value": 5.0, "estimate_unit": "points"}
        ]

        story.acceptance_criteria_contributions = ac_contrib_data
        story.testing_requirements_contributions = test_req_data
        story.effort_estimates_contributions = effort_est_data

        # Save the story
        saved_id = self.db_manager.save_story(story)
        self.assertEqual(saved_id, story_id)

        # Retrieve the story
        retrieved_story = self.db_manager.get_story(story_id)
        self.assertIsNotNone(retrieved_story)
        self.assertIsInstance(retrieved_story, UserStory)

        # Check the new fields
        self.assertEqual(
            retrieved_story.acceptance_criteria_contributions, ac_contrib_data
        )
        self.assertEqual(
            retrieved_story.testing_requirements_contributions, test_req_data
        )
        self.assertEqual(
            retrieved_story.effort_estimates_contributions, effort_est_data
        )

        # Check that other fields are also fine
        self.assertEqual(retrieved_story.title, "Story with Contributions")

    def test_get_story_with_empty_contribution_fields(self):
        story_id = "us_empty_contrib_002"
        story = UserStory(
            id=story_id,
            title="Story with Empty Contributions",
            description="Testing default empty lists for contributions",
            status=StoryStatus.READY,
            epic_id="epic_empty_002",
        )
        # Default empty lists should be handled by the model itself.
        # No need to explicitly set them to empty lists here.

        saved_id = self.db_manager.save_story(story)
        self.assertEqual(saved_id, story_id)

        retrieved_story = self.db_manager.get_story(story_id)
        self.assertIsNotNone(retrieved_story)

        # Ensure they are empty lists and not None or causing errors
        self.assertEqual(retrieved_story.acceptance_criteria_contributions, [])
        self.assertEqual(retrieved_story.testing_requirements_contributions, [])
        self.assertEqual(retrieved_story.effort_estimates_contributions, [])

    def test_row_to_story_deserialization_of_new_fields(self):
        # This test implicitly tests _row_to_story via get_story
        # We can also test it more directly if we could mock a db row easily,
        # but testing through save/get covers the end-to-end for these fields.

        story_id = "us_deser_test_003"
        original_story = UserStory(id=story_id, title="Deserialization Test")

        original_story.acceptance_criteria_contributions = [{"text": "Test AC"}]
        original_story.testing_requirements_contributions = [{"text": "Test TR"}]
        original_story.effort_estimates_contributions = [{"value": 1}]

        self.db_manager.save_story(original_story)
        retrieved_story = self.db_manager.get_story(story_id)

        self.assertEqual(len(retrieved_story.acceptance_criteria_contributions), 1)
        self.assertEqual(
            retrieved_story.acceptance_criteria_contributions[0]["text"], "Test AC"
        )

        self.assertEqual(len(retrieved_story.testing_requirements_contributions), 1)
        self.assertEqual(
            retrieved_story.testing_requirements_contributions[0]["text"], "Test TR"
        )

        self.assertEqual(len(retrieved_story.effort_estimates_contributions), 1)
        self.assertEqual(retrieved_story.effort_estimates_contributions[0]["value"], 1)


if __name__ == "__main__":
    unittest.main()
