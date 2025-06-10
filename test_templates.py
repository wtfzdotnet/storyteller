"""Test script for template system functionality."""

import os
import sys
from pathlib import Path

# Mock environment variables for testing
os.environ["GITHUB_TOKEN"] = "test_token"

# Import after setting env vars
from template_manager import TemplateManager


def test_template_system():
    """Test the template system."""
    try:
        # Initialize template manager
        manager = TemplateManager()
        print("✅ Template manager initialized successfully")

        # Test listing templates
        templates = manager.list_templates()
        print(f"✅ Found {len(templates)} templates")
        for template in templates[:5]:  # Show first 5
            print(f"   - {template}")

        # Test Python class template
        context = {
            "class_name": "TestComponent",
            "description": "Test component for validation",
            "class_description": "A test component for validating the template system",
            "imports": ["from typing import Any", "import logging"],
            "init_params": ", name: str = None",
            "init_docstring": "            name: Component name parameter",
            "attributes": [{"name": "name", "value": "name"}],
            "methods": [
                {
                    "name": "process",
                    "params": "",
                    "description": "Process the component",
                    "body": "return f'Processing {self.name}'",
                }
            ],
        }

        rendered = manager.render_template("python/class.py.j2", context)
        print("✅ Python template rendered successfully")
        print("Sample output (first 10 lines):")
        lines = rendered.split("\n")
        for i, line in enumerate(lines[:10]):
            print(f"   {i+1:2d}: {line}")

        # Test React component template
        react_context = {
            "component_name": "TestButton",
            "props_interface": "interface TestButtonProps {\n  label: string;\n}",
            "props_destructure": "{ label }: TestButtonProps",
            "container_class": "test-button",
        }

        rendered_react = manager.render_template(
            "react/functional_component.tsx.j2", react_context
        )
        print("✅ React template rendered successfully")

        # Test story template
        story_context = {
            "component_name": "TestButton",
            "component_file": "TestButton",
            "story_title": "Components/TestButton",
            "arg_types": [{"name": "label", "control": "text"}],
            "default_args": {"label": "'Click me'"},
            "additional_stories": [],
        }

        rendered_story = manager.render_template(
            "storybook/react_story.stories.tsx.j2", story_context
        )
        print("✅ Storybook template rendered successfully")

        print("\n🎉 All template tests passed!")
        return True

    except Exception as e:
        print(f"❌ Template test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_template_system()
    sys.exit(0 if success else 1)
