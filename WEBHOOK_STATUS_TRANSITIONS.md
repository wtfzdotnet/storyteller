# Automatic Story Status Transitions

This document describes the automatic story status transitions feature that allows GitHub events to automatically update story statuses through webhooks.

## Overview

The automatic status transitions feature monitors GitHub events (pull requests, issues, commits) and automatically updates story statuses based on configurable rules. This keeps project boards current without manual updates.

## Features

- **Webhook Integration**: Secure GitHub webhook handling with signature verification
- **Status Transition Rules**: Configurable mapping from GitHub events to story statuses
- **PR/Commit/Merge Handling**: Support for pull request, issue, and push events
- **Custom Status Mapping**: Repository-specific status transition configurations
- **Audit Trail**: Complete history of all status transitions with metadata

## Configuration

### Environment Variables

Set the webhook secret for signature verification:

```bash
WEBHOOK_SECRET=your_github_webhook_secret_here
```

### Repository Configuration

Add webhook configuration to `.storyteller/config.json`:

```json
{
  "webhook_config": {
    "enabled": true,
    "status_mappings": {
      "pull_request.opened": "in_progress",
      "pull_request.ready_for_review": "review",
      "pull_request.closed": null,
      "issues.opened": "ready",
      "issues.closed": "done",
      "issues.reopened": "in_progress",
      "push": null
    }
  }
}
```

### Status Mapping Rules

The `status_mappings` object defines how GitHub events map to story statuses:

- **pull_request.opened**: When a PR is opened → `in_progress`
- **pull_request.ready_for_review**: When PR is ready for review → `review`
- **pull_request.closed**: When PR is closed (special handling for merged vs closed)
- **issues.opened**: When an issue is opened → `ready`
- **issues.closed**: When an issue is closed → `done`
- **issues.reopened**: When an issue is reopened → `in_progress`
- **push**: When commits are pushed (auto-detects story references)

Set a value to `null` to use custom logic for that event type.

## GitHub Webhook Setup

1. Go to your repository's Settings → Webhooks
2. Add a new webhook with:
   - **Payload URL**: `https://your-domain.com/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: Your webhook secret (same as `WEBHOOK_SECRET` env var)
   - **Events**: Select "Pull requests", "Issues", and "Pushes"

## Story Reference Formats

The system automatically detects story references in:

- Pull request titles and descriptions
- Issue titles and descriptions  
- Commit messages

Supported formats:
- `story_abc12345` (direct reference)
- `#story_abc12345` (with hash prefix)

## Status Transition Logic

### Pull Request Events

- **Opened**: Transitions associated stories to `in_progress`
- **Ready for Review**: Transitions to `review` status
- **Closed (merged)**: Transitions to `done` status
- **Closed (not merged)**: Transitions back to `ready` status

### Issue Events

- **Opened**: Transitions to `ready` status
- **Closed**: Transitions to `done` status
- **Reopened**: Transitions to `in_progress` status

### Push Events

- Automatically detects story references in commit messages
- Transitions stories from `draft` or `ready` to `in_progress`
- Only affects stories not already in progress or beyond

## API Endpoints

### Webhook Endpoint

```http
POST /webhooks/github
Content-Type: application/json
X-Hub-Signature-256: sha256=...

{
  "action": "opened",
  "pull_request": { ... },
  "repository": { ... }
}
```

### Status Endpoints

```http
GET /webhooks/status
```

Returns webhook configuration status.

```http
GET /stories/{story_id}/transitions?limit=50
```

Get status transition history for a specific story.

```http
GET /transitions?limit=100
```

Get recent status transitions across all stories.

## Audit Trail

All status transitions are logged with:

- Story ID and old/new status
- Trigger type (webhook, manual, automation)
- Event details (PR number, issue number, commit SHA)
- Timestamp and metadata
- Repository information

## Security

- **Signature Verification**: All webhooks are verified using HMAC-SHA256
- **Secret Management**: Webhook secrets stored in environment variables
- **Input Validation**: All webhook payloads are validated
- **Error Handling**: Graceful handling of malformed or invalid requests

## Troubleshooting

### Common Issues

1. **Webhook not processing**: Check signature verification and secret configuration
2. **Stories not updating**: Verify story references are in correct format
3. **Missing transitions**: Ensure GitHub issues are linked to stories in database

### Debugging

Enable debug logging:

```bash
LOG_LEVEL=DEBUG
```

Check webhook processing logs and transition audit trail via API endpoints.

## Examples

### Example Webhook Payload (PR Opened)

```json
{
  "action": "opened",
  "pull_request": {
    "number": 123,
    "title": "Fix authentication issue",
    "body": "This PR fixes story_abc12345 and story_def67890",
    "merged": false
  },
  "repository": {
    "full_name": "myorg/myrepo"
  }
}
```

This would transition both `story_abc12345` and `story_def67890` to `in_progress` status.

### Example Transition Audit Entry

```json
{
  "id": 1,
  "story_id": "story_abc12345",
  "old_status": "ready",
  "new_status": "in_progress",
  "trigger_type": "webhook",
  "trigger_source": "github",
  "event_type": "pull_request.opened",
  "repository_name": "myorg/myrepo",
  "pr_number": 123,
  "timestamp": "2025-06-18T12:20:13.266589+00:00",
  "metadata": {
    "pr_title": "Fix authentication issue",
    "merged": false
  }
}
```