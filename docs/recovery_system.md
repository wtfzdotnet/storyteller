# Failure Recovery and Resumption System

The Storyteller recovery system provides comprehensive failure recovery and resumption capabilities for automated agent workflows. This system extends the existing pipeline monitoring with intelligent recovery strategies.

## Core Components

### 1. WorkflowCheckpoint Model
Stores workflow state snapshots at key execution points for recovery purposes.

```python
checkpoint = WorkflowCheckpoint(
    repository="repo/name",
    workflow_name="CI",
    run_id="run_123",
    commit_sha="abc123",
    checkpoint_type="job",  # step, job, workflow
    checkpoint_name="build_complete",
    workflow_state={"step": "build", "status": "completed"},
    environment_context={"python_version": "3.11"},
    dependencies=["requirements.txt"],
    artifacts=["dist/app.tar.gz"]
)
```

### 2. RecoveryState Model
Tracks recovery operations with detailed progress and context.

```python
recovery_state = RecoveryState(
    failure_id="failure_123",
    repository="repo/name",
    recovery_type="resume",  # retry, resume, rollback
    status=RecoveryStatus.IN_PROGRESS,
    target_checkpoint_id="checkpoint_456",
    recovery_plan=["validate_state", "restore_context", "resume_execution"],
    progress_steps=[{"step": "validation", "status": "completed"}]
)
```

### 3. RecoveryManager
Orchestrates all recovery operations with intelligent strategy selection.

## Recovery Strategies

### Retry Recovery
Enhanced retry with failure-specific fixes and exponential backoff.

- **Best for**: Linting, formatting, transient issues
- **Features**: Automatic failure classification, smart retry delays
- **Success Rate**: High for automatable failures

```python
# Automatic retry with enhanced logic
recovery_state = await recovery_manager.initiate_recovery(failure, "retry")
```

### Resume Recovery
Smart resumption from the last valid checkpoint.

- **Best for**: Build failures, long-running processes
- **Features**: State validation, dependency resolution, context restoration
- **Benefits**: Avoids re-executing completed work

```python
# Resume from last checkpoint
recovery_state = await recovery_manager.initiate_recovery(failure, "resume")
```

### Rollback Recovery
Safe rollback to known good states with corruption detection.

- **Best for**: Critical failures, corrupted states
- **Features**: State validation, safe rollback, environment restoration
- **Safety**: Validates target state before rollback

```python
# Rollback to specific checkpoint
success = await recovery_manager.rollback_to_checkpoint(checkpoint, "corruption_detected")
```

## Database Schema

### workflow_checkpoints
```sql
CREATE TABLE workflow_checkpoints (
    id TEXT PRIMARY KEY,
    repository TEXT NOT NULL,
    workflow_name TEXT NOT NULL,
    run_id TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    checkpoint_type TEXT NOT NULL,
    checkpoint_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    workflow_state TEXT DEFAULT '{}',
    environment_context TEXT DEFAULT '{}',
    dependencies TEXT DEFAULT '[]',
    artifacts TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}'
);
```

### recovery_states
```sql
CREATE TABLE recovery_states (
    id TEXT PRIMARY KEY,
    failure_id TEXT NOT NULL,
    repository TEXT NOT NULL,
    recovery_type TEXT NOT NULL,
    status TEXT NOT NULL,
    target_checkpoint_id TEXT,
    recovery_plan TEXT DEFAULT '[]',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    progress_steps TEXT DEFAULT '[]',
    recovery_context TEXT DEFAULT '{}',
    rollback_checkpoint_id TEXT,
    corruption_detected BOOLEAN DEFAULT FALSE,
    validation_results TEXT DEFAULT '{}',
    metadata TEXT DEFAULT '{}',
    
    FOREIGN KEY (failure_id) REFERENCES pipeline_failures (id),
    FOREIGN KEY (target_checkpoint_id) REFERENCES workflow_checkpoints (id),
    FOREIGN KEY (rollback_checkpoint_id) REFERENCES workflow_checkpoints (id)
);
```

