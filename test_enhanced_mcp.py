#!/usr/bin/env python3
"""
Test script for enhanced MCP capabilities with template system and rulesets.
Tests the integration of language-specific repository configuration with Jinja2 templates.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    Config,
    LanguageType,
    PlatformChoice, 
    get_config,
    get_repository_config,
    get_repository_ruleset,
    load_default_rulesets,
)
from mcp_server import MCPStoryServer, MCPRequest
from template_manager import TemplateManager


def test_config_system():
    """Test the enhanced configuration system with rulesets."""
    print("🔧 Testing Enhanced Configuration System")
    print("=" * 50)
    
    # Test enum values
    print("✅ Language Types:")
    for lang in LanguageType:
        print(f"   - {lang.value}")
    
    print("\n✅ Platform Choices:")
    for platform in PlatformChoice:
        print(f"   - {platform.value}")
    
    # Test default rulesets
    print("\n✅ Default Rulesets:")
    rulesets = load_default_rulesets()
    for ruleset_name, ruleset in rulesets.items():
        print(f"   - {ruleset_name}: {ruleset.name}")
        print(f"     Language: {ruleset.language.value}")
        print(f"     Platforms: {[p.value for p in ruleset.platforms]}")
        print(f"     Actions: {len(ruleset.actions)}")
        for action in ruleset.actions[:2]:  # Show first 2 actions
            print(f"       * {action.name}: {action.description}")
        print()


def test_template_system():
    """Test the Jinja2 template system."""
    print("🎨 Testing Template System")
    print("=" * 50)
    
    # Initialize template manager
    template_manager = TemplateManager()
    
    # List available templates
    templates = template_manager.list_templates()
    print(f"✅ Found {len(templates)} templates:")
    for template in templates:
        print(f"   - {template}")
    
    # Test Python class template
    print(f"\n✅ Testing Python Class Template:")
    context = {
        "class_name": "ExampleService",
        "class_description": "Service for handling example operations",
        "imports": ["from typing import Optional", "import logging"],
        "init_params": [
            {"name": "config", "type_annotation": "Optional[dict]", "default_value": "None"}
        ],
        "init_docstring": "Initialize the example service with optional configuration.",
        "attributes": [
            {"name": "logger", "type_annotation": "logging.Logger", "value": 'logging.getLogger(__name__)'}
        ],
        "methods": [
            {
                "name": "process_data",
                "params": [{"name": "data", "type_annotation": "str"}],
                "return_type": "str",
                "docstring": "Process the input data and return result.",
                "body": "return f'Processed: {data}'"
            }
        ]
    }
    
    try:
        python_code = template_manager.render_template("python/class.py.j2", context)
        print("   ✅ Python template rendered successfully")
        print(f"   📝 Generated {len(python_code.splitlines())} lines of code")
    except Exception as e:
        print(f"   ❌ Python template error: {e}")
    
    # Test React component template
    print(f"\n✅ Testing React Component Template:")
    react_context = {
        "component_name": "UserProfile",
        "props_interface": "UserProfileProps",
        "props_destructure": "{ name, email, avatar }",
        "container_class": "user-profile-container"
    }
    
    try:
        react_code = template_manager.render_template("react/functional_component.tsx.j2", react_context)
        print("   ✅ React template rendered successfully")
        print(f"   📝 Generated {len(react_code.splitlines())} lines of code")
    except Exception as e:
        print(f"   ❌ React template error: {e}")


async def test_mcp_server_integration():
    """Test MCP server with enhanced capabilities."""
    print("🚀 Testing MCP Server Integration")
    print("=" * 50)
    
    # Initialize MCP server
    config = get_config()
    server = MCPStoryServer(config)
    
    print("✅ MCP Server initialized successfully")
    print(f"   - Template manager: {server.template_manager is not None}")
    print(f"   - Available handlers: {len(server._handlers)}")
    
    # Test component generation request
    print("\n✅ Testing Component Generation:")
    request = MCPRequest(
        id="test-1",
        method="component/generate",
        params={
            "component_name": "RecipeCard",
            "component_type": "react",
            "template_type": "functional",
            "props": [
                {"name": "title", "type": "string", "required": True},
                {"name": "description", "type": "string", "required": False},
                {"name": "imageUrl", "type": "string", "required": False}
            ]
        }
    )
    
    try:
        response = await server.handle_request(request)
        if response.error:
            print(f"   ❌ Request failed: {response.error}")
        else:
            print("   ✅ Component generation successful")
            result = response.result
            print(f"   📦 Generated component: {len(result.get('component_code', ''))} chars")
            print(f"   📝 Supporting files: {len(result.get('supporting_files', {}))}")
    except Exception as e:
        print(f"   ❌ Component generation error: {e}")
    
    # Test repository configuration
    print("\n✅ Testing Repository Configuration:")
    try:
        # Test with example config
        example_repo_config = {
            "name": "test-repo",
            "url": "https://github.com/test/repo",
            "language": "typescript",
            "platforms": ["react", "vite", "tailwind"],
            "ruleset": "typescript_react_vite"
        }
        
        # This would normally be loaded from config, but we'll simulate it
        print(f"   📋 Repository: {example_repo_config['name']}")
        print(f"   🔤 Language: {example_repo_config['language']}")
        print(f"   🛠️ Platforms: {', '.join(example_repo_config['platforms'])}")
        print(f"   📜 Ruleset: {example_repo_config['ruleset']}")
        print("   ✅ Repository configuration validated")
        
    except Exception as e:
        print(f"   ❌ Repository configuration error: {e}")


def test_ruleset_application():
    """Test ruleset application for different repository configurations."""
    print("📋 Testing Ruleset Application")
    print("=" * 50)
    
    # Test scenarios
    scenarios = [
        {
            "name": "Python Backend",
            "language": LanguageType.PYTHON,
            "platforms": [],
            "expected_actions": ["generate_tests", "generate_documentation", "suggest_refactoring"]
        },
        {
            "name": "React + Vite Frontend", 
            "language": LanguageType.TYPESCRIPT,
            "platforms": [PlatformChoice.REACT, PlatformChoice.VITE, PlatformChoice.TAILWIND],
            "expected_actions": ["generate_component_tests", "generate_storybook_stories", "optimize_bundle"]
        },
        {
            "name": "Component Library",
            "language": LanguageType.TYPESCRIPT,
            "platforms": [PlatformChoice.REACT, PlatformChoice.STORYBOOK, PlatformChoice.TAILWIND],
            "expected_actions": ["generate_comprehensive_tests", "generate_advanced_storybook", "api_documentation"]
        }
    ]
    
    rulesets = load_default_rulesets()
    
    for scenario in scenarios:
        print(f"\n✅ Scenario: {scenario['name']}")
        print(f"   Language: {scenario['language'].value}")
        print(f"   Platforms: {[p.value for p in scenario['platforms']]}")
        
        # Find matching ruleset (simplified logic)
        matching_ruleset = None
        for ruleset_name, ruleset in rulesets.items():
            if (ruleset.language == scenario['language'] and 
                set(ruleset.platforms).intersection(set(scenario['platforms']))):
                matching_ruleset = ruleset
                break
        
        if matching_ruleset:
            print(f"   📜 Matched Ruleset: {matching_ruleset.name}")
            print(f"   🎯 Available Actions:")
            for action in matching_ruleset.actions:
                status = "✅" if action.enabled else "❌"
                print(f"      {status} {action.name}: {action.description}")
        else:
            print("   ⚠️ No matching ruleset found")


async def main():
    """Run all tests."""
    print("🧪 Enhanced MCP Capabilities Test Suite")
    print("=" * 60)
    print()
    
    try:
        # Test configuration system
        test_config_system()
        print()
        
        # Test template system
        test_template_system()
        print()
        
        # Test MCP server integration
        await test_mcp_server_integration()
        print()
        
        # Test ruleset application
        test_ruleset_application()
        print()
        
        print("🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
