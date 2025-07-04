"""Handles importing roadmaps from various file formats."""

import csv
import json
import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd  # We'll add this to requirements.txt later

from .models import Epic, StoryHierarchy, SubStory, UserStory

logger = logging.getLogger(__name__)


class RoadmapImporter:
    """Imports roadmaps and converts them into StoryHierarchy objects."""

    def __init__(self) -> None:
        pass

    def import_from_csv(self, file_path: str) -> List[StoryHierarchy]:
        """
        Imports a roadmap from a CSV file.

        Expected CSV format:
        - Each row represents a story (Epic, UserStory, or SubStory).
        - Columns: type, id, parent_id, title, description, ... (other relevant fields)
        - 'type' column specifies 'epic', 'user_story', or 'sub_story'.
        - 'parent_id' links UserStories to Epics and SubStories to UserStories.
        """
        stories_data: List[Dict[str, Any]] = []
        try:
            with open(
                file_path, mode="r", encoding="utf-8-sig"
            ) as file:  # utf-8-sig to handle BOM
                reader = csv.DictReader(file)
                for row in reader:
                    stories_data.append(row)
        except FileNotFoundError:
            logger.error(f"CSV file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            raise

        if not stories_data:
            return []

        # Convert rows to story objects
        parsed_stories: List[Union[Epic, UserStory, SubStory]] = []
        for row_data in stories_data:
            story = self._parse_row_to_story(row_data)
            if story:
                parsed_stories.append(story)

        # Build hierarchies
        # This part will be more complex and will be refined when _build_story_hierarchies is implemented
        return self._build_story_hierarchies(parsed_stories)

    def import_from_json(self, file_path: str) -> List[StoryHierarchy]:
        """
        Imports a roadmap from a JSON file.

        Expected JSON format:
        - A list of Epics.
        - Each Epic can contain a list of UserStories ('user_stories' key).
        - Each UserStory can contain a list of SubStories ('sub_stories' key).
        """
        logger.info(f"Importing roadmap from JSON: {file_path}")
        hierarchies: List[StoryHierarchy] = []
        try:
            with open(file_path, mode="r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            logger.error(f"JSON file not found: {file_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON file {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading JSON file {file_path}: {e}")
            raise

        if not isinstance(data, list):
            logger.error("JSON root must be a list of epics.")
            # Or handle a single epic object if that's a desired format
            # For now, strictly expecting a list.
            return []

        for epic_data in data:
            if not isinstance(epic_data, dict):
                logger.warning(
                    f"Skipping non-dictionary item in JSON epic list: {epic_data}"
                )
                continue

            # Create Epic
            epic = Epic(
                title=epic_data.get("title", "Untitled Epic"),
                description=epic_data.get("description", ""),
                business_value=epic_data.get("business_value", ""),
                acceptance_criteria=epic_data.get("acceptance_criteria", []),
                target_repositories=epic_data.get("target_repositories", []),
                estimated_duration_weeks=epic_data.get("estimated_duration_weeks"),
                metadata=epic_data.get("metadata", {}),
            )
            if "id" in epic_data:  # Allow specifying ID, otherwise auto-generate
                epic.id = epic_data["id"]

            user_stories: List[UserStory] = []
            sub_stories_map: Dict[str, List[SubStory]] = {}

            # Process UserStories within the Epic
            for us_data in epic_data.get("user_stories", []):
                if not isinstance(us_data, dict):
                    logger.warning(
                        f"Skipping non-dictionary item in user_stories for epic {epic.id}: {us_data}"
                    )
                    continue

                user_story = UserStory(
                    epic_id=epic.id,
                    title=us_data.get("title", "Untitled User Story"),
                    description=us_data.get("description", ""),
                    user_persona=us_data.get("user_persona", ""),
                    user_goal=us_data.get("user_goal", ""),
                    acceptance_criteria=us_data.get("acceptance_criteria", []),
                    target_repositories=us_data.get("target_repositories", []),
                    story_points=us_data.get("story_points"),
                    metadata=us_data.get("metadata", {}),
                )
                if "id" in us_data:
                    user_story.id = us_data["id"]
                user_stories.append(user_story)

                current_sub_stories: List[SubStory] = []
                # Process SubStories within the UserStory
                for ss_data in us_data.get("sub_stories", []):
                    if not isinstance(ss_data, dict):
                        logger.warning(
                            f"Skipping non-dictionary item in sub_stories for user_story {user_story.id}: {ss_data}"
                        )
                        continue

                    sub_story = SubStory(
                        user_story_id=user_story.id,
                        title=ss_data.get("title", "Untitled Sub-Story"),
                        description=ss_data.get("description", ""),
                        department=ss_data.get("department", ""),
                        technical_requirements=ss_data.get(
                            "technical_requirements", []
                        ),
                        dependencies=ss_data.get("dependencies", []),
                        target_repository=ss_data.get("target_repository", ""),
                        assignee=ss_data.get("assignee"),
                        estimated_hours=ss_data.get("estimated_hours"),
                        metadata=ss_data.get("metadata", {}),
                    )
                    if "id" in ss_data:
                        sub_story.id = ss_data["id"]
                    current_sub_stories.append(sub_story)

                if current_sub_stories:
                    sub_stories_map[user_story.id] = current_sub_stories

            hierarchies.append(
                StoryHierarchy(
                    epic=epic, user_stories=user_stories, sub_stories=sub_stories_map
                )
            )

        return hierarchies

    def import_from_excel(
        self, file_path: str, sheet_name: Optional[Union[str, int]] = 0
    ) -> List[StoryHierarchy]:
        """
        Imports a roadmap from an Excel file.

        Supports similar structure to CSV, potentially in a specific sheet.
        Each row represents a story (Epic, UserStory, or SubStory).
        Expected Columns: type, id, parent_id, title, description, ...
        """
        logger.info(f"Importing roadmap from Excel: {file_path}, sheet: {sheet_name}")
        stories_data: List[Dict[str, Any]] = []
        try:
            # Read the specified sheet from the Excel file
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            # Convert NaN to None for easier processing, and then to dict
            stories_data = df.where(pd.notnull(df), None).to_dict(orient="records")
        except FileNotFoundError:
            logger.error(f"Excel file not found: {file_path}")
            raise
        except Exception as e:
            # More specific pandas exceptions could be caught here, e.g., XLRDError, EmptyDataError
            logger.error(
                f"Error reading Excel file {file_path} (sheet: {sheet_name}): {e}"
            )
            raise

        if not stories_data:
            return []

        # Convert rows to story objects
        parsed_stories: List[Union[Epic, UserStory, SubStory]] = []
        for row_data in stories_data:
            # Ensure all keys are strings and handle potential non-string keys from pandas
            processed_row_data = {str(k): v for k, v in row_data.items()}
            story = self._parse_row_to_story(processed_row_data)
            if story:
                parsed_stories.append(story)

        # Build hierarchies
        # This part will be more complex and will be refined when _build_story_hierarchies is implemented
        return self._build_story_hierarchies(parsed_stories)

    def _parse_row_to_story(
        self, row: Dict[str, Any]
    ) -> Union[Epic, UserStory, SubStory, None]:
        """
        Parses a single row (from CSV or Excel) into a story object.
        This is a helper method that will be implemented in detail later.
        """
        story_type = row.get("type", "").lower()
        title = row.get("title", "Untitled Story")
        description = row.get("description", "")

        if story_type == "epic":
            return Epic(title=title, description=description)
        elif story_type == "user_story":
            return UserStory(
                title=title, description=description, epic_id=row.get("parent_id")
            )
        elif story_type == "sub_story":
            return SubStory(
                title=title, description=description, user_story_id=row.get("parent_id")
            )
        else:
            logger.warning(f"Unknown story type '{story_type}' in row: {row}")
            return None

    def _build_story_hierarchies(
        self, stories: List[Union[Epic, UserStory, SubStory]]
    ) -> List[StoryHierarchy]:
        """
        Builds StoryHierarchy objects from a flat list of stories.
        This is a helper method that will be implemented in detail later.
        """
        # Placeholder implementation
        epics = [s for s in stories if isinstance(s, Epic)]
        hierarchies = []
        for epic in epics:
            # Simplified for now, will need to link user stories and sub-stories correctly
            hierarchies.append(StoryHierarchy(epic=epic))
        return hierarchies

    def preview_import(self, file_path: str, file_format: str) -> Dict[str, Any]:
        """
        Previews the import process without actually creating stories.
        Returns a summary of what would be imported.
        """
        logger.info(f"Previewing import for {file_path} (format: {file_format})")
        stories: List[StoryHierarchy] = []
        if file_format == "csv":
            stories = self.import_from_csv(file_path)  # This will be a dry run
        elif file_format == "json":
            stories = self.import_from_json(file_path)  # Dry run
        elif file_format == "excel":
            stories = self.import_from_excel(file_path)  # Dry run
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

        summary = {
            "file_path": file_path,
            "file_format": file_format,
            "epics_to_be_created": 0,
            "user_stories_to_be_created": 0,
            "sub_stories_to_be_created": 0,
            "warnings": [],  # Collect any validation warnings
        }

        for hierarchy in stories:
            summary["epics_to_be_created"] += 1
            summary["user_stories_to_be_created"] += len(hierarchy.user_stories)
            for us_id in hierarchy.sub_stories:
                summary["sub_stories_to_be_created"] += len(
                    hierarchy.sub_stories[us_id]
                )

        # In a real implementation, the import_from_X methods would need a dry_run parameter
        # or a separate set of parsing/validation methods that don't persist.
        # For now, this is a conceptual placeholder.

        if not stories:  # Simulate some data if parsing is not yet implemented
            summary["epics_to_be_created"] = 2  # Dummy data
            summary["user_stories_to_be_created"] = 5  # Dummy data
            summary["sub_stories_to_be_created"] = 10  # Dummy data
            summary["warnings"].append(
                "Preview is using dummy data as full parsing is not yet implemented."
            )

        return summary
