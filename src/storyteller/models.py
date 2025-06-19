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

    def get_cross_repository_progress(self) -> Dict[str, Any]:
        """Calculate progress aggregated across all target repositories."""
        repository_progress = {}

        # Aggregate repositories from epic and user stories
        all_repositories = set(self.epic.target_repositories)
        for user_story in self.user_stories:
            all_repositories.update(user_story.target_repositories)

        # Add repositories from sub-stories
        for sub_story_list in self.sub_stories.values():
            for sub_story in sub_story_list:
                if sub_story.target_repository:
                    all_repositories.add(sub_story.target_repository)

        # Calculate progress per repository
        for repository in all_repositories:
            repo_data = self._calculate_repository_progress(repository)
            if repo_data["total"] > 0:  # Only include repos with actual work
                repository_progress[repository] = repo_data

        # Calculate overall cross-repository summary
        total_items = sum(repo["total"] for repo in repository_progress.values())
        completed_items = sum(
            repo["completed"] for repo in repository_progress.values()
        )
        overall_percentage = (
            (completed_items / total_items * 100) if total_items > 0 else 0
        )

        return {
            "overall": {
                "total": total_items,
                "completed": completed_items,
                "percentage": round(overall_percentage, 1),
                "repositories_involved": len(repository_progress),
            },
            "by_repository": repository_progress,
        }

    def _calculate_repository_progress(self, repository: str) -> Dict[str, Any]:
        """Calculate progress for a specific repository."""
        total = 0
        completed = 0

        # Count user stories targeting this repository
        for user_story in self.user_stories:
            if repository in user_story.target_repositories:
                total += 1
                if user_story.status == StoryStatus.DONE:
                    completed += 1

        # Count sub-stories targeting this repository
        for sub_story_list in self.sub_stories.values():
            for sub_story in sub_story_list:
                if sub_story.target_repository == repository:
                    total += 1
                    if sub_story.status == StoryStatus.DONE:
                        completed += 1

        percentage = (completed / total * 100) if total > 0 else 0

        return {
            "total": total,
            "completed": completed,
            "percentage": round(percentage, 1),
            "status": self._get_repository_status(completed, total),
        }

    def _get_repository_status(self, completed: int, total: int) -> str:
        """Determine repository status based on completion."""
        if total == 0:
            return "not_started"
        elif completed == 0:
            return "not_started"
        elif completed == total:
            return "completed"
        else:
            return "in_progress"

    def get_repository_specific_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for each repository involved in the epic."""
        metrics = {}

        # Get all repositories involved
        all_repositories = set(self.epic.target_repositories)
        for user_story in self.user_stories:
            all_repositories.update(user_story.target_repositories)

        for sub_story_list in self.sub_stories.values():
            for sub_story in sub_story_list:
                if sub_story.target_repository:
                    all_repositories.add(sub_story.target_repository)

        # Calculate detailed metrics per repository
        for repository in all_repositories:
            metrics[repository] = self._get_detailed_repository_metrics(repository)

        return metrics

    def _get_detailed_repository_metrics(self, repository: str) -> Dict[str, Any]:
        """Get detailed metrics for a specific repository."""
        user_stories_in_repo = []
        sub_stories_in_repo = []

        # Collect user stories for this repository
        for user_story in self.user_stories:
            if repository in user_story.target_repositories:
                user_stories_in_repo.append(user_story)

        # Collect sub-stories for this repository
        for sub_story_list in self.sub_stories.values():
            for sub_story in sub_story_list:
                if sub_story.target_repository == repository:
                    sub_stories_in_repo.append(sub_story)

        # Calculate status distribution
        status_distribution = self._calculate_status_distribution(
            user_stories_in_repo + sub_stories_in_repo
        )

        # Calculate estimated hours (for sub-stories that have it)
        total_estimated_hours = sum(
            sub_story.estimated_hours or 0
            for sub_story in sub_stories_in_repo
            if sub_story.estimated_hours
        )

        # Calculate department breakdown for sub-stories
        department_breakdown = {}
        for sub_story in sub_stories_in_repo:
            dept = sub_story.department or "unassigned"
            if dept not in department_breakdown:
                department_breakdown[dept] = {"total": 0, "completed": 0}
            department_breakdown[dept]["total"] += 1
            if sub_story.status == StoryStatus.DONE:
                department_breakdown[dept]["completed"] += 1

        return {
            "user_stories": {
                "total": len(user_stories_in_repo),
                "completed": sum(
                    1 for us in user_stories_in_repo if us.status == StoryStatus.DONE
                ),
            },
            "sub_stories": {
                "total": len(sub_stories_in_repo),
                "completed": sum(
                    1 for ss in sub_stories_in_repo if ss.status == StoryStatus.DONE
                ),
            },
            "status_distribution": status_distribution,
            "estimated_hours": total_estimated_hours,
            "department_breakdown": department_breakdown,
        }

    def _calculate_status_distribution(
        self, stories: List[BaseStory]
    ) -> Dict[str, int]:
        """Calculate the distribution of statuses across a list of stories."""
        distribution = {}
        for story in stories:
            status = story.status.value
            distribution[status] = distribution.get(status, 0) + 1
        return distribution


@dataclass
class CrossRepositoryProgressSnapshot:
    """Snapshot of progress across multiple repositories for an epic."""

    epic_id: str
    epic_title: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_progress: Dict[str, Any] = field(default_factory=dict)
    repository_progress: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    repository_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    real_time_updates_enabled: bool = True
    last_updated_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert progress snapshot to dictionary."""
        return {
            "epic_id": self.epic_id,
            "epic_title": self.epic_title,
            "timestamp": self.timestamp.isoformat(),
            "overall_progress": self.overall_progress,
            "repository_progress": self.repository_progress,
            "repository_metrics": self.repository_metrics,
            "real_time_updates_enabled": self.real_time_updates_enabled,
            "last_updated_by": self.last_updated_by,
        }

    @classmethod
    def from_story_hierarchy(
        cls, hierarchy: StoryHierarchy
    ) -> "CrossRepositoryProgressSnapshot":
        """Create a progress snapshot from a story hierarchy."""
        cross_repo_progress = hierarchy.get_cross_repository_progress()

        return cls(
            epic_id=hierarchy.epic.id,
            epic_title=hierarchy.epic.title,
            overall_progress=cross_repo_progress["overall"],
            repository_progress=cross_repo_progress["by_repository"],
            repository_metrics=hierarchy.get_repository_specific_metrics(),
        )

    def get_visualization_data(self) -> Dict[str, Any]:
        """Get data formatted for progress visualization."""
        return {
            "epic": {
                "id": self.epic_id,
                "title": self.epic_title,
                "overall_percentage": self.overall_progress.get("percentage", 0),
            },
            "repositories": [
                {
                    "name": repo_name,
                    "progress": repo_data["percentage"],
                    "status": repo_data["status"],
                    "total_items": repo_data["total"],
                    "completed_items": repo_data["completed"],
                }
                for repo_name, repo_data in self.repository_progress.items()
            ],
            "summary": {
                "total_repositories": len(self.repository_progress),
                "total_items": self.overall_progress.get("total", 0),
                "completed_items": self.overall_progress.get("completed", 0),
                "overall_percentage": self.overall_progress.get("percentage", 0),
            },
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ConversationParticipant:
    """Represents a participant in a cross-repository conversation."""

    id: str = field(default_factory=lambda: f"participant_{uuid.uuid4().hex[:8]}")
    name: str = ""
    role: str = ""  # e.g., "system-architect", "lead-developer", "user"
    repository: Optional[str] = None  # Repository context for this participant
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert participant to dictionary for database storage."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "repository": self.repository,
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class Message:
    """Represents a single message in a conversation."""

    id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    conversation_id: str = ""
    participant_id: str = ""
    content: str = ""
    message_type: str = "text"  # text, system, decision, context_share
    repository_context: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for database storage."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "participant_id": self.participant_id,
            "content": self.content,
            "message_type": self.message_type,
            "repository_context": self.repository_context,
            "created_at": self.created_at.isoformat(),
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class Conversation:
    """Represents a cross-repository conversation."""

    id: str = field(default_factory=lambda: f"conv_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    repositories: List[str] = field(default_factory=list)
    participants: List[ConversationParticipant] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    status: str = "active"  # active, resolved, archived
    decision_summary: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary for database storage."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "repositories": json.dumps(self.repositories),
            "status": self.status,
            "decision_summary": self.decision_summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": json.dumps(self.metadata),
        }

    def add_message(
        self,
        participant_id: str,
        content: str,
        message_type: str = "text",
        repository_context: Optional[str] = None,
    ) -> Message:
        """Add a new message to the conversation."""
        message = Message(
            conversation_id=self.id,
            participant_id=participant_id,
            content=content,
            message_type=message_type,
            repository_context=repository_context,
        )
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
        return message

    def get_messages_by_repository(self, repository: str) -> List[Message]:
        """Get all messages related to a specific repository."""
        return [msg for msg in self.messages if msg.repository_context == repository]

    def get_participants_by_repository(
        self, repository: str
    ) -> List[ConversationParticipant]:
        """Get all participants associated with a specific repository."""
        return [p for p in self.participants if p.repository == repository]

    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation."""
        return {
            "id": self.id,
            "title": self.title,
            "repositories": self.repositories,
            "status": self.status,
            "message_count": len(self.messages),
            "participant_count": len(self.participants),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class RolePerspective:
    """Represents a role's perspective on a discussion topic."""

    id: str = field(default_factory=lambda: f"perspective_{uuid.uuid4().hex[:8]}")
    role_name: str = ""
    viewpoint: str = ""
    arguments: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence_level: float = 0.0  # 0.0 to 1.0
    repository_context: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert perspective to dictionary for database storage."""
        return {
            "id": self.id,
            "role_name": self.role_name,
            "viewpoint": self.viewpoint,
            "arguments": json.dumps(self.arguments),
            "concerns": json.dumps(self.concerns),
            "suggestions": json.dumps(self.suggestions),
            "confidence_level": self.confidence_level,
            "repository_context": self.repository_context,
            "created_at": self.created_at.isoformat(),
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class DiscussionThread:
    """Represents a threaded discussion with arguments and counter-arguments."""

    id: str = field(default_factory=lambda: f"thread_{uuid.uuid4().hex[:8]}")
    conversation_id: str = ""
    topic: str = ""
    parent_thread_id: Optional[str] = None  # For nested threads
    perspectives: List[RolePerspective] = field(default_factory=list)
    consensus_level: float = 0.0  # 0.0 (no consensus) to 1.0 (full consensus)
    status: str = "active"  # active, resolved, blocked, needs_human_input
    resolution: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert thread to dictionary for database storage."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "topic": self.topic,
            "parent_thread_id": self.parent_thread_id,
            "consensus_level": self.consensus_level,
            "status": self.status,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": json.dumps(self.metadata),
        }

    def add_perspective(self, perspective: RolePerspective) -> None:
        """Add a role perspective to this thread."""
        self.perspectives.append(perspective)
        self.updated_at = datetime.now(timezone.utc)

    def calculate_consensus(self) -> float:
        """Calculate consensus level based on role perspectives."""
        if not self.perspectives:
            return 0.0

        # Simple consensus calculation based on agreement in viewpoints
        # More sophisticated algorithms could be implemented
        agreement_scores = []

        for i, perspective1 in enumerate(self.perspectives):
            for j, perspective2 in enumerate(self.perspectives[i + 1 :], i + 1):
                # Calculate similarity between viewpoints (simplified)
                if perspective1.viewpoint and perspective2.viewpoint:
                    # Simple keyword overlap check
                    words1 = set(perspective1.viewpoint.lower().split())
                    words2 = set(perspective2.viewpoint.lower().split())
                    if words1 and words2:
                        overlap = len(words1.intersection(words2))
                        total = len(words1.union(words2))
                        similarity = overlap / total if total > 0 else 0.0
                        agreement_scores.append(similarity)

        if agreement_scores:
            self.consensus_level = sum(agreement_scores) / len(agreement_scores)
        else:
            self.consensus_level = 0.0

        return self.consensus_level


@dataclass
class DiscussionSummary:
    """Summary of a multi-role discussion."""

    id: str = field(default_factory=lambda: f"summary_{uuid.uuid4().hex[:8]}")
    conversation_id: str = ""
    discussion_topic: str = ""
    participating_roles: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    areas_of_agreement: List[str] = field(default_factory=list)
    areas_of_disagreement: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    unresolved_issues: List[str] = field(default_factory=list)
    overall_consensus: float = 0.0
    confidence_score: float = 0.0
    requires_human_input: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary for database storage."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "discussion_topic": self.discussion_topic,
            "participating_roles": json.dumps(self.participating_roles),
            "key_points": json.dumps(self.key_points),
            "areas_of_agreement": json.dumps(self.areas_of_agreement),
            "areas_of_disagreement": json.dumps(self.areas_of_disagreement),
            "recommended_actions": json.dumps(self.recommended_actions),
            "unresolved_issues": json.dumps(self.unresolved_issues),
            "overall_consensus": self.overall_consensus,
            "confidence_score": self.confidence_score,
            "requires_human_input": self.requires_human_input,
            "created_at": self.created_at.isoformat(),
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class ProjectFieldValue:
    """Represents a custom field value in a GitHub Project."""

    field_id: str
    value: Any
    field_type: str = "text"  # text, number, date, single_select, iteration


@dataclass
class ProjectItemData:
    """Data structure for GitHub Project item creation/update."""

    content_id: str  # Issue or PR ID
    project_id: str
    field_values: List[ProjectFieldValue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for GraphQL operations."""
        return {
            "content_id": self.content_id,
            "project_id": self.project_id,
            "field_values": [
                {
                    "field_id": fv.field_id,
                    "value": fv.value,
                    "field_type": fv.field_type,
                }
                for fv in self.field_values
            ],
        }


@dataclass
class ProjectData:
    """Data structure for GitHub Project creation/management."""

    title: str
    description: str = ""
    repository_id: Optional[str] = None  # Repository node ID if repo-level project
    organization_login: Optional[str] = None  # Org login if org-level project
    visibility: str = "PRIVATE"  # PRIVATE, PUBLIC
    template: Optional[str] = None  # Template to use for project creation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for GraphQL operations."""
        data = {
            "title": self.title,
            "description": self.description,
            "visibility": self.visibility,
        }
        if self.repository_id:
            data["repository_id"] = self.repository_id
        if self.organization_login:
            data["organization_login"] = self.organization_login
        if self.template:
            data["template"] = self.template
        return data


@dataclass
class ProjectField:
    """Represents a custom field in a GitHub Project."""

    id: str
    name: str
    data_type: str  # TEXT, NUMBER, DATE, SINGLE_SELECT, ITERATION
    options: List[Dict[str, Any]] = field(
        default_factory=list
    )  # For single_select fields

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for operations."""
        return {
            "id": self.id,
            "name": self.name,
            "data_type": self.data_type,
            "options": self.options,
        }


# Pipeline Monitoring Models


class PipelineStatus(Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class FailureSeverity(Enum):
    """Severity levels for pipeline failures."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailureCategory(Enum):
    """Categories of pipeline failures."""

    LINTING = "linting"
    FORMATTING = "formatting"
    TESTING = "testing"
    BUILD = "build"
    DEPLOYMENT = "deployment"
    DEPENDENCY = "dependency"
    TIMEOUT = "timeout"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


@dataclass
class PipelineFailure:
    """Represents a pipeline failure with analysis and context."""

    id: str = field(default_factory=lambda: f"failure_{uuid.uuid4().hex[:8]}")
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""
    pipeline_id: str = ""
    job_name: str = ""
    step_name: str = ""
    failure_message: str = ""
    failure_logs: str = ""
    category: FailureCategory = FailureCategory.UNKNOWN
    severity: FailureSeverity = FailureSeverity.MEDIUM
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "repository": self.repository,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "pipeline_id": self.pipeline_id,
            "job_name": self.job_name,
            "step_name": self.step_name,
            "failure_message": self.failure_message,
            "failure_logs": self.failure_logs,
            "category": self.category.value,
            "severity": self.severity.value,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineFailure":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            repository=data["repository"],
            branch=data["branch"],
            commit_sha=data["commit_sha"],
            pipeline_id=data["pipeline_id"],
            job_name=data["job_name"],
            step_name=data["step_name"],
            failure_message=data["failure_message"],
            failure_logs=data["failure_logs"],
            category=FailureCategory(data["category"]),
            severity=FailureSeverity(data["severity"]),
            detected_at=datetime.fromisoformat(data["detected_at"]),
            resolved_at=(
                datetime.fromisoformat(data["resolved_at"])
                if data["resolved_at"]
                else None
            ),
            retry_count=data["retry_count"],
            max_retries=data["max_retries"],
            metadata=json.loads(data["metadata"]) if data["metadata"] else {},
        )


