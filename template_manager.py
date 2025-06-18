"""Enhanced template management for context-aware code generation."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from jinja2 import Environment, FileSystemLoader, Template
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


class ContextAwareTemplateManager:
    """Enhanced template manager for context-aware story generation."""

    def __init__(self, templates_dir: Optional[Path] = None):
        """Initialize template manager."""
        self.templates_dir = templates_dir or Path(__file__).parent / ".storyteller" / "templates"
        
        if JINJA2_AVAILABLE:
            self.env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                trim_blocks=True,
                lstrip_blocks=True
            )
        else:
            self.env = None

    def render_user_story_template(
        self, 
        repo_type: str, 
        story_content: str,
        repository_context: Optional[Dict[str, Any]] = None,
        cross_repo_insights: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Render a repository-specific user story template with context."""
        
        template_name = f"user_stories/{repo_type}_user_story.md"
        
        # Prepare template context
        context = {
            "story_content": story_content,
            "repository_context": repository_context or {},
            "cross_repo_insights": cross_repo_insights or {},
            **kwargs
        }
        
        # Extract context-aware data
        if repository_context:
            context.update({
                "repo_name": repository_context.get("repository", ""),
                "repo_type": repository_context.get("repo_type", repo_type),
                "key_technologies": repository_context.get("key_technologies", []),
                "dependencies": repository_context.get("dependencies", []),
                "important_files": repository_context.get("important_files", [])
            })
            
        # Generate context-aware acceptance criteria
        context["acceptance_criteria"] = self._generate_context_aware_acceptance_criteria(
            story_content, repo_type, repository_context, cross_repo_insights
        )
        
        # Generate context-aware technical requirements
        context["technical_requirements"] = self._generate_technical_requirements(
            repo_type, repository_context
        )
        
        return self._render_template(template_name, context)

    def _generate_context_aware_acceptance_criteria(
        self,
        story_content: str,
        repo_type: str,
        repository_context: Optional[Dict[str, Any]] = None,
        cross_repo_insights: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate context-aware acceptance criteria based on repository and story context."""
        
        criteria = []
        
        # Base criteria from story content analysis
        if "login" in story_content.lower() or "auth" in story_content.lower():
            if repo_type == "backend":
                criteria.extend([
                    "Authentication endpoint validates credentials",
                    "JWT tokens generated for valid authentication",
                    "Password validation follows security standards"
                ])
            elif repo_type == "frontend":
                criteria.extend([
                    "Login form captures username and password",
                    "Authentication state managed in application",
                    "User redirected appropriately after login"
                ])
                
        elif "search" in story_content.lower():
            if repo_type == "backend":
                criteria.extend([
                    "Search API endpoint accepts query parameters",
                    "Results filtered and paginated appropriately",
                    "Search performance meets requirements"
                ])
            elif repo_type == "frontend":
                criteria.extend([
                    "Search input component captures user queries",
                    "Search results displayed with proper formatting",
                    "Loading states shown during search operations"
                ])

        # Add technology-specific criteria based on repository context
        if repository_context:
            dependencies = repository_context.get("dependencies", [])
            
            # Database-related criteria
            if any(db in dep.lower() for dep in dependencies for db in ["postgres", "mysql", "mongo", "sqlite"]):
                criteria.append("Database operations handle data persistence correctly")
                
            # API framework criteria
            if any(api in dep.lower() for dep in dependencies for api in ["fastapi", "flask", "express", "django"]):
                criteria.append("API endpoints follow REST conventions and return appropriate status codes")
                
            # Frontend framework criteria  
            if any(fe in dep.lower() for dep in dependencies for fe in ["react", "vue", "angular"]):
                criteria.append("Component renders correctly and handles user interactions")
                
        # Add cross-repository criteria
        if cross_repo_insights and cross_repo_insights.get("integration_points"):
            for integration_point in cross_repo_insights["integration_points"]:
                criteria.append(f"Integration with {integration_point} functions correctly")

        return criteria if criteria else [
            "Feature implements core functionality as described",
            "All edge cases are handled appropriately",
            "Performance meets expected standards"
        ]

    def _generate_technical_requirements(
        self, 
        repo_type: str,
        repository_context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate technical requirements based on repository type and context."""
        
        requirements = []
        
        if repo_type == "backend":
            requirements.extend([
                "API endpoint implementation",
                "Business logic development",
                "Data validation and error handling"
            ])
            
            if repository_context:
                dependencies = repository_context.get("dependencies", [])
                
                # Add database requirements
                if any(db in dep.lower() for dep in dependencies for db in ["postgres", "mysql", "mongo"]):
                    requirements.append("Database schema updates and migrations")
                    
                # Add specific framework requirements
                if "fastapi" in [dep.lower() for dep in dependencies]:
                    requirements.extend([
                        "FastAPI route definitions with proper typing",
                        "Pydantic model validation"
                    ])
                    
        elif repo_type == "frontend":
            requirements.extend([
                "User interface component development",
                "State management implementation",
                "User experience optimization"
            ])
            
            if repository_context:
                dependencies = repository_context.get("dependencies", [])
                
                if "react" in [dep.lower() for dep in dependencies]:
                    requirements.extend([
                        "React component development with hooks",
                        "Component testing with appropriate libraries"
                    ])
                    
                if any(style in dep.lower() for dep in dependencies for style in ["styled", "emotion", "tailwind"]):
                    requirements.append("Responsive styling implementation")

        # Add testing requirements
        requirements.extend([
            "Unit tests for core functionality",
            "Integration tests for critical paths"
        ])
        
        return requirements

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context."""
        
        if self.env:
            try:
                template = self.env.get_template(template_name)
                return template.render(**context)
            except Exception as e:
                # Fallback to simple template if Jinja2 fails
                pass
                
        # Simple fallback template rendering
        return self._render_simple_template(template_name, context)

    def _render_simple_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Fallback simple template rendering without Jinja2."""
        
        repo_type = context.get("repo_type", "backend")
        story_content = context.get("story_content", "")
        acceptance_criteria = context.get("acceptance_criteria", [])
        technical_requirements = context.get("technical_requirements", [])
        
        template = f"""# {repo_type.title()} User Story

## User Story
{story_content}

## Acceptance Criteria
{chr(10).join(f"- [ ] {criteria}" for criteria in acceptance_criteria)}

## Technical Requirements
{chr(10).join(f"- {req}" for req in technical_requirements)}

## Target Repository
{context.get("repo_name", repo_type)}

## Context Information
- Repository Type: {repo_type}
- Key Technologies: {", ".join(context.get("key_technologies", []))}
- Dependencies: {", ".join(context.get("dependencies", [])[:5])}
"""

        if context.get("cross_repo_insights"):
            insights = context["cross_repo_insights"]
            template += f"""
## Cross-Repository Considerations
- Shared Technologies: {", ".join(insights.get("shared_languages", []))}
- Integration Points: {", ".join(insights.get("integration_points", []))}
"""

        return template


class TemplateManager:
    """Basic template manager for code generation - maintained for backward compatibility."""

    def __init__(self):
        """Initialize template manager."""
        self.context_aware_manager = ContextAwareTemplateManager()

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context.

        For now, this is a placeholder implementation.
        """
        return f"# Generated from template: {template_name}\n# Context: {context}"
    
    def render_context_aware_story(
        self,
        repo_type: str,
        story_content: str,
        repository_context: Optional[Dict[str, Any]] = None,
        cross_repo_insights: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Render context-aware story using enhanced template manager."""
        return self.context_aware_manager.render_user_story_template(
            repo_type=repo_type,
            story_content=story_content,
            repository_context=repository_context,
            cross_repo_insights=cross_repo_insights,
            **kwargs
        )
