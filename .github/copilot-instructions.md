# GitHub Copilot Instructions for AI Story Management System

## Code Quality Standards

This project enforces strict code quality standards through automated CI/CD pipelines. **All code changes must comply with these standards before committing** to avoid pipeline failures and back-and-forth discussions.

## Pre-Commit Requirements

### 1. Python Code Formatting with Black

**MANDATORY:** All Python files must be formatted with Black before committing.

```bash
# Install Black (if not already installed)
pip install black

# Format all Python files
black .

# Check formatting compliance
black --check --diff .
```

**Black Configuration:**
- Line length: 88 characters (Black default)
- String quotes: Double quotes preferred
- All Python files must pass `black --check .`

### 2. Import Sorting with isort

**MANDATORY:** All Python imports must be sorted with isort.

```bash
# Install isort (if not already installed)  
pip install isort

# Sort imports in all Python files
isort .

# Check import sorting compliance
isort --check-only --diff .
```

### 3. Code Linting with flake8

**MANDATORY:** All Python code must pass flake8 linting checks.

```bash
# Install flake8 (if not already installed)
pip install flake8

# Run syntax and undefined name checks (CRITICAL - will fail CI)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=venv

# Run full linting check
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --exclude=venv
```

**Critical flake8 errors that will fail CI:**
- `E9`: Runtime errors
- `F63`: Invalid print statement
- `F7`: Syntax errors  
- `F82`: Undefined names

### 4. Python Syntax Validation

**MANDATORY:** All Python files must have valid syntax.

```bash
# Run our custom syntax validator
python test_syntax.py
```

This validates syntax for core files:
- `main.py`
- `story_manager.py` 
- `llm_handler.py`
- `github_handler.py`
- `config.py`
- `automation/label_manager.py`
- `automation/workflow_processor.py`

## Pre-Commit Workflow

**ALWAYS run this complete workflow before committing:**

```bash
# 1. Format code with Black
black .

# 2. Sort imports with isort  
isort .

# 3. Validate syntax
python test_syntax.py

# 4. Run linting checks
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=venv

# 5. Verify formatting compliance
black --check --diff .
isort --check-only --diff .

# 6. If all checks pass, commit your changes
git add -A
git commit -m "your commit message"
```

## Dependencies Management

### Core Dependencies (requirements.txt)

When adding new dependencies, ensure they are:
1. **Pinned to minimum versions** using `>=` syntax
2. **Categorized appropriately** with comments
3. **Compatible with Python 3.11+**

Current dependency categories:
- Core dependencies (python-dotenv, typer)
- GitHub API (PyGithub)
- Async HTTP requests (aiohttp)
- AI/LLM providers (openai, ollama)
- Data handling (pydantic)
- Additional utilities (requests, asyncio-mqtt)

### Virtual Environment

Always work within the project's virtual environment:

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install black flake8 isort
```

## File Structure Standards

### Python Files
- All Python files must have valid syntax
- Follow PEP 8 standards (enforced by flake8)
- Use Black formatting (88 character line limit)
- Sort imports with isort
- Include proper error handling
- Add logging where appropriate

### Configuration Files
- `.env.example` - Template for environment variables
- `requirements.txt` - Python dependencies with version constraints
- `pyproject.toml` - Project metadata and tool configurations

### Documentation
- `README.md` - Project overview and basic usage
- `SETUP.md` - Detailed setup instructions
- `*.md` files - Feature-specific documentation

## CI/CD Pipeline Compliance

The CI/CD pipeline (`ci-cd.yml`) runs these checks:

1. **Syntax Check**: `flake8 . --select=E9,F63,F7,F82` (FAILS build on errors)
2. **Code Formatting**: `black --check --diff .` (FAILS build if not formatted)
3. **Import Sorting**: `isort --check-only --diff .` (FAILS build if not sorted)
4. **Full Linting**: `flake8 . --max-complexity=10 --max-line-length=127`
5. **Tests**: `python test_multi_repo.py`

**Pipeline will FAIL if any of these checks fail.**

## Common Issues to Avoid

### 1. Import Errors
```python
# ❌ WRONG - Will cause F821 undefined name error
from config import get_config
# Using Config class without importing it

# ✅ CORRECT
from config import get_config, Config
```

### 2. Formatting Issues
```python
# ❌ WRONG - Black will reformat
def function(param1,param2,param3="default"):
    return f'{param1} {param2}'

# ✅ CORRECT - Black formatted
def function(param1, param2, param3="default"):
    return f"{param1} {param2}"
```

### 3. Line Length
```python
# ❌ WRONG - Line too long
really_long_function_call_with_many_parameters(param1, param2, param3, param4, param5, param6)

# ✅ CORRECT - Black will format properly
really_long_function_call_with_many_parameters(
    param1, param2, param3, param4, param5, param6
)
```

## GitHub Copilot Guidance

When using GitHub Copilot in this project:

1. **Always format code** with Black after accepting suggestions
2. **Check import statements** and add missing imports
3. **Run syntax validation** after making changes
4. **Follow existing code patterns** in the project
5. **Add proper error handling** for new functions
6. **Include type hints** where appropriate
7. **Add docstrings** for new functions and classes

## Testing Requirements

Before committing, ensure:

1. **Syntax tests pass**: `python test_syntax.py`
2. **Setup tests pass**: `python test_setup.py` 
3. **Multi-repo tests pass**: `python test_multi_repo.py`
4. **Refactor tests pass**: `python test_refactor.py`

## Quick Reference Commands

```bash
# Pre-commit checklist (run all of these)
black . && isort . && python test_syntax.py && flake8 . --select=E9,F63,F7,F82 --show-source --exclude=venv

# Verify everything is ready for commit
black --check . && isort --check-only . && echo "✅ Ready to commit!"

# Install all development tools
pip install black flake8 isort

# Full project validation
bash validate_setup.sh
```

## Emergency Fixes

If CI/CD pipeline fails:

1. **Check the exact error message** in GitHub Actions
2. **Run the failing command locally** to reproduce the issue
3. **Apply the fix** using the appropriate tool (Black, isort, flake8)
4. **Re-run all pre-commit checks** before pushing

Remember: **Prevention is better than pipeline fixes.** Always run the pre-commit workflow!