@dataclass
class PipelineRun:
    """Represents a complete pipeline run across all jobs."""

    id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""
    workflow_name: str = ""
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    failures: List[PipelineFailure] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "repository": self.repository,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class FailurePattern:
    """Represents a detected pattern in pipeline failures."""

    pattern_id: str = field(default_factory=lambda: f"pattern_{uuid.uuid4().hex[:8]}")
    category: FailureCategory = FailureCategory.UNKNOWN
    description: str = ""
    failure_count: int = 0
    repositories: List[str] = field(default_factory=list)
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolution_suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "pattern_id": self.pattern_id,
            "category": self.category.value,
            "description": self.description,
            "failure_count": self.failure_count,
            "repositories": json.dumps(self.repositories),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "resolution_suggestions": json.dumps(self.resolution_suggestions),
            "metadata": json.dumps(self.metadata),
        }


@dataclass
class RetryAttempt:
    """Represents a retry attempt for a failed operation."""

    id: str = field(default_factory=lambda: f"retry_{uuid.uuid4().hex[:8]}")
    failure_id: str = ""  # References PipelineFailure.id
    repository: str = ""
    attempt_number: int = 1
    attempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    retry_delay_seconds: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "failure_id": self.failure_id,
            "repository": self.repository,
            "attempt_number": self.attempt_number,
            "attempted_at": self.attempted_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "success": self.success,
            "error_message": self.error_message,
            "retry_delay_seconds": self.retry_delay_seconds,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryAttempt":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            failure_id=data["failure_id"],
            repository=data["repository"],
            attempt_number=data["attempt_number"],
            attempted_at=datetime.fromisoformat(data["attempted_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"]
                else None
            ),
            success=data["success"],
            error_message=data["error_message"],
            retry_delay_seconds=data["retry_delay_seconds"],
            metadata=json.loads(data["metadata"]) if data["metadata"] else {},
        )


