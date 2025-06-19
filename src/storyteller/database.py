"""Database schema and migration system for hierarchical story management."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    # Try relative imports first (for package usage)
    from .models import (
        Conversation,
        ConversationParticipant,
        Epic,
        Message,
        RecoveryState,
        StoryHierarchy,
        StoryStatus,
        StoryType,
        SubStory,
        UserStory,
        WorkflowCheckpoint,
    )
except ImportError:
    # Fall back to absolute imports (for direct execution)
    from models import (
        Conversation,
        ConversationParticipant,
        Epic,
        Message,
        RecoveryState,
        StoryHierarchy,
        StoryStatus,
        StoryType,
        SubStory,
        UserStory,
        WorkflowCheckpoint,
    )

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database manager for hierarchical story storage."""

    def __init__(self, db_path: str = "storyteller.db"):
        """Initialize database manager with SQLite database."""
        self.db_path = Path(db_path)
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self):
        """Initialize database with schema."""
        with self.get_connection() as conn:
            self.create_schema(conn)

    def create_schema(self, conn: sqlite3.Connection):
        """Create database schema for hierarchical stories."""

        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")

        # Main stories table with hierarchical structure
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                story_type TEXT NOT NULL CHECK (story_type IN ('epic', 'user_story', 'sub_story')),
                parent_id TEXT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'ready', 'in_progress', 'review', 'done', 'blocked')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',

                -- Epic-specific fields
                business_value TEXT DEFAULT '',
                estimated_duration_weeks INTEGER,

                -- User Story-specific fields
                user_persona TEXT DEFAULT '',
                user_goal TEXT DEFAULT '',
                story_points INTEGER,

                -- Sub-story-specific fields
                department TEXT DEFAULT '',
                target_repository TEXT DEFAULT '',
                assignee TEXT,
                estimated_hours REAL,

                -- Common array fields stored as JSON
                acceptance_criteria TEXT DEFAULT '[]',
                target_repositories TEXT DEFAULT '[]',
                technical_requirements TEXT DEFAULT '[]',
                dependencies TEXT DEFAULT '[]',

                FOREIGN KEY (parent_id) REFERENCES stories (id) ON DELETE CASCADE
            )
        """
        )

        # Index for hierarchical queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stories_parent_id ON stories (parent_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stories_type ON stories (story_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stories_status ON stories (status)"
        )

        # Story relationships table for complex relationships
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS story_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_story_id TEXT NOT NULL,
                target_story_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL
                    CHECK (relationship_type IN ('depends_on', 'blocks', 'relates_to', 'duplicates')),
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (source_story_id) REFERENCES stories (id) ON DELETE CASCADE,
                FOREIGN KEY (target_story_id) REFERENCES stories (id) ON DELETE CASCADE,
                UNIQUE (source_story_id, target_story_id, relationship_type)
            )
        """
        )

        # GitHub integration table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS github_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT NOT NULL,
                repository_name TEXT NOT NULL,
                issue_number INTEGER NOT NULL,
                issue_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                synced_at TEXT,

                FOREIGN KEY (story_id) REFERENCES stories (id) ON DELETE CASCADE,
                UNIQUE (story_id, repository_name)
            )
        """
        )

        # Status transition audit table for webhook events
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS status_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual', 'webhook', 'automation')),
                trigger_source TEXT,
                event_type TEXT,
                repository_name TEXT,
                pr_number INTEGER,
                issue_number INTEGER,
                commit_sha TEXT,
                user_id TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (story_id) REFERENCES stories (id) ON DELETE CASCADE
            )
        """
        )

        # Create conversation-related tables
        self.create_conversation_schema(conn)

        # Create pipeline monitoring tables
        self.create_pipeline_monitoring_schema(conn)

        conn.commit()

    def create_conversation_schema(self, conn: sqlite3.Connection):
        """Create database schema for cross-repository conversations."""

        # Conversations table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                repositories TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved', 'archived')),
                decision_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """
        )

        # Conversation participants table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_participants (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                repository TEXT,
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """
        )

        # Messages table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                participant_id TEXT NOT NULL,
                content TEXT NOT NULL,
                message_type TEXT NOT NULL DEFAULT 'text'
                    CHECK (message_type IN ('text', 'system', 'decision', 'context_share')),
                repository_context TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE,
                FOREIGN KEY (participant_id) REFERENCES conversation_participants (id) ON DELETE CASCADE
            )
        """
        )

        # Indexes for conversation queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations (status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_participants_conversation ON conversation_participants (conversation_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages (conversation_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_participant ON conversation_messages (participant_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_repository ON conversation_messages (repository_context)"
        )

    def create_pipeline_monitoring_schema(self, conn: sqlite3.Connection):
        """Create database schema for pipeline monitoring."""

        # Pipeline runs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                workflow_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'success', 'failure', 'cancelled', 'skipped')),
                started_at TEXT NOT NULL,
                completed_at TEXT,
                metadata TEXT DEFAULT '{}'
            )
        """
        )

        # Pipeline failures table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_failures (
                id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                pipeline_id TEXT NOT NULL,
                job_name TEXT NOT NULL,
                step_name TEXT NOT NULL,
                failure_message TEXT NOT NULL,
                failure_logs TEXT DEFAULT '',
                category TEXT NOT NULL CHECK (category IN ('linting', 'formatting', 'testing', 'build', 'deployment', 'dependency', 'timeout', 'infrastructure', 'unknown')),
                severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
                detected_at TEXT NOT NULL,
                resolved_at TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (pipeline_id) REFERENCES pipeline_runs (id) ON DELETE CASCADE
            )
        """
        )

        # Failure patterns table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS failure_patterns (
                pattern_id TEXT PRIMARY KEY,
                category TEXT NOT NULL CHECK (category IN ('linting', 'formatting', 'testing', 'build', 'deployment', 'dependency', 'timeout', 'infrastructure', 'unknown')),
                description TEXT NOT NULL,
                failure_count INTEGER DEFAULT 0,
                repositories TEXT DEFAULT '[]',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                resolution_suggestions TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}'
            )
        """
        )

        # Retry attempts table for tracking retry operations
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS retry_attempts (
                id TEXT PRIMARY KEY,
                failure_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                attempted_at TEXT NOT NULL,
                completed_at TEXT,
                success BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                retry_delay_seconds INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (failure_id) REFERENCES pipeline_failures (id) ON DELETE CASCADE
            )
        """
        )

        # Escalation records table for tracking failure escalations
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS escalation_records (
                id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                failure_pattern TEXT NOT NULL,
                failure_count INTEGER DEFAULT 0,
                escalated_at TEXT NOT NULL,
                escalation_level TEXT NOT NULL CHECK (escalation_level IN ('agent', 'human', 'critical')),
                contacts_notified TEXT DEFAULT '[]',
                channels_used TEXT DEFAULT '[]',
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at TEXT,
                metadata TEXT DEFAULT '{}'
            )
        """
        )

        # Manual interventions table for tracking human consensus interventions
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS manual_interventions (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                consensus_id TEXT NOT NULL,
                trigger_reason TEXT NOT NULL CHECK (trigger_reason IN ('timeout', 'failed_consensus', 'manual_request')),
                intervention_type TEXT NOT NULL CHECK (intervention_type IN ('decision', 'override', 'escalation')),
                original_decision TEXT NOT NULL,
                human_decision TEXT DEFAULT '',
                human_rationale TEXT DEFAULT '',
                intervener_id TEXT DEFAULT '',
                intervener_role TEXT DEFAULT '',
                triggered_at TEXT NOT NULL,
                resolved_at TEXT,
                status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'resolved', 'cancelled')),
                affected_roles TEXT DEFAULT '[]',
                override_data TEXT DEFAULT '{}',
                audit_trail TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}'
            )
        """
        )

        # Workflow checkpoints table for state persistence
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                id TEXT PRIMARY KEY,
                repository TEXT NOT NULL,
                workflow_name TEXT NOT NULL,
                run_id TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                checkpoint_type TEXT NOT NULL CHECK (checkpoint_type IN ('step', 'job', 'workflow')),
                checkpoint_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                workflow_state TEXT DEFAULT '{}',
                environment_context TEXT DEFAULT '{}',
                dependencies TEXT DEFAULT '[]',
                artifacts TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}'
            )
        """
        )

        # Recovery states table for tracking recovery operations
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_states (
                id TEXT PRIMARY KEY,
                failure_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                recovery_type TEXT NOT NULL CHECK (recovery_type IN ('retry', 'resume', 'rollback')),
                status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
                target_checkpoint_id TEXT,
                recovery_plan TEXT DEFAULT '[]',
                started_at TEXT NOT NULL,
                completed_at TEXT,
                progress_steps TEXT DEFAULT '[]',
                recovery_context TEXT DEFAULT '{}',
                rollback_checkpoint_id TEXT,
                corruption_detected BOOLEAN DEFAULT FALSE,
                validation_results TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (failure_id) REFERENCES pipeline_failures (id) ON DELETE CASCADE,
                FOREIGN KEY (target_checkpoint_id) REFERENCES workflow_checkpoints (id) ON DELETE SET NULL,
                FOREIGN KEY (rollback_checkpoint_id) REFERENCES workflow_checkpoints (id) ON DELETE SET NULL
            )
        """
        )

        # Create indexes for pipeline monitoring
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_repository ON pipeline_runs (repository)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs (status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_failures_repository ON pipeline_failures (repository)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_failures_category ON pipeline_failures (category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_failures_severity ON pipeline_failures (severity)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pipeline_failures_detected_at ON pipeline_failures (detected_at)"
        )

        # Create indexes for retry attempts and escalation records
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_retry_attempts_failure_id ON retry_attempts (failure_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_retry_attempts_repository ON retry_attempts (repository)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_retry_attempts_attempted_at ON retry_attempts (attempted_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_escalation_records_repository ON escalation_records (repository)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_escalation_records_escalated_at ON escalation_records (escalated_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_escalation_records_resolved ON escalation_records (resolved)"
        )

        # Create indexes for manual interventions
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_manual_interventions_conversation_id ON manual_interventions (conversation_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_manual_interventions_consensus_id ON manual_interventions (consensus_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_manual_interventions_triggered_at ON manual_interventions (triggered_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_manual_interventions_status ON manual_interventions (status)"
        )

        # Create indexes for workflow checkpoints
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_repository ON workflow_checkpoints (repository)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_run_id ON workflow_checkpoints (run_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_created_at ON workflow_checkpoints (created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_type ON workflow_checkpoints (checkpoint_type)"
        )

        # Create indexes for recovery states
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recovery_states_failure_id ON recovery_states (failure_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recovery_states_repository ON recovery_states (repository)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recovery_states_status ON recovery_states (status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recovery_states_started_at ON recovery_states (started_at)"
        )

    def save_story(self, story: Union[Epic, UserStory, SubStory]) -> str:
        """Save a story to the database."""
        with self.get_connection() as conn:
            data = story.to_dict()
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Convert lists to JSON strings for storage
            for field in [
                "acceptance_criteria",
                "target_repositories",
                "technical_requirements",
                "dependencies",
            ]:
                if field in data and isinstance(data[field], list):
                    data[field] = json.dumps(data[field])

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            conn.execute(
                f"INSERT OR REPLACE INTO stories ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )

            return story.id

    def get_story(self, story_id: str) -> Optional[Union[Epic, UserStory, SubStory]]:
        """Retrieve a story by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_story(row)

    def get_epic_hierarchy(self, epic_id: str) -> Optional[StoryHierarchy]:
        """Get complete epic hierarchy including all user stories and sub-stories."""
        epic = self.get_story(epic_id)
        if not epic or not isinstance(epic, Epic):
            return None

        user_stories = self.get_children_stories(epic_id, StoryType.USER_STORY)
        sub_stories = {}

        for user_story in user_stories:
            sub_story_list = self.get_children_stories(
                user_story.id, StoryType.SUB_STORY
            )
            if sub_story_list:
                sub_stories[user_story.id] = sub_story_list

        return StoryHierarchy(
            epic=epic, user_stories=user_stories, sub_stories=sub_stories
        )

    def get_children_stories(
        self, parent_id: str, story_type: StoryType
    ) -> List[Union[UserStory, SubStory]]:
        """Get all child stories of a specific type for a parent."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM stories WHERE parent_id = ? AND story_type = ? ORDER BY created_at",
                (parent_id, story_type.value),
            )

            return [self._row_to_story(row) for row in cursor.fetchall()]

    def get_all_epics(self) -> List[Epic]:
        """Get all epics in the system."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM stories WHERE story_type = 'epic' ORDER BY created_at DESC"
            )

            return [self._row_to_story(row) for row in cursor.fetchall()]

    def update_story_status(
        self, story_id: str, status: StoryStatus, propagate: bool = True
    ) -> bool:
        """Update the status of a story with optional status propagation to parent."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE stories SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, datetime.now(timezone.utc).isoformat(), story_id),
            )

            if cursor.rowcount > 0 and propagate:
                self._propagate_status_to_parent(story_id, conn)

            return cursor.rowcount > 0

    def _propagate_status_to_parent(self, story_id: str, conn: sqlite3.Connection):
        """Propagate status changes from child to parent story."""
        # Get the current story to find its parent
        cursor = conn.execute(
            "SELECT parent_id, story_type FROM stories WHERE id = ?", (story_id,)
        )
        row = cursor.fetchone()

        if not row or not row["parent_id"]:
            return  # No parent to propagate to

        parent_id = row["parent_id"]

        # Calculate new parent status based on children
        new_parent_status = self._calculate_parent_status(parent_id, conn)

        if new_parent_status:
            # Update parent status (without further propagation to avoid infinite loops)
            conn.execute(
                "UPDATE stories SET status = ?, updated_at = ? WHERE id = ?",
                (
                    new_parent_status.value,
                    datetime.now(timezone.utc).isoformat(),
                    parent_id,
                ),
            )

            # Recursively propagate up the hierarchy
            self._propagate_status_to_parent(parent_id, conn)

    def _calculate_parent_status(
        self, parent_id: str, conn: sqlite3.Connection
    ) -> Optional[StoryStatus]:
        """Calculate what the parent status should be based on children statuses."""
        # Get all children of this parent
        cursor = conn.execute(
            "SELECT status FROM stories WHERE parent_id = ?", (parent_id,)
        )
        child_statuses = [StoryStatus(row["status"]) for row in cursor.fetchall()]

        if not child_statuses:
            return None  # No children, don't change parent status

        # Apply status propagation rules
        done_count = sum(1 for status in child_statuses if status == StoryStatus.DONE)
        in_progress_count = sum(
            1 for status in child_statuses if status == StoryStatus.IN_PROGRESS
        )
        review_count = sum(
            1 for status in child_statuses if status == StoryStatus.REVIEW
        )
        blocked_count = sum(
            1 for status in child_statuses if status == StoryStatus.BLOCKED
        )
        total_count = len(child_statuses)

        # Status propagation rules based on SCHEMA.md
        if done_count == total_count:
            # All children are done -> parent is done
            return StoryStatus.DONE
        elif blocked_count > 0:
            # Any child is blocked -> parent is blocked
            return StoryStatus.BLOCKED
        elif in_progress_count > 0 or review_count > 0:
            # Any child is in progress or review -> parent is in progress
            return StoryStatus.IN_PROGRESS
        elif all(
            status in [StoryStatus.READY, StoryStatus.DRAFT]
            for status in child_statuses
        ):
            # All children are ready or draft -> parent should be ready
            return StoryStatus.READY
        else:
            # Mixed states, keep parent in progress
            return StoryStatus.IN_PROGRESS

    def delete_story(self, story_id: str) -> bool:
        """Delete a story and all its children (CASCADE)."""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
            return cursor.rowcount > 0

    def add_story_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        metadata: Dict[str, Any] = None,
        validate: bool = True,
    ):
        """Add a relationship between two stories with optional validation."""
        if validate and relationship_type == "depends_on":
            # Check if this would create a circular dependency
            with self.get_connection() as conn:
                # Temporarily add the relationship to check for cycles
                temp_conn = sqlite3.connect(":memory:")
                temp_conn.row_factory = sqlite3.Row
                temp_conn.execute("PRAGMA foreign_keys = ON")

                # Copy current relationships to memory
                with self.get_connection() as main_conn:
                    main_conn.backup(temp_conn)

                # Add the new relationship temporarily
                temp_conn.execute(
                    """
                    INSERT INTO story_relationships
                    (source_story_id, target_story_id, relationship_type, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        target_id,
                        relationship_type,
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(metadata or {}),
                    ),
                )

                # Check for cycles with temporary data
                if self._has_circular_dependency_in_conn(source_id, temp_conn):
                    temp_conn.close()
                    raise ValueError(
                        f"Adding relationship would create circular dependency: {source_id} -> {target_id}"
                    )

                temp_conn.close()

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO story_relationships
                (source_story_id, target_story_id, relationship_type, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    source_id,
                    target_id,
                    relationship_type,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(metadata or {}),
                ),
            )

    def get_story_relationships(self, story_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for a story."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM story_relationships
                WHERE source_story_id = ? OR target_story_id = ?
            """,
                (story_id, story_id),
            )

            return [dict(row) for row in cursor.fetchall()]

    def link_github_issue(
        self, story_id: str, repository_name: str, issue_number: int, issue_url: str
    ):
        """Link a story to a GitHub issue."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO github_issues
                (story_id, repository_name, issue_number, issue_url, created_at, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    story_id,
                    repository_name,
                    issue_number,
                    issue_url,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_github_issues(self, story_id: str) -> List[Dict[str, Any]]:
        """Get GitHub issues linked to a story."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM github_issues WHERE story_id = ?", (story_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def validate_parent_child_relationship(self, child_id: str, parent_id: str) -> bool:
        """Validate that a parent-child relationship is valid (no cycles)."""
        if child_id == parent_id:
            return False  # Can't be parent of itself

        # Check if making this relationship would create a cycle
        return not self._would_create_cycle(child_id, parent_id)

    def _would_create_cycle(self, child_id: str, potential_parent_id: str) -> bool:
        """Check if setting potential_parent_id as parent of child_id would create a cycle."""
        visited = set()
        current = potential_parent_id

        with self.get_connection() as conn:
            while current and current not in visited:
                visited.add(current)

                # If we reach the child_id while traversing up, it would create a cycle
                if current == child_id:
                    return True

                # Get parent of current node
                cursor = conn.execute(
                    "SELECT parent_id FROM stories WHERE id = ?", (current,)
                )
                row = cursor.fetchone()
                current = row["parent_id"] if row else None

        return False

    def get_dependency_chain(self, story_id: str) -> List[Dict[str, Any]]:
        """Get the full dependency chain for a story."""
        dependencies = []
        visited = set()

        def _get_dependencies_recursive(current_id: str):
            if current_id in visited:
                return  # Avoid infinite loops

            visited.add(current_id)

            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT target_story_id, relationship_type, metadata
                    FROM story_relationships
                    WHERE source_story_id = ? AND relationship_type = 'depends_on'
                    """,
                    (current_id,),
                )

                for row in cursor.fetchall():
                    dep_info = dict(row)
                    dependencies.append(dep_info)
                    _get_dependencies_recursive(dep_info["target_story_id"])

        _get_dependencies_recursive(story_id)
        return dependencies

    def validate_relationship_integrity(self) -> List[str]:
        """Validate all relationships for integrity issues and return any problems found."""
        issues = []

        with self.get_connection() as conn:
            # Check for orphaned relationships (references to non-existent stories)
            cursor = conn.execute(
                """
                SELECT DISTINCT source_story_id FROM story_relationships
                WHERE source_story_id NOT IN (SELECT id FROM stories)
                UNION
                SELECT DISTINCT target_story_id FROM story_relationships
                WHERE target_story_id NOT IN (SELECT id FROM stories)
                """
            )

            for row in cursor.fetchall():
                issues.append(
                    f"Orphaned relationship references non-existent story: {row[0]}"
                )

            # Check for circular dependencies in 'depends_on' relationships
            cursor = conn.execute(
                "SELECT DISTINCT source_story_id FROM story_relationships WHERE relationship_type = 'depends_on'"
            )

            for row in cursor.fetchall():
                story_id = row[0]
                if self._has_circular_dependency(story_id):
                    issues.append(
                        f"Circular dependency detected starting from story: {story_id}"
                    )

        return issues

    def _has_circular_dependency(self, start_story_id: str) -> bool:
        """Check if a story has circular dependencies."""
        visited = set()

        def _check_cycle(current_id: str) -> bool:
            if current_id in visited:
                return True  # Found a cycle

            visited.add(current_id)

            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT target_story_id FROM story_relationships
                    WHERE source_story_id = ? AND relationship_type = 'depends_on'
                    """,
                    (current_id,),
                )

                for row in cursor.fetchall():
                    if _check_cycle(row[0]):
                        return True

            visited.remove(current_id)  # Backtrack
            return False

        return _check_cycle(start_story_id)

    def _has_circular_dependency_in_conn(
        self, start_story_id: str, conn: sqlite3.Connection
    ) -> bool:
        """Check if a story has circular dependencies using a specific connection."""
        visited = set()

        def _check_cycle(current_id: str) -> bool:
            if current_id in visited:
                return True  # Found a cycle

            visited.add(current_id)

            cursor = conn.execute(
                """
                SELECT target_story_id FROM story_relationships
                WHERE source_story_id = ? AND relationship_type = 'depends_on'
                """,
                (current_id,),
            )

            for row in cursor.fetchall():
                if _check_cycle(row[0]):
                    return True

            visited.remove(current_id)  # Backtrack
            return False

        return _check_cycle(start_story_id)

    def get_stories_topological_order(self, story_ids: List[str]) -> List[str]:
        """Get stories ordered by their dependencies using topological sort."""
        # Build adjacency list and in-degree count
        graph = {story_id: [] for story_id in story_ids}
        in_degree = {story_id: 0 for story_id in story_ids}

        with self.get_connection() as conn:
            # Get all dependencies for the given stories
            for story_id in story_ids:
                cursor = conn.execute(
                    """
                    SELECT target_story_id FROM story_relationships
                    WHERE source_story_id = ? AND relationship_type = 'depends_on'
                    AND target_story_id IN ({})
                    """.format(
                        ",".join("?" * len(story_ids))
                    ),
                    [story_id] + story_ids,
                )

                for row in cursor.fetchall():
                    dependency_id = row[0]
                    graph[dependency_id].append(story_id)
                    in_degree[story_id] += 1

        # Perform topological sort using Kahn's algorithm
        queue = [story_id for story_id in story_ids if in_degree[story_id] == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(result) != len(story_ids):
            raise ValueError(
                "Circular dependency detected - cannot determine topological order"
            )

        return result

    def calculate_dependency_priorities(self, story_ids: List[str]) -> Dict[str, int]:
        """Calculate priority levels based on dependency depth (1 = highest priority)."""
        priorities = {}
        depths = self.analyze_dependency_depths(story_ids)

        # Convert depths to priorities (deeper dependencies get higher priority/lower number)
        for story_id, depth in depths.items():
            priorities[story_id] = depth + 1

        return priorities

    def analyze_dependency_depths(self, story_ids: List[str]) -> Dict[str, int]:
        """Analyze the dependency depth for each story (0 = no dependencies, higher = depends on more)."""
        depths = {}

        def _calculate_depth(story_id: str, visited: set) -> int:
            if story_id in visited:
                return 0  # Avoid infinite recursion on cycles
            if story_id in depths:
                return depths[story_id]

            visited.add(story_id)
            max_depth = 0

            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT target_story_id FROM story_relationships
                    WHERE source_story_id = ? AND relationship_type = 'depends_on'
                    """,
                    (story_id,),
                )

                dependencies = [row[0] for row in cursor.fetchall()]

                if dependencies:
                    # If this story has dependencies, its depth is 1 + max depth of its dependencies
                    for dependency_id in dependencies:
                        if (
                            dependency_id in story_ids
                        ):  # Only consider dependencies in our set
                            dep_depth = _calculate_depth(dependency_id, visited.copy())
                            max_depth = max(max_depth, dep_depth + 1)
                else:
                    # No dependencies means this is a base story with depth 0
                    max_depth = 0

            depths[story_id] = max_depth
            return max_depth

        for story_id in story_ids:
            if story_id not in depths:
                _calculate_depth(story_id, set())

        return depths

    def get_ordered_stories_for_parent(self, parent_id: str) -> List[Dict[str, Any]]:
        """Get child stories ordered by dependencies for a given parent."""
        with self.get_connection() as conn:
            # Get all child stories
            cursor = conn.execute(
                "SELECT * FROM stories WHERE parent_id = ?", (parent_id,)
            )

            stories = [dict(row) for row in cursor.fetchall()]
            if not stories:
                return []

            story_ids = [story["id"] for story in stories]

            try:
                # Get topological order
                ordered_ids = self.get_stories_topological_order(story_ids)

                # Return stories in dependency order
                ordered_stories = []
                for story_id in ordered_ids:
                    story_data = next(s for s in stories if s["id"] == story_id)
                    ordered_stories.append(story_data)

                return ordered_stories
            except ValueError:
                # If there are cycles, return stories sorted by creation date
                return sorted(stories, key=lambda s: s["created_at"])

    def generate_dependency_visualization(self, story_ids: List[str]) -> str:
        """Generate a visual representation of story dependencies."""
        if not story_ids:
            return "No stories to visualize."

        # Get story information
        stories = {}
        with self.get_connection() as conn:
            for story_id in story_ids:
                cursor = conn.execute(
                    "SELECT id, title, story_type FROM stories WHERE id = ?",
                    (story_id,),
                )
                row = cursor.fetchone()
                if row:
                    stories[story_id] = {
                        "id": row["id"],
                        "title": row["title"],
                        "type": row["story_type"],
                    }

        # Get dependencies
        dependencies = {}
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT source_story_id, target_story_id FROM story_relationships
                WHERE source_story_id IN ({}) AND target_story_id IN ({})
                AND relationship_type = 'depends_on'
                """.format(
                    ",".join("?" * len(story_ids)), ",".join("?" * len(story_ids))
                ),
                story_ids + story_ids,
            )

            for row in cursor.fetchall():
                source_id = row[0]
                target_id = row[1]
                if source_id not in dependencies:
                    dependencies[source_id] = []
                dependencies[source_id].append(target_id)

        # Generate visualization
        lines = ["Dependency Visualization:", "=" * 50]

        # Add priority information
        try:
            priorities = self.calculate_dependency_priorities(story_ids)
            depths = self.analyze_dependency_depths(story_ids)
            topological_order = self.get_stories_topological_order(story_ids)

            lines.append("\nExecution Order (dependencies first):")
            for i, story_id in enumerate(topological_order, 1):
                story = stories.get(story_id, {"title": "Unknown", "type": "unknown"})
                priority = priorities.get(story_id, 0)
                depth = depths.get(story_id, 0)
                lines.append(
                    f"  {i:2d}. [{story['type']:10}] {story['title']} (Priority: {priority}, Depth: {depth})"
                )

            lines.append("\nDependency Graph:")
            for story_id in story_ids:
                story = stories.get(story_id, {"title": "Unknown", "type": "unknown"})
                story_deps = dependencies.get(story_id, [])

                if story_deps:
                    dep_titles = [
                        stories.get(dep_id, {"title": "Unknown"})["title"]
                        for dep_id in story_deps
                    ]
                    lines.append(
                        f"  • {story['title']} → depends on → {', '.join(dep_titles)}"
                    )
                else:
                    lines.append(f"  • {story['title']} (no dependencies)")

        except ValueError as e:
            lines.append(f"\nError: {e}")
            lines.append("\nStories (unordered due to cycles):")
            for story_id in story_ids:
                story = stories.get(story_id, {"title": "Unknown", "type": "unknown"})
                lines.append(f"  • [{story['type']:10}] {story['title']}")

        return "\n".join(lines)

    def _row_to_story(self, row: sqlite3.Row) -> Union[Epic, UserStory, SubStory]:
        """Convert database row to appropriate story object."""
        story_type = StoryType(row["story_type"])

        # Parse JSON fields
        metadata = json.loads(row["metadata"] or "{}")
        acceptance_criteria = json.loads(row["acceptance_criteria"] or "[]")
        target_repositories = json.loads(row["target_repositories"] or "[]")

        # Common fields
        common_data = {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "status": StoryStatus(row["status"]),
            "created_at": datetime.fromisoformat(row["created_at"]),
            "updated_at": datetime.fromisoformat(row["updated_at"]),
            "metadata": metadata,
        }

        if story_type == StoryType.EPIC:
            return Epic(
                **common_data,
                business_value=row["business_value"] or "",
                acceptance_criteria=acceptance_criteria,
                target_repositories=target_repositories,
                estimated_duration_weeks=row["estimated_duration_weeks"],
            )

        elif story_type == StoryType.USER_STORY:
            return UserStory(
                **common_data,
                epic_id=row["parent_id"] or "",
                user_persona=row["user_persona"] or "",
                user_goal=row["user_goal"] or "",
                acceptance_criteria=acceptance_criteria,
                target_repositories=target_repositories,
                story_points=row["story_points"],
            )

        elif story_type == StoryType.SUB_STORY:
            technical_requirements = json.loads(row["technical_requirements"] or "[]")
            dependencies = json.loads(row["dependencies"] or "[]")

            return SubStory(
                **common_data,
                user_story_id=row["parent_id"] or "",
                department=row["department"] or "",
                technical_requirements=technical_requirements,
                dependencies=dependencies,
                target_repository=row["target_repository"] or "",
                assignee=row["assignee"],
                estimated_hours=row["estimated_hours"],
            )

        else:
            raise ValueError(f"Unknown story type: {story_type}")

    # Conversation management methods

    def save_conversation(self, conversation: Conversation) -> str:
        """Save a conversation to the database."""
        with self.get_connection() as conn:
            # Save conversation
            conv_data = conversation.to_dict()
            conv_data["updated_at"] = datetime.now(timezone.utc).isoformat()

            conv_columns = ", ".join(conv_data.keys())
            conv_placeholders = ", ".join(["?" for _ in conv_data])

            conn.execute(
                f"INSERT OR REPLACE INTO conversations ({conv_columns}) VALUES ({conv_placeholders})",
                list(conv_data.values()),
            )

            # Save participants
            for participant in conversation.participants:
                part_data = participant.to_dict()
                part_data["conversation_id"] = conversation.id

                part_columns = ", ".join(part_data.keys())
                part_placeholders = ", ".join(["?" for _ in part_data])

                conn.execute(
                    f"INSERT OR REPLACE INTO conversation_participants ({part_columns}) VALUES ({part_placeholders})",
                    list(part_data.values()),
                )

            # Save messages
            for message in conversation.messages:
                msg_data = message.to_dict()

                msg_columns = ", ".join(msg_data.keys())
                msg_placeholders = ", ".join(["?" for _ in msg_data])

                conn.execute(
                    f"INSERT OR REPLACE INTO conversation_messages ({msg_columns}) VALUES ({msg_placeholders})",
                    list(msg_data.values()),
                )

            return conversation.id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Retrieve a conversation by ID with all participants and messages."""
        with self.get_connection() as conn:
            # Get conversation
            cursor = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            )
            conv_row = cursor.fetchone()

            if not conv_row:
                return None

            # Get participants
            cursor = conn.execute(
                "SELECT * FROM conversation_participants WHERE conversation_id = ?",
                (conversation_id,),
            )
            participants = []
            for part_row in cursor.fetchall():
                participant = ConversationParticipant(
                    id=part_row["id"],
                    name=part_row["name"],
                    role=part_row["role"],
                    repository=part_row["repository"],
                    metadata=json.loads(part_row["metadata"] or "{}"),
                )
                participants.append(participant)

            # Get messages
            cursor = conn.execute(
                "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY created_at",
                (conversation_id,),
            )
            messages = []
            for msg_row in cursor.fetchall():
                message = Message(
                    id=msg_row["id"],
                    conversation_id=msg_row["conversation_id"],
                    participant_id=msg_row["participant_id"],
                    content=msg_row["content"],
                    message_type=msg_row["message_type"],
                    repository_context=msg_row["repository_context"],
                    created_at=datetime.fromisoformat(msg_row["created_at"]),
                    metadata=json.loads(msg_row["metadata"] or "{}"),
                )
                messages.append(message)

            # Create conversation object
            conversation = Conversation(
                id=conv_row["id"],
                title=conv_row["title"],
                description=conv_row["description"],
                repositories=json.loads(conv_row["repositories"] or "[]"),
                participants=participants,
                messages=messages,
                status=conv_row["status"],
                decision_summary=conv_row["decision_summary"],
                created_at=datetime.fromisoformat(conv_row["created_at"]),
                updated_at=datetime.fromisoformat(conv_row["updated_at"]),
                metadata=json.loads(conv_row["metadata"] or "{}"),
            )

            return conversation

    def list_conversations(
        self, repository: Optional[str] = None, status: Optional[str] = None
    ) -> List[Conversation]:
        """List conversations, optionally filtered by repository or status."""
        with self.get_connection() as conn:
            query = "SELECT id FROM conversations"
            params = []
            conditions = []

            if status:
                conditions.append("status = ?")
                params.append(status)

            if repository:
                conditions.append("repositories LIKE ?")
                params.append(f'%"{repository}"%')

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY updated_at DESC"

            cursor = conn.execute(query, params)
            conversation_ids = [row[0] for row in cursor.fetchall()]

            conversations = []
            for conv_id in conversation_ids:
                conv = self.get_conversation(conv_id)
                if conv:
                    conversations.append(conv)

            return conversations

    def get_conversations_by_repository(self, repository: str) -> List[Conversation]:
        """Get all conversations involving a specific repository."""
        return self.list_conversations(repository=repository)

    def get_stories_by_github_issue(
        self, repository_name: str, issue_number: int
    ) -> List[Union[Epic, UserStory, SubStory]]:
        """Get stories linked to a specific GitHub issue."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT s.* FROM stories s
                JOIN github_issues gi ON s.id = gi.story_id
                WHERE gi.repository_name = ? AND gi.issue_number = ?
                """,
                (repository_name, issue_number),
            )

            return [self._row_to_story(row) for row in cursor.fetchall()]

    def log_status_transition(
        self,
        story_id: str,
        old_status: Optional[str],
        new_status: str,
        trigger_type: str = "manual",
        trigger_source: Optional[str] = None,
        event_type: Optional[str] = None,
        repository_name: Optional[str] = None,
        pr_number: Optional[int] = None,
        issue_number: Optional[int] = None,
        commit_sha: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Log a status transition to the audit trail."""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO status_transitions (
                        story_id, old_status, new_status, trigger_type, trigger_source,
                        event_type, repository_name, pr_number, issue_number, commit_sha,
                        user_id, timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        story_id,
                        old_status,
                        new_status,
                        trigger_type,
                        trigger_source,
                        event_type,
                        repository_name,
                        pr_number,
                        issue_number,
                        commit_sha,
                        user_id,
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(metadata or {}),
                    ),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to log status transition: {e}")
                return False

    def get_status_transitions(
        self, story_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get status transition history."""
        with self.get_connection() as conn:
            if story_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM status_transitions
                    WHERE story_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (story_id, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM status_transitions
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            transitions = []
            for row in cursor.fetchall():
                transition = dict(row)
                transition["metadata"] = json.loads(transition["metadata"] or "{}")
                transitions.append(transition)

            return transitions

    def create_github_issue_link(
        self, story_id: str, repository_name: str, issue_number: int, issue_url: str
    ) -> bool:
        """Create a link between a story and a GitHub issue."""
        with self.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO github_issues (
                        story_id, repository_name, issue_number, issue_url, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        story_id,
                        repository_name,
                        issue_number,
                        issue_url,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to create GitHub issue link: {e}")
                return False

    # Pipeline monitoring methods

    def store_pipeline_run(self, pipeline_run) -> bool:
        """Store a pipeline run in the database."""
        with self.get_connection() as conn:
            try:
                data = pipeline_run.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO pipeline_runs ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store pipeline run: {e}")
                return False

    def store_pipeline_failure(self, failure) -> bool:
        """Store a pipeline failure in the database."""
        with self.get_connection() as conn:
            try:
                data = failure.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO pipeline_failures ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store pipeline failure: {e}")
                return False

    def store_failure_pattern(self, pattern) -> bool:
        """Store a failure pattern in the database."""
        with self.get_connection() as conn:
            try:
                data = pattern.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO failure_patterns ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store failure pattern: {e}")
                return False

    def get_recent_pipeline_failures(
        self, repository: Optional[str] = None, days: int = 7
    ) -> List:
        """Get recent pipeline failures from the database."""
        from models import FailureCategory, FailureSeverity, PipelineFailure

        with self.get_connection() as conn:
            query = """
                SELECT * FROM pipeline_failures 
                WHERE detected_at >= datetime('now', '-{} days')
            """.format(
                days
            )
            params = []

            if repository:
                query += " AND repository = ?"
                params.append(repository)

            query += " ORDER BY detected_at DESC"

            cursor = conn.execute(query, params)
            failures = []

            for row in cursor.fetchall():
                failure = PipelineFailure.from_dict(dict(row))
                failures.append(failure)

            return failures

    def get_failure_patterns(self, days: int = 30) -> List:
        """Get failure patterns from the database."""
        import json

        from models import FailureCategory, FailurePattern

        with self.get_connection() as conn:
            query = """
                SELECT * FROM failure_patterns 
                WHERE last_seen >= datetime('now', '-{} days')
                ORDER BY failure_count DESC
            """.format(
                days
            )

            cursor = conn.execute(query)
            patterns = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                pattern = FailurePattern(
                    pattern_id=row_dict["pattern_id"],
                    category=FailureCategory(row_dict["category"]),
                    description=row_dict["description"],
                    failure_count=row_dict["failure_count"],
                    repositories=json.loads(row_dict["repositories"]),
                    first_seen=datetime.fromisoformat(row_dict["first_seen"]),
                    last_seen=datetime.fromisoformat(row_dict["last_seen"]),
                    resolution_suggestions=json.loads(
                        row_dict["resolution_suggestions"]
                    ),
                    metadata=json.loads(row_dict["metadata"]),
                )
                patterns.append(pattern)

            return patterns

    def get_recent_pipeline_runs(
        self, repository: Optional[str] = None, days: int = 7
    ) -> List:
        """Get recent pipeline runs from the database."""
        from models import PipelineRun, PipelineStatus

        with self.get_connection() as conn:
            query = """
                SELECT * FROM pipeline_runs 
                WHERE started_at >= datetime('now', '-{} days')
            """.format(
                days
            )
            params = []

            if repository:
                query += " AND repository = ?"
                params.append(repository)

            query += " ORDER BY started_at DESC"

            cursor = conn.execute(query, params)
            runs = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                run = PipelineRun(
                    id=row_dict["id"],
                    repository=row_dict["repository"],
                    branch=row_dict["branch"],
                    commit_sha=row_dict["commit_sha"],
                    workflow_name=row_dict["workflow_name"],
                    status=PipelineStatus(row_dict["status"]),
                    started_at=datetime.fromisoformat(row_dict["started_at"]),
                    completed_at=(
                        datetime.fromisoformat(row_dict["completed_at"])
                        if row_dict["completed_at"]
                        else None
                    ),
                    metadata=json.loads(row_dict["metadata"]),
                )
                runs.append(run)

            return runs

    def store_retry_attempt(self, retry_attempt) -> bool:
        """Store a retry attempt in the database."""
        with self.get_connection() as conn:
            try:
                data = retry_attempt.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO retry_attempts ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store retry attempt: {e}")
                return False

    def get_retry_attempts(self, failure_id: str) -> List:
        """Get retry attempts for a specific failure."""
        from models import RetryAttempt

        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM retry_attempts WHERE failure_id = ? ORDER BY attempt_number",
                (failure_id,),
            )
            attempts = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                attempt = RetryAttempt.from_dict(row_dict)
                attempts.append(attempt)

            return attempts

    def get_recent_retry_attempts(
        self, repository: Optional[str] = None, days: int = 7
    ) -> List:
        """Get recent retry attempts from the database."""
        from models import RetryAttempt

        with self.get_connection() as conn:
            query = """
                SELECT * FROM retry_attempts 
                WHERE attempted_at >= datetime('now', '-{} days')
            """.format(
                days
            )
            params = []

            if repository:
                query += " AND repository = ?"
                params.append(repository)

            query += " ORDER BY attempted_at DESC"

            cursor = conn.execute(query, params)
            attempts = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                attempt = RetryAttempt.from_dict(row_dict)
                attempts.append(attempt)

            return attempts

    def store_escalation_record(self, escalation_record) -> bool:
        """Store an escalation record in the database."""
        with self.get_connection() as conn:
            try:
                data = escalation_record.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO escalation_records ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store escalation record: {e}")
                return False

    def get_recent_escalations(
        self,
        repository: Optional[str] = None,
        days: int = 30,
        resolved: Optional[bool] = None,
    ) -> List:
        """Get recent escalation records from the database."""
        from models import EscalationRecord

        with self.get_connection() as conn:
            query = """
                SELECT * FROM escalation_records 
                WHERE escalated_at >= datetime('now', '-{} days')
            """.format(
                days
            )
            params = []

            if repository:
                query += " AND repository = ?"
                params.append(repository)

            if resolved is not None:
                query += " AND resolved = ?"
                params.append(resolved)

            query += " ORDER BY escalated_at DESC"

            cursor = conn.execute(query, params)
            escalations = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                escalation = EscalationRecord.from_dict(row_dict)
                escalations.append(escalation)

            return escalations

    def store_manual_intervention(self, intervention) -> bool:
        """Store a manual intervention record in the database."""
        with self.get_connection() as conn:
            try:
                data = intervention.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO manual_interventions ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store manual intervention: {e}")
                return False

    def get_manual_intervention(self, intervention_id: str):
        """Get a manual intervention by ID."""
        try:
            from .models import ManualIntervention
        except ImportError:
            from models import ManualIntervention

        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM manual_interventions WHERE id = ?", (intervention_id,)
            )
            row = cursor.fetchone()
            if row:
                return ManualIntervention.from_dict(dict(row))
            return None

    def get_interventions_by_conversation(
        self, conversation_id: str, status: Optional[str] = None
    ) -> List:
        """Get manual interventions for a conversation."""
        try:
            from .models import ManualIntervention
        except ImportError:
            from models import ManualIntervention

        with self.get_connection() as conn:
            query = "SELECT * FROM manual_interventions WHERE conversation_id = ?"
            params = [conversation_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY triggered_at DESC"

            cursor = conn.execute(query, params)
            interventions = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                intervention = ManualIntervention.from_dict(row_dict)
                interventions.append(intervention)

            return interventions

    def get_pending_interventions(self, limit: int = 50) -> List:
        """Get pending manual interventions across all conversations."""
        try:
            from .models import ManualIntervention
        except ImportError:
            from models import ManualIntervention

        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM manual_interventions 
                WHERE status = 'pending' 
                ORDER BY triggered_at ASC 
                LIMIT ?
                """,
                (limit,),
            )
            interventions = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                intervention = ManualIntervention.from_dict(row_dict)
                interventions.append(intervention)

            return interventions

    def count_recent_failures_by_pattern(
        self, repository: str, failure_pattern: str, hours: int = 24
    ) -> int:
        """Count recent failures matching a pattern."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM pipeline_failures 
                WHERE repository = ? 
                AND failure_message LIKE ? 
                AND detected_at >= datetime('now', '-{} hours')
                """.format(
                    hours
                ),
                (repository, f"%{failure_pattern}%"),
            )
            return cursor.fetchone()[0]

    def store_workflow_checkpoint(self, checkpoint) -> bool:
        """Store a workflow checkpoint in the database."""
        with self.get_connection() as conn:
            try:
                data = checkpoint.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO workflow_checkpoints ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store workflow checkpoint: {e}")
                return False

    def get_workflow_checkpoints(
        self,
        repository: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
    ) -> List:
        """Get workflow checkpoints from the database."""
        with self.get_connection() as conn:
            query = "SELECT * FROM workflow_checkpoints WHERE 1=1"
            params = []

            if repository:
                query += " AND repository = ?"
                params.append(repository)

            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            checkpoints = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                checkpoint = WorkflowCheckpoint.from_dict(row_dict)
                checkpoints.append(checkpoint)

            return checkpoints

    def get_latest_checkpoint(
        self, repository: str, workflow_name: str, checkpoint_type: Optional[str] = None
    ) -> Optional:
        """Get the latest checkpoint for a repository and workflow."""
        with self.get_connection() as conn:
            query = """
                SELECT * FROM workflow_checkpoints 
                WHERE repository = ? AND workflow_name = ?
            """
            params = [repository, workflow_name]

            if checkpoint_type:
                query += " AND checkpoint_type = ?"
                params.append(checkpoint_type)

            query += " ORDER BY created_at DESC LIMIT 1"

            cursor = conn.execute(query, params)
            row = cursor.fetchone()

            if row:
                row_dict = dict(row)
                return WorkflowCheckpoint.from_dict(row_dict)

            return None

    def store_recovery_state(self, recovery_state) -> bool:
        """Store a recovery state in the database."""
        with self.get_connection() as conn:
            try:
                data = recovery_state.to_dict()
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])

                conn.execute(
                    f"INSERT OR REPLACE INTO recovery_states ({columns}) VALUES ({placeholders})",
                    list(data.values()),
                )
                return True
            except Exception as e:
                logger.error(f"Failed to store recovery state: {e}")
                return False

    def get_recovery_states(
        self,
        repository: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List:
        """Get recovery states from the database."""
        with self.get_connection() as conn:
            query = "SELECT * FROM recovery_states WHERE 1=1"
            params = []

            if repository:
                query += " AND repository = ?"
                params.append(repository)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            recovery_states = []

            for row in cursor.fetchall():
                row_dict = dict(row)
                recovery_state = RecoveryState.from_dict(row_dict)
                recovery_states.append(recovery_state)

            return recovery_states

    def get_recovery_state_by_id(self, recovery_id: str) -> Optional:
        """Get a recovery state by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM recovery_states WHERE id = ?",
                (recovery_id,),
            )
            row = cursor.fetchone()

            if row:
                row_dict = dict(row)
                return RecoveryState.from_dict(row_dict)

            return None

    def delete_old_checkpoints(self, repository: str, keep_days: int = 30) -> int:
        """Delete old workflow checkpoints to manage storage."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM workflow_checkpoints 
                WHERE repository = ? 
                AND created_at < datetime('now', '-{} days')
                """.format(
                    keep_days
                ),
                (repository,),
            )
            return cursor.rowcount


def run_migrations(db_path: str = "storyteller.db"):
    """Run database migrations to set up the schema."""
    print(f"Setting up database schema at {db_path}...")

    db_manager = DatabaseManager(db_path)

    # Check if database was created successfully
    with db_manager.get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "stories",
            "story_relationships",
            "github_issues",
            "status_transitions",
            "conversations",
            "conversation_participants",
            "conversation_messages",
            "pipeline_runs",
            "pipeline_failures",
            "failure_patterns",
            "retry_attempts",
            "escalation_records",
            "manual_interventions",
            "workflow_checkpoints",
            "recovery_states",
        ]
        missing_tables = [t for t in expected_tables if t not in tables]

        if missing_tables:
            raise Exception(f"Failed to create tables: {missing_tables}")

        print(f"✓ Created tables: {', '.join(tables)}")

        # Create indexes
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"✓ Created indexes: {', '.join(indexes)}")

    print("Database migration completed successfully!")
    return db_manager


if __name__ == "__main__":
    # Run migrations when script is executed directly
    run_migrations()
