# Storyteller - AI-Powered Story Management System

Storyteller is an intelligent story management system that helps you break down complex projects into manageable stories, integrate with GitHub Projects, and automate workflows using AI-powered analysis.

## Quick Setup

### Prerequisites
- Python 3.8 or higher
- GitHub account with Personal Access Token
- Access to AI providers (OpenAI, GitHub Models, or Ollama)

### Installation

1. **Clone and setup environment:**
```bash
git clone <repository-url>
cd storyteller
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment variables:**
Create a `.env` file or set these environment variables:
```bash
export GITHUB_TOKEN=ghp_your_token_here
export DEFAULT_LLM_PROVIDER=github  # or openai, ollama
export OPENAI_API_KEY=sk_your_key_here  # if using OpenAI
export LOG_LEVEL=INFO
```

3. **Initialize database:**
```bash
python migrate.py
```

## How to Use Storyteller

### 1. Console Interface

**Start the main application:**
```bash
python main.py
```

This launches the interactive console where you can:
- Create and manage epics
- Break down epics into user stories
- Assign stories to team members
- Track progress and dependencies

### 2. API Server

**Start the REST API server:**
```bash
python -m uvicorn src.storyteller.api:app --reload
```

Access the API at `http://localhost:8000` with automatic documentation at `/docs`.

**Key endpoints:**
- `POST /epics` - Create new epics
- `GET /epics/{id}` - Get epic details
- `POST /epics/{id}/breakdown` - Generate user stories
- `PUT /stories/{id}/status` - Update story status

### 3. MCP Server (Model Context Protocol)

**For Claude Desktop integration:**
```bash
python mcp_server.py
```

Add to your Claude Desktop config:
```json
{
  "mcpServers": {
    "storyteller": {
      "command": "python",
      "args": ["/path/to/storyteller/mcp_server.py"],
      "env": {
        "GITHUB_TOKEN": "your_token"
      }
    }
  }
}
```

### 4. GitHub Copilot Integration

Storyteller includes Copilot instructions in `.github/copilot-instructions.md` for:
- Automated story creation from issues
- Intelligent role assignment
- Context-aware suggestions
- Repository-specific recommendations

## Core Workflows

### Creating and Managing Stories

1. **Create an Epic:**
```python
epic = Epic(
    title="User Authentication System",
    description="Implement secure user login and registration",
    business_value="Enable user accounts and security",
    target_repositories=["backend", "frontend"]
)
```

2. **Break down Epic to User Stories:**
The AI automatically analyzes your epic and creates relevant user stories based on:
- Repository context (frontend/backend/database)
- Existing codebase patterns
- Role-based expertise requirements

3. **Assign Stories:**
Stories are automatically assigned to appropriate team members based on:
- Technical expertise (roles in `.storyteller/roles/`)
- Repository knowledge
- Current workload

### GitHub Integration

**Sync with GitHub Projects:**
- Automatically creates GitHub issues for stories
- Updates GitHub Project boards
- Syncs status changes bi-directionally
- Manages labels and assignments

**Webhook Integration:**
```bash
# Set up webhook endpoint
POST /webhook/github
```

### Multi-Repository Context

Storyteller understands your codebase across multiple repositories:
- Analyzes file structure and dependencies
- Suggests appropriate technologies and patterns
- Creates context-aware stories
- Maintains consistency across repositories

## AI Providers

### GitHub Models (Recommended)
```bash
export DEFAULT_LLM_PROVIDER=github
export GITHUB_TOKEN=your_github_token
```

### OpenAI
```bash
export DEFAULT_LLM_PROVIDER=openai
export OPENAI_API_KEY=your_openai_key
```

### Ollama (Local)
```bash
export DEFAULT_LLM_PROVIDER=ollama
# Ensure Ollama is running locally
```

## Configuration

### Repository Configuration
Edit `src/storyteller/config.py` to define your repositories:
```python
repositories = {
    "backend": {
        "type": "backend",
        "description": "API and business logic",
        "technologies": ["python", "fastapi", "postgresql"]
    },
    "frontend": {
        "type": "frontend", 
        "description": "User interface",
        "technologies": ["react", "typescript", "tailwind"]
    }
}
```

### Role Customization
Customize expert roles in `src/storyteller/.storyteller/roles/`:
- `system-architect.md` - Technical architecture decisions
- `lead-developer.md` - Code quality and implementation
- `qa-engineer.md` - Testing and quality assurance
- `security-expert.md` - Security considerations
- `product-owner.md` - Business requirements

## Troubleshooting

### Common Issues

**Database connection errors:**
```bash
# Recreate database
rm storyteller.db
python migrate.py
```

**GitHub API rate limits:**
- Use GitHub token with appropriate permissions
- Enable GitHub Apps for higher limits

**AI provider issues:**
- Verify API keys are set correctly
- Check provider-specific documentation
- Try switching providers for testing

### Logs and Debugging
```bash
export LOG_LEVEL=DEBUG
python main.py
```

### Getting Help

1. Check the logs for detailed error messages
2. Verify environment variables are set correctly
3. Ensure all dependencies are installed
4. Review the AI-generated documentation in `docs/ai/`

## Advanced Features

- **Dependency Management:** Automatic story ordering based on dependencies
- **Status Propagation:** Child story completion updates parent epic status
- **Context Intelligence:** Multi-repository awareness for better story generation
- **Role-based Assignment:** Expert system for optimal task distribution
- **Pipeline Integration:** CI/CD workflow integration and monitoring

For technical implementation details, see the AI-generated documentation in `docs/ai/`.