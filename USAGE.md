# Usage Guide

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GitHub token
python main.py validate
```

## Commands

### Story Management
```bash
# Create story
python main.py story create "Your story description" --repository backend

# Analyze story
python main.py story analyze "Your story description" --roles ai-expert

# Multi-repository story
python main.py story create-multi "Story description" --repos backend,frontend

# List repositories and roles
python main.py story list-repositories
python main.py story list-roles
```

### MCP Server
```bash
# Start MCP server
python main.py mcp start

# Start with WebSocket
python main.py mcp start --transport websocket --port 8765

# Test MCP
python main.py mcp test "system/health"
```

## Components

- `config.py` - Configuration management
- `story_manager.py` - Story processing
- `llm_handler.py` - LLM integration
- `github_handler.py` - GitHub API
- `main.py` - CLI interface
- `mcp_server.py` - MCP server
