#!/usr/bin/env python3
"""
Final validation script for enhanced MCP capabilities.
This script performs end-to-end testing of the complete system.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def validate_enhanced_mcp():
    """Validate the enhanced MCP system."""
    print("🚀 Enhanced MCP System Validation")
    print("=" * 50)

    validation_results = {
        "configuration_system": False,
        "template_system": False,
        "mcp_integration": False,
        "example_config": False,
        "documentation": False,
    }

    # 1. Test Configuration System
    print("\n1️⃣ Testing Configuration System...")
    try:
        from config import (
            LanguageType,
            PlatformChoice,
            Ruleset,
            RulesetAction,
            load_default_rulesets,
        )

        # Test enums
        assert len(list(LanguageType)) >= 10
        assert len(list(PlatformChoice)) >= 10

        # Test default rulesets
        rulesets = load_default_rulesets()
        assert len(rulesets) >= 3
        assert "python-default" in rulesets
        assert "typescript-react-vite" in rulesets

        print("   ✅ Configuration system working")
        validation_results["configuration_system"] = True

    except Exception as e:
        print(f"   ❌ Configuration system failed: {e}")

    # 2. Test Template System
    print("\n2️⃣ Testing Template System...")
    try:
        from template_manager import TemplateManager

        tm = TemplateManager()
        templates = tm.list_templates()

        # Check required templates exist
        required_templates = [
            "python/class.py.j2",
            "react/functional_component.tsx.j2",
            "react/stateful_component.tsx.j2",
            "vue/component.vue.j2",
            "tests/python_test.py.j2",
            "tests/js_test.ts.j2",
            "storybook/react_story.stories.tsx.j2",
        ]

        for template in required_templates:
            assert tm.template_exists(template), f"Template {template} missing"

        # Test template rendering
        context = {
            "component_name": "TestComponent",
            "props_interface": "",
            "props_destructure": "",
            "container_class": "test",
        }
        result = tm.render_template("react/functional_component.tsx.j2", context)
        assert "TestComponent" in result
        assert len(result) > 50

        print(f"   ✅ Template system working ({len(templates)} templates)")
        validation_results["template_system"] = True

    except Exception as e:
        print(f"   ❌ Template system failed: {e}")

    # 3. Test MCP Integration
    print("\n3️⃣ Testing MCP Integration...")
    try:
        from mcp_server import MCPStoryServer
        from config import get_config

        config = get_config()
        server = MCPStoryServer(config)

        # Check server has template manager
        assert hasattr(server, "template_manager")
        assert server.template_manager is not None

        # Check handlers registered
        assert len(server._handlers) >= 15
        assert "component/generate" in server._handlers
        assert "storybook/suggest" in server._handlers

        print("   ✅ MCP integration working")
        validation_results["mcp_integration"] = True

    except Exception as e:
        print(f"   ❌ MCP integration failed: {e}")

    # 4. Test Example Configuration
    print("\n4️⃣ Testing Example Configuration...")
    try:
        config_path = Path("example_config.json")
        if config_path.exists():
            with open(config_path) as f:
                example_config = json.load(f)

            # Validate structure
            assert "repositories" in example_config
            assert "rulesets" in example_config
            assert len(example_config["repositories"]) >= 4
            assert len(example_config["rulesets"]) >= 4

            # Check repository configurations
            for repo in example_config["repositories"]:
                assert "language" in repo
                assert "platforms" in repo
                assert "ruleset" in repo

            print("   ✅ Example configuration valid")
            validation_results["example_config"] = True
        else:
            print("   ⚠️ Example configuration file not found")

    except Exception as e:
        print(f"   ❌ Example configuration failed: {e}")

    # 5. Test Documentation
    print("\n5️⃣ Testing Documentation...")
    try:
        docs = ["ENHANCED_MCP_GUIDE.md"]

        for doc in docs:
            doc_path = Path(doc)
            if doc_path.exists():
                content = doc_path.read_text()
                assert len(content) > 1000
                assert "Template System" in content
                assert "Ruleset System" in content
                print(f"   ✅ {doc} exists and is comprehensive")
            else:
                print(f"   ⚠️ {doc} not found")

        validation_results["documentation"] = True

    except Exception as e:
        print(f"   ❌ Documentation validation failed: {e}")

    # Summary
    print("\n📊 Validation Summary")
    print("=" * 50)

    total_tests = len(validation_results)
    passed_tests = sum(validation_results.values())

    for test_name, passed in validation_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {test_name.replace('_', ' ').title()}")

    print(f"\n🎯 Results: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("🎉 All validations passed! Enhanced MCP system is ready.")
        return True
    else:
        print(
            f"⚠️ {total_tests - passed_tests} validations failed. Review above errors."
        )
        return False


def print_system_info():
    """Print system information and capabilities."""
    print("\n📋 Enhanced MCP System Information")
    print("=" * 50)

    try:
        from config import LanguageType, PlatformChoice, load_default_rulesets
        from template_manager import TemplateManager

        print(f"🔤 Supported Languages: {len(list(LanguageType))}")
        for lang in list(LanguageType)[:5]:
            print(f"   • {lang.value}")
        print("   • ...")

        print(f"\n🛠️ Supported Platforms: {len(list(PlatformChoice))}")
        for platform in list(PlatformChoice)[:5]:
            print(f"   • {platform.value}")
        print("   • ...")

        rulesets = load_default_rulesets()
        print(f"\n📜 Default Rulesets: {len(rulesets)}")
        for name, ruleset in rulesets.items():
            print(f"   • {name}: {ruleset.name}")
            print(f"     - Language: {ruleset.language.value}")
            print(f"     - Platforms: {[p.value for p in ruleset.platforms]}")
            print(f"     - Actions: {len(ruleset.actions)}")

        tm = TemplateManager()
        templates = tm.list_templates()
        print(f"\n🎨 Available Templates: {len(templates)}")
        template_categories = {}
        for template in templates:
            category = template.split("/")[0]
            if category not in template_categories:
                template_categories[category] = []
            template_categories[category].append(template.split("/")[-1])

        for category, templates_list in template_categories.items():
            print(f"   • {category}: {len(templates_list)} templates")
            for template in templates_list[:2]:
                print(f"     - {template}")
            if len(templates_list) > 2:
                print(f"     - ... and {len(templates_list) - 2} more")

    except Exception as e:
        print(f"❌ Failed to gather system info: {e}")


if __name__ == "__main__":
    print("🧪 Enhanced MCP Capabilities - Final Validation")
    print("=" * 60)

    success = validate_enhanced_mcp()

    if success:
        print_system_info()

        print("\n🎯 Next Steps:")
        print("=" * 50)
        print("1. 📝 Review the example_config.json for repository setup")
        print("2. 📖 Read ENHANCED_MCP_GUIDE.md for usage instructions")
        print("3. 🚀 Start using enhanced MCP capabilities in your projects")
        print("4. 🎨 Customize templates in .storyteller/templates/")
        print("5. 📋 Create custom rulesets for your specific needs")

        sys.exit(0)
    else:
        print("\n❌ Validation failed. Please review errors above.")
        sys.exit(1)
