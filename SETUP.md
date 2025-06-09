# 🚀 AI Story Management System - Local Setup Guide

This guide will walk you through setting up the AI Story Management System on your local machine.

## 📋 Prerequisites

- **Python 3.8+** (required)
- **Git** (for cloning and version control)
- **GitHub Personal Access Token** (required for GitHub API access)
- **LLM Provider Access** (choose one):
  - GitHub Models API (recommended, free)
  - OpenAI API (paid)
  - Ollama (local, free)

## 🛠️ Quick Setup

### Option 1: Automated Setup (Recommended)

```bash
# Navigate to the project directory
cd /home/m/git/wtfzdotnet/storyteller

# Run the setup script
./setup.sh
```

### Option 2: Manual Setup

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## 🔑 Configuration

### 1. Environment Variables (.env)

Copy `.env.example` to `.env` and configure:

```bash
# Required
GITHUB_TOKEN=your_github_personal_access_token
DEFAULT_LLM_PROVIDER=github  # or openai, ollama

# Optional (for single-repository mode)
GITHUB_REPOSITORY=your_username/your_repository

# If using OpenAI
OPENAI_API_KEY=your_openai_api_key

# If using Ollama (local)
OLLAMA_API_HOST=http://localhost:11434
```

### 2. GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with these permissions:
   - `repo` (full repository access)
   - `write:discussion` (for issue management)
3. Copy the token to your `.env` file

### 3. Multi-Repository Configuration (Optional)

Edit `.storyteller/config.json` for multi-repository setup:

```json
{
  "repositories": {
    "backend": {
      "name": "your-org/backend-repo",
      "type": "backend",
      "description": "Backend API and services",
      "dependencies": [],
      "story_labels": ["backend", "api"]
    },
    "frontend": {
      "name": "your-org/frontend-repo",
      "type": "frontend",
      "description": "User interface",
      "dependencies": ["backend"],
      "story_labels": ["frontend", "ui"]
    }
  },
  "default_repository": "backend"
}
```

## 🧪 Testing Your Setup

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Check configuration:**
   ```bash
   python main.py story config
   ```

3. **Test LLM connection:**
   ```bash
   python llm_handler.py  # Runs built-in tests
   ```

4. **Create a test story:**
   ```bash
   python main.py story create "Test story for setup validation"
   ```

## 🎯 Available Commands

### Core Commands

```bash
# Configuration
python main.py story config              # Show current configuration

# Single Repository Mode
python main.py story create "Story description"
python main.py story iterate <issue_number>
python main.py story check-agreement <issue_number>

# Multi-Repository Mode
python main.py story list-repositories    # List available repositories
python main.py story create-multi "Story description"
python main.py story create "Story" --repository backend
```

### Advanced Options

```bash
# Use specific roles
python main.py story create "Story" --roles "Product Owner,Lead Developer"

# Enable repository-based prompts (GitHub Models)
python main.py story create "Story" --use-repository-prompts

# Auto-consensus mode
python main.py story create "Story" --auto-consensus
```

## 🔧 LLM Provider Setup

### GitHub Models (Recommended)
- **Cost:** Free
- **Setup:** Only requires GitHub token
- **Models:** GPT-4o-mini, other GitHub Models
- **Configuration:** Set `DEFAULT_LLM_PROVIDER=github` in `.env`

### OpenAI
- **Cost:** Paid (API usage)
- **Setup:** Requires OpenAI API key
- **Models:** GPT-3.5-turbo, GPT-4, etc.
- **Configuration:** Set `DEFAULT_LLM_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`

### Ollama (Local)
- **Cost:** Free (local processing)
- **Setup:** Install and run Ollama locally
- **Models:** Llama3, Mistral, etc.
- **Configuration:** 
  1. Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
  2. Start Ollama: `ollama serve`
  3. Pull a model: `ollama pull llama3`
  4. Set `DEFAULT_LLM_PROVIDER=ollama` in `.env`

## 🐛 Troubleshooting

### Common Issues

1. **"GITHUB_TOKEN is required" error:**
   - Ensure you've set `GITHUB_TOKEN` in your `.env` file
   - Verify the token has correct permissions

2. **"Connection refused" with Ollama:**
   - Make sure Ollama is running: `ollama serve`
   - Check the host URL in `.env`

3. **OpenAI API errors:**
   - Verify your API key is valid
   - Check your OpenAI account has sufficient credits

4. **Module import errors:**
   - Ensure virtual environment is activated
   - Reinstall dependencies: `pip install -r requirements.txt`

### Getting Help

- Check the logs for detailed error messages
- Review the example configurations in `.storyteller/`
- Test individual components with the built-in test functions

## 📁 Project Structure

```
storyteller/
├── main.py                 # CLI entry point
├── llm_handler.py          # LLM integration
├── github_handler.py       # GitHub API integration
├── story_manager.py        # Core story logic
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── setup.sh              # Setup script
├── .env.example           # Environment template
├── .storyteller/          # Configuration and AI context
│   ├── config.json        # Multi-repo configuration
│   ├── roles/             # AI role definitions
│   └── README.md          # AI documentation
└── automation/            # GitHub workflow automation
    ├── workflow_processor.py
    └── label_manager.py
```

## 🚀 Next Steps

After setup:

1. **Explore the AI roles** in `.storyteller/roles/` to understand the expert system
2. **Try different story creation modes** (single repo vs multi-repo)
3. **Experiment with different AI roles** using the `--roles` option
4. **Set up GitHub Actions** for automated story processing (see `story-automation.yml`)

Happy story crafting! 🎭
