# GitHub Copilot Instructions for Storyteller

## Project Overview
Storyteller is an AI-powered story management system that creates and manages user stories with expert analysis and GitHub integration. The system implements hierarchical story management (Epic � User Story � Sub-story) with multi-repository support and intelligent automation.

## Core Architecture

### System Components
- **Story Manager**: Core story processing with AI expert analysis
- **GitHub Handler**: GitHub API integration for issue/project management  
- **LLM Handler**: AI/LLM provider abstraction (OpenAI, GitHub Models, Ollama)
- **MCP Server**: Model Context Protocol server for AI assistant integration
- **Workflow Processor**: CLI and automation workflow orchestration
- **Role Analyzer**: Expert role-based story analysis system

### Key Data Models
- **ProcessedStory**: Complete story with expert analyses and metadata
- **StoryAnalysis**: Expert role analysis with recommendations and concerns
- **IssueData**: GitHub issue creation structure
- **RepositoryConfig**: Multi-repository configuration

## Development Guidelines

### Code Style & Patterns
- Use Python 3.11+ with type hints and dataclasses
- Follow async/await patterns for I/O operations
- Implement proper error handling with specific exception types
- Use structured logging with context
- Follow the existing pattern: `story_manager.py`, `github_handler.py`, etc.

### Story Management Patterns
```python
# Epic/User Story/Sub-story hierarchy
@dataclass
class Epic:
    id: str
    title: str
    description: str
    user_stories: List[UserStory]
    status: EpicStatus

@dataclass  
class UserStory:
    id: str
    epic_id: str
    title: str
    acceptance_criteria: List[str]
    sub_stories: List[SubStory]
    target_repositories: List[str]
```

### Multi-Repository Context
- Always consider cross-repository dependencies
- Use repository-specific configurations from `.storyteller/config.json`
- Implement intelligent context gathering from multiple repos
- Follow dependency ordering when creating issues

### GitHub Integration Patterns
- Use GitHub Projects API for advanced project management
- Implement automatic status transitions based on GitHub events
- Support `@copilot` mentions for agent triggering
- Create proper issue relationships and cross-references

## Implementation Priorities

### Current Epic Implementation Order
1. **Epic #28**: Hierarchical story management (Epic � User Story � Sub-story)
2. **Epic #29**: Multi-repository context intelligence with MCP
3. **Epic #30**: Advanced GitHub Projects integration
4. **Epic #31**: Automated agent workflow with pipeline monitoring
5. **Epic #32**: Role-based consensus and discussion system
6. **Epic #33**: Roadmap import and automated planning

### Key Features to Implement

#### 1. Hierarchical Story Management
- Database schema for Epic/UserStory/SubStory relationships
- Parent-child relationship tracking
- Status propagation (child completion � parent progress)
- Department-specific sub-story generation (Frontend, Backend, Testing, DevOps, etc.)

#### 2. Enhanced MCP Server
- Multi-repository code context reading
- Intelligent role assignment based on repository type
- Context-aware story generation
- Cross-repository conversation capabilities

#### 3. GitHub Projects Integration
- Automatic project board management
- Story status transitions via GitHub webhooks
- Dependency-based issue ordering
- Cross-repository progress tracking

#### 4. Agent Workflow System
- Pipeline failure monitoring and notification
- Retry logic with failure limits (max 3 attempts)
- Logical resumption patterns after failures
- Agent workload and assignment management

#### 5. Consensus Engine
- Multi-role discussion simulation
- Consensus reaching algorithms
- Manual intervention triggers
- Role-based requirement gathering (acceptance criteria, testing, effort estimation)

## Configuration Management

### Repository Configuration (.storyteller/config.json)
```json
{
  "repositories": {
    "backend": {
      "name": "wtfzdotnet/backend-repo",
      "type": "backend",
      "description": "API services and business logic",
      "dependencies": [],
      "story_labels": ["backend", "api"],
      "auto_assign": {
        "assignee": ["copilot-sve-agent"]
      }
    },
    "frontend": {
      "name": "wtfzdotnet/frontend-repo", 
      "type": "frontend",
      "description": "User interface and client applications",
      "dependencies": ["backend"],
      "story_labels": ["frontend", "ui"],
      "auto_assign": {
        "assignee": ["copilot-sve-agent"]
      }
    }
  },
  "default_repository": "backend",
  "story_workflow": {
    "create_subtickets": true,
    "respect_dependencies": true
  }
}
```

### Expert Roles (.storyteller/roles/*.md)
- Create role-specific analysis templates
- Include domain expertise (food/nutrition for Recipe Authority)
- Support technical roles (system-architect, lead-developer, security-expert)
- Include specialized roles (qa-engineer, devops-engineer, ux-ui-designer)

## API Integration Patterns

