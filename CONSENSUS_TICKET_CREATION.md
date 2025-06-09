# Consensus-Based Repository Ticket Creation

## Overview

When consensus is reached on a story (transition to `story/consensus` state), the system now automatically creates tickets in designated repositories with repository-specific customization.

## How It Works

### 1. Consensus Detection
- When a story reaches the `story/consensus` state (consensus score ≥ 80%)
- The `create_repository_tickets` auto action is triggered

### 2. Multi-Repository Mode Check
- Only activates if multi-repository mode is enabled via `.storyteller/config.json`
- Gracefully skips if in single repository mode

### 3. Repository Ticket Creation
- Uses the existing `create_multi_repository_stories` infrastructure
- Creates tickets in dependency order (backend → frontend)
- Each ticket is customized for its repository type:
  - **Backend tickets**: Focus on API design, data models, business logic
  - **Frontend tickets**: Focus on UI/UX, user interactions, API consumption

### 4. Cross-Repository Linking
- Original consensus issue gets a comment with links to all created tickets
- Each created ticket includes references to its dependencies
- Clear indication of repository-specific focus areas

## Example Workflow

```
1. Story created: "User authentication system"
2. Multiple iterations and feedback rounds
3. Consensus reached (score ≥ 80%)
4. Automatic transition to story/consensus state
5. Auto action triggered: create_repository_tickets
6. Tickets created:
   - Backend ticket: "User authentication API endpoints" (#124)
   - Frontend ticket: "User authentication interface" (#125) 
7. Original issue updated with links and completion message
```

## Configuration

Requires `.storyteller/config.json` with repository definitions:

```json
{
  "repositories": {
    "backend": {
      "name": "myorg/backend-api",
      "type": "backend",
      "description": "Backend API and services",
      "dependencies": [],
      "story_labels": ["backend", "api"]
    },
    "frontend": {
      "name": "myorg/frontend-app", 
      "type": "frontend",
      "description": "User interface",
      "dependencies": ["backend"],
      "story_labels": ["frontend", "ui"]
    }
  },
  "default_repository": "backend"
}
```

## Content Customization

### Backend Tickets
- API endpoint design and implementation
- Data models and database schema
- Business logic and validation rules
- Authentication and authorization
- Performance and scalability considerations

### Frontend Tickets  
- User interface design and components
- User experience and interaction flows
- API integration and data handling
- State management and routing
- Responsive design and accessibility

## Error Handling

- Graceful fallback if ticket creation fails
- User-friendly error messages in the original issue
- Detailed logging for troubleshooting
- No impact on existing story workflow if errors occur

## Benefits

1. **Automatic Workload Distribution**: Consensus immediately creates actionable tickets
2. **Repository-Specific Focus**: Removes confusing cross-repository details
3. **Dependency Awareness**: Tickets created in correct order with proper references  
4. **Zero Manual Effort**: Fully automated based on consensus reaching
5. **CoPilot Assignment**: Leverages existing assignment mechanisms
6. **Clear Traceability**: Original story links to all derived tickets

## Implementation Details

- **File**: `automation/workflow_processor.py`
- **State**: `story/consensus` with `create_repository_tickets` auto action
- **Function**: `_create_repository_tickets_for_consensus`
- **Dependencies**: Existing multi-repository infrastructure
- **Error Recovery**: Graceful degradation with user feedback