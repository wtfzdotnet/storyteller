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
                    str(self.template_dir / "go"),
                    str(self.template_dir / "gokit"),
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
            self.template_dir / "go",
            self.template_dir / "gokit",
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
            # Go kit templates
            "go/service.go.j2": """// Package {{ package_name }} provides {{ service_description }}.
package {{ package_name }}

import (
	"context"
{% if imports %}
{% for import_line in imports %}
	"{{ import_line }}"
{% endfor %}
{% endif %}
)

// {{ service_name }}Service represents the {{ service_name }} service interface.
type {{ service_name }}Service interface {
{% for method in methods %}
	{{ method.name }}(ctx context.Context{% for param in method.params %}, {{ param.name }} {{ param.type }}{% endfor %}) ({% for result in method.results %}{{ result.type }}{% if not loop.last %}, {% endif %}{% endfor %})
{% endfor %}
}

// {{ service_name.lower() }}Service is a concrete implementation of {{ service_name }}Service.
type {{ service_name.lower() }}Service struct {
{% for field in fields %}
	{{ field.name }} {{ field.type }}
{% endfor %}
}

// New{{ service_name }}Service creates a new {{ service_name }} service.
func New{{ service_name }}Service({% for field in fields %}{{ field.name }} {{ field.type }}{% if not loop.last %}, {% endif %}{% endfor %}) {{ service_name }}Service {
	return &{{ service_name.lower() }}Service{
{% for field in fields %}
		{{ field.name }}: {{ field.name }},
{% endfor %}
	}
}

{% for method in methods %}
// {{ method.name }} {{ method.description }}.
func (s *{{ service_name.lower() }}Service) {{ method.name }}(ctx context.Context{% for param in method.params %}, {{ param.name }} {{ param.type }}{% endfor %}) ({% for result in method.results %}{{ result.type }}{% if not loop.last %}, {% endif %}{% endfor %}) {
	// TODO: Implement {{ method.name }}
{% if method.results|length == 1 %}
	return {{ method.default_return }}
{% else %}
	return {{ method.default_returns|join(', ') }}
{% endif %}
}

{% endfor %}
""",
            "gokit/endpoint.go.j2": """// Package {{ package_name }} provides endpoints for {{ service_name }} service.
package {{ package_name }}

import (
	"context"

	"github.com/go-kit/kit/endpoint"
{% if imports %}
{% for import_line in imports %}
	"{{ import_line }}"
{% endfor %}
{% endif %}
)

// Endpoints collects all of the endpoints that compose the {{ service_name }} service.
type Endpoints struct {
{% for method in methods %}
	{{ method.name }}Endpoint endpoint.Endpoint
{% endfor %}
}

// New{{ service_name }}Endpoints returns an Endpoints struct that wraps the provided service.
func New{{ service_name }}Endpoints(svc {{ service_name }}Service) Endpoints {
	return Endpoints{
{% for method in methods %}
		{{ method.name }}Endpoint: make{{ method.name }}Endpoint(svc),
{% endfor %}
	}
}

{% for method in methods %}
// {{ method.name }}Request collects the request parameters for the {{ method.name }} method.
type {{ method.name }}Request struct {
{% for param in method.params %}
	{{ param.name|title }} {{ param.type }} `json:"{{ param.name }}"`
{% endfor %}
}

// {{ method.name }}Response collects the response parameters for the {{ method.name }} method.
type {{ method.name }}Response struct {
{% for result in method.results %}
	{{ result.name|title }} {{ result.type }} `json:"{{ result.name }}"`
{% endfor %}
}

// make{{ method.name }}Endpoint creates an endpoint for the {{ method.name }} method.
func make{{ method.name }}Endpoint(svc {{ service_name }}Service) endpoint.Endpoint {
	return func(ctx context.Context, request interface{}) (interface{}, error) {
		req := request.({{ method.name }}Request)
		{% if method.results|length == 1 %}result, err{% else %}{% for result in method.results %}{{ result.name }}{% if not loop.last %}, {% endif %}{% endfor %}, err{% endif %} := svc.{{ method.name }}(ctx{% for param in method.params %}, req.{{ param.name|title }}{% endfor %})
		if err != nil {
			return {{ method.name }}Response{}, err
		}
		return {{ method.name }}Response{
{% for result in method.results %}
			{{ result.name|title }}: {{ result.name }},
{% endfor %}
		}, nil
	}
}

{% endfor %}
""",
            "gokit/transport.go.j2": """// Package {{ package_name }} provides HTTP transport for {{ service_name }} service.
package {{ package_name }}

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/go-kit/kit/log"
	"github.com/go-kit/kit/transport/http"
	"github.com/gorilla/mux"
{% if imports %}
{% for import_line in imports %}
	"{{ import_line }}"
{% endfor %}
{% endif %}
)

// New{{ service_name }}HTTPHandler returns an HTTP handler that makes a set of endpoints
// available on predefined paths.
func New{{ service_name }}HTTPHandler(endpoints Endpoints, logger log.Logger) http.Handler {
	r := mux.NewRouter()
{% for method in methods %}
	r.Methods("{{ method.http_method|default('POST') }}").Path("{{ method.path|default('/' + method.name.lower()) }}").Handler(http.NewServer(
		endpoints.{{ method.name }}Endpoint,
		decode{{ method.name }}Request,
		encodeResponse,
	))
{% endfor %}

	return r
}

{% for method in methods %}
// decode{{ method.name }}Request is a transport/http.DecodeRequestFunc that decodes a
// JSON-encoded request from the HTTP request body.
func decode{{ method.name }}Request(_ context.Context, r *http.Request) (interface{}, error) {
	var request {{ method.name }}Request
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		return nil, err
	}
	return request, nil
}

{% endfor %}

// encodeResponse is a transport/http.EncodeResponseFunc that encodes
// the response as JSON to the response writer.
func encodeResponse(_ context.Context, w http.ResponseWriter, response interface{}) error {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	return json.NewEncoder(w).Encode(response)
}

// encodeError encodes errors from business-logic.
func encodeError(_ context.Context, err error, w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"error": err.Error(),
	})
}
""",
            "go/struct.go.j2": """// Package {{ package_name }} provides {{ struct_description }}.
package {{ package_name }}

{% if imports %}
import (
{% for import_line in imports %}
	"{{ import_line }}"
{% endfor %}
)

{% endif %}
// {{ struct_name }} represents {{ struct_description }}.
type {{ struct_name }} struct {
{% for field in fields %}
	{{ field.name }} {{ field.type }}{% if field.tag %} `{{ field.tag }}`{% endif %}{% if field.comment %} // {{ field.comment }}{% endif %}
{% endfor %}
}

{% if constructor %}
// New{{ struct_name }} creates a new {{ struct_name }} instance.
func New{{ struct_name }}({% for field in constructor.params %}{{ field.name }} {{ field.type }}{% if not loop.last %}, {% endif %}{% endfor %}) *{{ struct_name }} {
	return &{{ struct_name }}{
{% for field in constructor.params %}
		{{ field.name|title }}: {{ field.name }},
{% endfor %}
	}
}
{% endif %}

{% for method in methods %}
// {{ method.name }} {{ method.description }}.
func ({{ receiver_name }} *{{ struct_name }}) {{ method.name }}({% for param in method.params %}{{ param.name }} {{ param.type }}{% if not loop.last %}, {% endif %}{% endfor %}){% if method.results %} ({% for result in method.results %}{{ result.type }}{% if not loop.last %}, {% endif %}{% endfor %}){% endif %} {
	// TODO: Implement {{ method.name }}
{% if method.default_return %}
	return {{ method.default_return }}
{% endif %}
}

{% endfor %}
""",
            "tests/go_test.go.j2": """// Package {{ package_name }} provides tests for {{ module_name }}.
package {{ package_name }}

import (
	"testing"
{% if imports %}
{% for import_line in imports %}
	"{{ import_line }}"
{% endfor %}
{% endif %}
)

{% for test in tests %}
// {{ test.name }} tests {{ test.description }}.
func {{ test.name }}(t *testing.T) {
	// Arrange
	{{ test.arrange | indent(4) }}

	// Act
	{{ test.act | indent(4) }}

	// Assert
	{{ test.assert | indent(4) }}
}

{% endfor %}

{% if benchmark_tests %}
{% for benchmark in benchmark_tests %}
// {{ benchmark.name }} benchmarks {{ benchmark.description }}.
func {{ benchmark.name }}(b *testing.B) {
	// Setup
	{{ benchmark.setup | indent(4) }}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		{{ benchmark.operation | indent(8) }}
	}
}

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
