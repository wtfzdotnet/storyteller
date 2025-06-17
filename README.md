# Storyteller - AI Story Management Tool

A simple AI-powered tool for creating and managing user stories with expert analysis and GitHub integration.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Features

- Create user stories with AI expert analysis
    - Epics
    - Epics with user stories
    - User stories diverge into actionable frontend or backend issues
    - When issues are completed, they should close automatically based on their dependencies
- Multi-repository support
    - Mcp servers that are able to read from multiple repositories to gather the correct context to solve a problem, that for example is frontend and backend related.
    - The way roles are applied should be intelligent, we want a conversation to happen
- GitHub project and issue integration
    - Through projects we should have a clear overview of the user stories we are processing, and the relevant backend or frontend issues being worked on as well within configurable repositories.
    - Should be able to be automatically assigned to `copilot-sve-agent` when ready to be picked up
    - Story should transition when copilot is done
    - Story should transition when changes are requested, or the story is merged
    - Should unblock other stories if a blockage is removed
    - Issues should always be executed in the order of blockages being removed
    - When the pipelines fail, the agent should be informed at max 3 times in a row to fix these conflicts, if it then still fails pause ( think of a logical resumal pattern )
- CLI interface
- MCP server support for AI assistants
    - Read code for implementing API calls from golang backend
    - Read code for creating API calls based on frontend
    - Just be smart about spreading the information we have over multiple repositories

## Expactations

- Roles basically do the usual 40 hour workflow
    - Create / Discover new issues
        - Create epics
            - For the upcoming x sprints, create issues ahead
            - Maintain these tickets according to other tickets being created later on, make sure to reference them properly through github projects.
            - Epics are dissected into user stories ( more discussion )
            - User stories;
                - Require acceptance criteria from relevant roles
                - Require testing criteria from relevant roles
                - Require value from relevant roles
                - Require effort from relevant roles
                - Should be dissected into relevant tasks for different departments, only create tasks for the configured environments in `.storyteller/types/*.md`;
                    - Testing
                    - Devops
                    - Frontend
                    - Backend
                    - Sysops
                    - Product Owner
    - Discuss these and try to reach concensus
        - If no concensus mark the issue and ask for manual resolutation of the end user, leaving where the conversation got stuck on
        - If concensus, and no blockages on other epics/issues, automatically assign to `copilot-sve-agent` if applicable.
        - On pull request failures in pipelines, make sure to discuss this problem with all groups, and make a single comment that represents all their perspectives. You must tag `@copilot` in the comment to trigger the agent to start again.

    - In the end we want a pipeline that can basically run 24/7 tackling one issue after the other in chronological order.

## Setup

```bash
# Clone repository
git clone https://github.com/wtfzdotnet/storyteller.git
cd storyteller

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your GitHub token
```

## Usage

```bash
# Create a story
python main.py story create "Your story description"

# Analyze a story
python main.py story analyze "Your story description"

# Start MCP server
python main.py mcp start
```

## License

MIT License
