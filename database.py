"""Database schema and migration system for hierarchical story management."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from models import (
    Conversation,
    ConversationParticipant,
    Epic,
    Message,
    StoryHierarchy,
    StoryStatus,
    StoryType,
    SubStory,
    UserStory,
)


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
                status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'ready', 'in_progress', 'review', 'done', 'blocked')),
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
                relationship_type TEXT NOT NULL CHECK (relationship_type IN ('depends_on', 'blocks', 'relates_to', 'duplicates')),
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
                message_type TEXT NOT NULL DEFAULT 'text' CHECK (message_type IN ('text', 'system', 'decision', 'context_share')),
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

    def get_stories_by_github_issue(self, repository_name: str, issue_number: int) -> List[Union[Epic, UserStory, SubStory]]:
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
        metadata: Optional[Dict[str, Any]] = None
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
                        json.dumps(metadata or {})
                    )
                )
                return True
            except Exception as e:
                logger.error(f"Failed to log status transition: {e}")
                return False

    def get_status_transitions(self, story_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
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
                    (story_id, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM status_transitions 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            transitions = []
            for row in cursor.fetchall():
                transition = dict(row)
                transition['metadata'] = json.loads(transition['metadata'] or '{}')
                transitions.append(transition)
            
            return transitions

    def create_github_issue_link(self, story_id: str, repository_name: str, issue_number: int, issue_url: str) -> bool:
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
                        datetime.now(timezone.utc).isoformat()
                    )
                )
                return True
            except Exception as e:
                logger.error(f"Failed to create GitHub issue link: {e}")
                return False


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
            "conversations",
            "conversation_participants",
            "conversation_messages",
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
