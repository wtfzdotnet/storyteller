# Test Structure Documentation

This document describes the test organization for the Storyteller project.

## Test Structure

### Unit Tests
Unit tests focus on testing individual components in isolation without external dependencies like GitHub API calls.

#### Root Level Unit Tests
- `test_basic.py` - Basic smoke tests ensuring core functionality works
- `test_conversation_system.py` - Unit tests for conversation system models and core functionality
- `test_multi_repo_context.py` - Unit tests for multi-repository context components  
- `test_comprehensive_multi_repo.py` - Unit tests for multi-repository configuration

#### Organized Unit Tests
- `tests/unit/test_conversation_models.py` - Detailed unit tests for conversation data models
- `tests/unit/test_multi_repo_context_units.py` - Comprehensive unit tests for multi-repo context

### Integration Tests
Integration tests focus on testing complete workflows and may include external dependencies (with proper mocking for CI/CD).

#### Integration Test Suite
- `tests/integration/test_cross_repo_integration.py` - Cross-repository conversation system integration tests
- `tests/integration/test_conversation_comprehensive.py` - Complete conversation workflow tests
- `tests/integration/test_multi_repo_comprehensive.py` - Multi-repository context integration tests
- `tests/integration/test_multi_repo_context_comprehensive.py` - Complete multi-repo context tests

## Running Tests

### Run Basic Unit Tests Only
```bash
# Quick smoke tests
python -m pytest test_basic.py -v

# Core unit tests (no external dependencies)
python -m pytest test_basic.py test_conversation_system.py test_multi_repo_context.py test_comprehensive_multi_repo.py -v

# All unit tests
python -m pytest tests/unit/ -v
```

### Run Integration Tests
```bash
# Integration tests (may require external services or will test error handling)
python -m pytest tests/integration/ -v
```

### Run All Tests
```bash
# Everything
python -m pytest -v
```

## Test Philosophy

### Unit Tests
- **Fast**: Run quickly without external dependencies
- **Isolated**: Test individual components with proper mocking
- **Reliable**: Should always pass in any environment
- **Focused**: Test specific functionality without side effects

### Integration Tests
- **Comprehensive**: Test complete workflows and feature interactions
- **Realistic**: May include external dependencies (with fallback handling)
- **End-to-End**: Test the system as users would interact with it
- **Robust**: Handle external service failures gracefully

## Key Features Tested

### Conversation System
- Data models (ConversationParticipant, Message, Conversation)
- Repository filtering and context management
- Cross-repository conversation capabilities
- MCP server integration

### Multi-Repository Context
- Repository type detection
- Intelligent file selection
- Context caching
- Language detection
- Configuration management

### System Integration
- Full workflow testing
- External API integration (with mocking)
- Error handling and resilience
- Feature capability validation

## Mock Strategy

Unit tests use extensive mocking to avoid external dependencies:
- GitHub API calls are mocked with `AsyncMock`
- Database operations use temporary files
- External services return predictable test data

Integration tests may make real external calls but handle failures gracefully by testing the error handling paths.