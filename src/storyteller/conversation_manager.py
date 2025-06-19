"""Cross-repository conversation management system."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from .config import Config, get_config
    from .consensus_engine import ConsensusEngine
    from .database import DatabaseManager
    from .models import Conversation, ConversationParticipant, Message, VotingPosition
    from .multi_repo_context import MultiRepositoryContextReader
except ImportError:
    # Fallback for existing tests
    from config import Config, get_config
    from consensus_engine import ConsensusEngine
    from database import DatabaseManager
    from models import Conversation, ConversationParticipant, Message, VotingPosition
    from multi_repo_context import MultiRepositoryContextReader

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages cross-repository conversations and decision-making processes."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.database = DatabaseManager()
        self.context_reader = MultiRepositoryContextReader(self.config)
        self.consensus_engine = ConsensusEngine(self.config)

    async def create_conversation(
        self,
        title: str,
        description: str,
        repositories: List[str],
        initial_participants: Optional[List[Dict[str, str]]] = None,
    ) -> Conversation:
        """Create a new cross-repository conversation."""

        conversation = Conversation(
            title=title,
            description=description,
            repositories=repositories,
        )

        # Add initial participants if provided
        if initial_participants:
            for participant_data in initial_participants:
                participant = ConversationParticipant(
                    name=participant_data.get("name", ""),
                    role=participant_data.get("role", ""),
                    repository=participant_data.get("repository"),
                )
                conversation.participants.append(participant)

        # Save to database
        self.database.save_conversation(conversation)

        logger.info(
            f"Created conversation: {conversation.id} for repositories: {repositories}"
        )
        return conversation

    async def add_participant(
        self,
        conversation_id: str,
        name: str,
        role: str,
        repository: Optional[str] = None,
    ) -> ConversationParticipant:
        """Add a participant to an existing conversation."""

        conversation = self.database.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        participant = ConversationParticipant(
            name=name,
            role=role,
            repository=repository,
        )

        conversation.participants.append(participant)
        self.database.save_conversation(conversation)

        logger.info(
            f"Added participant {name} ({role}) to conversation {conversation_id}"
        )
        return participant

    async def add_message(
        self,
        conversation_id: str,
        participant_id: str,
        content: str,
        message_type: str = "text",
        repository_context: Optional[str] = None,
    ) -> Message:
        """Add a message to a conversation."""

        conversation = self.database.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Verify participant exists
        participant = next(
            (p for p in conversation.participants if p.id == participant_id), None
        )
        if not participant:
            raise ValueError(f"Participant {participant_id} not found in conversation")

        message = conversation.add_message(
            participant_id=participant_id,
            content=content,
            message_type=message_type,
            repository_context=repository_context,
        )

        self.database.save_conversation(conversation)

        logger.info(
            f"Added message to conversation {conversation_id} from {participant.name}"
        )
        return message

    async def add_context_message(
        self,
        conversation_id: str,
        participant_id: str,
        repository: str,
        context_summary: str,
    ) -> Message:
        """Add a context-sharing message with repository information."""

        # Get repository context
        try:
            repo_context = await self.context_reader.get_repository_context(repository)
            if repo_context:
                context_content = f"**Repository Context: {repository}**\n\n"
                context_content += f"Type: {repo_context.repo_type}\n"
                context_content += f"Description: {repo_context.description}\n"
                context_content += (
                    f"Key Files: {len(repo_context.key_files)} files analyzed\n"
                )
                context_content += (
                    f"Languages: {', '.join(repo_context.languages.keys())}\n\n"
                )
                context_content += f"Summary: {context_summary}"
            else:
                context_content = (
                    f"**Repository Context: {repository}**\n\n{context_summary}"
                )
        except Exception as e:
            logger.warning(f"Failed to get repository context for {repository}: {e}")
            context_content = (
                f"**Repository Context: {repository}**\n\n{context_summary}"
            )

        return await self.add_message(
            conversation_id=conversation_id,
            participant_id=participant_id,
            content=context_content,
            message_type="context_share",
            repository_context=repository,
        )

    async def add_decision_message(
        self,
        conversation_id: str,
        participant_id: str,
        decision: str,
        repositories_affected: Optional[List[str]] = None,
    ) -> Message:
        """Add a decision message to the conversation."""

        content = f"**Decision Made**\n\n{decision}"
        if repositories_affected:
            content += (
                f"\n\n**Repositories Affected**: {', '.join(repositories_affected)}"
            )

        message = await self.add_message(
            conversation_id=conversation_id,
            participant_id=participant_id,
            content=content,
            message_type="decision",
        )

        # Update conversation with decision summary
        conversation = self.database.get_conversation(conversation_id)
        if conversation and not conversation.decision_summary:
            conversation.decision_summary = decision
            conversation.status = "resolved"
            self.database.save_conversation(conversation)

        return message

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.database.get_conversation(conversation_id)

    def list_conversations(
        self, repository: Optional[str] = None, status: Optional[str] = None
    ) -> List[Conversation]:
        """List conversations, optionally filtered by repository or status."""
        return self.database.list_conversations(repository=repository, status=status)

    def get_conversation_history(self, conversation_id: str) -> Dict[str, Any]:
        """Get formatted conversation history."""

        conversation = self.database.get_conversation(conversation_id)
        if not conversation:
            return {"error": "Conversation not found"}

        history = {
            "conversation": conversation.get_conversation_summary(),
            "participants": [p.to_dict() for p in conversation.participants],
            "messages": [],
            "repository_summary": {},
        }

        # Format messages
        for message in conversation.messages:
            participant = next(
                (
                    p
                    for p in conversation.participants
                    if p.id == message.participant_id
                ),
                None,
            )

            history["messages"].append(
                {
                    "id": message.id,
                    "participant": participant.name if participant else "Unknown",
                    "role": participant.role if participant else "Unknown",
                    "content": message.content,
                    "type": message.message_type,
                    "repository_context": message.repository_context,
                    "created_at": message.created_at.isoformat(),
                }
            )

        # Repository-specific summaries
        for repository in conversation.repositories:
            repo_messages = conversation.get_messages_by_repository(repository)
            repo_participants = conversation.get_participants_by_repository(repository)

            history["repository_summary"][repository] = {
                "message_count": len(repo_messages),
                "participant_count": len(repo_participants),
                "participants": [p.name for p in repo_participants],
            }

        return history

    async def get_cross_repository_insights(
        self, conversation_id: str
    ) -> Dict[str, Any]:
        """Generate insights about cross-repository implications from the conversation."""

        conversation = self.database.get_conversation(conversation_id)
        if not conversation:
            return {"error": "Conversation not found"}

        insights = {
            "repositories_involved": conversation.repositories,
            "decision_status": conversation.status,
            "key_decisions": [],
            "repository_impacts": {},
            "cross_repo_dependencies": [],
        }

        # Extract decisions from messages
        decision_messages = [
            msg for msg in conversation.messages if msg.message_type == "decision"
        ]
        insights["key_decisions"] = [msg.content for msg in decision_messages]

        # Analyze repository impacts
        for repository in conversation.repositories:
            repo_messages = conversation.get_messages_by_repository(repository)
            context_messages = [
                msg for msg in repo_messages if msg.message_type == "context_share"
            ]

            insights["repository_impacts"][repository] = {
                "message_count": len(repo_messages),
                "context_shares": len(context_messages),
                "has_decisions": any(
                    msg.message_type == "decision" for msg in repo_messages
                ),
            }

        # Identify potential cross-repository dependencies
        for message in conversation.messages:
            if message.message_type == "context_share" and message.repository_context:
                for other_repo in conversation.repositories:
                    if (
                        other_repo != message.repository_context
                        and other_repo.lower() in message.content.lower()
                    ):
                        dependency = {
                            "from": message.repository_context,
                            "to": other_repo,
                            "mentioned_in": message.id,
                        }
                        if dependency not in insights["cross_repo_dependencies"]:
                            insights["cross_repo_dependencies"].append(dependency)

        return insights

    def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a completed conversation."""

        conversation = self.database.get_conversation(conversation_id)
        if not conversation:
            return False

        conversation.status = "archived"
        conversation.updated_at = datetime.now(timezone.utc)
        self.database.save_conversation(conversation)

        logger.info(f"Archived conversation: {conversation_id}")
        return True

    async def initiate_consensus(
        self,
        conversation_id: str,
        decision_topic: str,
        required_roles: Optional[List[str]] = None,
        threshold: Optional[float] = None,
    ) -> str:
        """Initiate a consensus process for a conversation."""

        conversation = self.database.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create consensus process
        consensus = self.consensus_engine.create_consensus_process(
            conversation_id=conversation_id,
            decision_topic=decision_topic,
            required_roles=required_roles,
            threshold=threshold,
        )

        # Add system message about consensus initiation
        system_participant = ConversationParticipant(
            name="Consensus System",
            role="system",
        )
        conversation.participants.append(system_participant)

        consensus_message = f"""**Consensus Process Initiated**

Decision Topic: {decision_topic}
Consensus ID: {consensus.id}
Threshold: {consensus.threshold:.0%}
Required Roles: {', '.join(required_roles) if required_roles else 'None specified'}

Please provide your position on this decision."""

        await self.add_message(
            conversation_id=conversation_id,
            participant_id=system_participant.id,
            content=consensus_message,
            message_type="consensus_initiation",
        )

        logger.info(
            f"Initiated consensus {consensus.id} for conversation {conversation_id}"
        )

        return consensus.id

    async def submit_consensus_vote(
        self,
        conversation_id: str,
        consensus_id: str,
        participant_id: str,
        role_name: str,
        position: str,  # "agree", "disagree", "abstain", "needs_clarification"
        confidence: float = 0.8,
        rationale: str = "",
        concerns: Optional[List[str]] = None,
        suggestions: Optional[List[str]] = None,
    ) -> bool:
        """Submit a vote for a consensus process."""

        # Validate inputs
        try:
            voting_position = VotingPosition(position.lower())
        except ValueError:
            raise ValueError(f"Invalid voting position: {position}")

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

        # Get the consensus process (would need to be stored in database)
        # For now, create a temporary one for demonstration
        consensus = self.consensus_engine.create_consensus_process(
            conversation_id=conversation_id,
            decision_topic="Retrieved from storage",  # This would be retrieved
        )
        consensus.id = consensus_id  # Override with provided ID

        # Add the vote
        vote = self.consensus_engine.add_role_vote(
            consensus=consensus,
            role_name=role_name,
            participant_id=participant_id,
            position=voting_position,
            confidence=confidence,
            rationale=rationale,
            concerns=concerns,
            suggestions=suggestions,
        )

        # Add message about the vote
        vote_content = f"""**Consensus Vote Submitted**

Position: {position.title()}
Confidence: {confidence:.0%}
Rationale: {rationale}"""

        if concerns:
            vote_content += f"\n\nConcerns:\n" + "\n".join(
                f"• {concern}" for concern in concerns
            )

        if suggestions:
            vote_content += f"\n\nSuggestions:\n" + "\n".join(
                f"• suggestion" for suggestion in suggestions
            )

        await self.add_message(
            conversation_id=conversation_id,
            participant_id=participant_id,
            content=vote_content,
            message_type="consensus_vote",
        )

        # Check if consensus is reached
        status = self.consensus_engine.check_consensus_status(consensus)
        if status.value in ["reached", "failed", "timeout"]:
            await self._finalize_consensus(conversation_id, consensus)

        logger.info(
            f"Vote submitted by {role_name} for consensus {consensus_id}: {position}"
        )

        return True

    async def _finalize_consensus(self, conversation_id: str, consensus) -> None:
        """Finalize a consensus process and add result message."""

        # Generate comprehensive report
        report = self.consensus_engine.generate_consensus_report(consensus)

        # Create finalization message
        if consensus.status.value == "reached":
            result_content = f"""**🎉 Consensus Reached**

Decision: {consensus.decision}
Final Score: {consensus.achieved_score:.0%} (required: {consensus.threshold:.0%})

{consensus.rationale}

**Next Steps:**
The decision has been approved and can proceed to implementation."""

        elif consensus.status.value == "failed":
            result_content = f"""**❌ Consensus Failed**

Decision: {consensus.decision}
Final Score: {consensus.achieved_score:.0%} (required: {consensus.threshold:.0%})

{consensus.rationale}

**Remaining Concerns:**
""" + "\n".join(
                f"• {concern}" for concern in consensus.get_dissenting_concerns()[:5]
            )

            result_content += """

**Next Steps:**
Manual review required. Consider addressing concerns or modifying the proposal."""

        else:  # timeout
            result_content = f"""**⏰ Consensus Process Timeout**

Decision: {consensus.decision}
Final Score: {consensus.achieved_score:.0%} (required: {consensus.threshold:.0%})
Iterations: {consensus.iterations}/{consensus.max_iterations}

{consensus.rationale}

**Next Steps:**
Manual intervention required to complete the decision process."""

        # Add system participant if not exists
        system_participants = [
            p
            for p in await self._get_conversation_participants(conversation_id)
            if p.role == "system"
        ]
        if system_participants:
            system_participant_id = system_participants[0].id
        else:
            system_participant = ConversationParticipant(
                name="Consensus System",
                role="system",
            )
            conversation = self.database.get_conversation(conversation_id)
            conversation.participants.append(system_participant)
            system_participant_id = system_participant.id

        await self.add_message(
            conversation_id=conversation_id,
            participant_id=system_participant_id,
            content=result_content,
            message_type="consensus_result",
        )

        logger.info(
            f"Finalized consensus {consensus.id} with status: {consensus.status.value}"
        )

    async def _get_conversation_participants(
        self, conversation_id: str
    ) -> List[ConversationParticipant]:
        """Get participants for a conversation."""
        conversation = self.database.get_conversation(conversation_id)
        return conversation.participants if conversation else []

    async def get_consensus_status(
        self, conversation_id: str, consensus_id: str
    ) -> Dict[str, Any]:
        """Get the current status of a consensus process."""

        # This is a simplified implementation
        # In a real implementation, you'd retrieve the consensus from storage
        consensus = self.consensus_engine.create_consensus_process(
            conversation_id=conversation_id,
            decision_topic="Retrieved from storage",
        )
        consensus.id = consensus_id

        report = self.consensus_engine.generate_consensus_report(consensus)

        return {
            "consensus_id": consensus_id,
            "conversation_id": conversation_id,
            "status": report["status"],
            "current_score": report["metrics"]["weighted_score"],
            "threshold": report["metrics"]["threshold"],
            "participating_roles": report["role_analysis"]["participating_roles"],
            "missing_required_roles": report["role_analysis"]["missing_required_roles"],
            "vote_distribution": report["vote_distribution"],
            "iterations": report["metrics"]["iterations"],
        }

    async def auto_resolve_consensus_conflicts(
        self, conversation_id: str, consensus_id: str
    ) -> Dict[str, Any]:
        """Attempt automatic resolution of consensus conflicts."""

        # This is a simplified implementation
        consensus = self.consensus_engine.create_consensus_process(
            conversation_id=conversation_id,
            decision_topic="Retrieved from storage",
        )
        consensus.id = consensus_id

        # Attempt auto-resolution
        resolved = self.consensus_engine.auto_resolve_minor_conflicts(consensus)

        if resolved:
            # Add message about auto-resolution
            system_participants = [
                p
                for p in await self._get_conversation_participants(conversation_id)
                if p.role == "system"
            ]
            if system_participants:
                await self.add_message(
                    conversation_id=conversation_id,
                    participant_id=system_participants[0].id,
                    content="**Minor conflicts have been automatically resolved.** Consensus process updated.",
                    message_type="system",
                )

        # Check if consensus is now reached
        status = self.consensus_engine.check_consensus_status(consensus)
        if status.value in ["reached", "failed"]:
            await self._finalize_consensus(conversation_id, consensus)

        return {
            "resolved": resolved,
            "new_status": status.value,
            "current_score": consensus.calculate_consensus_score(),
        }

    async def trigger_manual_intervention(
        self,
        conversation_id: str,
        consensus_id: str,
        trigger_reason: str = "manual_request",
        intervention_type: str = "decision",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Trigger a manual intervention for a consensus process."""

        conversation = self.database.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create consensus object for intervention
        consensus = self.consensus_engine.create_consensus_process(
            conversation_id=conversation_id,
            decision_topic="Retrieved from storage",
        )
        consensus.id = consensus_id

        # Trigger intervention
        intervention_id = self.consensus_engine.trigger_manual_intervention(
            consensus=consensus,
            conversation_id=conversation_id,
            trigger_reason=trigger_reason,
            intervention_type=intervention_type,
            metadata=metadata,
        )

        # Add system message about intervention
        system_participants = [
            p for p in conversation.participants if p.role == "system"
        ]
        if system_participants:
            await self.add_message(
                conversation_id=conversation_id,
                participant_id=system_participants[0].id,
                content=f"**Manual Intervention Triggered**\n\nIntervention ID: {intervention_id}\nReason: {trigger_reason}\nType: {intervention_type}\n\nA human decision maker will review this consensus process.",
                message_type="intervention",
            )

        logger.info(
            f"Triggered manual intervention {intervention_id} for conversation {conversation_id}"
        )

        return intervention_id

    async def resolve_manual_intervention(
        self,
        intervention_id: str,
        human_decision: str,
        human_rationale: str,
        intervener_id: str,
        intervener_role: str = "project-manager",
        override_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Resolve a manual intervention with human decision."""

        # Get intervention details
        intervention = self.database.get_manual_intervention(intervention_id)
        if not intervention:
            raise ValueError(f"Manual intervention {intervention_id} not found")

        # Resolve the intervention
        success = self.consensus_engine.resolve_manual_intervention(
            intervention_id=intervention_id,
            human_decision=human_decision,
            human_rationale=human_rationale,
            intervener_id=intervener_id,
            intervener_role=intervener_role,
            override_data=override_data,
        )

        if success:
            # Add system message about resolution
            conversation = self.database.get_conversation(intervention.conversation_id)
            if conversation:
                system_participants = [
                    p for p in conversation.participants if p.role == "system"
                ]
                if system_participants:
                    await self.add_message(
                        conversation_id=intervention.conversation_id,
                        participant_id=system_participants[0].id,
                        content=f"**Manual Intervention Resolved**\n\nIntervention ID: {intervention_id}\nDecision: {human_decision}\nRationale: {human_rationale}\nResolved by: {intervener_role}\n\nThis decision overrides the automated consensus process.",
                        message_type="intervention_resolution",
                    )

            logger.info(
                f"Resolved manual intervention {intervention_id} in conversation {intervention.conversation_id}"
            )

        return success

    async def check_and_trigger_intervention_if_needed(
        self, conversation_id: str, consensus_id: str
    ) -> Optional[str]:
        """Check if consensus requires intervention and trigger if needed."""

        # Create consensus object for checking
        consensus = self.consensus_engine.create_consensus_process(
            conversation_id=conversation_id,
            decision_topic="Retrieved from storage",
        )
        consensus.id = consensus_id

        # Check if intervention is needed
        requires_intervention, reason = (
            self.consensus_engine.check_consensus_requires_intervention(consensus)
        )

        if requires_intervention:
            return await self.trigger_manual_intervention(
                conversation_id=conversation_id,
                consensus_id=consensus_id,
                trigger_reason=reason,
                intervention_type="decision",
            )

        return None

    def get_pending_interventions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending manual interventions."""
        interventions = self.database.get_pending_interventions(limit)
        return [
            {
                "id": intervention.id,
                "conversation_id": intervention.conversation_id,
                "consensus_id": intervention.consensus_id,
                "trigger_reason": intervention.trigger_reason,
                "intervention_type": intervention.intervention_type,
                "original_decision": intervention.original_decision,
                "triggered_at": intervention.triggered_at.isoformat(),
                "affected_roles": intervention.affected_roles,
                "metadata": intervention.metadata,
            }
            for intervention in interventions
        ]

    def get_intervention_status(self, intervention_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a manual intervention."""
        intervention = self.database.get_manual_intervention(intervention_id)
        if not intervention:
            return None

        return {
            "id": intervention.id,
            "conversation_id": intervention.conversation_id,
            "consensus_id": intervention.consensus_id,
            "status": intervention.status,
            "trigger_reason": intervention.trigger_reason,
            "intervention_type": intervention.intervention_type,
            "original_decision": intervention.original_decision,
            "human_decision": intervention.human_decision,
            "human_rationale": intervention.human_rationale,
            "intervener_id": intervention.intervener_id,
            "intervener_role": intervention.intervener_role,
            "triggered_at": intervention.triggered_at.isoformat(),
            "resolved_at": (
                intervention.resolved_at.isoformat()
                if intervention.resolved_at
                else None
            ),
            "affected_roles": intervention.affected_roles,
            "audit_trail": intervention.audit_trail,
            "metadata": intervention.metadata,
        }
