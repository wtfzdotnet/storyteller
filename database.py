"""Database schema and migration system for hierarchical story management."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from models import BaseStory, Epic, UserStory, SubStory, StoryStatus, StoryType, StoryHierarchy


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
        conn.execute("""
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
        """)
        
        # Index for hierarchical queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_parent_id ON stories (parent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_type ON stories (story_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_status ON stories (status)")
        
        # Story relationships table for complex relationships
        conn.execute("""
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
        """)
        
        # GitHub integration table
        conn.execute("""
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
        """)
        
        conn.commit()
    
    def save_story(self, story: Union[Epic, UserStory, SubStory]) -> str:
        """Save a story to the database."""
        with self.get_connection() as conn:
            data = story.to_dict()
            data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Convert lists to JSON strings for storage
            for field in ['acceptance_criteria', 'target_repositories', 'technical_requirements', 'dependencies']:
                if field in data and isinstance(data[field], list):
                    data[field] = json.dumps(data[field])
            
            placeholders = ', '.join(['?' for _ in data])
            columns = ', '.join(data.keys())
            
            conn.execute(
                f"INSERT OR REPLACE INTO stories ({columns}) VALUES ({placeholders})",
                list(data.values())
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
            sub_story_list = self.get_children_stories(user_story.id, StoryType.SUB_STORY)
            if sub_story_list:
                sub_stories[user_story.id] = sub_story_list
        
        return StoryHierarchy(
            epic=epic,
            user_stories=user_stories,
            sub_stories=sub_stories
        )
    
    def get_children_stories(self, parent_id: str, story_type: StoryType) -> List[Union[UserStory, SubStory]]:
        """Get all child stories of a specific type for a parent."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM stories WHERE parent_id = ? AND story_type = ? ORDER BY created_at",
                (parent_id, story_type.value)
            )
            
            return [self._row_to_story(row) for row in cursor.fetchall()]
    
    def get_all_epics(self) -> List[Epic]:
        """Get all epics in the system."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM stories WHERE story_type = 'epic' ORDER BY created_at DESC"
            )
            
            return [self._row_to_story(row) for row in cursor.fetchall()]
    
    def update_story_status(self, story_id: str, status: StoryStatus) -> bool:
        """Update the status of a story."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE stories SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, datetime.now(timezone.utc).isoformat(), story_id)
            )
            return cursor.rowcount > 0
    
    def delete_story(self, story_id: str) -> bool:
        """Delete a story and all its children (CASCADE)."""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
            return cursor.rowcount > 0
    
    def add_story_relationship(self, source_id: str, target_id: str, relationship_type: str, metadata: Dict[str, Any] = None):
        """Add a relationship between two stories."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO story_relationships 
                (source_story_id, target_story_id, relationship_type, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                source_id, target_id, relationship_type,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(metadata or {})
            ))
    
    def get_story_relationships(self, story_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for a story."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM story_relationships 
                WHERE source_story_id = ? OR target_story_id = ?
            """, (story_id, story_id))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def link_github_issue(self, story_id: str, repository_name: str, issue_number: int, issue_url: str):
        """Link a story to a GitHub issue."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO github_issues 
                (story_id, repository_name, issue_number, issue_url, created_at, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                story_id, repository_name, issue_number, issue_url,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat()
            ))
    
    def get_github_issues(self, story_id: str) -> List[Dict[str, Any]]:
        """Get GitHub issues linked to a story."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM github_issues WHERE story_id = ?", 
                (story_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def _row_to_story(self, row: sqlite3.Row) -> Union[Epic, UserStory, SubStory]:
        """Convert database row to appropriate story object."""
        story_type = StoryType(row['story_type'])
        
        # Parse JSON fields
        metadata = json.loads(row['metadata'] or '{}')
        acceptance_criteria = json.loads(row['acceptance_criteria'] or '[]')
        target_repositories = json.loads(row['target_repositories'] or '[]')
        
        # Common fields
        common_data = {
            'id': row['id'],
            'title': row['title'],
            'description': row['description'],
            'status': StoryStatus(row['status']),
            'created_at': datetime.fromisoformat(row['created_at']),
            'updated_at': datetime.fromisoformat(row['updated_at']),
            'metadata': metadata
        }
        
        if story_type == StoryType.EPIC:
            return Epic(
                **common_data,
                business_value=row['business_value'] or '',
                acceptance_criteria=acceptance_criteria,
                target_repositories=target_repositories,
                estimated_duration_weeks=row['estimated_duration_weeks']
            )
        
        elif story_type == StoryType.USER_STORY:
            return UserStory(
                **common_data,
                epic_id=row['parent_id'] or '',
                user_persona=row['user_persona'] or '',
                user_goal=row['user_goal'] or '',
                acceptance_criteria=acceptance_criteria,
                target_repositories=target_repositories,
                story_points=row['story_points']
            )
        
        elif story_type == StoryType.SUB_STORY:
            technical_requirements = json.loads(row['technical_requirements'] or '[]')
            dependencies = json.loads(row['dependencies'] or '[]')
            
            return SubStory(
                **common_data,
                user_story_id=row['parent_id'] or '',
                department=row['department'] or '',
                technical_requirements=technical_requirements,
                dependencies=dependencies,
                target_repository=row['target_repository'] or '',
                assignee=row['assignee'],
                estimated_hours=row['estimated_hours']
            )
        
        else:
            raise ValueError(f"Unknown story type: {story_type}")


def run_migrations(db_path: str = "storyteller.db"):
    """Run database migrations to set up the schema."""
    print(f"Setting up database schema at {db_path}...")
    
    db_manager = DatabaseManager(db_path)
    
    # Check if database was created successfully
    with db_manager.get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['stories', 'story_relationships', 'github_issues']
        missing_tables = [t for t in expected_tables if t not in tables]
        
        if missing_tables:
            raise Exception(f"Failed to create tables: {missing_tables}")
        
        print(f"✓ Created tables: {', '.join(tables)}")
        
        # Create indexes
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"✓ Created indexes: {', '.join(indexes)}")
    
    print("Database migration completed successfully!")
    return db_manager


if __name__ == "__main__":
    # Run migrations when script is executed directly
    run_migrations()