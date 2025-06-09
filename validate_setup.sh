#!/bin/bash

# Quick Setup Validation Script
echo "🔍 AI Story Management System - Setup Validation"
echo "================================================"

# Check virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment active: $(basename $VIRTUAL_ENV)"
else
    echo "⚠️  Virtual environment not active"
    echo "   Run: source venv/bin/activate"
fi

# Check Python dependencies
echo ""
echo "📦 Checking dependencies..."
python -c "
try:
    import openai, ollama, aiohttp, typer, pydantic, github
    from dotenv import load_dotenv
    print('✅ All core dependencies installed')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
" 2>/dev/null

# Check project files
echo ""
echo "📁 Checking project structure..."
for file in main.py llm_handler.py github_handler.py story_manager.py config.py .env requirements.txt; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file missing"
    fi
done

# Check .storyteller directory
if [ -d ".storyteller" ] && [ -f ".storyteller/config.json" ]; then
    echo "✅ .storyteller/config.json"
else
    echo "❌ .storyteller/config.json missing"
fi

echo ""
echo "🎯 Next Steps:"
echo "1. Edit .env file with your API keys:"
echo "   - GITHUB_TOKEN=your_github_token"
echo "   - OPENAI_API_KEY=your_openai_key (optional)"
echo ""
echo "2. Test configuration:"
echo "   source venv/bin/activate"
echo "   python main.py story config"
echo ""
echo "3. Create your first story:"
echo "   python main.py story create 'Your story idea'"
echo ""

# Check if .env has any configuration
if [ -s ".env" ]; then
    echo "📝 .env file exists and has content"
    if grep -q "your_.*_here" .env; then
        echo "⚠️  Please update placeholder values in .env"
    fi
else
    echo "📝 .env file is empty - please add your configuration"
fi
