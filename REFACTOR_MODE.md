# Refactor Mode

The Storyteller refactor mode enables immediate creation of refactor tickets across repositories with relevant file context, bypassing the normal consensus workflow.

## Overview

Unlike regular user stories that go through a consensus-building process, refactor tickets are created immediately and marked as ready for development. The system automatically:

1. **Analyzes the refactor request** to understand what type of changes are needed
2. **Discovers relevant files** based on the refactor type and AI analysis
3. **Creates repository-specific tickets** with tailored context for each repository type
4. **Assigns appropriate roles** based on the refactor complexity and type
5. **Adds file context** to help developers understand the scope of changes

## Usage

### Basic Refactor Command

```bash
python main.py story refactor "Extract authentication logic into a service"
```

### Specify Refactor Type

```bash
python main.py story refactor "Optimize database queries" --type optimize
```

### Target Specific Repositories

```bash
python main.py story refactor "Update React components to TypeScript" --repos frontend
```

### Include Specific Files

```bash
python main.py story refactor "Refactor user model" --files "models/user.py,tests/test_user.py"
```

### With Repository Prompts (GitHub Models)

```bash
python main.py story refactor "Modernize authentication system" --use-repository-prompts
```

## Refactor Types

The system supports different refactor types, each with specific roles and file patterns:

### `extract`
- **Purpose**: Extract functionality into separate modules, services, or components
- **Roles**: Senior Developer, Software Architect, Code Reviewer
- **Example**: "Extract authentication logic into a service"

### `move`
- **Purpose**: Move files, modules, or functionality to different locations
- **Roles**: Senior Developer, DevOps Engineer, Tech Lead
- **Example**: "Move utility functions to shared library"

### `rename`
- **Purpose**: Rename files, variables, classes, or methods consistently
- **Roles**: Senior Developer, Documentation Specialist, QA Engineer
- **Example**: "Rename UserAccount to Customer throughout codebase"

### `optimize`
- **Purpose**: Improve performance, reduce complexity, or optimize resource usage
- **Roles**: Performance Engineer, Senior Developer, DevOps Engineer
- **Example**: "Optimize database queries for user search"

### `modernize`
- **Purpose**: Update code to modern standards, frameworks, or patterns
- **Roles**: Tech Lead, Senior Developer, Security Engineer
- **Example**: "Migrate from class components to React hooks"

### `general`
- **Purpose**: General refactoring that doesn't fit other categories
- **Roles**: Senior Developer, Tech Lead, Code Reviewer
- **Example**: "Improve code organization in payment module"

## File Discovery

The system uses multiple strategies to identify relevant files:

### 1. Explicit File Specification
Use the `--files` option to specify exact files:
```bash
--files "auth/models.py,auth/views.py,tests/test_auth.py"
```

### 2. AI-Powered Discovery
The system prompts AI to analyze the refactor request and suggest relevant files based on:
- Refactor type and description
- Repository type (backend, frontend, mobile)
- Common patterns for the requested changes

### 3. Fallback Patterns
If AI discovery fails, the system uses default file patterns based on:
- **Backend**: `**/*.py`, `**/*.sql`, `**/*.yml`, `**/*.json`
- **Frontend**: `**/*.js`, `**/*.ts`, `**/*.jsx`, `**/*.tsx`, `**/*.css`
- **Mobile**: `**/*.swift`, `**/*.kt`, `**/*.dart`

## Generated Ticket Structure

Each refactor ticket includes:

### Title
- Starts with "Refactor:" for easy identification
- Descriptive and under 80 characters
- Example: "Refactor: Extract Authentication Service"

### Body
- **Task Description**: Clear explanation of what needs to be refactored
- **Refactor Type**: Categorization (extract, optimize, etc.)
- **Repository Context**: Specific repository information in multi-repo mode
- **Relevant Files**: List of files/patterns that need attention
- **Deliverables**: What should be produced (analysis, implementation, tests, docs)
- **Acceptance Criteria**: Checklist of requirements for completion

