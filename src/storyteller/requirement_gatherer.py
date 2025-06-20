"""Role-based requirement gathering for comprehensive story analysis."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from jinja2 import Environment, FileSystemLoader, Template

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

from config import Config
from llm_handler import LLMHandler
from multi_repo_context import RepositoryContext
from role_analyzer import RoleAssignment

logger = logging.getLogger(__name__)


@dataclass
class RequirementSet:
    """Set of requirements gathered from a specific role."""

    role_name: str
    acceptance_criteria: List[str] = field(default_factory=list)
    testing_requirements: List[str] = field(default_factory=list)
    effort_estimate: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    confidence_level: str = "medium"  # high, medium, low
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatheredRequirements:
    """Complete set of requirements gathered from all roles."""

    story_id: str
    story_content: str
    role_requirements: List[RequirementSet] = field(default_factory=list)
    synthesized_acceptance_criteria: List[str] = field(default_factory=list)
    synthesized_testing_requirements: List[str] = field(default_factory=list)
    estimated_story_points: Optional[int] = None
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class RequirementGatherer:
    """Orchestrates requirement gathering from multiple expert roles."""

    def __init__(self, config: Config, llm_handler: LLMHandler):
        """Initialize the requirement gatherer."""
        self.config = config
        self.llm_handler = llm_handler
        self.templates_dir = (
            Path(__file__).parent / ".storyteller" / "templates" / "requirements"
        )

        if JINJA2_AVAILABLE:
            self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
        else:
            self.env = None
            logger.warning("Jinja2 not available, using simple template substitution")

    async def gather_requirements(
        self,
        story_content: str,
        story_id: str,
        assigned_roles: List[RoleAssignment],
        repository_contexts: List[RepositoryContext],
    ) -> GatheredRequirements:
        """
        Gather requirements from all assigned roles.

        Args:
            story_content: The story content to analyze
            story_id: Unique identifier for the story
            assigned_roles: List of roles assigned to analyze the story
            repository_contexts: Repository contexts for additional context

        Returns:
            GatheredRequirements with all gathered requirements
        """
        logger.info(
            f"Gathering requirements for story {story_id} from {len(assigned_roles)} roles"
        )

        role_requirements = []

        # Gather requirements from each role
        for role_assignment in assigned_roles:
            try:
                requirements = await self._gather_role_requirements(
                    story_content=story_content,
                    story_id=story_id,
                    role_assignment=role_assignment,
                    repository_contexts=repository_contexts,
                )
                role_requirements.append(requirements)
                logger.debug(
                    f"Gathered requirements from role: {role_assignment.role_name}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to gather requirements from role {role_assignment.role_name}: {e}"
                )
                # Create empty requirement set to maintain consistency
                role_requirements.append(
                    RequirementSet(
                        role_name=role_assignment.role_name,
                        confidence_level="low",
                        metadata={"error": str(e)},
                    )
                )

        # Synthesize requirements across roles
        synthesized = await self._synthesize_requirements(
            story_content=story_content,
            story_id=story_id,
            role_requirements=role_requirements,
            repository_contexts=repository_contexts,
        )

        return GatheredRequirements(
            story_id=story_id,
            story_content=story_content,
            role_requirements=role_requirements,
            synthesized_acceptance_criteria=synthesized["acceptance_criteria"],
            synthesized_testing_requirements=synthesized["testing_requirements"],
            estimated_story_points=synthesized["story_points"],
            confidence_score=synthesized["confidence_score"],
            metadata={
                "total_roles": len(assigned_roles),
                "successful_roles": len(
                    [r for r in role_requirements if "error" not in r.metadata]
                ),
                "repository_contexts": [r.repository for r in repository_contexts],
                "synthesis_method": "llm_consensus",
            },
        )

    async def _gather_role_requirements(
        self,
        story_content: str,
        story_id: str,
        role_assignment: RoleAssignment,
        repository_contexts: List[RepositoryContext],
    ) -> RequirementSet:
        """Gather requirements from a specific role."""

        # Prepare context for templates
        context = {
            "story_content": story_content,
            "story_id": story_id,
            "role_name": role_assignment.role_name,
            "repository_context": self._format_repository_context(repository_contexts),
            "assignment_reason": role_assignment.assignment_reason,
        }

        # Gather acceptance criteria
        acceptance_criteria = await self._gather_acceptance_criteria(
            role_assignment, context
        )

        # Gather testing requirements
        testing_requirements = await self._gather_testing_requirements(
            role_assignment, context
        )

        # Gather effort estimation
        effort_estimate = await self._gather_effort_estimation(role_assignment, context)

        return RequirementSet(
            role_name=role_assignment.role_name,
            acceptance_criteria=acceptance_criteria,
            testing_requirements=testing_requirements,
            effort_estimate=effort_estimate,
            confidence_level=self._determine_confidence_level(role_assignment),
            metadata={
                "assignment_reason": role_assignment.assignment_reason,
                "confidence_score": role_assignment.confidence_score,
            },
        )

    async def _gather_acceptance_criteria(
        self, role_assignment: RoleAssignment, context: Dict[str, Any]
    ) -> List[str]:
        """Gather acceptance criteria from a specific role."""

        template_content = self._load_template(
            "acceptance_criteria_template.md", context
        )

        prompt = f"""
