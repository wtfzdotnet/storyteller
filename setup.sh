#!/bin/bash

# AI Story Management System - Local Setup Script
# This script will help you set up the project locally

set -e  # Exit on any error

echo "🚀 Setting up AI Story Management System locally..."
echo "================================================="

# Check if Python 3.8+ is installed
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d" " -f2)
required_version="3.8"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    echo "✅ Python $python_version is installed and compatible"
else
    echo "❌ Python 3.8+ is required. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Copy environment template if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created from template"
    echo "⚠️  Please edit .env file and add your API keys and configuration"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit the .env file and add your API keys:"
echo "   - GITHUB_TOKEN (required)"
echo "   - OPENAI_API_KEY (if using OpenAI)"
echo "   - GITHUB_REPOSITORY (if using single-repo mode)"
echo ""
echo "2. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Test the setup:"
echo "   python main.py story config"
echo ""
echo "4. Create your first story:"
echo "   python main.py story create 'Your story idea here'"
echo ""
echo "📖 For more information, see README.md"