### Labels
- `refactor`: Marks as a refactor task
- `refactor/{type}`: Specific refactor type (e.g., `refactor/extract`)
- `ready-for-development`: Immediate ready status
- `needs/{role}`: Required roles (e.g., `needs/senior-developer`)
- Repository-specific labels in multi-repo mode

### Context Comment
Automatically added comment with:
- Refactor type and scope
- Relevant file patterns
- Assigned roles
- Development readiness status

## Multi-Repository Support

In multi-repository mode, refactor tickets are created across all specified repositories with:

### Repository-Specific Customization
- **Backend**: Focus on API, services, data models, business logic
- **Frontend**: Focus on UI components, state management, user interactions
- **Mobile**: Focus on platform-specific features and mobile patterns

### Independent Tickets
Unlike regular stories with dependencies, refactor tickets are independent and can be worked on simultaneously across repositories.

### Cross-Repository Coordination
While tickets are independent, they can reference related refactors in other repositories when needed.

## Integration with Existing Workflow

### Bypasses Consensus
Refactor tickets skip the normal story consensus workflow and are immediately ready for development.

### Uses Existing Infrastructure
- Leverages multi-repository configuration
- Integrates with role-based assignments
- Uses repository-specific prompts when available
- Compatible with existing labeling and automation

### Maintains Traceability
- Clear labeling for tracking refactor work
- Detailed context for understanding scope
- Links to relevant files and patterns

## Best Practices

### Clear Descriptions
Provide specific, actionable descriptions:
- ✅ "Extract user authentication logic into a reusable service"
- ❌ "Clean up auth stuff"

### Appropriate Scope
Keep refactors focused and manageable:
- ✅ "Optimize user search query performance"
- ❌ "Refactor the entire application"

### File Specification
When possible, specify key files to provide better context:
```bash
--files "auth/models.py,auth/services.py,auth/tests.py"
```

### Repository Targeting
Target appropriate repositories for the refactor:
```bash
--repos backend,frontend  # For changes affecting both
--repos frontend          # For UI-specific refactors
```

## Example Workflows

### Extract Service Pattern
```bash
python main.py story refactor "Extract payment processing into PaymentService" \
  --type extract \
  --repos backend \
  --files "payments/views.py,payments/models.py"
```

### Performance Optimization
```bash
python main.py story refactor "Optimize user dashboard loading performance" \
  --type optimize \
  --repos frontend \
  --use-repository-prompts
```

### Code Modernization
```bash
python main.py story refactor "Migrate to Python 3.12 and update deprecated syntax" \
  --type modernize \
  --repos backend
```

### Cross-Repository Refactor
```bash
python main.py story refactor "Standardize error handling across applications" \
  --type general \
  --repos backend,frontend
```

## Configuration

Refactor mode uses the same configuration as regular stories:

### Multi-Repository Mode
Defined in `.storyteller/config.json`:
```json
{
  "repositories": {
    "backend": {
      "name": "myorg/backend-api",
      "type": "backend",
      "story_labels": ["backend", "api"]
    },
    "frontend": {
      "name": "myorg/frontend-app", 
      "type": "frontend",
      "story_labels": ["frontend", "ui"]
    }
  }
}
```

### Environment Variables
Standard storyteller environment variables apply:
- `GITHUB_TOKEN`: Required for creating tickets
- `OPENAI_API_KEY`: For AI-powered file discovery
- `DEFAULT_LLM_PROVIDER`: AI provider configuration

## Error Handling

The system gracefully handles common issues:

### AI Service Unavailable
Falls back to default file patterns based on repository type and refactor type.

### Invalid Repository
Validates repository keys and provides helpful error messages with available options.

### Network Issues
Provides clear error messages and guidance for troubleshooting connectivity problems.

### Missing Configuration
Warns about missing multi-repository configuration and falls back to single-repository mode.