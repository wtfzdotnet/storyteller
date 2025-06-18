# Multi-Repository Code Context Reading

This document describes the multi-repository code context reading functionality implemented for the Storyteller MCP server.

## Overview

The multi-repository context reading system allows the MCP server to intelligently analyze and extract context from multiple GitHub repositories. It provides automatic repository type detection, intelligent file selection, and cross-repository insights.

## Key Features

### Repository Type Detection
- **Frontend**: React, Vue, Angular applications
- **Backend**: API services, microservices
- **Mobile**: React Native, Flutter, native mobile apps
- **Documentation**: README files, docs sites
- **DevOps**: Docker, Kubernetes, CI/CD configurations
- **Data**: Jupyter notebooks, data analysis projects

### Intelligent File Selection
The system prioritizes important files based on repository type:
- Configuration files (package.json, requirements.txt, etc.)
- Main application files (App.js, main.py, etc.)
- Documentation (README.md, docs/)
- Root-level files over deeply nested ones

### Context Caching
- In-memory LRU cache for repository contexts
- Configurable cache size and TTL
- Reduces GitHub API calls for repeated requests

## MCP Server Endpoints

### `context/repository`
Get context for a single repository.

```json
{
  "method": "context/repository",
  "params": {
    "repository": "backend",
    "max_files": 20,
    "use_cache": true
  }
}
```

### `context/multi_repository`
Get aggregated context from multiple repositories.

```json
{
  "method": "context/multi_repository", 
  "params": {
    "repositories": ["backend", "frontend"],
    "max_files_per_repo": 15
  }
}
```

### `context/file_content`
Read specific file content from a repository.

```json
{
  "method": "context/file_content",
  "params": {
    "repository": "backend",
    "file_path": "src/main.py",
    "ref": "main"
  }
}
```

### `context/repository_structure`
Get repository structure and metadata.

```json
{
  "method": "context/repository_structure",
  "params": {
    "repository": "frontend",
    "ref": "main"
  }
}
```

## Configuration

Repository configurations are defined in `.storyteller/config.json`:

```json
{
  "repositories": {
    "backend": {
      "name": "owner/backend-repo",
      "type": "backend",
      "description": "API services and business logic",
      "dependencies": [],
      "story_labels": ["backend", "api"]
    },
    "frontend": {
      "name": "owner/frontend-repo",
      "type": "frontend", 
      "description": "User interface application",
      "dependencies": ["backend"],
      "story_labels": ["frontend", "ui"]
    }
  }
}
```

## Usage Examples

### Python Client
```python
import asyncio
from mcp_server import MCPStoryServer, MCPRequest

async def get_repository_context():
    server = MCPStoryServer()
    
    request = MCPRequest(
        id="ctx1",
        method="context/repository",
        params={"repository": "backend", "max_files": 10}
    )
    
    response = await server.handle_request(request)
    if response.result and response.result.get("success"):
        context = response.result["data"]
        print(f"Repository: {context['repository']}")
        print(f"Type: {context['repo_type']}")
        print(f"Key files: {len(context['key_files'])}")

asyncio.run(get_repository_context())
```

### Multi-Repository Analysis
```python
async def analyze_all_repositories():
    server = MCPStoryServer()
    
    request = MCPRequest(
        id="ctx2",
        method="context/multi_repository",
        params={"max_files_per_repo": 5}
    )
    
    response = await server.handle_request(request)
    if response.result and response.result.get("success"):
        data = response.result["data"]
        print(f"Analyzed {len(data['repositories'])} repositories")
        print(f"Total files: {data['total_files_analyzed']}")
        print(f"Quality score: {data['context_quality_score']}")
        
        # Cross-repository insights
        insights = data["cross_repository_insights"]
        print(f"Shared languages: {insights['shared_languages']}")
        print(f"Common patterns: {insights['common_patterns']}")

asyncio.run(analyze_all_repositories())
```

## Architecture

### Core Components

1. **MultiRepositoryContextReader**: Main orchestrator
2. **RepositoryTypeDetector**: Analyzes file patterns to detect repo type
3. **IntelligentFileSelector**: Selects most relevant files
4. **ContextCache**: Caches results for performance
5. **GitHubHandler**: Extended with file reading capabilities

### Data Models

- **FileContext**: Individual file information with content and metadata
- **RepositoryContext**: Complete repository analysis with key files
- **MultiRepositoryContext**: Aggregated cross-repository insights

## Performance Considerations

- **File Limits**: Default max 20 files per repository to prevent API rate limiting
- **Caching**: Repository contexts cached to minimize repeated API calls
- **Smart Selection**: Only analyzes important files, skips generated/vendor code
- **Async Processing**: Concurrent repository analysis for better performance

## Error Handling

- Graceful handling of GitHub API rate limits
- Repository access errors don't fail entire multi-repo analysis
- Invalid repository configurations are logged and skipped
- Network timeouts handled with retries

## Security

- Repository access controlled by GitHub token permissions
- File path validation prevents directory traversal
- Repository list restricted to configured repositories
- Content size limits prevent memory exhaustion

## Future Enhancements

- **Semantic Analysis**: Code understanding beyond file structure
- **Dependency Mapping**: Automatic detection of cross-repo dependencies  
- **Change Detection**: Track file changes across repositories
- **AI Summarization**: Generate natural language summaries of repositories
- **Performance Metrics**: Detailed timing and usage analytics