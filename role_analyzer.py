"""Intelligent role assignment based on repository context and story content."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from config import Config
from multi_repo_context import RepositoryContext, RepositoryTypeDetector

logger = logging.getLogger(__name__)


@dataclass
class RoleAssignment:
    """Represents a role assignment with metadata."""

    role_name: str
    confidence_score: float
    assignment_reason: str
    repository_context: Optional[str] = None
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_by: str = "automatic"  # "automatic" or "manual"
    override_reason: Optional[str] = None


@dataclass
class RoleAssignmentResult:
    """Result of role assignment operation."""

    story_id: str
    primary_roles: List[RoleAssignment]
    secondary_roles: List[RoleAssignment]
    suggested_roles: List[RoleAssignment]
    assignment_metadata: Dict[str, Any] = field(default_factory=dict)


class RoleAssignmentEngine:
    """Engine for intelligent role assignment based on repository context."""

    # Mapping of repository types to primary technical roles
    REPO_TYPE_ROLE_MAPPING = {
        "frontend": ["ux-ui-designer", "lead-developer"],
        "backend": ["system-architect", "lead-developer", "security-expert"],
        "mobile": ["ux-ui-designer", "lead-developer"],
        "devops": ["devops-engineer", "security-expert"],
        "documentation": ["documentation-hoarder"],
        "data": ["ai-expert", "system-architect"],
        "storyteller": ["product-owner", "system-architect"],
    }

    # Mapping of technologies/frameworks to specialized roles
    TECHNOLOGY_ROLE_MAPPING = {
        "react": ["ux-ui-designer"],
        "vue": ["ux-ui-designer"],
        "angular": ["ux-ui-designer"],
        "python": ["ai-expert", "lead-developer"],
        "django": ["lead-developer", "security-expert"],
        "flask": ["lead-developer"],
        "fastapi": ["lead-developer", "system-architect"],
        "javascript": ["lead-developer"],
        "typescript": ["lead-developer"],
        "java": ["system-architect", "lead-developer"],
        "spring": ["system-architect", "lead-developer"],
        "docker": ["devops-engineer"],
        "kubernetes": ["devops-engineer"],
        "terraform": ["devops-engineer"],
        "postgresql": ["system-architect"],
        "mongodb": ["system-architect"],
        "redis": ["system-architect"],
        "machine learning": ["ai-expert"],
        "tensorflow": ["ai-expert"],
        "pytorch": ["ai-expert"],
        "semantic web": ["linked-web-expert-ontologies-rdf-semantic-web"],
        "rdf": ["linked-web-expert-ontologies-rdf-semantic-web"],
        "ontology": ["linked-web-expert-ontologies-rdf-semantic-web"],
    }

    # Story content keywords that suggest specific roles
    CONTENT_ROLE_MAPPING = {
        "ui": ["ux-ui-designer"],
        "user interface": ["ux-ui-designer"],
        "user experience": ["ux-ui-designer"],
        "design": ["ux-ui-designer"],
        "accessibility": ["ux-ui-designer"],
        "api": ["system-architect", "lead-developer"],
        "database": ["system-architect"],
        "security": ["security-expert"],
        "authentication": ["security-expert"],
        "authorization": ["security-expert"],
        "performance": ["system-architect"],
        "scaling": ["system-architect", "devops-engineer"],
        "deployment": ["devops-engineer"],
        "monitoring": ["devops-engineer"],
        "testing": ["qa-engineer"],
        "test": ["qa-engineer"],
        "quality": ["qa-engineer"],
        "documentation": ["documentation-hoarder"],
        "ai": ["ai-expert"],
        "machine learning": ["ai-expert"],
        "ml": ["ai-expert"],
        "recommendation": ["ai-expert"],
        "search": ["ai-expert"],
        "nutrition": ["domain-expert-food-nutrition"],
        "recipe": ["domain-expert-food-nutrition", "professional-chef"],
        "food": ["domain-expert-food-nutrition"],
        "cooking": ["professional-chef"],
        "cultural": ["food-historian-anthropologist"],
        "heritage": ["food-historian-anthropologist"],
        "semantic": ["linked-web-expert-ontologies-rdf-semantic-web"],
        "ontology": ["linked-web-expert-ontologies-rdf-semantic-web"],
        "rdf": ["linked-web-expert-ontologies-rdf-semantic-web"],
    }

    # Always include these roles for comprehensive analysis
    DEFAULT_ROLES = ["product-owner", "system-architect"]

    def __init__(self, config: Config):
        """Initialize the role assignment engine."""
        self.config = config
        self.detector = RepositoryTypeDetector()

    def assign_roles(
        self,
        story_content: str,
        repository_contexts: List[RepositoryContext],
        story_id: str,
        manual_overrides: Optional[List[str]] = None,
    ) -> RoleAssignmentResult:
        """
        Assign roles based on story content and repository context.

        Args:
            story_content: The content of the story
            repository_contexts: List of repository contexts
            story_id: Unique identifier for the story
            manual_overrides: List of manually specified roles

        Returns:
            RoleAssignmentResult with assigned roles
        """
        primary_roles = []
        secondary_roles = []
        suggested_roles = []

        # Handle manual overrides first
        if manual_overrides:
            for role in manual_overrides:
                assignment = RoleAssignment(
                    role_name=role,
                    confidence_score=1.0,
                    assignment_reason="Manual override",
                    assigned_by="manual",
                )
                primary_roles.append(assignment)

        # Always include default roles
        for role in self.DEFAULT_ROLES:
            if not any(r.role_name == role for r in primary_roles):
                assignment = RoleAssignment(
                    role_name=role,
                    confidence_score=0.9,
                    assignment_reason="Default strategic role",
                )
                primary_roles.append(assignment)

        # Analyze repository contexts
        repo_roles = self._analyze_repository_contexts(repository_contexts)

        # Analyze story content
        content_roles = self._analyze_story_content(story_content)

        # Combine and score roles
        all_role_scores = {}

        # Add repository-based roles
        for role, score in repo_roles.items():
            all_role_scores[role] = all_role_scores.get(role, 0) + score

        # Add content-based roles
        for role, score in content_roles.items():
            all_role_scores[role] = all_role_scores.get(role, 0) + score

        # Convert scores to assignments
        for role, score in all_role_scores.items():
            if any(r.role_name == role for r in primary_roles):
                continue  # Already assigned

            assignment = RoleAssignment(
                role_name=role,
                confidence_score=min(score / 10.0, 1.0),  # Normalize to 0-1
                assignment_reason=self._generate_assignment_reason(
                    role, repository_contexts, story_content
                ),
                repository_context=", ".join(
                    [r.repository for r in repository_contexts]
                ),
            )

            if score >= 8:
                primary_roles.append(assignment)
            elif score >= 5:
                secondary_roles.append(assignment)
            else:
                suggested_roles.append(assignment)

        # Sort by confidence score
        primary_roles.sort(key=lambda x: x.confidence_score, reverse=True)
        secondary_roles.sort(key=lambda x: x.confidence_score, reverse=True)
        suggested_roles.sort(key=lambda x: x.confidence_score, reverse=True)

        return RoleAssignmentResult(
            story_id=story_id,
            primary_roles=primary_roles,
            secondary_roles=secondary_roles,
            suggested_roles=suggested_roles,
            assignment_metadata={
                "repository_types": [r.repo_type for r in repository_contexts],
                "repositories": [r.repository for r in repository_contexts],
                "assignment_timestamp": datetime.now(timezone.utc).isoformat(),
                "total_roles_considered": len(all_role_scores),
            },
        )

    def _analyze_repository_contexts(
        self, repository_contexts: List[RepositoryContext]
    ) -> Dict[str, float]:
        """Analyze repository contexts to determine relevant roles."""
        role_scores = {}

        for repo_context in repository_contexts:
            # Score based on repository type
            if repo_context.repo_type in self.REPO_TYPE_ROLE_MAPPING:
                for role in self.REPO_TYPE_ROLE_MAPPING[repo_context.repo_type]:
                    role_scores[role] = role_scores.get(role, 0) + 5.0

            # Score based on detected languages and technologies
            for language in repo_context.languages.keys():
                if language in self.TECHNOLOGY_ROLE_MAPPING:
                    for role in self.TECHNOLOGY_ROLE_MAPPING[language]:
                        role_scores[role] = role_scores.get(role, 0) + 3.0

            # Score based on file content analysis
            for file_context in repo_context.key_files:
                content_lower = file_context.content.lower()
                for tech, roles in self.TECHNOLOGY_ROLE_MAPPING.items():
                    if tech in content_lower:
                        for role in roles:
                            role_scores[role] = role_scores.get(role, 0) + 2.0

        return role_scores

    def _analyze_story_content(self, story_content: str) -> Dict[str, float]:
        """Analyze story content to determine relevant roles."""
        role_scores = {}
        content_lower = story_content.lower()

        for keyword, roles in self.CONTENT_ROLE_MAPPING.items():
            if keyword in content_lower:
                for role in roles:
                    # Weight based on keyword relevance
                    weight = 4.0 if len(keyword) > 5 else 2.0
                    role_scores[role] = role_scores.get(role, 0) + weight

        return role_scores

    def _generate_assignment_reason(
        self,
        role: str,
        repository_contexts: List[RepositoryContext],
        story_content: str,
    ) -> str:
        """Generate a human-readable reason for role assignment."""
        reasons = []

        # Check repository type matches
        for repo_context in repository_contexts:
            if repo_context.repo_type in self.REPO_TYPE_ROLE_MAPPING:
                if role in self.REPO_TYPE_ROLE_MAPPING[repo_context.repo_type]:
                    reasons.append(f"Repository type '{repo_context.repo_type}'")

        # Check technology matches
        content_lower = story_content.lower()
        for keyword, roles in self.CONTENT_ROLE_MAPPING.items():
            if keyword in content_lower and role in roles:
                reasons.append(f"Story mentions '{keyword}'")

        if not reasons:
            reasons.append("General expertise relevance")

        return "; ".join(reasons[:3])  # Limit to top 3 reasons

    def get_role_assignment_audit_trail(self, story_id: str) -> List[Dict[str, Any]]:
        """Get audit trail for role assignments (placeholder for future database integration)."""
        # This would integrate with the database to track assignment history
        return []

    def validate_role_exists(self, role_name: str) -> bool:
        """Validate that a role exists in the system."""
        role_path = Path(__file__).parent / ".storyteller" / "roles" / f"{role_name}.md"
        return role_path.exists()

    def get_available_roles(self) -> List[str]:
        """Get list of all available roles."""
        roles_dir = Path(__file__).parent / ".storyteller" / "roles"
        if not roles_dir.exists():
            return []

        return [f.stem for f in roles_dir.glob("*.md")]
