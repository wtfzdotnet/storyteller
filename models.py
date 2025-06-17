"""Hierarchical data models for Epic → User Story → Sub-story management."""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class StoryStatus(Enum):
    """Status enumeration for stories at all levels."""

    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


class StoryType(Enum):
    """Type enumeration for hierarchical story levels."""

    EPIC = "epic"
    USER_STORY = "user_story"
    SUB_STORY = "sub_story"


@dataclass
class BaseStory:
    """Base class for all story types with common fields."""

    id: str = field(default_factory=lambda: f"story_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    status: StoryStatus = StoryStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert story to dictionary for database storage."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class Epic(BaseStory):
    """Epic story - highest level in the hierarchy."""

    business_value: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    target_repositories: List[str] = field(default_factory=list)
    estimated_duration_weeks: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert epic to dictionary for database storage."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "story_type": StoryType.EPIC.value,
                "parent_id": None,
                "business_value": self.business_value,
                "acceptance_criteria": json.dumps(self.acceptance_criteria),
                "target_repositories": json.dumps(self.target_repositories),
                "estimated_duration_weeks": self.estimated_duration_weeks,
            }
        )
        return base_dict


@dataclass
class UserStory(BaseStory):
    """User Story - middle level, belongs to an Epic."""

    epic_id: str = ""
    user_persona: str = ""
    user_goal: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    target_repositories: List[str] = field(default_factory=list)
    story_points: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert user story to dictionary for database storage."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "story_type": StoryType.USER_STORY.value,
                "parent_id": self.epic_id,
                "user_persona": self.user_persona,
                "user_goal": self.user_goal,
                "acceptance_criteria": json.dumps(self.acceptance_criteria),
                "target_repositories": json.dumps(self.target_repositories),
                "story_points": self.story_points,
            }
        )
        return base_dict


@dataclass
class SubStory(BaseStory):
    """Sub-story - lowest level, belongs to a User Story."""

    user_story_id: str = ""
    department: str = ""  # e.g., "frontend", "backend", "testing", "devops"
    technical_requirements: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    target_repository: str = ""
    assignee: Optional[str] = None
    estimated_hours: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert sub-story to dictionary for database storage."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "story_type": StoryType.SUB_STORY.value,
                "parent_id": self.user_story_id,
                "department": self.department,
                "technical_requirements": json.dumps(self.technical_requirements),
                "dependencies": json.dumps(self.dependencies),
                "target_repository": self.target_repository,
                "assignee": self.assignee,
                "estimated_hours": self.estimated_hours,
            }
        )
        return base_dict


@dataclass
class StoryHierarchy:
    """Complete story hierarchy representation."""

    epic: Epic
    user_stories: List[UserStory] = field(default_factory=list)
    sub_stories: Dict[str, List[SubStory]] = field(
        default_factory=dict
    )  # keyed by user_story_id

    def get_all_stories(self) -> List[BaseStory]:
        """Get all stories in the hierarchy as a flat list."""
        stories = [self.epic]
        stories.extend(self.user_stories)
        for sub_story_list in self.sub_stories.values():
            stories.extend(sub_story_list)
        return stories

    def get_user_story_progress(self, user_story_id: str) -> Dict[str, Any]:
        """Calculate progress for a specific user story based on sub-stories."""
        sub_stories = self.sub_stories.get(user_story_id, [])
        if not sub_stories:
            return {"total": 0, "completed": 0, "percentage": 0}

        total = len(sub_stories)
        completed = sum(1 for s in sub_stories if s.status == StoryStatus.DONE)
        percentage = (completed / total) * 100 if total > 0 else 0

        return {
            "total": total,
            "completed": completed,
            "percentage": round(percentage, 1),
        }

    def get_epic_progress(self) -> Dict[str, Any]:
        """Calculate overall epic progress based on user stories."""
        if not self.user_stories:
            return {"total": 0, "completed": 0, "percentage": 0}

        total = len(self.user_stories)
        completed = sum(1 for us in self.user_stories if us.status == StoryStatus.DONE)
        percentage = (completed / total) * 100 if total > 0 else 0

        return {
            "total": total,
            "completed": completed,
            "percentage": round(percentage, 1),
        }