@dataclass
class EscalationRecord:
    """Represents an escalation event for persistent failures."""

    id: str = field(default_factory=lambda: f"escalation_{uuid.uuid4().hex[:8]}")
    repository: str = ""
    failure_pattern: str = ""  # Description of failure pattern
    failure_count: int = 0
    escalated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    escalation_level: str = "agent"  # agent, human, critical
    contacts_notified: List[str] = field(default_factory=list)
    channels_used: List[str] = field(default_factory=list)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "repository": self.repository,
            "failure_pattern": self.failure_pattern,
            "failure_count": self.failure_count,
            "escalated_at": self.escalated_at.isoformat(),
            "escalation_level": self.escalation_level,
            "contacts_notified": json.dumps(self.contacts_notified),
            "channels_used": json.dumps(self.channels_used),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EscalationRecord":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            repository=data["repository"],
            failure_pattern=data["failure_pattern"],
            failure_count=data["failure_count"],
            escalated_at=datetime.fromisoformat(data["escalated_at"]),
            escalation_level=data["escalation_level"],
            contacts_notified=(
                json.loads(data["contacts_notified"])
                if data["contacts_notified"]
                else []
            ),
            channels_used=(
                json.loads(data["channels_used"]) if data["channels_used"] else []
            ),
            resolved=data["resolved"],
            resolved_at=(
                datetime.fromisoformat(data["resolved_at"])
                if data["resolved_at"]
                else None
            ),
            metadata=json.loads(data["metadata"]) if data["metadata"] else {},
        )


