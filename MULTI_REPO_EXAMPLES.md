# Multi-Repository Storyteller Usage Examples

This document demonstrates the new multi-repository functionality of the Storyteller system.

## Configuration Example

The system uses `.storyteller/config.json` for multi-repository configuration:

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
      "description": "User interface and client applications",
      "dependencies": ["backend"],
      "story_labels": ["frontend", "ui"]
    },
    "mobile": {
      "name": "myorg/mobile-app",
      "type": "mobile",
      "description": "Mobile application",
      "dependencies": ["backend"],
      "story_labels": ["mobile", "ios", "android"]
    }
  },
  "default_repository": "backend",
  "story_workflow": {
    "create_subtickets": true,
    "respect_dependencies": true
  }
}
```

## Command Examples

### 1. Check Current Configuration
```bash
python main.py story config
```
Output:
```
📋 Current Configuration:

🔧 GitHub Token: ✅ Set
🤖 Default LLM Provider: github
📊 Log Level: INFO

🏢 Multi-Repository Mode: ✅ Enabled
📂 Configuration Source: /path/to/.storyteller/config.json
📁 Available Repositories: 3
   ⭐ backend: myorg/backend-api (backend)
      frontend: myorg/frontend-app (frontend)
      mobile: myorg/mobile-app (mobile)
🎯 Default Repository: backend
```

### 2. List Available Repositories
```bash
python main.py story list-repositories
```
Output:
```
📁 Available Repositories:

⭐ backend
   Repository: myorg/backend-api
   Type: backend
   Description: Backend API and services
   Dependencies: None
   Default Labels: backend, api

   frontend
   Repository: myorg/frontend-app
   Type: frontend
   Description: User interface and client applications
   Dependencies: backend
   Default Labels: frontend, ui

   mobile
   Repository: myorg/mobile-app
   Type: mobile
   Description: Mobile application
   Dependencies: backend
   Default Labels: mobile, ios, android

⭐ Default repository: backend
```

### 3. Create Story in Specific Repository
```bash
python main.py story create "User authentication system" --repository backend
```
Creates a story focused on backend authentication implementation.

### 4. Create Stories Across Multiple Repositories
```bash
python main.py story create-multi "User profile management with dashboard"
```
This creates stories in dependency order:
1. Backend: "User profile management API endpoints"
2. Frontend: "User profile dashboard interface" (with reference to backend story)
3. Mobile: "User profile mobile screens" (with reference to backend story)

### 5. Create Stories in Specific Repositories Only
```bash
python main.py story create-multi "Shopping cart feature" --repos backend,frontend
```
Creates stories only in backend and frontend repositories, respecting their dependency order.

## Story Creation Flow

When creating multi-repository stories, the system:

1. **Sorts repositories by dependencies**: Backend → Frontend → Mobile
2. **Customizes prompts per repository type**:
   - Backend: Focuses on API design, data models, business logic
   - Frontend: Focuses on UI/UX, user interactions, state management
   - Mobile: Focuses on mobile-specific features, platform considerations
3. **Adds cross-repository references**: Each story links to its dependencies
4. **Applies repository-specific labels**: Automatic labeling based on configuration

## Backward Compatibility

The system maintains full backward compatibility:

```bash
# Still works with environment variables
export GITHUB_REPOSITORY=myorg/single-repo
export GITHUB_TOKEN=your_token

python main.py story create "Feature request"
# Creates story in the single repository specified by environment variable
```

## Migration Path

To migrate from single to multi-repository mode:

1. Create `.storyteller/config.json` with repository definitions
2. Existing ENV variables are still respected for backward compatibility
3. New commands become available automatically
4. Existing workflows continue to work unchanged

## Best Practices

1. **Repository Types**: Use meaningful types (backend, frontend, mobile, docs, etc.)
2. **Dependencies**: Define clear dependency chains to ensure proper story ordering
3. **Labels**: Use consistent labeling conventions across repositories
4. **Descriptions**: Provide clear descriptions to help AI generate appropriate stories
5. **Default Repository**: Set the most common target as default to reduce typing

This multi-repository approach enables teams to manage complex projects with multiple codebases while maintaining story consistency and proper dependency relationships.