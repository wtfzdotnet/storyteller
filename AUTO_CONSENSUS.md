# Auto-Consensus Feature

The `--auto-consensus` feature enables automatic iteration without manual intervention until consensus is reached or the maximum iteration limit is exceeded.

## Configuration

### Environment Variables
- `AUTO_CONSENSUS_ENABLED`: Set to `true` to enable auto-consensus mode (default: `false`)
- `AUTO_CONSENSUS_THRESHOLD`: Consensus threshold percentage (default: `70`)
- `AUTO_CONSENSUS_MAX_ITERATIONS`: Maximum iterations before giving up (default: `10`)

### CLI Flags
- `--auto-consensus`: Enable automatic consensus iteration
- `--consensus-threshold <percent>`: Set consensus threshold (1-100)
- `--max-iterations <count>`: Set maximum iterations

## How It Works

1. **Without manual intervention**: When auto-consensus is enabled, the system automatically iterates through the feedback and refinement cycle.

2. **Configurable consensus threshold**: Default is 70% (vs 80% in normal mode), but can be customized.

3. **Configurable iteration limit**: Default is 10 iterations (vs 5 in normal mode), but can be customized.

4. **Automatic repository ticket creation**: When consensus is reached, the system automatically creates tickets in designated repositories.

5. **Copilot instructions integration**: The system reads `.github/copilot-instructions.md` from target repositories to refine user stories with repository-specific context.

## Usage Examples

### Create story with auto-consensus
```bash
python main.py story create "User authentication system" --auto-consensus
```

### Create story with custom thresholds
```bash
python main.py story create "User authentication system" \
  --auto-consensus \
  --consensus-threshold 75 \
  --max-iterations 8
```

### Iterate existing story with auto-consensus
```bash
python main.py story iterate 123 --auto-consensus
```

## Workflow Changes

When auto-consensus is enabled:

1. **story/enriching → story/reviewing**: Automatically transitions and triggers consensus check
2. **story/reviewing**: Uses configurable consensus threshold
3. **Consensus not met**: Automatically returns to enriching and adds iterate trigger
4. **Consensus met**: Proceeds to consensus state and creates repository tickets
5. **Max iterations reached**: Transitions to blocked state

## Repository Ticket Enhancement

When creating repository tickets, the system:

1. Attempts to read `.github/copilot-instructions.md` from each target repository
2. Enhances the user story with repository-specific context
3. Creates customized tickets for each repository type (backend, frontend, etc.)
4. Links all created tickets back to the original consensus issue

## Error Handling

- Gracefully handles missing copilot instructions files
- Falls back to standard behavior if repository access fails
- Transitions to blocked state if maximum iterations are reached without consensus
- Provides detailed logging for troubleshooting