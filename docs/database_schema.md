# Hierarchical Story Database Schema Documentation

## Overview

The storyteller system implements a three-tier hierarchical story management system designed to support complex project organization with clear parent-child relationships.

## Hierarchy Structure

```
Epic (Top Level)
├── User Story (Mid Level)
│   ├── Sub-story (Task Level)
│   ├── Sub-story (Task Level)
│   └── Sub-story (Task Level)
├── User Story (Mid Level)
│   └── Sub-story (Task Level)
└── User Story (Mid Level)
```

## Database Tables

### Epics Table

**Purpose**: Top-level containers for major features or initiatives

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key, auto-increment |
| `title` | String(255) | Epic title |
| `description` | Text | Detailed epic description |
| `story_id` | String(50) | External unique identifier |
| `status` | String(50) | Epic status (open, in_progress, done, closed) |
| `priority` | String(20) | Priority level (low, medium, high, critical) |
| `labels` | JSON | Array of labels for categorization |
| `github_repository` | String(255) | Associated GitHub repository |
| `github_issue_number` | Integer | GitHub issue number |
| `github_url` | String(500) | Direct link to GitHub issue |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

**Indexes**:
- Primary key on `id`
- Unique index on `story_id`
- Index on `status` for filtering
- Index on `title` for searches

### Stories Table

**Purpose**: User stories that belong to epics

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key, auto-increment |
| `title` | String(255) | Story title |
| `description` | Text | Story description |
| `story_id` | String(50) | External unique identifier |
| `epic_id` | Integer | Foreign key to epics table |
| `status` | String(50) | Story status |
| `priority` | String(20) | Priority level |
| `labels` | JSON | Array of labels |
| `story_points` | Integer | Estimation points |
| `original_content` | Text | Original story content |
| `synthesized_analysis` | Text | AI-generated analysis |
| `expert_analyses_count` | Integer | Number of expert analyses |
| `target_repositories` | JSON | Array of target repositories |
| `github_repository` | String(255) | Associated GitHub repository |
| `github_issue_number` | Integer | GitHub issue number |
| `github_url` | String(500) | Direct link to GitHub issue |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

**Relationships**:
- `epic_id` → `epics.id` (Many-to-One)

**Indexes**:
- Primary key on `id`
- Unique index on `story_id`
- Index on `epic_id` for parent lookups
- Index on `status` for filtering
- Index on `title` for searches

### Sub-Stories Table

**Purpose**: Individual tasks that implement user stories

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key, auto-increment |
| `title` | String(255) | Sub-story title |
| `description` | Text | Task description |
| `story_id` | String(50) | External unique identifier |
| `story_id_fk` | Integer | Foreign key to stories table |
| `status` | String(50) | Task status |
| `priority` | String(20) | Priority level |
| `labels` | JSON | Array of labels |
| `story_points` | Integer | Estimation points |
| `acceptance_criteria` | JSON | Array of acceptance criteria |
| `technical_requirements` | Text | Technical implementation details |
| `estimated_hours` | Integer | Estimated work hours |
| `github_repository` | String(255) | Associated GitHub repository |
| `github_issue_number` | Integer | GitHub issue number |
| `github_url` | String(500) | Direct link to GitHub issue |
| `assigned_to` | String(255) | Assigned developer/team |
| `assigned_role` | String(100) | Expert role responsible |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

**Relationships**:
- `story_id_fk` → `stories.id` (Many-to-One)

**Indexes**:
- Primary key on `id`
- Unique index on `story_id`
- Index on `story_id_fk` for parent lookups
- Index on `status` for filtering
- Index on `title` for searches

## Relationship Constraints

### Foreign Key Relationships

1. **Stories → Epics**: 
   - Column: `stories.epic_id`
   - References: `epics.id`
   - Constraint: `fk_stories_epic_id`
   - Cascade: Restrict (prevent epic deletion if stories exist)