As a {role_assignment.role_name}, analyze the following story and template to provide specific acceptance criteria:

{template_content}

Please provide 3-5 specific, measurable acceptance criteria from your role's perspective.
Format each criterion as a clear, testable statement starting with "The system shall" or "The user can".
Focus on what can be verified and validated from your domain expertise.

Return only the acceptance criteria as a bulleted list, one per line.
"""

        try:
            response = await self.llm_handler.generate_response(
                prompt=prompt,
                role_context=role_assignment.role_name,
                max_tokens=1000,
            )

            # Parse response into list of criteria
            criteria = self._parse_bulleted_list(response.content)
            return criteria[:5]  # Limit to max 5 criteria per role

        except Exception as e:
            logger.error(
                f"Failed to gather acceptance criteria from {role_assignment.role_name}: {e}"
            )
            return []

    async def _gather_testing_requirements(
        self, role_assignment: RoleAssignment, context: Dict[str, Any]
    ) -> List[str]:
        """Gather testing requirements from a specific role."""

        template_content = self._load_template(
            "testing_requirements_template.md", context
        )

        prompt = f"""
As a {role_assignment.role_name}, analyze the following story and template to provide specific testing requirements:

{template_content}

Please provide 3-5 specific testing requirements from your role's perspective.
Focus on test types, test scenarios, and testing strategies that are critical from your domain expertise.
Include both functional and non-functional testing considerations.

