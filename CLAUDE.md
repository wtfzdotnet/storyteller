# Claude Code Instructions for Storyteller

## Quick Start Commands

### Development Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Code Quality Checks (Run Before Committing)
```bash
# Activate virtual environment first
source venv/bin/activate

# Check for critical syntax errors
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Check formatting
python -m black --check --diff .

# Check import sorting
python -m isort --check-only --diff .

# Fix formatting issues
python -m black .
python -m isort .
```

### Testing
```bash
# Run basic tests (as per CI pipeline)
python test_basic.py
python test_hierarchical_models.py
python test_integration.py

# Run all tests
python -m pytest tests/
```

## Project Structure Guidelines

### Directory Structure
```
storyteller/
├── src/storyteller/          # Main source code
│   ├── __init__.py
│   ├── api.py               # FastAPI application
│   ├── models.py            # Data models
│   ├── story_manager.py     # Core business logic
│   ├── automation/          # Workflow automation
│   └── .storyteller/        # Role definitions
├── docs/
│   ├── enduser/             # End-user documentation
│   │   └── README.md        # Setup and usage guide
│   └── ai/                  # AI-generated documentation
│       ├── SCHEMA.md        # Database schema docs
│       ├── USAGE.md         # Technical usage docs
│       └── *.md             # Other AI-generated docs
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── scripts/
│   ├── demos/               # Demo scripts
│   └── *.py                 # Simple test/utility scripts
├── main.py                  # Console application entry point
├── mcp_server.py           # MCP server entry point
└── test_*.py               # Core CI test files
```

### Test File Organization
- **NEW TESTS**: Always place in `tests/unit/` or `tests/integration/`
- **AI TESTING SCRIPTS**: Place simple scripts in `scripts/`
- **PATTERN**: `tests/unit/test_<component>.py` or `tests/integration/test_<feature>.py`
- **DEMOS**: Place in `scripts/demos/`

### Documentation Organization
- **END-USER DOCS**: Place in `docs/enduser/` (setup, usage, tutorials)
- **AI-GENERATED DOCS**: Place in `docs/ai/` (technical specs, schemas, implementation details)
- **PROJECT DOCS**: Keep CLAUDE.md, README.md in root

### Code Quality Standards
- Line length: 88 characters (Black default)
- Use type hints consistently
- Follow async/await patterns for I/O operations
- Mock external dependencies in tests

## Common Pipeline Failures & Fixes

### 1. Linting Failures
**Problem**: Flake8 errors in CI
**Fix**: Run `python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`

### 2. Formatting Issues
**Problem**: Black formatting check fails
**Fix**: Run `python -m black .`

### 3. Import Sorting
**Problem**: isort check fails
**Fix**: Run `python -m isort .`

### 4. Test Discovery Issues
**Problem**: Root-level test files confuse the pipeline
**Fix**: Move test files to `tests/unit/` or `tests/integration/`

## Repository References

### Correct Repository Names
- **Frontend**: `wtfzdotnet/recipeer-frontend` (NOT recipes-frontend)
- **Backend**: `wtfzdotnet/storyteller`

## Architecture Overview

### Core Components
- **Story Manager**: Core story processing with AI expert analysis
- **GitHub Handler**: GitHub API integration for issue/project management
- **LLM Handler**: AI/LLM provider abstraction (OpenAI, GitHub Models, Ollama)
- **MCP Server**: Model Context Protocol server for AI assistant integration
- **Assignment Engine**: Automated agent assignment and workflow management

### Key Features
- Hierarchical story management (Epic → User Story → Sub-story)
- Multi-repository context intelligence
- Role-based expert analysis system
- Automated GitHub integration
- Pipeline failure monitoring and recovery

## Environment Variables
```bash
GITHUB_TOKEN=ghp_xxx
DEFAULT_LLM_PROVIDER=github
OPENAI_API_KEY=sk-xxx  # If using OpenAI
LOG_LEVEL=INFO
AUTO_CONSENSUS_ENABLED=true
```

## Best Practices for Claude Code

### Before Making Changes
1. Always pull latest changes: `git pull origin main`
2. Activate virtual environment: `source venv/bin/activate`
3. Install/update dependencies: `pip install -r requirements.txt`

### After Making Changes
1. Run code quality checks (see commands above)
2. Run tests to ensure functionality
3. Move any root-level test files to proper directories
4. Update repository references from recipes-frontend to recipeer-frontend

### CI/CD Pipeline
The pipeline runs:
1. Flake8 linting (critical errors only)
2. Black formatting check
3. isort import sorting check
4. Basic test suite (test_basic.py, test_hierarchical_models.py, test_integration.py)
5. Docker build and push (on main branch)

### Role Management
- **Location**: `src/storyteller/.storyteller/roles/`
- **Essential roles**: system-architect, lead-developer, qa-engineer, security-expert, product-owner
- **Domain-specific**: registered-dietitian, professional-chef, domain-expert-food-nutrition
- **Cleaned up**: Removed 15+ bloated AI-generated roles, keeping only 8 essential ones

### Documentation Maintenance
- **End-user docs**: Maintain `docs/enduser/README.md` for setup, usage, and workflows
- **AI-generated docs**: Keep technical implementation details in `docs/ai/`
- **Keep docs current**: Update documentation when adding features or changing architecture
- **Console vs API vs MCP**: Document all three usage modes clearly