2. **Sub-Stories → Stories**:
   - Column: `sub_stories.story_id_fk`
   - References: `stories.id`
   - Constraint: `fk_sub_stories_story_id`
   - Cascade: Restrict (prevent story deletion if sub-stories exist)

### Unique Constraints

- Each `story_id` must be unique across all tables
- This enables cross-table lookups and external system integration

## Status Values

### Common Status Values
- `open` - Newly created, ready for work
- `in_progress` - Currently being worked on
- `review` - Under review/testing
- `done` - Completed successfully
- `closed` - Closed without completion
- `blocked` - Cannot proceed due to dependencies

### Epic-Specific Status
- `planning` - In planning phase
- `active` - Has active stories

### Story-Specific Status
- `backlog` - In product backlog
- `ready` - Ready for development
- `testing` - In QA testing

## Priority Values

- `low` - Low priority
- `medium` - Medium priority (default)
- `high` - High priority
- `critical` - Critical/urgent

## JSON Field Structures

### Labels Field
```json
["backend", "api", "database", "user-management"]
```

### Target Repositories Field (Stories)
```json
["backend", "frontend", "mobile"]
```

### Acceptance Criteria Field (Sub-Stories)
```json
[
  "User can login with email and password",
  "Invalid credentials show error message",
  "Successful login redirects to dashboard"
]
```

## Query Patterns

### Get Complete Hierarchy
```sql
-- Get epic with all stories and sub-stories
SELECT e.*, s.*, ss.*
FROM epics e
LEFT JOIN stories s ON e.id = s.epic_id
LEFT JOIN sub_stories ss ON s.id = ss.story_id_fk
WHERE e.id = ?
ORDER BY s.created_at, ss.created_at;
```

### Get Story Counts by Epic
```sql
SELECT 
    e.id,
    e.title,
    COUNT(DISTINCT s.id) as story_count,
    COUNT(ss.id) as sub_story_count
FROM epics e
LEFT JOIN stories s ON e.id = s.epic_id
LEFT JOIN sub_stories ss ON s.id = ss.story_id_fk
GROUP BY e.id, e.title
ORDER BY e.created_at DESC;
```

### Search Across Hierarchy
```sql
-- Search by title across all levels
SELECT 'epic' as type, id, title, story_id FROM epics WHERE title LIKE '%search%'
UNION ALL
SELECT 'story' as type, id, title, story_id FROM stories WHERE title LIKE '%search%'
UNION ALL
SELECT 'sub_story' as type, id, title, story_id FROM sub_stories WHERE title LIKE '%search%'
ORDER BY title;
```

## Migration Strategy

### Initial Migration
- File: `686d51beb1b0_create_hierarchical_story_schema.py`
- Creates all three tables with proper relationships
- Includes all indexes and constraints

### Future Migrations
- Use Alembic for schema changes
- Always include both upgrade and downgrade paths
- Test migrations on sample data

## Performance Considerations

### Indexing Strategy
- All primary keys automatically indexed
- Foreign keys indexed for join performance
- Status fields indexed for filtering
- Title fields indexed for search

### Query Optimization
- Use `selectinload()` for eager loading relationships
- Limit result sets with pagination
- Consider query complexity for deep hierarchies

## Integration Points

### GitHub Integration
- Each level can link to GitHub issues
- Repository field supports multi-repo workflows
- URL field provides direct navigation

### External Systems
- `story_id` field enables external system integration
- JSON fields support flexible metadata
- Status synchronization possible

## Data Integrity Rules

1. **Orphan Prevention**: Stories cannot exist without valid epic (optional foreign key allows orphaned stories)
2. **Unique Identifiers**: All `story_id` values must be unique
3. **Status Consistency**: Status values should follow defined enum
4. **Audit Trail**: All creation and update timestamps maintained

## Security Considerations

1. **Input Validation**: All text fields should be validated for length and content
2. **JSON Validation**: JSON fields should validate structure
3. **Access Control**: Repository-level access control recommended
4. **Data Sanitization**: HTML/script content in descriptions should be sanitized