@dataclass
class WorkflowCheckpoint:
    """Represents a workflow state checkpoint for recovery purposes."""

    id: str = field(default_factory=lambda: f"checkpoint_{uuid.uuid4().hex[:8]}")
    repository: str = ""
    workflow_name: str = ""
    run_id: str = ""
    commit_sha: str = ""
    checkpoint_type: str = "step"  # step, job, workflow
    checkpoint_name: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    environment_context: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "repository": self.repository,
            "workflow_name": self.workflow_name,
            "run_id": self.run_id,
            "commit_sha": self.commit_sha,
            "checkpoint_type": self.checkpoint_type,
            "checkpoint_name": self.checkpoint_name,
            "created_at": self.created_at.isoformat(),
            "workflow_state": json.dumps(self.workflow_state),
            "environment_context": json.dumps(self.environment_context),
            "dependencies": json.dumps(self.dependencies),
            "artifacts": json.dumps(self.artifacts),
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowCheckpoint":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            repository=data["repository"],
            workflow_name=data["workflow_name"],
            run_id=data["run_id"],
            commit_sha=data["commit_sha"],
            checkpoint_type=data["checkpoint_type"],
            checkpoint_name=data["checkpoint_name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            workflow_state=(
                json.loads(data["workflow_state"]) if data["workflow_state"] else {}
            ),
            environment_context=(
                json.loads(data["environment_context"])
                if data["environment_context"]
                else {}
            ),
            dependencies=(
                json.loads(data["dependencies"]) if data["dependencies"] else []
            ),
            artifacts=json.loads(data["artifacts"]) if data["artifacts"] else [],
            metadata=json.loads(data["metadata"]) if data["metadata"] else {},
        )


