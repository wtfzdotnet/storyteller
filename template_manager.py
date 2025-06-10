"""Template management system for code generation."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, Template


class TemplateManager:
    """Manages Jinja2 templates for code generation."""

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize the template manager."""
        # Use provided template dir or create default
        if template_dir is None:
            template_dir = Path(".storyteller/templates")

        self.template_dir = template_dir
        self._ensure_template_directories()

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(
                [
                    str(self.template_dir),
                    str(self.template_dir / "components"),
                    str(self.template_dir / "tests"),
                    str(self.template_dir / "storybook"),
                    str(self.template_dir / "python"),
                    str(self.template_dir / "typescript"),
                    str(self.template_dir / "react"),
                    str(self.template_dir / "vue"),
                ]
            ),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Create default templates if they don't exist
        self._create_default_templates()

    def _ensure_template_directories(self):
        """Ensure all template directories exist."""
        directories = [
            self.template_dir,
            self.template_dir / "components",
            self.template_dir / "tests",
            self.template_dir / "storybook",
            self.template_dir / "python",
            self.template_dir / "typescript",
            self.template_dir / "react",
            self.template_dir / "vue",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Create default templates if they don't exist
        self._create_default_templates()

    def _create_default_templates(self):
        """Create default template files if they don't exist."""
        default_templates = {
            # Python test templates
            "tests/python_test.py.j2": """\"\"\"Test module for {{ module_name }}.\"\"\"

import pytest
{% if imports %}
{% for import_line in imports %}
{{ import_line }}
{% endfor %}
{% endif %}


class Test{{ class_name }}:
    \"\"\"Test class for {{ class_name }}.\"\"\"

    def setup_method(self):
        \"\"\"Set up test fixtures before each test method.\"\"\"
        pass

    def teardown_method(self):
        \"\"\"Clean up after each test method.\"\"\"
        pass
{% if test_methods %}

{% for method in test_methods %}
    def test_{{ method.name }}(self):
        \"\"\"Test {{ method.description }}.\"\"\"
        # Arrange
        {{ method.arrange | indent(8) }}
        
        # Act
        {{ method.act | indent(8) }}
        
        # Assert
        {{ method.assert | indent(8) }}
{% endfor %}
{% endif %}
""",
            # JavaScript/TypeScript test templates
            "tests/js_test.ts.j2": """/**
 * Test module for {{ module_name }}
 */

{% if framework == 'jest' %}
import { render, screen } from '@testing-library/react';
{% elif framework == 'vitest' %}
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
{% endif %}
{% if imports %}
{% for import_line in imports %}
{{ import_line }}
{% endfor %}
{% endif %}

describe('{{ component_name }}', () => {
{% if test_cases %}
{% for test in test_cases %}
  it('{{ test.description }}', () => {
    {{ test.code | indent(4) }}
  });

{% endfor %}
{% endif %}
});
""",
            # React component templates
            "react/functional_component.tsx.j2": """{% if props_interface %}{{ props_interface }}

{% endif %}const {{ component_name }} = ({{ props_destructure }}) => {
  return (
    <div className="{{ container_class }}">
      <h1>{{ component_name }}</h1>
      {/* TODO: Implement component content */}
    </div>
  );
};

export default {{ component_name }};
""",
            "react/stateful_component.tsx.j2": """{% if props_interface %}{{ props_interface }}

{% endif %}import { useState } from 'react';

const {{ component_name }} = ({{ props_destructure }}) => {
  {% if state_variables %}
  {% for var in state_variables %}
  const [{{ var.name }}, set{{ var.name | title }}] = useState{{ var.type_annotation }}({{ var.default_value }});
  {% endfor %}
  {% endif %}

  return (
    <div className="{{ container_class }}">
      <h1>{{ component_name }}</h1>
      {/* TODO: Implement component content */}
    </div>
  );
};

export default {{ component_name }};
""",
            # Vue component templates
            "vue/component.vue.j2": """<template>
  <div class="{{ container_class }}">
    <h1>{{ component_name }}</h1>
    <!-- TODO: Implement component template -->
  </div>
</template>

<script lang="ts">
import { defineComponent{% if has_props %}, PropType{% endif %} } from 'vue';

export default defineComponent({
  name: '{{ component_name }}',
{% if props %}
  props: {
{% for prop in props %}
    {{ prop.name }}: {
      type: {{ prop.type }} as PropType<{{ prop.type_name }}>,
{% if prop.required %}
      required: true,
{% else %}
      default: {{ prop.default }},
{% endif %}
    },
{% endfor %}
  },
{% endif %}
{% if has_data %}
  data() {
    return {
{% for data_item in data %}
      {{ data_item.name }}: {{ data_item.default }},
{% endfor %}
    };
  },
{% endif %}
{% if methods %}
  methods: {
{% for method in methods %}
    {{ method.name }}({{ method.params }}) {
      // TODO: Implement {{ method.name }}
    },
{% endfor %}
  },
{% endif %}
});
</script>

<style scoped>
.{{ container_class }} {
  /* TODO: Add component styles */
}
</style>
""",
            # Python class templates
            "python/class.py.j2": """\"\"\"{{ description }}.\"\"\"

{% if imports %}
{% for import_line in imports %}
{{ import_line }}
{% endfor %}

{% endif %}
class {{ class_name }}:
    \"\"\"{{ class_description }}.\"\"\"

    def __init__(self{% if init_params %}, {{ init_params }}{% endif %}):
        \"\"\"Initialize the {{ class_name }}.
        
{% if init_docstring %}
        {{ init_docstring }}
{% endif %}
        \"\"\"
{% if attributes %}
{% for attr in attributes %}
        self.{{ attr.name }} = {{ attr.value }}
{% endfor %}
{% endif %}
{% if methods %}

{% for method in methods %}
    def {{ method.name }}(self{% if method.params %}, {{ method.params }}{% endif %}):
        \"\"\"{{ method.description }}.\"\"\"
        {{ method.body | indent(8) }}
{% endfor %}
{% endif %}
""",
            # Storybook story templates
            "storybook/react_story.stories.tsx.j2": """import type { Meta, StoryObj } from '@storybook/react';
import {{ component_name }} from './{{ component_file }}';

const meta: Meta<typeof {{ component_name }}> = {
  title: '{{ story_title }}',
  component: {{ component_name }},
  parameters: {
    layout: 'centered',
  },
{% if arg_types %}
  argTypes: {
{% for arg in arg_types %}
    {{ arg.name }}: {
      control: '{{ arg.control }}',
{% if arg.description %}
      description: '{{ arg.description }}',
{% endif %}
    },
{% endfor %}
  },
{% endif %}
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
{% if default_args %}
  args: {
{% for arg, value in default_args.items() %}
    {{ arg }}: {{ value }},
{% endfor %}
  },
{% endif %}
};

{% if additional_stories %}
{% for story in additional_stories %}
export const {{ story.name }}: Story = {
{% if story.args %}
  args: {
{% for arg, value in story.args.items() %}
    {{ arg }}: {{ value }},
{% endfor %}
  },
{% endif %}
};

{% endfor %}
{% endif %}
""",
        }

        # Create template files
        for template_path, content in default_templates.items():
            full_path = self.template_dir / template_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            if not full_path.exists():
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context."""
        try:
            template = self.env.get_template(template_name)
            return template.render(context)
        except Exception as e:
            raise ValueError(f"Failed to render template {template_name}: {e}")

    def list_templates(self, category: Optional[str] = None) -> List[str]:
        """List available templates, optionally filtered by category."""
        templates = []

        search_dirs = [self.template_dir]
        if category:
            category_dir = self.template_dir / category
            if category_dir.exists():
                search_dirs = [category_dir]

        for search_dir in search_dirs:
            for template_file in search_dir.rglob("*.j2"):
                relative_path = template_file.relative_to(self.template_dir)
                templates.append(str(relative_path))

        return sorted(templates)

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists."""
        template_path = self.template_dir / template_name
        return template_path.exists()

    def get_template_context_schema(self, template_name: str) -> Dict[str, Any]:
        """Get the expected context schema for a template."""
        # This is a simplified schema - in a full implementation,
        # you might parse the template to extract variable names
        schemas = {
            "tests/python_test.py.j2": {
                "module_name": "str",
                "class_name": "str",
                "imports": "List[str]",
                "test_methods": "List[TestMethod]",
            },
            "tests/js_test.ts.j2": {
                "module_name": "str",
                "component_name": "str",
                "framework": "str",
                "imports": "List[str]",
                "test_cases": "List[TestCase]",
            },
            "react/functional_component.tsx.j2": {
                "component_name": "str",
                "props_interface": "str",
                "props_destructure": "str",
                "container_class": "str",
            },
            "react/stateful_component.tsx.j2": {
                "component_name": "str",
                "props_interface": "str",
                "props_destructure": "str",
                "container_class": "str",
                "state_variables": "List[StateVariable]",
            },
            "vue/component.vue.j2": {
                "component_name": "str",
                "container_class": "str",
                "props": "List[Prop]",
                "has_props": "bool",
                "data": "List[DataItem]",
                "has_data": "bool",
                "methods": "List[Method]",
            },
            "python/class.py.j2": {
                "class_name": "str",
                "description": "str",
                "class_description": "str",
                "imports": "List[str]",
                "init_params": "str",
                "init_docstring": "str",
                "attributes": "List[Attribute]",
                "methods": "List[Method]",
            },
            "storybook/react_story.stories.tsx.j2": {
                "component_name": "str",
                "component_file": "str",
                "story_title": "str",
                "arg_types": "List[ArgType]",
                "default_args": "Dict[str, Any]",
                "additional_stories": "List[Story]",
            },
        }

        return schemas.get(template_name, {})


# Global template manager instance
_template_manager = None


def get_template_manager() -> TemplateManager:
    """Get the global template manager instance."""
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager


def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Convenience function to render a template."""
    manager = get_template_manager()
    return manager.render_template(template_name, context)


def list_templates(category: Optional[str] = None) -> List[str]:
    """Convenience function to list templates."""
    manager = get_template_manager()
    return manager.list_templates(category)
