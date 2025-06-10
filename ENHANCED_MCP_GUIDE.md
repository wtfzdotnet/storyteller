# Enhanced MCP Capabilities with Language-Specific Rulesets

This document describes the enhanced Model Context Protocol (MCP) capabilities that have been added to the AI Story Management System, specifically focusing on language-specific repository configuration with rulesets and the migration to Jinja2 templates.

## Overview

The enhanced MCP system provides:

- **Language-Specific Repository Configuration**: Configure repositories with specific programming languages and platform combinations
- **Ruleset System**: Define actions and behaviors based on language/platform combinations  
- **Jinja2 Template Engine**: Maintainable code generation using templates instead of f-strings
- **Enhanced Code Generation**: Support for React, Vue, Python, and test file generation
- **Storybook Integration**: Automatic story generation for component libraries

## Configuration System

### Language Types

The system supports the following programming languages:

```python
class LanguageType(Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript" 
    JAVASCRIPT = "javascript"
    REACT = "react"
    VUE = "vue"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CSHARP = "csharp"
    OTHER = "other"
```

### Platform Choices  

For TypeScript/JavaScript repositories, you can specify platform configurations:

```python
class PlatformChoice(Enum):
    REACT = "react"
    TAILWIND = "tailwind"
    VITE = "vite"
    NEXT_JS = "nextjs"
    WEBPACK = "webpack"
    STORYBOOK = "storybook"
    VITEST = "vitest"
    JEST = "jest"
    CYPRESS = "cypress"
    PLAYWRIGHT = "playwright"
```

### Repository Configuration

Configure repositories in your `config.json`:

```json
{
  "repositories": [
    {
      "name": "recipe-backend",
      "url": "https://github.com/recipeauthority/recipe-backend",
      "language": "python",
      "platforms": [],
      "ruleset": "python_default",
      "description": "Python Flask backend"
    },
    {
      "name": "recipe-frontend-react", 
      "url": "https://github.com/recipeauthority/recipe-frontend-react",
      "language": "typescript",
      "platforms": ["react", "tailwind", "vite"],
      "ruleset": "typescript_react_vite",
      "description": "React frontend with TypeScript, Tailwind CSS, and Vite"
    }
  ]
}
```

## Ruleset System

### Default Rulesets

The system provides several default rulesets:

#### 1. Python Default (`python_default`)

For Python repositories:

```json
{
  "actions": [
    {
      "name": "generate_tests",
      "description": "Generate pytest test files",
      "parameters": {
        "test_framework": "pytest",
        "coverage_threshold": 80,
        "include_docstring_tests": true
      }
    },
    {
      "name": "generate_documentation", 
      "description": "Generate docstrings and README updates",
      "parameters": {
        "style": "google",
        "include_examples": true
      }
    }
  ]
}
```

#### 2. TypeScript React with Vite (`typescript_react_vite`)

For modern React development:

```json
{
  "actions": [
    {
      "name": "generate_component_tests",
      "description": "Generate React Testing Library tests",
      "parameters": {
        "test_framework": "vitest",
        "include_accessibility_tests": true
      }
    },
    {
      "name": "generate_storybook_stories",
      "description": "Generate Storybook stories for components",
      "parameters": {
        "include_controls": true,
        "include_accessibility_addon": true
      }
    },
    {
      "name": "optimize_bundle",
      "description": "Suggest Vite configuration optimizations"
    }
  ]
}
```

#### 3. Component Library (`component_library`)

For shared component libraries:

```json
{
  "actions": [
    {
      "name": "generate_comprehensive_tests",
      "description": "Generate extensive test coverage",
      "parameters": {
        "coverage_threshold": 95,
        "include_visual_regression_tests": true
      }
    },
    {
      "name": "generate_advanced_storybook",
      "description": "Generate comprehensive Storybook documentation"
    },
    {
      "name": "api_documentation",
      "description": "Generate API documentation"
    }
  ]
}
```

### Custom Rulesets

You can define custom rulesets in your configuration:

```json
{
  "rulesets": {
    "my_custom_ruleset": {
      "name": "My Custom Ruleset",
      "description": "Custom development practices",
      "language": "typescript",
      "platforms": ["react", "storybook"],
      "actions": [
        {
          "name": "custom_action",
          "description": "My custom action",
          "enabled": true,
          "parameters": {
            "custom_param": "value"
          }
        }
      ]
    }
  }
}
```