class RecoveryStatus(Enum):
    """Recovery operation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RecoveryState:
    """Represents a recovery operation state and progress."""

    id: str = field(default_factory=lambda: f"recovery_{uuid.uuid4().hex[:8]}")
    failure_id: str = ""  # References PipelineFailure.id
    repository: str = ""
    recovery_type: str = "retry"  # retry, resume, rollback
    status: RecoveryStatus = RecoveryStatus.PENDING
    target_checkpoint_id: Optional[str] = None
    recovery_plan: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    progress_steps: List[Dict[str, Any]] = field(default_factory=list)
    recovery_context: Dict[str, Any] = field(default_factory=dict)
    rollback_checkpoint_id: Optional[str] = None
    corruption_detected: bool = False
    validation_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "failure_id": self.failure_id,
            "repository": self.repository,
            "recovery_type": self.recovery_type,
            "status": self.status.value,
            "target_checkpoint_id": self.target_checkpoint_id,
            "recovery_plan": json.dumps(self.recovery_plan),
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "progress_steps": json.dumps(self.progress_steps),
            "recovery_context": json.dumps(self.recovery_context),
            "rollback_checkpoint_id": self.rollback_checkpoint_id,
            "corruption_detected": self.corruption_detected,
            "validation_results": json.dumps(self.validation_results),
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryState":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            failure_id=data["failure_id"],
            repository=data["repository"],
            recovery_type=data["recovery_type"],
            status=RecoveryStatus(data["status"]),
            target_checkpoint_id=data.get("target_checkpoint_id"),
            recovery_plan=(
                json.loads(data["recovery_plan"]) if data["recovery_plan"] else []
            ),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data["completed_at"]
                else None
            ),
            progress_steps=(
                json.loads(data["progress_steps"]) if data["progress_steps"] else []
            ),
            recovery_context=(
                json.loads(data["recovery_context"]) if data["recovery_context"] else {}
            ),
            rollback_checkpoint_id=data.get("rollback_checkpoint_id"),
            corruption_detected=data.get("corruption_detected", False),
            validation_results=(
                json.loads(data["validation_results"])
                if data["validation_results"]
                else {}
            ),
            metadata=json.loads(data["metadata"]) if data["metadata"] else {},
        )
