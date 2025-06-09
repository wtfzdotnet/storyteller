#!/usr/bin/env python3
"""
Test script to verify the setup without requiring API keys
"""

import os
import sys
from pathlib import Path


def test_python_version():
    """Test Python version compatibility"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} is compatible")
    return True


def test_virtual_environment():
    """Test if virtual environment is active"""
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        print("✅ Virtual environment is active")
        return True
    else:
        print("⚠️  Virtual environment not detected (optional)")
        return True


def test_dependencies():
    """Test if required dependencies are installed"""
    required_packages = [
        "openai",
        "ollama",
        "aiohttp",
        "typer",
        "pydantic",
        "dotenv",
        "github",
    ]

    missing = []
    for package in required_packages:
        try:
            if package == "dotenv":
                import python_dotenv
            elif package == "github":
                import github
            else:
                __import__(package)
            print(f"✅ {package} is installed")
        except ImportError:
            print(f"❌ {package} is missing")
            missing.append(package)

    return len(missing) == 0


def test_project_structure():
    """Test if project files exist"""
    required_files = [
        "main.py",
        "llm_handler.py",
        "github_handler.py",
        "story_manager.py",
        "config.py",
        "requirements.txt",
        ".env.example",
        ".storyteller/config.json",
    ]

    missing = []
    for file in required_files:
        if Path(file).exists():
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} is missing")
            missing.append(file)

    return len(missing) == 0


def test_env_file():
    """Test if .env file exists"""
    if Path(".env").exists():
        print("✅ .env file exists")
        print("⚠️  Remember to configure your API keys in .env")
        return True
    else:
        print("⚠️  .env file not found - create it from .env.example")
        return False


def main():
    """Run all tests"""
    print("🧪 Testing AI Story Management System Setup")
    print("=" * 50)

    tests = [
        test_python_version,
        test_virtual_environment,
        test_dependencies,
        test_project_structure,
        test_env_file,
    ]

    results = []
    for test in tests:
        print()
        results.append(test())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 All {total} tests passed! Setup is complete.")
        print("\n📋 Next steps:")
        print("1. Edit .env file and add your API keys")
        print("2. Activate virtual environment: source venv/bin/activate")
        print("3. Test with: python main.py story config")
    else:
        print(f"⚠️  {passed}/{total} tests passed. Please address the issues above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
