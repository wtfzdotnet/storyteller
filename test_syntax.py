#!/usr/bin/env python3
"""
Test script to validate that all Python syntax errors are resolved
"""

import ast
import sys
from pathlib import Path


def test_syntax(filepath):
    """Test if a Python file has valid syntax"""
    try:
        with open(filepath, "r") as f:
            source = f.read()

        # Parse the AST to check for syntax errors
        ast.parse(source, filename=str(filepath))
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Test all Python files for syntax errors"""
    print("🧪 Testing Python files for syntax errors...")
    print("=" * 50)

    # Core Python files to test
    files_to_test = [
        "main.py",
        "story_manager.py",
        "llm_handler.py",
        "github_handler.py",
        "config.py",
        "automation/label_manager.py",
        "automation/workflow_processor.py",
    ]

    all_passed = True

    for filepath in files_to_test:
        path = Path(filepath)
        if path.exists():
            passed, error = test_syntax(path)
            if passed:
                print(f"✅ {filepath}")
            else:
                print(f"❌ {filepath}: {error}")
                all_passed = False
        else:
            print(f"⚠️  {filepath}: File not found")

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All Python files have valid syntax!")
        return 0
    else:
        print("❌ Some files have syntax errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