Return only the testing requirements as a bulleted list, one per line.
"""

        try:
            response = await self.llm_handler.generate_response(
                prompt=prompt,
                role_context=role_assignment.role_name,
                max_tokens=1000,
            )

            # Parse response into list of requirements
            requirements = self._parse_bulleted_list(response.content)
            return requirements[:5]  # Limit to max 5 requirements per role

        except Exception as e:
            logger.error(
                f"Failed to gather testing requirements from {role_assignment.role_name}: {e}"
            )
            return []

    async def _gather_effort_estimation(
        self, role_assignment: RoleAssignment, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Gather effort estimation from a specific role."""

        template_content = self._load_template("effort_estimation_template.md", context)

        prompt = f"""
As a {role_assignment.role_name}, analyze the following story and template to provide effort estimation:

{template_content}

Please provide:
1. Story points estimate (1, 2, 3, 5, 8, 13, or 21)
2. Complexity assessment (1-5 scale)
3. Time estimate in hours/days
4. Key risk factors
5. Confidence level (high/medium/low)

Return as JSON format:
{{
    "story_points": number,
    "complexity": number,
    "time_estimate_hours": number,
    "risk_factors": ["risk1", "risk2"],
    "confidence": "high|medium|low",
    "reasoning": "brief explanation"
}}
"""

        try:
            response = await self.llm_handler.generate_response(
                prompt=prompt,
                role_context=role_assignment.role_name,
                max_tokens=800,
            )

            # Parse JSON response
            import json

            try:
                estimate = json.loads(response.content.strip())
                return estimate
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                return self._parse_effort_estimate_fallback(response.content)

        except Exception as e:
            logger.error(
                f"Failed to gather effort estimation from {role_assignment.role_name}: {e}"
            )
            return {
                "story_points": 3,
                "complexity": 3,
                "confidence": "low",
                "reasoning": "Default estimate due to analysis failure",
            }

    async def _synthesize_requirements(
        self,
        story_content: str,
        story_id: str,
        role_requirements: List[RequirementSet],
        repository_contexts: List[RepositoryContext],
    ) -> Dict[str, Any]:
        """Synthesize requirements from all roles into final requirements."""

        # Collect all acceptance criteria
        all_criteria = []
        for req in role_requirements:
            all_criteria.extend(req.acceptance_criteria)

        # Collect all testing requirements
        all_testing = []
        for req in role_requirements:
            all_testing.extend(req.testing_requirements)

        # Calculate story points from estimates
        story_points_estimates = []
        for req in role_requirements:
            if req.effort_estimate.get("story_points"):
                story_points_estimates.append(req.effort_estimate["story_points"])

        # Use median or most common estimate
        estimated_points = self._calculate_consensus_story_points(
            story_points_estimates
        )

        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(role_requirements)

        # Use LLM to synthesize and deduplicate requirements
        synthesis_prompt = f"""
Given the following story and requirements gathered from multiple expert roles, synthesize them into final comprehensive requirements:

Story: {story_content}

Acceptance Criteria from all roles:
{self._format_criteria_list(all_criteria)}

Testing Requirements from all roles:
{self._format_criteria_list(all_testing)}

Please provide:
1. Synthesized acceptance criteria (remove duplicates, merge similar items, ensure comprehensive coverage)
2. Synthesized testing requirements (remove duplicates, organize by test type)

Return as JSON:
{{
    "acceptance_criteria": ["criterion1", "criterion2", ...],
    "testing_requirements": ["requirement1", "requirement2", ...]
}}
"""

        try:
            response = await self.llm_handler.generate_response(
                prompt=synthesis_prompt,
                role_context="system-architect",  # Use architect for synthesis
                max_tokens=1500,
            )

            import json

            synthesized = json.loads(response.content.strip())

            return {
                "acceptance_criteria": synthesized.get(
                    "acceptance_criteria", all_criteria[:10]
                ),
                "testing_requirements": synthesized.get(
                    "testing_requirements", all_testing[:8]
                ),
                "story_points": estimated_points,
                "confidence_score": confidence_score,
            }

        except Exception as e:
            logger.error(f"Failed to synthesize requirements: {e}")
            # Fallback to direct aggregation
            return {
                "acceptance_criteria": list(set(all_criteria))[
                    :10
                ],  # Remove duplicates, limit to 10
                "testing_requirements": list(set(all_testing))[
                    :8
                ],  # Remove duplicates, limit to 8
                "story_points": estimated_points,
                "confidence_score": confidence_score,
            }

    def _load_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Load and render a requirement template."""
        if self.env and JINJA2_AVAILABLE:
            try:
                template = self.env.get_template(template_name)
                return template.render(**context)
            except Exception as e:
                logger.warning(f"Failed to load Jinja2 template {template_name}: {e}")

        # Fallback to simple file reading and substitution
        template_path = self.templates_dir / template_name
        if template_path.exists():
            content = template_path.read_text()
            # Simple substitution
            for key, value in context.items():
                content = content.replace(f"{{{{ {key} }}}}", str(value))
            return content
        else:
            return f"Template {template_name} not found. Context: {context}"

    def _format_repository_context(
        self, repository_contexts: List[RepositoryContext]
    ) -> str:
        """Format repository contexts for template substitution."""
        if not repository_contexts:
            return "No repository context available"

        contexts = []
        for repo in repository_contexts:
            contexts.append(f"{repo.repository} ({repo.repo_type})")

        return ", ".join(contexts)

    def _determine_confidence_level(self, role_assignment: RoleAssignment) -> str:
        """Determine confidence level based on role assignment score."""
        if role_assignment.confidence_score >= 0.8:
            return "high"
        elif role_assignment.confidence_score >= 0.5:
            return "medium"
        else:
            return "low"

    def _parse_bulleted_list(self, content: str) -> List[str]:
        """Parse bulleted list from LLM response."""
        lines = content.strip().split("\n")
        items = []

        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
                items.append(line[2:].strip())
            elif (
                line.startswith("1.") or line.startswith("2.") or line.startswith("3.")
            ):
                # Handle numbered lists
                items.append(line.split(".", 1)[1].strip())

        return items

    def _parse_effort_estimate_fallback(self, content: str) -> Dict[str, Any]:
        """Fallback parsing for effort estimates when JSON parsing fails."""
        # Simple regex-based parsing for common patterns
        import re

        estimate = {
            "story_points": 3,
            "complexity": 3,
            "confidence": "medium",
            "reasoning": "Parsed from fallback method",
        }

        # Look for story points
        points_match = re.search(r"story.points?[:\s]*(\d+)", content, re.IGNORECASE)
        if points_match:
            estimate["story_points"] = int(points_match.group(1))

        # Look for complexity
        complexity_match = re.search(r"complexity[:\s]*(\d+)", content, re.IGNORECASE)
        if complexity_match:
            estimate["complexity"] = int(complexity_match.group(1))

        # Look for confidence - be more specific to avoid false matches
        confidence_pattern = (
            r"confidence\s+(?:level\s+)?is\s+(\w+)|confidence[:\s]+(\w+)"
        )
        confidence_match = re.search(confidence_pattern, content, re.IGNORECASE)
        if confidence_match:
            confidence_word = (
                confidence_match.group(1) or confidence_match.group(2)
            ).lower()
            if confidence_word in ["high", "medium", "low"]:
                estimate["confidence"] = confidence_word
        else:
            # Fallback to simple word matching but be more specific
            if (
                "confidence level is low" in content.lower()
                or "confidence is low" in content.lower()
            ):
                estimate["confidence"] = "low"
            elif (
                "confidence level is high" in content.lower()
                or "confidence is high" in content.lower()
            ):
                estimate["confidence"] = "high"

        return estimate

    def _calculate_consensus_story_points(self, estimates: List[int]) -> int:
        """Calculate consensus story points from multiple estimates."""
        if not estimates:
            return 3  # Default

        # Use median for consensus
        estimates.sort()
        n = len(estimates)
        if n % 2 == 0:
            median = (estimates[n // 2 - 1] + estimates[n // 2]) / 2
        else:
            median = estimates[n // 2]

        # Round to nearest Fibonacci number used in story points
        fibonacci = [1, 2, 3, 5, 8, 13, 21]
        return min(fibonacci, key=lambda x: abs(x - median))

    def _calculate_confidence_score(
        self, role_requirements: List[RequirementSet]
    ) -> float:
        """Calculate overall confidence score from role requirements."""
        if not role_requirements:
            return 0.0

        confidence_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
        total_confidence = sum(
            confidence_map.get(req.confidence_level, 0.3) for req in role_requirements
        )

        return total_confidence / len(role_requirements)

    def _format_criteria_list(self, criteria: List[str]) -> str:
        """Format criteria list for prompt inclusion."""
        if not criteria:
            return "No criteria provided"

        return "\n".join(f"- {criterion}" for criterion in criteria)
