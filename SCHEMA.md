# Hierarchical Story Management Database Schema

## Overview

The hierarchical story management system implements a three-level story hierarchy: **Epic → User Story → Sub-story**. This document describes the database schema, relationships, and migration process.

## Database Schema

### Tables

#### `stories`
The main table storing all story types with a hierarchical parent-child relationship.

```sql
CREATE TABLE stories (
    id TEXT PRIMARY KEY,                    -- Unique story identifier (story_xxxxxxxx)
    story_type TEXT NOT NULL,               -- 'epic', 'user_story', or 'sub_story'
    parent_id TEXT,                         -- Reference to parent story (NULL for epics)
    title TEXT NOT NULL,                    -- Story title
    description TEXT NOT NULL DEFAULT '',   -- Detailed description
    status TEXT NOT NULL DEFAULT 'draft',   -- Current status (draft, ready, in_progress, review, done, blocked)
    created_at TEXT NOT NULL,               -- ISO timestamp of creation
    updated_at TEXT NOT NULL,               -- ISO timestamp of last update
    metadata TEXT DEFAULT '{}',             -- JSON metadata for extensibility
    
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
    
    FOREIGN KEY (parent_id) REFERENCES stories (id) ON DELETE CASCADE,
    CHECK (story_type IN ('epic', 'user_story', 'sub_story')),
    CHECK (status IN ('draft', 'ready', 'in_progress', 'review', 'done', 'blocked'))
);
```

**Indexes:**
- `idx_stories_parent_id` - For hierarchical queries
- `idx_stories_type` - For filtering by story type
- `idx_stories_status` - For status-based queries

#### `story_relationships`
Stores complex relationships between stories beyond the basic hierarchy.

```sql
CREATE TABLE story_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_story_id TEXT NOT NULL,
    target_story_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,        -- 'depends_on', 'blocks', 'relates_to', 'duplicates'
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    
    FOREIGN KEY (source_story_id) REFERENCES stories (id) ON DELETE CASCADE,
    FOREIGN KEY (target_story_id) REFERENCES stories (id) ON DELETE CASCADE,
    UNIQUE (source_story_id, target_story_id, relationship_type),
    CHECK (relationship_type IN ('depends_on', 'blocks', 'relates_to', 'duplicates'))
);
```

#### `github_issues`
Links stories to GitHub issues for integration tracking.

```sql
CREATE TABLE github_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    synced_at TEXT,
    
    FOREIGN KEY (story_id) REFERENCES stories (id) ON DELETE CASCADE,
    UNIQUE (story_id, repository_name)
);
```

## Data Model Hierarchy

### Epic
- **Purpose**: High-level business objectives spanning multiple user stories
- **Parent**: None (top-level)
- **Children**: User Stories
- **Key Fields**: `business_value`, `estimated_duration_weeks`, `acceptance_criteria`, `target_repositories`

### User Story
- **Purpose**: Feature requests from user perspective
- **Parent**: Epic
- **Children**: Sub-stories
- **Key Fields**: `user_persona`, `user_goal`, `story_points`, `acceptance_criteria`

### Sub-story
- **Purpose**: Technical implementation tasks
- **Parent**: User Story
- **Children**: None (leaf nodes)
- **Key Fields**: `department`, `technical_requirements`, `target_repository`, `assignee`, `estimated_hours`

## Relationships

### Hierarchical Relationships
- **Epic ← User Story**: One-to-many (epic.id = user_story.parent_id)
- **User Story ← Sub-story**: One-to-many (user_story.id = sub_story.parent_id)

### Cross-cutting Relationships
Stories can have additional relationships stored in `story_relationships`:
- **depends_on**: Story A depends on Story B completion
- **blocks**: Story A blocks Story B from starting  
- **relates_to**: General relationship between stories
- **duplicates**: Story A duplicates Story B functionality

## Status Management

### Status Flow
```
draft → ready → in_progress → review → done
  ↓       ↓         ↓           ↓
blocked ← blocked ← blocked ← blocked
```

### Status Propagation Rules
- Epic status should reflect overall progress of user stories
- User Story status should reflect overall progress of sub-stories
- Status updates can trigger automated workflows

## Migration Process

### Initial Setup
```bash
# Run migration with sample data
python migrate.py --reset --sample-data

# Run migration on existing database
python migrate.py

# Custom database location
python migrate.py --db-path /path/to/custom.db
```

### Schema Versioning
The schema supports incremental migrations:
1. Check existing schema version
2. Apply only necessary changes
3. Maintain backward compatibility
4. Preserve data integrity

## Usage Examples

### Creating a Complete Hierarchy
```python
from database import DatabaseManager
from models import Epic, UserStory, SubStory

db = DatabaseManager()

# Create epic
epic = Epic(
    title="User Authentication System",
    business_value="Enable personalized user experiences",
    estimated_duration_weeks=4
)
db.save_story(epic)

# Create user story
user_story = UserStory(
    epic_id=epic.id,
    title="User Registration",
    user_persona="New User",
    user_goal="Create account to access platform",
    story_points=5
)
db.save_story(user_story)

# Create sub-stories
backend_task = SubStory(
    user_story_id=user_story.id,
    title="Registration API",
    department="backend",
    target_repository="backend",
    estimated_hours=16
)
db.save_story(backend_task)
```

### Querying Hierarchies
```python
# Get complete epic with all children
hierarchy = db.get_epic_hierarchy(epic.id)

# Calculate progress
epic_progress = hierarchy.get_epic_progress()
print(f"Epic: {epic_progress['completed']}/{epic_progress['total']} stories done")

# Get user story progress
us_progress = hierarchy.get_user_story_progress(user_story.id)
print(f"User Story: {us_progress['percentage']}% complete")
```

### Managing Relationships
```python
# Add dependency relationship
db.add_story_relationship(
    source_id=frontend_task.id,
    target_id=backend_task.id,
    relationship_type="depends_on",
    metadata={"priority": "high"}
)

# Link to GitHub issue
db.link_github_issue(
    story_id=epic.id,
    repository_name="company/backend",
    issue_number=123,
    issue_url="https://github.com/company/backend/issues/123"
)
```

## Data Integrity

### Foreign Key Constraints
- `PRAGMA foreign_keys = ON` ensures referential integrity
- CASCADE deletes automatically remove child stories
- Unique constraints prevent duplicate relationships

### Validation
- CHECK constraints enforce valid enums
- JSON fields validated at application level
- Required fields enforced by NOT NULL constraints

### Backup and Recovery
```bash
# Backup database
sqlite3 storyteller.db ".backup backup.db"

# Restore from backup
cp backup.db storyteller.db
```

## Performance Considerations

### Indexing Strategy
- Parent-child queries optimized with `idx_stories_parent_id`
- Status filtering optimized with `idx_stories_status`
- Story type queries optimized with `idx_stories_type`

### Query Patterns
- Use `get_epic_hierarchy()` for complete trees
- Use `get_children_stories()` for specific levels
- Batch operations for bulk updates

### Scaling
- SQLite suitable for single-user scenarios
- For multi-user scenarios, consider PostgreSQL migration
- JSON fields provide schema flexibility without migrations

## Security

### Access Control
- Application-level security (no database users)
- File system permissions protect SQLite file
- Backup encryption recommended for sensitive data

### Data Sanitization
- All user inputs validated and escaped
- JSON fields validated before storage
- SQL injection prevented by parameterized queries