## Template System

### Template Directory Structure

Templates are organized in the `.storyteller/templates/` directory:

```
.storyteller/templates/
├── python/
│   └── class.py.j2
├── react/
│   ├── functional_component.tsx.j2
│   └── stateful_component.tsx.j2
├── vue/
│   └── component.vue.j2
├── tests/
│   ├── python_test.py.j2
│   └── js_test.ts.j2
└── storybook/
    └── react_story.stories.tsx.j2
```

### Available Templates

#### 1. Python Class Template (`python/class.py.j2`)

Generates Python classes with proper typing and documentation:

```python
# Context variables:
{
    "class_name": "ExampleService",
    "class_description": "Service description", 
    "imports": ["from typing import Optional"],
    "init_params": [{"name": "config", "type_annotation": "dict"}],
    "attributes": [{"name": "logger", "value": "logging.getLogger(__name__)"}],
    "methods": [{"name": "process", "params": [], "return_type": "str"}]
}
```

#### 2. React Functional Component (`react/functional_component.tsx.j2`)

Generates React functional components with TypeScript:

```javascript
// Context variables:
{
    "component_name": "UserProfile",
    "props_interface": "UserProfileProps", 
    "props_destructure": "{ name, email }",
    "container_class": "user-profile"
}
```

#### 3. React Stateful Component (`react/stateful_component.tsx.j2`)

Generates React components with state management:

```javascript
// Context variables:
{
    "component_name": "ContactForm",
    "props_interface": "ContactFormProps",
    "state_interface": "ContactFormState",
    "initial_state": [{"name": "email", "value": "''"}],
    "methods": [{"name": "handleSubmit", "params": ["event"]}]
}
```

#### 4. Test Templates

- **Python Tests** (`tests/python_test.py.j2`): Generates pytest test classes
- **JavaScript Tests** (`tests/js_test.ts.j2`): Generates Jest/Vitest tests

#### 5. Storybook Template (`storybook/react_story.stories.tsx.j2`)

Generates comprehensive Storybook stories:

```javascript
// Context variables:
{
    "component_name": "Button",
    "component_file": "Button",
    "story_title": "Components/Button",
    "arg_types": [{"name": "variant", "control": "select"}],
    "default_args": {"variant": "primary"},
    "additional_stories": [{"name": "Secondary", "args": {}}]
}
```

### Using Templates

The `TemplateManager` class provides methods for working with templates:

```python
from template_manager import TemplateManager

# Initialize template manager  
template_manager = TemplateManager()

# List available templates
templates = template_manager.list_templates()

# Render a template
context = {"component_name": "MyComponent"}
code = template_manager.render_template("react/functional_component.tsx.j2", context)

# Validate template exists
if template_manager.template_exists("python/class.py.j2"):
    # Use template
    pass
```

## MCP Server Integration

### Enhanced Capabilities

The MCP server now provides enhanced capabilities:

#### 1. Component Generation

Generate components with language-specific templates:

```json
{
  "method": "component/generate",
  "params": {
    "component_name": "RecipeCard",
    "component_type": "react",
    "template_type": "functional",
    "props": [
      {"name": "title", "type": "string", "required": true},
      {"name": "description", "type": "string", "required": false}
    ]
  }
}
```

#### 2. Test Generation

Generate tests based on repository language and platform:

```json
{
  "method": "test/generate", 
  "params": {
    "component_name": "UserService",
    "test_type": "unit",
    "framework": "pytest"
  }
}
```

#### 3. Storybook Generation

Generate Storybook stories for component documentation:

```json
{
  "method": "storybook/suggest",
  "params": {
    "repository_path": "/path/to/repo",
    "component_patterns": ["**/*.tsx", "**/*.jsx"]
  }
}
```

### Repository-Aware Generation

The MCP server uses repository configuration to determine:

- Which templates to use
- What testing frameworks to target  
- Which platforms to optimize for
- What additional files to generate

## Usage Examples

### 1. Setting Up a TypeScript React Project

```json
{
  "name": "my-react-app",
  "language": "typescript",
  "platforms": ["react", "vite", "tailwind", "storybook"],
  "ruleset": "typescript_react_vite"
}
```

This configuration will:
- Generate React components with TypeScript
- Create Vitest tests with accessibility checks
- Generate Storybook stories with controls
- Suggest Vite bundle optimizations
- Recommend Tailwind CSS patterns

