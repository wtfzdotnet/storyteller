"""Cross-repository conversation management system."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from config import Config, get_config
from database import DatabaseManager
from models import Conversation, ConversationParticipant, Message
from multi_repo_context import MultiRepositoryContextReader

if TYPE_CHECKING:
    from models import DiscussionSummary, DiscussionThread

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages cross-repository conversations and decision-making processes."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.database = DatabaseManager()
        self.context_reader = MultiRepositoryContextReader(self.config)

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

    async def start_discussion(
        self,
        topic: str,
        story_content: str,
        repositories: List[str],
        required_roles: Optional[List[str]] = None,
        max_discussion_rounds: int = 3,
    ) -> "DiscussionThread":
        """
        Start a multi-role discussion simulation.

        This is a convenience method that creates a discussion engine instance
        and delegates to it for the actual discussion simulation.
        """
        from discussion_engine import DiscussionEngine

        discussion_engine = DiscussionEngine(self.config)

        return await discussion_engine.start_discussion(
            topic=topic,
            story_content=story_content,
            repositories=repositories,
            required_roles=required_roles,
            max_discussion_rounds=max_discussion_rounds,
        )

    async def generate_discussion_summary(
        self, conversation_id: str
    ) -> Optional["DiscussionSummary"]:
        """Generate a summary for discussions in a conversation."""
        from discussion_engine import DiscussionEngine

        # Get discussion threads for this conversation
        threads = self.database.list_discussion_threads(conversation_id=conversation_id)

        if not threads:
            logger.warning(
                f"No discussion threads found for conversation {conversation_id}"
            )
            return None

        # Use the most recent thread for summary generation
        latest_thread = threads[0]  # Already sorted by created_at DESC

        discussion_engine = DiscussionEngine(self.config)
        return await discussion_engine.generate_discussion_summary(latest_thread)

    async def check_discussion_consensus(self, conversation_id: str) -> Dict[str, Any]:
        """Check consensus status for all discussions in a conversation."""
        threads = self.database.list_discussion_threads(conversation_id=conversation_id)

        if not threads:
            return {
                "conversation_id": conversation_id,
                "has_discussions": False,
                "overall_consensus": 0.0,
                "threads": [],
            }

        thread_summaries = []
        total_consensus = 0.0

        for thread in threads:
            consensus = thread.calculate_consensus()
            thread_summaries.append(
                {
                    "thread_id": thread.id,
                    "topic": thread.topic,
                    "consensus_level": consensus,
                    "status": thread.status,
                    "participating_roles": [p.role_name for p in thread.perspectives],
                }
            )
            total_consensus += consensus

        overall_consensus = total_consensus / len(threads) if threads else 0.0

        return {
            "conversation_id": conversation_id,
            "has_discussions": True,
            "overall_consensus": overall_consensus,
            "thread_count": len(threads),
            "threads": thread_summaries,
            "requires_human_input": any(
                t.status == "needs_human_input" for t in threads
            ),
        }
