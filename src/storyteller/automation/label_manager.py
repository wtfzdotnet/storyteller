"""Label management for automated GitHub issue labeling."""

import logging
from dataclasses import dataclass
from typing import List

from config import Config, RepositoryConfig

logger = logging.getLogger(__name__)


@dataclass
class LabelRule:
    """Rule for automatic label assignment."""

    name: str
    keywords: List[str]
    description: str
    color: str = "0366d6"  # Default GitHub blue
    priority: int = 1  # Higher priority rules override lower priority


class LabelManager:
    """Manager for automatic label assignment and GitHub label synchronization."""

    def __init__(self, config: Config):
        self.config = config
        self._label_rules = self._initialize_label_rules()

    def _initialize_label_rules(self) -> List[LabelRule]:
        """Initialize default label rules for story categorization."""

        return [
            # Story type labels
            LabelRule(
                name="user_story",
                keywords=["story", "feature", "requirement"],
                description="User story or feature request",
                color="0366d6",
                priority=10,
            ),
            # Technical domain labels
            LabelRule(
                name="backend",
                keywords=["api", "database", "service", "server", "backend"],
                description="Backend/API related",
                color="d73a49",
                priority=8,
            ),
            LabelRule(
                name="frontend",
                keywords=["ui", "interface", "client", "frontend", "react", "vue"],
                description="Frontend/UI related",
                color="28a745",
                priority=8,
            ),
            LabelRule(
                name="security",
                keywords=["security", "auth", "permission", "vulnerability"],
                description="Security related",
                color="dc3545",
                priority=9,
            ),
            # Domain-specific labels
            LabelRule(
                name="recipe",
                keywords=["recipe", "ingredient", "cooking", "meal"],
                description="Recipe functionality",
                color="ffc107",
                priority=7,
            ),
            LabelRule(
                name="nutrition",
                keywords=["nutrition", "dietary", "health", "calories"],
                description="Nutrition related",
                color="17a2b8",
                priority=7,
            ),
            LabelRule(
                name="cultural",
                keywords=["cultural", "heritage", "traditional", "authentic"],
                description="Cultural authenticity",
                color="6f42c1",
                priority=7,
            ),
            # Complexity labels
            LabelRule(
                name="complex",
                keywords=["complex", "integration", "multiple", "advanced"],
                description="Complex implementation",
                color="fd7e14",
                priority=6,
            ),
            LabelRule(
                name="enhancement",
                keywords=["improve", "enhance", "optimize", "better"],
                description="Enhancement to existing feature",
                color="6610f2",
                priority=5,
            ),
            # Priority labels
            LabelRule(
                name="high-priority",
                keywords=["urgent", "critical", "important", "asap"],
                description="High priority item",
                color="e83e8c",
                priority=9,
            ),
        ]

    def analyze_content_for_labels(
        self, title: str, body: str, repository_config: RepositoryConfig
    ) -> List[str]:
        """Analyze content to determine appropriate labels."""

        content = f"{title} {body}".lower()
        assigned_labels = set()

        # Add repository-specific labels
        assigned_labels.update(repository_config.story_labels)

        # Apply label rules
        for rule in sorted(self._label_rules, key=lambda x: -x.priority):
            if any(keyword in content for keyword in rule.keywords):
                assigned_labels.add(rule.name)

        return list(assigned_labels)

    def get_expert_role_labels(self, expert_roles: List[str]) -> List[str]:
        """Generate labels based on expert roles that analyzed the story."""

        role_label_mapping = {
            "system-architect": "architecture",
            "security-expert": "security",
            "domain-expert-food-nutrition": "nutrition",
            "professional-chef": "recipe",
            "ux-ui-designer": "ui-ux",
            "devops-engineer": "devops",
            "ai-expert": "ai-ml",
            "qa-engineer": "testing",
            "food-historian-anthropologist": "cultural",
            "product-owner": "product",
        }

        labels = []
        for role in expert_roles:
            if role in role_label_mapping:
                labels.append(role_label_mapping[role])

        return labels

    def combine_labels(
        self,
        content_labels: List[str],
        expert_labels: List[str],
        repository_labels: List[str],
    ) -> List[str]:
        """Combine labels from different sources, removing duplicates."""

        all_labels = set()
        all_labels.update(content_labels)
        all_labels.update(expert_labels)
        all_labels.update(repository_labels)

        # Always include user_story label
        all_labels.add("user_story")

        return sorted(list(all_labels))

    def get_labels_for_story(
        self, title: str, body: str, repository_key: str, expert_roles: List[str]
    ) -> List[str]:
        """Get complete label set for a story."""

        repository_config = self.config.repositories.get(repository_key)
        if not repository_config:
            repository_config = RepositoryConfig(
                name="unknown",
                type="unknown",
                description="Unknown repository",
                story_labels=["user_story"],
            )

        # Analyze content
        content_labels = self.analyze_content_for_labels(title, body, repository_config)

        # Get expert role labels
        expert_labels = self.get_expert_role_labels(expert_roles)

        # Get repository labels
        repository_labels = repository_config.story_labels

        # Combine all labels
        return self.combine_labels(content_labels, expert_labels, repository_labels)

    async def ensure_labels_exist(
        self, repository_name: str, labels: List[str]
    ) -> None:
        """Ensure labels exist in the GitHub repository."""

        # This would interact with GitHub API to create labels if they don't exist
        # For now, we'll just log what labels would be created
        logger.info(f"Ensuring labels exist in {repository_name}: {labels}")

        # TODO: Implement actual GitHub label creation
        # This would require extending GitHubHandler with label management methods

    def get_label_color(self, label_name: str) -> str:
        """Get the color for a specific label."""

        for rule in self._label_rules:
            if rule.name == label_name:
                return rule.color

        # Default colors for common labels
        default_colors = {
            "user_story": "0366d6",
            "bug": "d73a49",
            "enhancement": "a2eeef",
            "documentation": "0075ca",
            "good first issue": "7057ff",
            "help wanted": "008672",
        }

        return default_colors.get(label_name, "ededed")  # Default gray

    def validate_labels(self, labels: List[str]) -> List[str]:
        """Validate and clean up label list."""

        # Remove empty or invalid labels
        valid_labels = []
        for label in labels:
            if label and isinstance(label, str) and len(label.strip()) > 0:
                # Clean up label (lowercase, replace spaces with hyphens)
                clean_label = label.strip().lower().replace(" ", "-")
                if clean_label not in valid_labels:
                    valid_labels.append(clean_label)

        return valid_labels