### GitHub API Usage
```python
# Create hierarchical issues with relationships
async def create_epic_with_stories(epic_data: EpicData) -> List[Issue]:
    epic_issue = await github_handler.create_issue(epic_data.to_issue_data())
    
    user_stories = []
    for story in epic_data.user_stories:
        story.parent_epic = epic_issue.number
        story_issue = await github_handler.create_issue(story.to_issue_data())
        user_stories.append(story_issue)
    
    return [epic_issue] + user_stories
```

### LLM Integration
```python
# Multi-role consensus analysis
async def reach_consensus(story_content: str, required_roles: List[str]) -> ConsensusResult:
    analyses = await asyncio.gather(*[
        llm_handler.analyze_with_role(story_content, role)
        for role in required_roles
    ])
    
    consensus = await llm_handler.synthesize_consensus(analyses)
    return consensus
```

## Error Handling & Resilience

### Pipeline Failure Handling
- Monitor CI/CD pipeline status via GitHub webhooks
- Implement retry logic with exponential backoff
- Maximum 3 retry attempts before pausing
- Create agent notifications with failure context
- Support manual resumption after investigation

### Consensus Failure Recovery
- Detect when roles cannot reach consensus
- Mark issues for manual intervention
- Preserve conversation state and stuck points
- Notify human stakeholders for resolution

## Testing Patterns

### Unit Testing
- Test each component in isolation
- Mock external dependencies (GitHub API, LLM providers)
- Use pytest with async support
- Test error conditions and edge cases

### Integration Testing
- Test complete workflows end-to-end
- Validate multi-repository operations
- Test GitHub integration with test repositories
- Verify MCP server functionality

### Test Organization
- **IMPORTANT**: All new test files MUST be placed in the `tests/` directory structure
- Use `tests/unit/` for unit tests and `tests/integration/` for integration tests
- Root-level test files (test_*.py) are legacy and should be moved to appropriate directories
- Follow the pattern: `tests/unit/test_<component>.py` or `tests/integration/test_<feature>.py`

## CLI Command Patterns

### Story Creation
```bash
# Create epic with automatic user story breakdown
python main.py story create-epic "Epic: User Authentication System"

# Create cross-repository story
python main.py story create-multi "User can log in with OAuth" --repos backend,frontend

# Import roadmap and generate stories
python main.py roadmap import roadmap.json --create-sprints 3
```

### Workflow Management
```bash
# Process story queue
python main.py workflow process-queue --max-concurrent 5

# Check consensus status
python main.py consensus status --story-id story_abc123

# Resume failed workflows
python main.py workflow resume --story-id story_abc123
```

## MCP Server Commands

### Available Tools
- `create_story`: Create new story with expert analysis
- `analyze_story`: Analyze existing story content
- `get_repository_context`: Get context from multiple repositories
- `create_epic`: Create epic with user story breakdown
- `check_consensus`: Check role-based consensus status
- `import_roadmap`: Import and process roadmap data

## Best Practices

### When Working on Issues
1. **Always read the parent epic** to understand the broader context
2. **Check repository dependencies** before making changes
3. **Follow the established data models** and patterns
4. **Implement proper error handling** with specific exception types
5. **Add comprehensive logging** for debugging and monitoring
6. **Write tests** for new functionality
7. **Update configuration** when adding new repository types or roles
8. **Consider multi-repository impact** for cross-cutting features

### Code Quality Standards
- Maintain high test coverage (>80%)
- Use type hints consistently
- Follow Python PEP 8 style guidelines with 88-character line limit (Black formatting)
- Document complex algorithms and business logic
- Use meaningful variable and function names
- Implement proper async/await patterns for I/O

### Pipeline Quality Gates
- **CRITICAL**: Always run linting and formatting before committing:
  - `python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
  - `python -m black --check --diff .`
  - `python -m isort --check-only --diff .`
- Fix all formatting issues with: `python -m black .` and `python -m isort .`
- Test files in root directory cause pipeline confusion - move to `tests/`
- Use virtual environments for dependency isolation: `python -m venv venv && source venv/bin/activate`

### GitHub Integration
- Always create issues with proper labels and assignments
- Use milestone tracking for epic progress
- Implement proper cross-references between related issues
- Support automated status transitions
- Tag `@copilot` in comments when agent action is needed

## Environment Variables

Required environment variables:
```bash
GITHUB_TOKEN=ghp_xxx  # GitHub API token
DEFAULT_LLM_PROVIDER=github  # github|openai|ollama
OPENAI_API_KEY=sk-xxx  # If using OpenAI
OLLAMA_API_HOST=http://localhost:11434  # If using Ollama
LOG_LEVEL=INFO
DEBUG_MODE=false
AUTO_CONSENSUS_ENABLED=true
AUTO_CONSENSUS_THRESHOLD=70
```

## Remember
This is a sophisticated AI-powered system that automates the entire software development lifecycle from roadmap to deployment. Focus on building robust, scalable components that can handle the complexity of multi-repository, multi-role, and multi-agent workflows.