## CLI Usage

### Create Checkpoint
```bash
python main.py recovery create-checkpoint \
    --repository "repo/name" \
    --workflow-name "CI" \
    --run-id "run_123" \
    --commit-sha "abc123" \
    --checkpoint-type "job" \
    --checkpoint-name "tests_passed"
```

### Initiate Recovery
```bash
# Automatic strategy selection
python main.py recovery initiate --failure-id "failure_123"

# Specific strategy
python main.py recovery initiate --failure-id "failure_123" --type "resume"
```

### Check Recovery Status
```bash
python main.py recovery status --recovery-id "recovery_456"
```

### Recovery Dashboard
```bash
python main.py recovery dashboard --repository "repo/name"
```

### Rollback to Checkpoint
```bash
python main.py recovery rollback --checkpoint-id "checkpoint_789" --reason "manual_fix"
```

## Integration with Pipeline Monitor

The recovery system integrates seamlessly with the existing pipeline monitor:

```python
# Enhanced recovery replaces basic retry
recovery_state = await pipeline_monitor.initiate_enhanced_recovery(failure, "auto")

# Automatic checkpoint creation
await pipeline_monitor._create_pre_recovery_checkpoint(failure)

# Smart strategy selection
strategy = pipeline_monitor._determine_recovery_strategy(failure)
```

## State Validation

Before any recovery operation, the system validates:

1. **Checkpoint Integrity**: Ensures checkpoint data is complete and valid
2. **Environment Context**: Validates environment variables and dependencies
3. **Artifact Availability**: Checks that required artifacts exist
4. **Dependency Resolution**: Verifies all dependencies are accessible

```python
validation = await recovery_manager.validate_state(checkpoint)
if not validation["is_valid"]:
    # Handle validation errors
    logger.error(f"Invalid state: {validation['errors']}")
```

## Recovery Dashboard

The recovery dashboard provides comprehensive monitoring:

- **Recovery Summary**: Success rates, active recoveries, statistics
- **Recovery by Type**: Breakdown by retry/resume/rollback
- **Recent Operations**: Latest recovery operations with status
- **Checkpoint Status**: Available checkpoints and their health

```json
{
  "recovery_summary": {
    "total_recoveries": 45,
    "successful_recoveries": 38,
    "failed_recoveries": 5,
    "in_progress_recoveries": 2,
    "success_rate": 84.44
  },
  "recovery_by_type": {
    "retry": {"total": 30, "successful": 27},
    "resume": {"total": 10, "successful": 8},
    "rollback": {"total": 5, "successful": 3}
  }
}
```

## Best Practices

### Checkpoint Creation
- Create checkpoints after significant milestones
- Include minimal but sufficient state information
- Store critical environment context
- Clean up old checkpoints regularly

### Recovery Strategy Selection
- Use retry for simple, automatable failures
- Use resume for complex, long-running processes
- Use rollback for critical failures or corruption
- Let the system auto-select for most cases

### State Management
- Validate state before recovery operations
- Monitor recovery progress actively
- Handle partial failures gracefully
- Maintain audit trails for compliance

## Error Handling

The recovery system includes comprehensive error handling:

- **Graceful Degradation**: Falls back to basic retry if recovery manager unavailable
- **Validation Errors**: Prevents recovery with invalid checkpoints
- **Partial Failures**: Handles incomplete recovery operations
- **Timeout Protection**: Prevents infinite recovery loops

## Performance Considerations

- **Checkpoint Storage**: Optimized with JSON compression and cleanup
- **Recovery Processing**: Async operations prevent blocking
- **Database Queries**: Indexed for fast checkpoint and recovery lookups
- **Memory Usage**: Lazy loading of checkpoint data

This recovery system provides a robust foundation for handling pipeline failures with intelligent recovery strategies, comprehensive state management, and seamless integration with existing workflow automation.