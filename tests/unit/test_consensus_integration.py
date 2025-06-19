"""Integration tests for consensus functionality with conversation manager."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import os

# Set up environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"

from src.storyteller.conversation_manager import ConversationManager
from src.storyteller.models import VotingPosition


class TestConversationManagerConsensusIntegration:
    """Test integration between ConversationManager and ConsensusEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock the database and context reader to avoid actual I/O
        with patch('src.storyteller.conversation_manager.DatabaseManager'), \
             patch('src.storyteller.conversation_manager.MultiRepositoryContextReader'):
            self.manager = ConversationManager()

    @pytest.mark.asyncio
    async def test_initiate_consensus_process(self):
        """Test initiating a consensus process through conversation manager."""
        
        # Mock conversation exists
        mock_conversation = Mock()
        mock_conversation.participants = []
        self.manager.database.get_conversation = Mock(return_value=mock_conversation)
        
        # Mock add_message to avoid database calls
        self.manager.add_message = AsyncMock()

        consensus_id = await self.manager.initiate_consensus(
            conversation_id="conv_123",
            decision_topic="Should we implement feature X?",
            required_roles=["system-architect", "lead-developer"],
            threshold=0.7,
        )

        assert consensus_id is not None
        assert consensus_id.startswith("consensus_")
        
        # Verify system message was added
        self.manager.add_message.assert_called_once()
        call_args = self.manager.add_message.call_args
        assert "Consensus Process Initiated" in call_args[1]["content"]
        assert call_args[1]["message_type"] == "consensus_initiation"

    @pytest.mark.asyncio
    async def test_submit_consensus_vote(self):
        """Test submitting a vote through conversation manager."""
        
        # Mock add_message to avoid database calls
        self.manager.add_message = AsyncMock()

        result = await self.manager.submit_consensus_vote(
            conversation_id="conv_123",
            consensus_id="consensus_456",
            participant_id="participant_1",
            role_name="system-architect",
            position="agree",
            confidence=0.9,
            rationale="This aligns with our architecture goals",
            concerns=[],
            suggestions=["Consider caching layer"],
        )

        assert result is True
        
        # Verify vote message was added (and possibly consensus finalization)
        assert self.manager.add_message.call_count >= 1
        
        # Check that at least one call was for the vote
        vote_call_found = False
        for call in self.manager.add_message.call_args_list:
            if call[1]["message_type"] == "consensus_vote":
                vote_call_found = True
                content = call[1]["content"]
                assert "Consensus Vote Submitted" in content
                assert "Position: Agree" in content
                break
        assert vote_call_found, "Vote message not found in calls"

    @pytest.mark.asyncio
    async def test_consensus_workflow_complete(self):
        """Test a complete consensus workflow from initiation to completion."""
        
        # Mock conversation and database operations
        mock_conversation = Mock()
        mock_conversation.participants = []
        self.manager.database.get_conversation = Mock(return_value=mock_conversation)
        self.manager.add_message = AsyncMock()
        
        # Step 1: Initiate consensus
        consensus_id = await self.manager.initiate_consensus(
            conversation_id="conv_123",
            decision_topic="Implement microservices architecture",
            required_roles=["system-architect", "lead-developer"],
            threshold=0.8,
        )

        # Step 2: Submit agreement votes
        await self.manager.submit_consensus_vote(
            conversation_id="conv_123",
            consensus_id=consensus_id,
            participant_id="p1",
            role_name="system-architect",
            position="agree",
            confidence=0.9,
            rationale="Improves scalability",
        )

        await self.manager.submit_consensus_vote(
            conversation_id="conv_123",
            consensus_id=consensus_id,
            participant_id="p2",
            role_name="lead-developer",
            position="agree",
            confidence=0.8,
            rationale="Enables better team structure",
        )

        # Verify multiple messages were added (initiation + 2 votes)
        assert self.manager.add_message.call_count >= 3

    @pytest.mark.asyncio
    async def test_consensus_with_disagreement(self):
        """Test consensus process with disagreement."""
        
        mock_conversation = Mock()
        mock_conversation.participants = []
        self.manager.database.get_conversation = Mock(return_value=mock_conversation)
        self.manager.add_message = AsyncMock()

        consensus_id = await self.manager.initiate_consensus(
            conversation_id="conv_123",
            decision_topic="Adopt new technology stack",
            threshold=0.7,
        )

        # Submit disagreement vote
        await self.manager.submit_consensus_vote(
            conversation_id="conv_123",
            consensus_id=consensus_id,
            participant_id="p1",
            role_name="security-expert",
            position="disagree",
            confidence=0.9,
            rationale="Security concerns not addressed",
            concerns=["No security audit", "Third-party dependencies"],
        )

        # Verify disagreement message includes concerns
        vote_call = None
        for call in self.manager.add_message.call_args_list:
            if call[1]["message_type"] == "consensus_vote":
                vote_call = call
                break
        
        assert vote_call is not None
        content = vote_call[1]["content"]
        assert "Position: Disagree" in content
        assert "Security concerns not addressed" in content
        assert "No security audit" in content

    @pytest.mark.asyncio
    async def test_get_consensus_status(self):
        """Test getting consensus status."""
        
        status = await self.manager.get_consensus_status(
            conversation_id="conv_123",
            consensus_id="consensus_456",
        )

        assert "consensus_id" in status
        assert "status" in status
        assert "current_score" in status
        assert "threshold" in status
        assert "vote_distribution" in status

    @pytest.mark.asyncio
    async def test_auto_resolve_conflicts(self):
        """Test automatic conflict resolution."""
        
        mock_conversation = Mock()
        mock_conversation.participants = [Mock(role="system", id="system_1")]
        self.manager.database.get_conversation = Mock(return_value=mock_conversation)
        self.manager.add_message = AsyncMock()

        result = await self.manager.auto_resolve_consensus_conflicts(
            conversation_id="conv_123",
            consensus_id="consensus_456",
        )

        assert "resolved" in result
        assert "new_status" in result
        assert "current_score" in result

    @pytest.mark.asyncio
    async def test_invalid_voting_position(self):
        """Test error handling for invalid voting positions."""
        
        with pytest.raises(ValueError, match="Invalid voting position"):
            await self.manager.submit_consensus_vote(
                conversation_id="conv_123",
                consensus_id="consensus_456",
                participant_id="p1",
                role_name="developer",
                position="invalid_position",  # Invalid position
                confidence=0.8,
            )

    @pytest.mark.asyncio
    async def test_invalid_confidence_level(self):
        """Test error handling for invalid confidence levels."""
        
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            await self.manager.submit_consensus_vote(
                conversation_id="conv_123",
                consensus_id="consensus_456",
                participant_id="p1",
                role_name="developer",
                position="agree",
                confidence=1.5,  # Invalid confidence
            )

    def test_consensus_engine_integration(self):
        """Test that ConversationManager properly integrates ConsensusEngine."""
        
        # Verify consensus engine is initialized
        assert hasattr(self.manager, 'consensus_engine')
        assert self.manager.consensus_engine is not None
        
        # Verify it has the expected role weights
        assert self.manager.consensus_engine.get_role_weight("system-architect") == 1.5
        assert self.manager.consensus_engine.get_role_weight("lead-developer") == 1.3
        assert self.manager.consensus_engine.get_role_weight("backend-developer") == 1.0

    def test_consensus_configuration_integration(self):
        """Test that consensus engine uses configuration from ConversationManager."""
        
        # Verify the consensus engine uses the same config
        assert self.manager.consensus_engine.config == self.manager.config
        
        # Test that auto_consensus settings are properly passed
        if hasattr(self.manager.config, 'auto_consensus_threshold'):
            expected_threshold = self.manager.config.auto_consensus_threshold / 100.0
            
            consensus = self.manager.consensus_engine.create_consensus_process(
                conversation_id="test",
                decision_topic="test",
            )
            
            assert consensus.threshold == expected_threshold