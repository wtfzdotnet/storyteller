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

The project should have an import method which imports a roadmap ( could be small ), which then through discussion turns it into;

- Epics
    - User stories
        - (Frontend/Backend/Testing/Devops/Sysops/etc...) Story

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

# Import a roadmap
python main.py story import-roadmap <path_to_file.csv> --format csv
python main.py story import-roadmap <path_to_file.json> --format json
python main.py story import-roadmap <path_to_file.xlsx> --format excel

# Preview roadmap import
python main.py story import-roadmap <path_to_file.csv> --format csv --preview

# Start MCP server
python main.py mcp start
```

## Roadmap Import File Formats

The roadmap import feature supports CSV, JSON, and Excel files.

### CSV and Excel Format

For CSV and Excel files, each row represents a story (Epic, UserStory, or SubStory). The following columns are expected (minimum):

- `type`: Specifies the story type. Must be one of `epic`, `user_story`, or `sub_story`.
- `title`: The title of the story.
- `description`: A description of the story.
- `id`: (Optional) A unique identifier for the story. If not provided, one will be generated.
- `parent_id`: (Required for `user_story` and `sub_story`) The ID of the parent story.
    - For a `user_story`, this is the ID of its parent `epic`.
    - For a `sub_story`, this is the ID of its parent `user_story`.

Additional columns can be included to map to other fields in the `Epic`, `UserStory`, and `SubStory` models, such as:
- For Epics: `business_value`, `acceptance_criteria` (comma-separated if multiple), `target_repositories` (comma-separated), `estimated_duration_weeks`.
- For UserStories: `user_persona`, `user_goal`, `acceptance_criteria` (comma-separated), `target_repositories` (comma-separated), `story_points`.
- For SubStories: `department`, `technical_requirements` (comma-separated), `dependencies` (comma-separated, referring to other sub-story IDs), `target_repository`, `assignee`, `estimated_hours`.

*Note: The parsing of comma-separated fields for lists and linking dependencies by ID in CSV/Excel will be fully fleshed out by the `_parse_row_to_story` and `_build_story_hierarchies` methods in `RoadmapImporter.py` which are currently placeholders.*

### JSON Format

The JSON file should contain a list of epic objects. Each epic object can have a `user_stories` key with a list of user story objects, and each user story object can have a `sub_stories` key with a list of sub-story objects.

Example JSON structure:
```json
[
  {
    "id": "EP01",
    "title": "Main Epic Title",
    "description": "Description of the main epic.",
    "business_value": "Significant business impact.",
    "acceptance_criteria": ["AC for Epic 1", "AC for Epic 2"],
    "target_repositories": ["backend-repo", "frontend-repo"],
    "estimated_duration_weeks": 4,
    "user_stories": [
      {
        "id": "US01",
        "title": "User Story 1 for EP01",
        "description": "As a user, I want to...",
        "user_persona": "End User",
        "user_goal": "Achieve something useful",
        "acceptance_criteria": ["US AC1", "US AC2"],
        "target_repositories": ["frontend-repo"],
        "story_points": 5,
        "sub_stories": [
          {
            "id": "SS01",
            "title": "Sub-task for US01 - Frontend",
            "description": "Implement the UI component.",
            "department": "frontend",
            "technical_requirements": ["React", "TypeScript"],
            "target_repository": "frontend-repo",
            "estimated_hours": 8
          },
          {
            "id": "SS02",
            "title": "Sub-task for US01 - Backend",
            "description": "Develop the API endpoint.",
            "department": "backend",
            "dependencies": ["SS01"],
            "target_repository": "backend-repo",
            "estimated_hours": 12
          }
        ]
      }
    ]
  },
  {
    "title": "Another Epic (ID will be auto-generated)",
    "description": "Another epic without a pre-defined ID."
  }
]
```
All fields within each story object correspond to the attributes of the `Epic`, `UserStory`, and `SubStory` models. Optional fields can be omitted.

## API Documentation

The roadmap import functionality is also available via the API:

- **POST /roadmap/import**
    - Imports a roadmap from an uploaded file.
    - **Query Parameters**:
        - `file_format: str` (required) - The format of the file (`csv`, `json`, `excel`).
        - `preview: bool` (optional, default: `false`) - If `true`, previews the import without saving.
    - **Request Body**: The file to import (multipart/form-data).
    - **Responses**:
        - `200 OK`: Successful import or preview.
            - For import: `{ "message": "Roadmap imported successfully.", "epics_created": X, "user_stories_created": Y, "sub_stories_created": Z }`
            - For preview: `{ "message": "Roadmap import preview generated successfully.", "preview_data": { ... } }`
        - `400 Bad Request`: Invalid file format, parsing error, or other issues with the request.
        - `500 Internal Server Error`: Unexpected server error.

Refer to the API server's auto-generated documentation (e.g., at `/docs` when the server is running) for more details.


## License

MIT License
