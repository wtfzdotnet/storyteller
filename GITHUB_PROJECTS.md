# GitHub Projects API Integration

This document describes the new GitHub Projects API integration capabilities added to the Storyteller system.

## Overview

The GitHub Projects API integration enables automatic project board creation and management for Epic-driven development workflows. This integration uses GitHub's Projects v2 API via GraphQL to provide seamless synchronization between story hierarchies and project boards.

## Key Features

### 1. Project Creation
- **Repository-level projects**: Create projects within specific repositories
- **Organization-level projects**: Create projects at the organization level
- **Epic-specific projects**: Automatically create projects for specific epics

### 2. Issue Synchronization
- **Single issue sync**: Add individual issues to project boards
- **Bulk operations**: Efficiently add multiple issues to projects
- **Cross-repository support**: Handle issues from multiple repositories

### 3. Custom Field Management
- **Field discovery**: Retrieve all custom fields from a project
- **Field updates**: Update custom field values for project items
- **Story metadata mapping**: Map story properties to project fields

### 4. Story Hierarchy Integration
- **Complete sync**: Synchronize entire epic → user story → sub-story hierarchies
- **Status propagation**: Update project board status based on story status
- **Progress tracking**: Track epic progress through project boards

## Usage Examples

### Basic Project Creation

```python
from github_handler import GitHubHandler
from models import ProjectData
from config import load_config

# Initialize handler
config = load_config()
github_handler = GitHubHandler(config)

# Create a repository-level project
project_data = ProjectData(
    title="Epic: User Authentication",
    description="Project board for user authentication epic"
)

project = await github_handler.create_project(project_data, "my-org/backend-repo")
print(f"Created project: {project['title']} (ID: {project['id']})")
```

### Adding Issues to Projects

```python
# Add single issue
item = await github_handler.add_issue_to_project(
    project_id="PVT_kwDOABC123",
    issue_number=42,
    repository_name="my-org/backend-repo"
)

# Bulk add multiple issues
issue_list = [
    (42, "my-org/backend-repo"),
    (43, "my-org/frontend-repo"),
    (44, "my-org/backend-repo")
]

results = await github_handler.bulk_add_issues_to_project(
    project_id="PVT_kwDOABC123",
    issue_data=issue_list
)
```

### Custom Field Management

```python
# Get all project fields
fields = await github_handler.get_project_fields("PVT_kwDOABC123")
for field in fields:
    print(f"Field: {field.name} (Type: {field.data_type})")

# Update a field value
await github_handler.update_project_item_field(
    project_id="PVT_kwDOABC123",
    item_id="PVTI_kwDOABC456",
    field_id="PVTF_kwDOABC789",
    value={"text": "In Progress"}
)
```

### Epic Project Workflow

```python
from models import Epic

# Create epic
epic = Epic(
    title="User Authentication System",
    description="Comprehensive user authentication",
    business_value="Enable secure user access"
)

# Create dedicated project for epic
project = await github_handler.create_project_for_epic(
    epic=epic,
    organization_login="my-org"
)

# Sync story hierarchy to project (assumes issues exist)
sync_results = await github_handler.sync_story_to_project(
    story_hierarchy=story_hierarchy,
    project_id=project["id"]
)
```

## Configuration

### Environment Variables

Required environment variables for GitHub Projects integration:

```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx  # GitHub token with Projects scope
```

### Repository Configuration

Add project-specific configuration to `.storyteller/config.json`:

```json
{
  "repositories": {
    "backend": {
      "name": "my-org/backend-repo",
      "type": "backend",
      "story_labels": ["backend", "api"],
      "project_settings": {
        "auto_create_projects": true,
        "project_template": "backend-template"
      }
    }
  },
  "github_projects": {
    "default_visibility": "PRIVATE",
    "organization_login": "my-org",
    "field_mappings": {
      "status": "Status",
      "priority": "Priority", 
      "story_points": "Story Points",
      "department": "Department"
    }
  }
}
```

## API Reference

### Core Methods

#### `create_project(project_data, repository_name=None)`
Creates a new GitHub Project v2.