### 2. Setting Up a Python API Project

```json
{
  "name": "my-python-api", 
  "language": "python",
  "platforms": [],
  "ruleset": "python_default"
}
```

This configuration will:
- Generate Python classes with type hints
- Create pytest tests with docstring examples
- Generate documentation with Google-style docstrings
- Suggest refactoring opportunities

### 3. Setting Up a Component Library

```json
{
  "name": "my-component-library",
  "language": "typescript",
  "platforms": ["react", "storybook", "vitest", "tailwind"],
  "ruleset": "component_library"
}
```

This configuration will:
- Generate comprehensive test coverage (95%+)
- Create advanced Storybook documentation
- Generate API documentation
- Include visual regression tests
- Validate design system integration

## Testing

Run the comprehensive test suite:

```bash
python test_enhanced_mcp.py
```

This will test:
- Configuration system functionality
- Template rendering
- MCP server integration
- Ruleset application
- Repository configuration validation

## Migration Guide

### From F-String Generation

The system has been migrated from Python f-string code generation to Jinja2 templates:

**Before:**
```python
def generate_component(name):
    return f"""
    function {name}() {{
        return <div>{name}</div>;
    }}
    """
```

**After:**
```python
def generate_component(name):
    context = {"component_name": name}
    return self.template_manager.render_template("react/functional_component.tsx.j2", context)
```

### Benefits

1. **Maintainability**: Templates are easier to modify and version
2. **Consistency**: Standardized formatting and structure
3. **Extensibility**: Easy to add new template variants
4. **Debugging**: Better error messages and validation
5. **Collaboration**: Non-developers can contribute to templates

## Advanced Configuration

### Environment-Specific Rulesets

Configure different rulesets for different environments:

```json
{
  "environments": {
    "development": {
      "ruleset_overrides": {
        "generate_tests": {"coverage_threshold": 70}
      }
    },
    "production": {
      "ruleset_overrides": {
        "generate_tests": {"coverage_threshold": 90}
      }
    }
  }
}
```

### Dynamic Ruleset Selection

Rulesets can be selected dynamically based on:
- Repository language and platforms
- File patterns and project structure
- Environment variables
- Custom logic in configuration

## Troubleshooting

### Common Issues

1. **Template Not Found**: Ensure template files exist in `.storyteller/templates/`
2. **Context Variables Missing**: Check template context matches requirements
3. **Ruleset Not Applied**: Verify language/platform configuration matches ruleset criteria
4. **Import Errors**: Run `pip install -r requirements.txt` to install dependencies

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

### Adding New Templates

1. Create template file in appropriate subdirectory
2. Follow Jinja2 syntax and conventions
3. Document required context variables
4. Add tests for template rendering
5. Update documentation

### Adding New Rulesets

1. Define ruleset in default rulesets or configuration
2. Specify language and platform requirements
3. Define actions with parameters
4. Test ruleset application logic
5. Document usage examples

