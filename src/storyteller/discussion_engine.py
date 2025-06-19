"""Multi-role discussion simulation engine."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import Config, get_config
from database import DatabaseManager
from llm_handler import LLMHandler
from models import (
    Conversation,
    ConversationParticipant,
    DiscussionSummary,
    DiscussionThread,
    Message,
    RolePerspective,
)
from role_analyzer import RoleAssignmentEngine
from multi_repo_context import MultiRepositoryContextReader

logger = logging.getLogger(__name__)


class DiscussionEngine:
    """Engine for simulating multi-role discussions."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize the discussion engine."""
        self.config = config or get_config()
        self.database = DatabaseManager()
        self.llm_handler = LLMHandler(self.config)
        self.role_engine = RoleAssignmentEngine(self.config)
        self.context_reader = MultiRepositoryContextReader(self.config)

    async def start_discussion(
        self,
        topic: str,
        story_content: str,
        repositories: List[str],
        required_roles: Optional[List[str]] = None,
        max_discussion_rounds: int = 3,
    ) -> DiscussionThread:
        """
        Start a multi-role discussion simulation.

        Args:
            topic: The discussion topic
            story_content: The story content to discuss
            repositories: List of relevant repositories
            required_roles: Optional list of specific roles to include
            max_discussion_rounds: Maximum number of discussion rounds

        Returns:
            DiscussionThread with the discussion results
        """
        logger.info(f"Starting discussion on topic: {topic}")

        # Create conversation for this discussion
        conversation = Conversation(
            title=f"Discussion: {topic}",
            description=f"Multi-role discussion about: {story_content[:200]}...",
            repositories=repositories,
        )
        self.database.save_conversation(conversation)

        # Create discussion thread
        thread = DiscussionThread(
            conversation_id=conversation.id,
            topic=topic,
        )

        # Determine participating roles
        participating_roles = await self._determine_participating_roles(
            story_content, repositories, required_roles
        )

        # Add participants to conversation
        for role_name in participating_roles:
            participant = ConversationParticipant(
                name=f"{role_name.replace('-', ' ').title()}",
                role=role_name,
            )
            conversation.participants.append(participant)

        self.database.save_conversation(conversation)

        # Generate initial perspectives from each role
        await self._generate_initial_perspectives(
            thread, story_content, participating_roles, repositories
        )

        # Conduct discussion rounds
        for round_num in range(max_discussion_rounds):
            logger.info(f"Starting discussion round {round_num + 1}")

            # Check if consensus is reached
            consensus = thread.calculate_consensus()
            if consensus >= self.config.auto_consensus_threshold / 100.0:
                logger.info(f"Consensus reached with score: {consensus:.2f}")
                thread.status = "resolved"
                break

            # Generate responses and counter-arguments
            await self._conduct_discussion_round(thread, story_content, repositories)

            # Update consensus after each round
            thread.calculate_consensus()

        # Mark as needing human input if no consensus reached
        if thread.consensus_level < self.config.auto_consensus_threshold / 100.0:
            thread.status = "needs_human_input"
            logger.info(
                f"Discussion requires human input. Consensus: {thread.consensus_level:.2f}"
            )

        # Save final thread state
        self.database.save_discussion_thread(thread)

        return thread

    async def _determine_participating_roles(
        self,
        story_content: str,
        repositories: List[str],
        required_roles: Optional[List[str]] = None,
    ) -> List[str]:
        """Determine which roles should participate in the discussion."""

        if required_roles:
            return required_roles

        # Get repository contexts
        repo_contexts = []
        for repo in repositories:
            try:
                context = await self.context_reader.get_repository_context(repo)
                repo_contexts.append(context)
            except Exception as e:
                logger.warning(f"Could not get context for repository {repo}: {e}")

        # Use role assignment engine to determine relevant roles
        assignment_result = self.role_engine.assign_roles(
            story_content=story_content,
            repository_contexts=repo_contexts,
            story_id="discussion",
        )

        # Extract primary and secondary roles
        roles = []
        for assignment in assignment_result.primary_roles:
            roles.append(assignment.role_name)

        for assignment in assignment_result.secondary_roles:
            if (
                assignment.confidence_score >= 0.6
            ):  # Only include high-confidence secondary roles
                roles.append(assignment.role_name)

        # Ensure minimum diversity in perspectives
        if len(roles) < 3:
            # Add some default roles for broader perspective
            default_roles = ["product-owner", "system-architect", "qa-engineer"]
            for role in default_roles:
                if role not in roles:
                    roles.append(role)
                    if len(roles) >= 3:
                        break

        return list(set(roles))  # Remove duplicates

    async def _generate_initial_perspectives(
        self,
        thread: DiscussionThread,
        story_content: str,
        roles: List[str],
        repositories: List[str],
    ) -> None:
        """Generate initial perspectives from each role."""

        # Generate perspectives concurrently for better performance
        perspective_tasks = []
        for role in roles:
            task = self._generate_role_perspective(
                role, story_content, repositories, thread.topic
            )
            perspective_tasks.append(task)

        perspectives = await asyncio.gather(*perspective_tasks, return_exceptions=True)

        for perspective in perspectives:
            if isinstance(perspective, Exception):
                logger.error(f"Error generating perspective: {perspective}")
                continue

            thread.add_perspective(perspective)

    async def _generate_role_perspective(
        self,
        role_name: str,
        story_content: str,
        repositories: List[str],
        topic: str,
    ) -> RolePerspective:
        """Generate a perspective from a specific role."""

        # Build role-specific system prompt
        system_prompt = self._build_role_system_prompt(role_name, repositories)

        # Build discussion prompt
        discussion_prompt = f"""
        You are analyzing this user story from the perspective of a {role_name}:

        Story: {story_content}
        
        Discussion Topic: {topic}
        
        Repositories Involved: {', '.join(repositories)}

        Please provide your perspective considering:
        1. Your viewpoint on this story from your role's expertise
        2. Key arguments supporting your position
        3. Concerns or potential issues you see
        4. Suggestions for improvement or alternative approaches
        5. Your confidence level in your assessment (0.0 to 1.0)

        Be specific, practical, and focus on aspects most relevant to your role.
        Consider cross-repository implications and dependencies.
        """

        try:
            response = await self.llm_handler.generate_response(
                prompt=discussion_prompt,
                system_prompt=system_prompt,
            )

            # Parse the response into structured perspective
            perspective = self._parse_perspective_response(
                response.content, role_name, repositories
            )

            return perspective

        except Exception as e:
            logger.error(f"Error generating perspective for role {role_name}: {e}")
            # Return a basic perspective as fallback
            return RolePerspective(
                role_name=role_name,
                viewpoint=f"Unable to generate perspective due to error: {str(e)}",
                confidence_level=0.0,
            )

    def _build_role_system_prompt(self, role_name: str, repositories: List[str]) -> str:
        """Build a system prompt for a specific role."""

        role_descriptions = {
            "product-owner": "You are a Product Owner focused on business value, user needs, and strategic alignment.",
            "system-architect": "You are a System Architect concerned with technical design, scalability, and system integration.",
            "lead-developer": "You are a Lead Developer focused on implementation feasibility, code quality, and technical execution.",
            "security-expert": "You are a Security Expert focused on security vulnerabilities, compliance, and risk mitigation.",
            "qa-engineer": "You are a QA Engineer focused on testing strategies, quality assurance, and defect prevention.",
            "devops-engineer": "You are a DevOps Engineer focused on deployment, infrastructure, and operational concerns.",
            "ux-ui-designer": "You are a UX/UI Designer focused on user experience, interface design, and usability.",
            "ai-expert": "You are an AI Expert focused on machine learning, data science, and AI implementation.",
        }

        base_description = role_descriptions.get(
            role_name,
            f"You are a {role_name.replace('-', ' ').title()} with expertise in your domain.",
        )

        return f"""
        {base_description}
        
        You are participating in a multi-role discussion about a software development story.
        The discussion involves repositories: {', '.join(repositories)}
        
        Your role is to:
        - Provide insights from your specific domain expertise
        - Identify potential risks or opportunities in your area
        - Suggest practical solutions and improvements
        - Consider how decisions impact your area of responsibility
        - Collaborate constructively with other roles
        
        Be specific, actionable, and focus on your area of expertise while considering the broader context.
        """

    def _parse_perspective_response(
        self, response_content: str, role_name: str, repositories: List[str]
    ) -> RolePerspective:
        """Parse LLM response into structured perspective."""

        # Simple parsing - in production, could use more sophisticated NLP
        lines = response_content.strip().split("\n")

        viewpoint = ""
        arguments = []
        concerns = []
        suggestions = []
        confidence_level = 0.7  # Default confidence

        current_section = "viewpoint"

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect section headers
            if any(
                keyword in line.lower()
                for keyword in ["viewpoint", "perspective", "opinion"]
            ):
                current_section = "viewpoint"
                continue
            elif any(
                keyword in line.lower() for keyword in ["argument", "support", "reason"]
            ):
                current_section = "arguments"
                continue
            elif any(
                keyword in line.lower()
                for keyword in ["concern", "issue", "risk", "problem"]
            ):
                current_section = "concerns"
                continue
            elif any(
                keyword in line.lower()
                for keyword in ["suggestion", "recommendation", "improve"]
            ):
                current_section = "suggestions"
                continue
            elif any(
                keyword in line.lower() for keyword in ["confidence", "certainty"]
            ):
                # Try to extract confidence score
                try:
                    import re

                    numbers = re.findall(r"0?\.\d+|[01]\.?0?", line)
                    if numbers:
                        confidence_level = float(numbers[0])
                except:
                    pass
                continue

            # Add content to appropriate section
            if current_section == "viewpoint" and not viewpoint:
                viewpoint = line
            elif current_section == "arguments":
                arguments.append(line)
            elif current_section == "concerns":
                concerns.append(line)
            elif current_section == "suggestions":
                suggestions.append(line)

        # Fallback: use first few sentences as viewpoint if not properly structured
        if not viewpoint and response_content:
            sentences = response_content.split(".")
            viewpoint = (
                ". ".join(sentences[:2]) + "."
                if len(sentences) >= 2
                else response_content[:200]
            )

        return RolePerspective(
            role_name=role_name,
            viewpoint=viewpoint,
            arguments=arguments,
            concerns=concerns,
            suggestions=suggestions,
            confidence_level=min(max(confidence_level, 0.0), 1.0),
            repository_context=", ".join(repositories),
        )

    async def _conduct_discussion_round(
        self,
        thread: DiscussionThread,
        story_content: str,
        repositories: List[str],
    ) -> None:
        """Conduct one round of discussion with responses and counter-arguments."""

        # Get current perspectives
        existing_perspectives = {p.role_name: p for p in thread.perspectives}

        # Generate responses to other perspectives
        response_tasks = []
        for role_name, perspective in existing_perspectives.items():
            task = self._generate_perspective_response(
                role_name, perspective, thread.perspectives, story_content, repositories
            )
            response_tasks.append(task)

        responses = await asyncio.gather(*response_tasks, return_exceptions=True)

        # Update perspectives with new insights
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Error generating response: {response}")
                continue

            role_name = list(existing_perspectives.keys())[i]
            if role_name in existing_perspectives:
                # Update existing perspective with new arguments/concerns
                existing_perspective = existing_perspectives[role_name]
                if response.get("arguments"):
                    existing_perspective.arguments.extend(response["arguments"])
                if response.get("concerns"):
                    existing_perspective.concerns.extend(response["concerns"])
                if response.get("suggestions"):
                    existing_perspective.suggestions.extend(response["suggestions"])

    async def _generate_perspective_response(
        self,
        role_name: str,
        current_perspective: RolePerspective,
        all_perspectives: List[RolePerspective],
        story_content: str,
        repositories: List[str],
    ) -> Dict[str, List[str]]:
        """Generate a response to other perspectives in the discussion."""

        # Build context of other perspectives
        other_perspectives = [p for p in all_perspectives if p.role_name != role_name]
        context = self._build_perspective_context(other_perspectives)

        system_prompt = self._build_role_system_prompt(role_name, repositories)

        response_prompt = f"""
        You previously provided this perspective on the story:
        Viewpoint: {current_perspective.viewpoint}
        Arguments: {'; '.join(current_perspective.arguments)}
        Concerns: {'; '.join(current_perspective.concerns)}
        
        Now consider these perspectives from other roles:
        {context}
        
        Based on this discussion, provide:
        1. Additional arguments that address points raised by others
        2. New concerns that emerge from the discussion
        3. Updated suggestions that incorporate insights from other roles
        
        Focus on constructive dialogue and finding common ground where possible.
        """

        try:
            response = await self.llm_handler.generate_response(
                prompt=response_prompt,
                system_prompt=system_prompt,
            )

            # Parse response for new arguments, concerns, suggestions
            return self._parse_response_updates(response.content)

        except Exception as e:
            logger.error(f"Error generating response for role {role_name}: {e}")
            return {"arguments": [], "concerns": [], "suggestions": []}

    def _build_perspective_context(self, perspectives: List[RolePerspective]) -> str:
        """Build a context string from multiple perspectives."""
        context_parts = []

        for perspective in perspectives:
            context = f"**{perspective.role_name}**: {perspective.viewpoint}"
            if perspective.concerns:
                context += f"\n  Concerns: {'; '.join(perspective.concerns[:3])}"  # Limit for brevity
            context_parts.append(context)

        return "\n\n".join(context_parts)

    def _parse_response_updates(self, response_content: str) -> Dict[str, List[str]]:
        """Parse response content for new arguments, concerns, and suggestions."""

        lines = response_content.strip().split("\n")

        arguments = []
        concerns = []
        suggestions = []
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect section headers
            if any(
                keyword in line.lower() for keyword in ["argument", "support", "reason"]
            ):
                current_section = "arguments"
                continue
            elif any(
                keyword in line.lower() for keyword in ["concern", "issue", "risk"]
            ):
                current_section = "concerns"
                continue
            elif any(
                keyword in line.lower() for keyword in ["suggestion", "recommendation"]
            ):
                current_section = "suggestions"
                continue

            # Add content to appropriate section
            if current_section == "arguments":
                arguments.append(line)
            elif current_section == "concerns":
                concerns.append(line)
            elif current_section == "suggestions":
                suggestions.append(line)

        return {
            "arguments": arguments,
            "concerns": concerns,
            "suggestions": suggestions,
        }

    async def generate_discussion_summary(
        self, thread: DiscussionThread
    ) -> DiscussionSummary:
        """Generate a comprehensive summary of the discussion."""

        logger.info(f"Generating discussion summary for thread: {thread.id}")

        # Collect all perspectives
        participating_roles = [p.role_name for p in thread.perspectives]
        all_viewpoints = [p.viewpoint for p in thread.perspectives if p.viewpoint]
        all_arguments = []
        all_concerns = []
        all_suggestions = []

        for perspective in thread.perspectives:
            all_arguments.extend(perspective.arguments)
            all_concerns.extend(perspective.concerns)
            all_suggestions.extend(perspective.suggestions)

        # Use LLM to generate structured summary
        summary_prompt = f"""
        Analyze this multi-role discussion and provide a comprehensive summary:

        Topic: {thread.topic}
        Participating Roles: {', '.join(participating_roles)}
        
        Role Perspectives:
        {self._build_perspective_context(thread.perspectives)}

        Please provide:
        1. Key points discussed
        2. Areas of agreement between roles
        3. Areas of disagreement or conflict
        4. Recommended actions based on the discussion
        5. Unresolved issues that need further attention
        6. Overall assessment of whether consensus was reached

        Focus on actionable insights and clear next steps.
        """

        try:
            response = await self.llm_handler.generate_response(
                prompt=summary_prompt,
                system_prompt="You are analyzing a multi-role software development discussion. Provide a clear, structured summary that helps decision-making.",
            )

            summary = self._parse_summary_response(
                response.content, thread, participating_roles
            )

            # Save summary to database
            self.database.save_discussion_summary(summary)

            return summary

        except Exception as e:
            logger.error(f"Error generating discussion summary: {e}")
            # Return basic summary as fallback
            return DiscussionSummary(
                conversation_id=thread.conversation_id,
                discussion_topic=thread.topic,
                participating_roles=participating_roles,
                overall_consensus=thread.consensus_level,
                confidence_score=0.0,
                requires_human_input=thread.status == "needs_human_input",
            )

    def _parse_summary_response(
        self,
        response_content: str,
        thread: DiscussionThread,
        participating_roles: List[str],
    ) -> DiscussionSummary:
        """Parse LLM response into structured discussion summary."""

        lines = response_content.strip().split("\n")

        key_points = []
        areas_of_agreement = []
        areas_of_disagreement = []
        recommended_actions = []
        unresolved_issues = []

        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect section headers
            if any(keyword in line.lower() for keyword in ["key point", "main point"]):
                current_section = "key_points"
                continue
            elif any(
                keyword in line.lower()
                for keyword in ["agreement", "consensus", "agree"]
            ):
                current_section = "agreement"
                continue
            elif any(
                keyword in line.lower()
                for keyword in ["disagreement", "conflict", "dispute"]
            ):
                current_section = "disagreement"
                continue
            elif any(
                keyword in line.lower()
                for keyword in ["recommend", "action", "next step"]
            ):
                current_section = "actions"
                continue
            elif any(
                keyword in line.lower()
                for keyword in ["unresolved", "issue", "problem"]
            ):
                current_section = "unresolved"
                continue

            # Add content to appropriate section
            if current_section == "key_points":
                key_points.append(line)
            elif current_section == "agreement":
                areas_of_agreement.append(line)
            elif current_section == "disagreement":
                areas_of_disagreement.append(line)
            elif current_section == "actions":
                recommended_actions.append(line)
            elif current_section == "unresolved":
                unresolved_issues.append(line)

        # Calculate confidence based on consensus and clarity
        confidence_score = thread.consensus_level * 0.7 + (
            0.3 if key_points and recommended_actions else 0.0
        )

        return DiscussionSummary(
            conversation_id=thread.conversation_id,
            discussion_topic=thread.topic,
            participating_roles=participating_roles,
            key_points=key_points,
            areas_of_agreement=areas_of_agreement,
            areas_of_disagreement=areas_of_disagreement,
            recommended_actions=recommended_actions,
            unresolved_issues=unresolved_issues,
            overall_consensus=thread.consensus_level,
            confidence_score=confidence_score,
            requires_human_input=thread.status == "needs_human_input",
        )

    async def check_consensus_status(self, thread_id: str) -> Dict[str, Any]:
        """Check the current consensus status of a discussion thread."""

        thread = self.database.get_discussion_thread(thread_id)
        if not thread:
            return {"error": "Discussion thread not found"}

        consensus = thread.calculate_consensus()

        return {
            "thread_id": thread_id,
            "topic": thread.topic,
            "consensus_level": consensus,
            "status": thread.status,
            "participating_roles": [p.role_name for p in thread.perspectives],
            "requires_human_input": thread.status == "needs_human_input",
            "perspective_count": len(thread.perspectives),
            "updated_at": thread.updated_at.isoformat(),
        }

    async def resume_discussion(
        self, thread_id: str, additional_input: Optional[str] = None
    ) -> DiscussionThread:
        """Resume a discussion that was marked as needing human input."""

        thread = self.database.get_discussion_thread(thread_id)
        if not thread:
            raise ValueError(f"Discussion thread {thread_id} not found")

        if additional_input:
            # Add human input as a system perspective
            human_perspective = RolePerspective(
                role_name="human-facilitator",
                viewpoint=additional_input,
                confidence_level=1.0,
            )
            thread.add_perspective(human_perspective)

        # Reset status and try one more discussion round
        thread.status = "active"

        # Get conversation details for context
        conversation = self.database.get_conversation(thread.conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {thread.conversation_id} not found")

        # Conduct one more round with the additional input
        await self._conduct_discussion_round(
            thread, conversation.description, conversation.repositories
        )

        # Update consensus
        consensus = thread.calculate_consensus()
        if consensus >= self.config.auto_consensus_threshold / 100.0:
            thread.status = "resolved"
        else:
            thread.status = "needs_human_input"

        self.database.save_discussion_thread(thread)

        return thread
