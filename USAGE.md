# AI Story Management System - Quick Start Guide

## Overview

The AI Story Management System is now fully implemented with comprehensive features for creating, analyzing, and managing user stories through expert AI collaboration.

## Prerequisites

- Python 3.11+
- GitHub account with API access
- Environment configuration

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your GitHub token
   ```

3. **Validate setup:**
   ```bash
   python main.py validate
   ```

## Core Features

### Story Creation

Create a story with expert analysis and GitHub issue creation:

```bash
# Create story for specific repository
python main.py story create "Implement user authentication system" --repository backend

# Create story with specific expert roles
python main.py story create "Recipe recommendation engine" --roles ai-expert,domain-expert-food-nutrition

# Create story across multiple repositories
python main.py story create-multi "User dashboard with API" --repos backend,frontend
```

### Story Analysis

Analyze a story without creating GitHub issues:

```bash
# Analyze with default expert roles
python main.py story analyze "Shopping cart integration"

# Analyze with specific roles and full output
python main.py story analyze "Cultural recipe validation" --roles food-historian-anthropologist,professional-chef --full
```

### Repository and Role Management

```bash
# List available repositories
python main.py story list-repositories

# List available expert roles
python main.py story list-roles

# Get story status
python main.py story status <story-id>
```

### MCP Server Integration

Start MCP server for AI assistant integration:

```bash
# Start with stdio transport (default)
python main.py mcp start

# Start with WebSocket transport
python main.py mcp start --transport websocket --port 8765

# Test MCP functionality
python main.py mcp test "system/health"
python main.py mcp test "role/list"
```

## Architecture

### Core Components

- **`config.py`** - Configuration management with multi-repository support
- **`story_manager.py`** - Core story processing and expert analysis orchestration
- **`llm_handler.py`** - LLM provider abstraction (GitHub Models, OpenAI, Ollama)
- **`github_handler.py`** - GitHub API integration for issue creation and management
- **`main.py`** - CLI interface with rich output and comprehensive commands
- **`mcp_server.py`** - Model Context Protocol server for AI assistant integration

### Automation

- **`automation/workflow_processor.py`** - Workflow orchestration and processing
- **`automation/label_manager.py`** - Automated label assignment and management

### Expert Roles

The system loads 23+ expert roles from `.storyteller/roles/*.md`:

- **Technical Leadership**: system-architect, lead-developer, security-expert, devops-engineer
- **Domain Expertise**: professional-chef, domain-expert-food-nutrition, food-historian-anthropologist
- **Specialized Nutrition**: registered-dietitian, sports-nutritionist, pediatric-nutritionist
- **Product & Strategy**: product-owner, ux-ui-designer
- **Technical Specialists**: ai-expert, qa-engineer

## Configuration

### Multi-Repository Setup

Edit `.storyteller/config.json`:

```json
{
  "repositories": {
    "backend": {
      "name": "owner/backend-repo",
      "type": "backend",
      "description": "Backend API services",
      "dependencies": [],
      "story_labels": ["backend", "api"],
      "auto_assign": {
        "assignee": ["developer-username"]
      }
    },
    "frontend": {
      "name": "owner/frontend-repo",
      "type": "frontend",
      "description": "User interface",
      "dependencies": ["backend"],
      "story_labels": ["frontend", "ui"]
    }
  },
  "default_repository": "backend",
  "story_workflow": {
    "create_subtickets": true,
    "respect_dependencies": true
  }
}
```

### Environment Variables

Key environment variables in `.env`:

```bash
# Required
GITHUB_TOKEN=your_github_token

# LLM Configuration
DEFAULT_LLM_PROVIDER=github  # or openai, ollama
OPENAI_API_KEY=your_openai_key  # if using OpenAI
OLLAMA_API_HOST=http://localhost:11434  # if using Ollama

# Optional
LOG_LEVEL=INFO
AUTO_CONSENSUS_ENABLED=false
DEBUG_MODE=false
```

## Story Processing Workflow

1. **Content Analysis** - Analyze story content to determine relevant expert roles and target repositories
2. **Expert Analysis** - Multiple expert roles analyze the story in parallel
3. **Synthesis** - Combine expert analyses into comprehensive recommendations
4. **Repository Distribution** - Route story to appropriate repositories based on content and dependencies
5. **GitHub Issue Creation** - Create properly labeled and assigned GitHub issues
6. **Cross-Repository Linking** - Add cross-references for multi-repository stories

## MCP Integration

The MCP server provides the following methods for AI assistant integration:

### Story Methods
- `story/create` - Create story with expert analysis
- `story/analyze` - Analyze story without GitHub issues
- `story/status` - Get story processing status

### Role Methods
- `role/query` - Query specific expert role with a question
- `role/list` - List available expert roles
- `role/analyze_story` - Get role-specific story analysis

### Repository Methods
- `repository/list` - List configured repositories
- `repository/get_config` - Get repository configuration

### System Methods
- `system/health` - Health check
- `system/capabilities` - Get available methods and features
- `system/validate` - Validate configuration

## Testing

Run the test suite:

```bash
# Basic functionality tests
python test_basic.py

# Integration tests
python test_integration.py
```

## Code Quality

The system enforces strict code quality standards:

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=venv
```

## Example Usage

```bash
# Complete workflow example
python main.py story create "
As a user, I want to save my favorite recipes so I can easily find them later.

Acceptance Criteria:
- Users can mark recipes as favorites
- Favorites are saved to user profile
- Users can view list of favorite recipes
- Users can remove recipes from favorites
" --repository backend --roles product-owner,ux-ui-designer,lead-developer

# Result: Creates GitHub issue with expert analysis, proper labels, and assignments
```

This creates a comprehensive user story with analysis from product, UX, and technical perspectives, automatically routed to the backend repository with appropriate labels and assignments.

## Troubleshooting

1. **Configuration Issues**: Run `python main.py validate` to check setup
2. **GitHub API Errors**: Verify token permissions and repository access
3. **LLM Provider Issues**: Check API keys and network connectivity
4. **Role Loading**: Ensure `.storyteller/roles/*.md` files exist

For more details, see the comprehensive documentation in `.storyteller/README.md`.