For more information, see the [GitHub repository](https://github.com/recipeauthority/storyteller) and join our community discussions.

## Go + Go Kit Backend Support

The enhanced MCP system now includes comprehensive support for Go backends using the Go kit microservice framework.

### Go Kit Templates

#### 1. Go Service Template (`go/service.go.j2`)

Generates Go kit service interfaces and implementations:

```go
// Context variables:
{
    "package_name": "user",
    "service_name": "UserService",
    "service_description": "User management service",
    "imports": ["context", "fmt"],
    "methods": [
        {
            "name": "CreateUser",
            "description": "creates a new user",
            "params": [{"name": "request", "type": "CreateUserRequest"}],
            "results": [{"type": "*User", "name": "user"}, {"type": "error", "name": "err"}],
            "default_returns": ["nil", "nil"]
        }
    ],
    "fields": [{"name": "repo", "type": "UserRepository"}]
}
```

#### 2. Go Struct Template (`go/struct.go.j2`)

Generates Go structs with JSON tags and methods:

```go
// Context variables:
{
    "package_name": "models",
    "struct_name": "Recipe",
    "struct_description": "represents a recipe entity",
    "fields": [
        {
            "name": "ID",
            "type": "string", 
            "tag": "json:\"id\" db:\"id\"",
            "comment": "Unique identifier"
        }
    ]
}
```

#### 3. Go Kit Endpoint Template (`gokit/endpoint.go.j2`)

Generates Go kit endpoints for HTTP transport:

```go
// Context variables:
{
    "package_name": "endpoints",
    "service_name": "RecipeService",
    "methods": [
        {
            "name": "CreateRecipe",
            "params": [{"name": "Title", "type": "string"}],
            "results": [{"name": "Recipe", "type": "*Recipe"}]
        }
    ]
}
```

#### 4. Go Kit Transport Template (`gokit/transport.go.j2`)

Generates HTTP transport layer with Gorilla Mux:

```go
// Context variables:
{
    "package_name": "transport",
    "service_name": "OrderService",
    "methods": [
        {
            "name": "CreateOrder",
            "http_method": "POST",
            "path": "/orders"
        }
    ]
}
```

#### 5. Go Test Template (`tests/go_test.go.j2`)

Generates Go tests with testify framework:

```go
// Context variables:
{
    "package_name": "recipe_test",
    "tests": [
        {
            "name": "TestCreateRecipe",
            "description": "creating a new recipe",
            "arrange": "service := NewRecipeService(mockRepo)",
            "act": "result, err := service.CreateRecipe(ctx, request)",
            "assert": "assert.NoError(t, err)"
        }
    ]
}
```

### Go Kit Ruleset

The `go-gokit` ruleset provides comprehensive Go kit development support:

```json
{
  "name": "Go with Go Kit",
  "language": "go",
  "platforms": ["gokit", "grpc", "docker"],
  "actions": [
    {
      "name": "service_generation",
      "description": "Generate Go kit service interfaces and implementations",
      "parameters": {
        "framework": "gokit",
        "include_middleware": true,
        "include_metrics": true
      }
    },
    {
      "name": "endpoint_generation",
      "description": "Generate Go kit endpoints for service methods",
      "parameters": {
        "transport": "http",
        "include_validation": true
      }
    },
    {
      "name": "transport_generation",
      "description": "Generate HTTP transport layer",
      "parameters": {
        "router": "gorilla/mux",
        "middleware": ["logging", "cors", "recovery"]
      }
    },
    {
      "name": "test_generation",
      "description": "Generate Go tests with testify",
      "parameters": {
        "framework": "testify",
        "include_benchmarks": true,
        "mock_external_deps": true
      }
    },
    {
      "name": "docker_generation",
      "description": "Generate Dockerfile and docker-compose",
      "parameters": {
        "base_image": "alpine",
        "include_health_check": true
      }
    }
  ]
}
```

### Go Repository Configuration

Configure your Go backend repository:

```json
{
  "name": "recipe-backend-go",
  "url": "https://github.com/recipeauthority/recipe-backend-go",
  "language": "go",
  "platforms": ["gokit", "grpc", "docker"],
  "ruleset": "go-gokit",
  "description": "Go backend with Go kit microservices architecture"
}
```

### MCP Server Go Support

Generate Go components using the MCP server:

```json
{
  "method": "component/generate",
  "params": {
    "component_name": "UserService",
    "component_type": "go",
    "template_type": "service",
    "props": [
      {
        "name": "CreateUser",
        "type": "method",
        "params": [{"name": "request", "type": "CreateUserRequest"}],
        "description": "Creates a new user account"
      }
    ]
  }
}
```

### Go Kit Platform Support

The system supports various Go platforms:

- **gokit**: Go kit microservice framework
- **grpc**: gRPC protocol buffer support
- **gin**: Gin web framework  
- **echo**: Echo web framework
- **fiber**: Fiber web framework
- **docker**: Docker containerization
- **kubernetes**: Kubernetes deployment
- **testify**: Testing framework
- **gorm**: ORM library

### Complete Microservice Generation

Generate a complete Go kit microservice:

1. **Service Interface**: Business logic interface
2. **Endpoints**: HTTP endpoint handlers
3. **Transport**: HTTP transport layer with routing
4. **Models**: Go structs with JSON/DB tags
5. **Tests**: Unit tests with testify and benchmarks
6. **Docker**: Containerization configuration

### Go Kit Best Practices

The templates follow Go kit best practices:

- **Separation of Concerns**: Clear separation between service, endpoint, and transport layers
- **Middleware Support**: Built-in logging, metrics, and recovery middleware
- **Error Handling**: Proper error handling and propagation
- **Testing**: Comprehensive test generation with mocking
- **Documentation**: Generated comments and documentation
- **Type Safety**: Strong typing with interfaces and structs