**Parameters:**
- `project_data` (ProjectData): Project configuration
- `repository_name` (str, optional): Repository for repo-level project

**Returns:** Dictionary with project details including ID and URL

#### `add_issue_to_project(project_id, issue_number, repository_name)`
Adds a single issue to a project board.

**Parameters:**
- `project_id` (str): Project ID (PVT_xxx format)
- `issue_number` (int): Issue number
- `repository_name` (str): Full repository name (owner/repo)

**Returns:** Dictionary with project item details

#### `bulk_add_issues_to_project(project_id, issue_data)`
Adds multiple issues to a project in bulk.

**Parameters:**
- `project_id` (str): Project ID
- `issue_data` (List[Tuple[int, str]]): List of (issue_number, repository_name)

**Returns:** List of results for each issue

#### `get_project_fields(project_id)`
Retrieves all custom fields for a project.

**Parameters:**
- `project_id` (str): Project ID

**Returns:** List of ProjectField objects

#### `update_project_item_field(project_id, item_id, field_id, value)`
Updates a custom field value for a project item.

**Parameters:**
- `project_id` (str): Project ID
- `item_id` (str): Project item ID (PVTI_xxx format)
- `field_id` (str): Field ID (PVTF_xxx format)
- `value` (Any): Field value (format depends on field type)

**Returns:** Updated project item details

#### `sync_story_to_project(story_hierarchy, project_id, field_mappings=None)`
Synchronizes a complete story hierarchy with a project.

**Parameters:**
- `story_hierarchy` (StoryHierarchy): Complete story hierarchy
- `project_id` (str): Project ID
- `field_mappings` (Dict[str, str], optional): Map story fields to project fields

**Returns:** Synchronization results for epic, user stories, and sub-stories

#### `create_project_for_epic(epic, repository_name=None, organization_login=None)`
Creates a project specifically designed for an epic.

**Parameters:**
- `epic` (Epic): Epic object
- `repository_name` (str, optional): Repository for repo-level project
- `organization_login` (str, optional): Organization for org-level project

**Returns:** Created project details

## Data Models

### ProjectData
```python
@dataclass
class ProjectData:
    title: str
    description: str = ""
    repository_id: Optional[str] = None
    organization_login: Optional[str] = None
    visibility: str = "PRIVATE"  # PRIVATE, PUBLIC
    template: Optional[str] = None
```

### ProjectField
```python
@dataclass
class ProjectField:
    id: str
    name: str
    data_type: str  # TEXT, NUMBER, DATE, SINGLE_SELECT, ITERATION
    options: List[Dict[str, Any]] = field(default_factory=list)
```

### ProjectFieldValue
```python
@dataclass
class ProjectFieldValue:
    field_id: str
    value: Any
    field_type: str = "text"
```

## Error Handling

All GitHub Projects API methods include comprehensive error handling:

- **GraphQL errors**: Automatically detected and raised with detailed messages
- **HTTP errors**: Network and API errors are caught and re-raised with context
- **Rate limiting**: Built-in retry logic for rate-limited requests
- **Validation errors**: Input validation with meaningful error messages

Example error handling:

```python
try:
    project = await github_handler.create_project(project_data)
except Exception as e:
    if "rate limit" in str(e).lower():
        # Handle rate limiting
        await asyncio.sleep(60)
        project = await github_handler.create_project(project_data)
    else:
        logger.error(f"Failed to create project: {e}")
        raise
```

## Testing

Run the comprehensive test suite:

```bash
python test_github_projects.py
```

Run the demo to see usage examples:

```bash
python demo_github_projects.py
```

## Integration with Existing Workflow

The GitHub Projects integration seamlessly extends the existing Storyteller workflow:

1. **Epic Creation**: Use existing epic creation methods
2. **Project Generation**: Automatically create projects for epics
3. **Issue Creation**: Use existing issue creation from stories
4. **Project Sync**: Automatically sync issues to project boards
5. **Status Updates**: Project board status reflects story progress
6. **Cross-Repository**: Handle multi-repository epics automatically

This integration maintains backward compatibility while adding powerful project management capabilities.