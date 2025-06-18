# Pipeline Failure Monitoring System

The pipeline failure monitoring system provides comprehensive monitoring and analysis of CI/CD pipeline failures across repositories with automated agent notifications and intelligent failure classification.

## Overview

The system consists of several key components:

- **PipelineMonitor**: Core monitoring engine with failure detection and classification
- **PipelineDashboard**: Real-time dashboard with health metrics and analytics
- **WebhookHandler**: GitHub webhook processing for pipeline events
- **Database**: Persistent storage for pipeline runs, failures, and patterns
- **CLI Interface**: Command-line tools for monitoring and analysis

## Features

### Automated Failure Detection
- Monitors GitHub workflow runs across all configured repositories
- Automatically classifies failures by category:
  - **Linting**: Code style and syntax errors (flake8, eslint, etc.)
  - **Formatting**: Code formatting issues (black, prettier, etc.)
  - **Testing**: Unit/integration test failures
  - **Build**: Compilation and build errors
  - **Deployment**: Deployment and publishing failures
  - **Dependency**: Package installation and dependency issues
  - **Timeout**: Long-running operations that exceed limits
  - **Infrastructure**: Network, service, and infrastructure errors

### Severity Assessment
- **Critical**: Security vulnerabilities, production outages
- **High**: Build failures, main branch issues, blocking dependencies
- **Medium**: Test failures, linting errors, documentation issues
- **Low**: Warnings, minor style issues, comments

### Agent Notification System
- Automatically notifies `@copilot` when failures exceed thresholds:
  - High or critical severity failures
  - Repeated failures (retry count ≥ 2)
- Creates detailed failure notifications with:
  - Failure summary by category
  - Resolution suggestions
  - Affected repositories and commits
  - Links to related issues

### Pattern Analysis
- Identifies recurring failure patterns across repositories
- Groups similar failures by message content and category
- Provides resolution suggestions based on failure types
- Tracks pattern frequency and affected repositories

### Real-time Dashboard
- Live pipeline status monitoring
- Health metrics and success rates
- Trending analysis over time
- Repository-specific health scores
- Alert summaries and recommendations

## Usage

### CLI Commands

#### Dashboard View
```bash
# View dashboard for last 24 hours
python main.py pipeline dashboard

# View specific repository for last 7 days
python main.py pipeline dashboard --repo wtfzdotnet/storyteller --time-range 7d

# Export as JSON
python main.py pipeline dashboard --format json
```

#### Health Status
```bash
# Get current health status
python main.py pipeline health

# Repository-specific health
python main.py pipeline health --repo wtfzdotnet/storyteller
```

#### Pattern Analysis
```bash
# Analyze patterns over last 30 days
python main.py pipeline patterns --days 30
```

#### Data Export
```bash
# Export monitoring data
python main.py pipeline export --output pipeline_data.json --time-range 7d
```

### GitHub Webhook Setup

To enable automatic pipeline monitoring, configure GitHub webhooks:

1. **Repository Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**: `https://your-domain.com/webhook` 
3. **Content type**: `application/json`
4. **Events**: Select "Workflow runs"
5. **Secret**: Configure webhook secret in environment

### Environment Variables

Required environment variables:
```bash
GITHUB_TOKEN=ghp_xxx           # GitHub API token with repo access
WEBHOOK_SECRET=your_secret     # GitHub webhook secret (optional)
```

## Database Schema

The system uses SQLite with the following tables:

- **pipeline_runs**: Complete pipeline execution records
- **pipeline_failures**: Individual job/step failures with classification
- **failure_patterns**: Detected patterns in recurring failures

## Integration with Existing Systems

### Webhook Handler
The system extends the existing `WebhookHandler` to process `workflow_run` events alongside existing PR and issue events.

### Workflow Processor
Pipeline monitoring integrates with the existing workflow processor to provide monitoring capabilities through the CLI and API interfaces.

### Database Manager
Extends the existing database schema with pipeline monitoring tables while maintaining compatibility with existing story management functionality.

## Configuration

Pipeline monitoring uses the existing configuration system. No additional configuration is required beyond the standard GitHub token setup.

### Repository Configuration
The system automatically monitors all repositories configured in `.storyteller/config.json`. Example:

```json
{
  "repositories": {
    "backend": {
      "name": "wtfzdotnet/storyteller",
      "type": "backend",
      "description": "Main application backend"
    },
    "frontend": {
      "name": "wtfzdotnet/frontend-repo", 
      "type": "frontend",
      "description": "User interface"
    }
  }
}
```

## Troubleshooting

### Common Issues

**No pipeline data showing**:
- Verify GitHub webhook is configured and receiving events
- Check GitHub token has appropriate repository access
- Ensure workflow_run events are enabled in webhook configuration

**Agent notifications not working**:
- Verify @copilot user exists and has access to repositories
- Check webhook processing is successful
- Review failure severity thresholds

**Pattern analysis not finding patterns**:
- Ensure sufficient failure history (minimum 2 similar failures)
- Check time range covers period with failures
- Verify database contains failure records

### Logging

Enable debug logging for troubleshooting:
```bash
python main.py pipeline dashboard --debug
```

## Architecture

The pipeline monitoring system follows the existing Storyteller architecture patterns:

- **Minimal Changes**: Extends existing components without breaking changes
- **Database Integration**: Uses existing database manager with new tables
- **Configuration Reuse**: Leverages existing configuration system
- **CLI Consistency**: Follows established CLI command patterns
- **Async Operations**: Uses async/await for GitHub API calls
- **Error Handling**: Comprehensive error handling with logging

## Performance Considerations

- Database queries are optimized with proper indexing
- API calls are batched where possible
- Dashboard data is cached for performance
- Large log outputs are truncated to prevent storage issues
- Pattern analysis runs in background to avoid blocking operations

## Security

- GitHub tokens are handled securely through environment variables
- Webhook signatures are verified when secret is configured
- Database uses parameterized queries to prevent injection
- Log outputs are sanitized to prevent sensitive data exposure