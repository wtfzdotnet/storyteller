# Simplified Story Management System - User Guide

This guide explains how to create user stories using the simplified AI-powered story management system.

## Overview

The simplified story management system provides intelligent assistance for creating complete, actionable user stories. It leverages AI to gather perspectives from multiple roles locally before creating ready-to-implement stories on GitHub.

## Key Features

- **Local AI Processing**: Stories are refined locally by considering multiple role perspectives before creating GitHub issues
- **No Iteration Overhead**: Complete stories are created immediately without GitHub-based iteration cycles
- **Multi-Repository Support**: Stories can be created across multiple repositories with repository-specific context
- **Ready for Development**: All created stories are immediately actionable

## Quick Start

### Command Line Interface

#### Create a Single Story
```bash
python main.py story create "As a user, I want to track my recipes so I can organize my cooking"
```

#### Create Stories Across Multiple Repositories
```bash
python main.py story create-multi "User authentication system" --repos backend,frontend
```

#### Create Refactor Tickets
```bash
python main.py story refactor "Extract authentication logic into a service" --type extract
```

### Story Labels

The simplified system uses essential labels for organization:

- **`story`**: Basic story marker
- **`ready-for-development`**: Ready for implementation
- **`in-development`**: Currently being worked on
- **`completed`**: Finished
- **`blocked`**: Blocked and needs attention

Repository-specific labels (for multi-repo mode):
- **`backend`**: Backend-related stories
- **`frontend`**: Frontend-related stories
- **`api`**: API-focused stories
- **`ui`**: User interface stories

## Simplified Workflow

1. **Create Story**: Use CLI or GitHub Issues to submit your initial idea
2. **AI Processing**: System locally processes the story considering multiple role perspectives
3. **Ready Story Created**: Complete, actionable story is created on GitHub
4. **Development**: Story is immediately ready for development work

## Advanced Usage

### Multi-Repository Mode

Configure `.storyteller/config.json` to enable multi-repository story creation:

```json
{
  "repositories": {
    "backend": {
      "name": "myorg/backend-api",
      "type": "backend",
      "description": "Backend API and services"
    },
    "frontend": {
      "name": "myorg/frontend-app", 
      "type": "frontend",
      "description": "User interface"
    }
  }
}
```

### Environment Setup

```bash
# Create .env file
cp .env.example .env

# Edit .env with your settings
GITHUB_TOKEN="your_github_token"
GITHUB_REPOSITORY="your/repository"
DEFAULT_LLM_PROVIDER="openai"  # or "github", "ollama"
```

### Command Examples

```bash
# Basic story creation
python main.py story create "User profile management system"

# With specific roles
python main.py story create "Payment processing" --roles "Product Owner,Security Engineer"

# Multi-repository story
python main.py story create-multi "User authentication" --repos backend,frontend

# Refactor ticket
python main.py story refactor "Extract user service" --type extract --files "user/*.py"
```

## Best Practices

### User Story Format

Follow the standard format:
```
As a [user type], I want [functionality] so that [benefit/goal].
```

**Example:**
```
As a home cook, I want to automatically scale recipe ingredients 
so that I can cook for different numbers of people without manual calculations.
```

### Acceptance Criteria

Include clear acceptance criteria:
```
**Acceptance Criteria:**
- [ ] Recipe ingredients scale proportionally
- [ ] Nutritional information updates automatically
- [ ] Serving size can be adjusted from 1-20 people
- [ ] Fractional measurements are handled correctly
- [ ] Imperial and metric units are supported
```

### Domain Context

Provide context about the recipe domain:
- **Recipe types** involved (main course, dessert, etc.)
- **Dietary considerations** (allergies, restrictions)
- **Cultural aspects** (regional variations, authenticity)
- **Nutritional requirements** (calorie tracking, macros)
- **User personas** (home cook, professional chef, nutritionist)


## Configuration

See [SETUP.md](SETUP.md) for detailed setup instructions.

## Multi-Repository Examples

See [MULTI_REPO_EXAMPLES.md](MULTI_REPO_EXAMPLES.md) for advanced multi-repository usage.

## Refactor Mode

See [REFACTOR_MODE.md](REFACTOR_MODE.md) for refactoring ticket creation.
