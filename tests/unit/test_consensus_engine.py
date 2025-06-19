"""Unit tests for consensus reaching algorithms."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.storyteller.consensus_engine import ConsensusEngine
from src.storyteller.models import (
    ConsensusResult,
    ConsensusStatus,
    RoleVote,
    VotingPosition,
)
from src.storyteller.config import Config


class TestConsensusEngine:
    """Test cases for the ConsensusEngine class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(
            github_token="test_token",
            auto_consensus_enabled=True,
            auto_consensus_threshold=70,
            auto_consensus_max_iterations=5,
        )
        self.engine = ConsensusEngine(self.config)

    def test_role_weight_initialization(self):
        """Test that role weights are properly initialized."""
        assert self.engine.get_role_weight("system-architect") == 1.5
        assert self.engine.get_role_weight("lead-developer") == 1.3
        assert self.engine.get_role_weight("backend-developer") == 1.0
        assert self.engine.get_role_weight("unknown-role") == 1.0

    def test_create_consensus_process(self):
        """Test creating a new consensus process."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Should we implement feature X?",
            required_roles=["system-architect", "lead-developer"],
            threshold=0.8,
        )

        assert consensus.conversation_id == "conv_123"
        assert consensus.decision == "Should we implement feature X?"
        assert consensus.threshold == 0.8
        assert consensus.required_roles == ["system-architect", "lead-developer"]
        assert consensus.status == ConsensusStatus.PENDING
        assert len(consensus.votes) == 0

    def test_add_role_vote(self):
        """Test adding votes from different roles."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        # Add an agreement vote
        vote = self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",
            participant_id="participant_1",
            position=VotingPosition.AGREE,
            confidence=0.9,
            rationale="This aligns with our architecture goals",
            concerns=[],
            suggestions=["Consider using pattern X"],
        )

        assert vote.role_name == "system-architect"
        assert vote.position == VotingPosition.AGREE
        assert vote.confidence == 0.9
        assert vote.weight == 1.5  # system-architect weight
        assert len(consensus.votes) == 1
        assert "system-architect" in consensus.participating_roles

    def test_add_role_vote_invalid_confidence(self):
        """Test that invalid confidence values raise errors."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            self.engine.add_role_vote(
                consensus=consensus,
                role_name="developer",
                participant_id="participant_1",
                position=VotingPosition.AGREE,
                confidence=1.5,  # Invalid confidence
            )

    def test_vote_replacement(self):
        """Test that new votes from the same role replace old ones."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        # Add initial vote
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="developer",
            participant_id="participant_1",
            position=VotingPosition.AGREE,
            confidence=0.8,
        )
        assert len(consensus.votes) == 1

        # Add another vote from same role
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="developer",
            participant_id="participant_1",
            position=VotingPosition.DISAGREE,
            confidence=0.9,
        )

        assert len(consensus.votes) == 1
        assert consensus.votes[0].position == VotingPosition.DISAGREE
        assert consensus.votes[0].confidence == 0.9

    def test_weighted_consensus_calculation(self):
        """Test the weighted consensus calculation algorithm."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        # Add high-weight agreement
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",  # weight 1.5
            participant_id="p1",
            position=VotingPosition.AGREE,
            confidence=1.0,
        )

        # Add standard-weight agreement
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="backend-developer",  # weight 1.0
            participant_id="p2",
            position=VotingPosition.AGREE,
            confidence=0.8,
        )

        score = self.engine.calculate_weighted_consensus(consensus)
        expected_score = (1.5 * 1.0 + 1.0 * 0.8) / (1.5 + 1.0)  # ~0.92
        assert abs(score - expected_score) < 0.01

    def test_consensus_with_disagreement(self):
        """Test consensus calculation with disagreeing votes."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        # Add agreement
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",  # weight 1.5
            participant_id="p1",
            position=VotingPosition.AGREE,
            confidence=1.0,
        )

        # Add disagreement
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="lead-developer",  # weight 1.3
            participant_id="p2",
            position=VotingPosition.DISAGREE,
            confidence=0.9,
        )

        score = self.engine.calculate_weighted_consensus(consensus)
        
        # Expected: (1.5 * 1.0 - 1.3 * 0.9 * 0.5) / (1.5 + 1.3)
        expected_score = (1.5 - 1.3 * 0.9 * 0.5) / (1.5 + 1.3)
        assert abs(score - expected_score) < 0.01

    def test_consensus_status_reached(self):
        """Test consensus status when threshold is reached."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
            threshold=0.6,
        )

        # Add enough agreement votes to reach threshold
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",
            participant_id="p1",
            position=VotingPosition.AGREE,
            confidence=1.0,
        )

        self.engine.add_role_vote(
            consensus=consensus,
            role_name="lead-developer",
            participant_id="p2",
            position=VotingPosition.AGREE,
            confidence=0.8,
        )

        status = self.engine.check_consensus_status(consensus)
        assert status == ConsensusStatus.REACHED
        assert consensus.completed_at is not None

    def test_consensus_status_failed(self):
        """Test consensus status when process fails due to strong disagreements."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
            threshold=0.7,
        )

        # Add strong disagreements
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",
            participant_id="p1",
            position=VotingPosition.DISAGREE,
            confidence=0.9,
            concerns=["Major security issues"],
        )

        self.engine.add_role_vote(
            consensus=consensus,
            role_name="lead-developer",
            participant_id="p2",
            position=VotingPosition.DISAGREE,
            confidence=0.8,
            concerns=["Technical feasibility concerns"],
        )

        status = self.engine.check_consensus_status(consensus)
        assert status == ConsensusStatus.FAILED

    def test_consensus_status_timeout(self):
        """Test consensus status when max iterations reached."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
            max_iterations=2,
        )

        consensus.iterations = 2  # Set to max iterations
        status = self.engine.check_consensus_status(consensus)
        assert status == ConsensusStatus.TIMEOUT

    def test_conflict_resolution_addressable_concerns(self):
        """Test conflict resolution with addressable concerns."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        # Add disagreement with addressable concerns
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="qa-engineer",
            participant_id="p1",
            position=VotingPosition.DISAGREE,
            confidence=0.7,
            concerns=["Need more testing documentation", "Timeline seems aggressive"],
        )

        success, actions, remaining = self.engine.resolve_conflicts(consensus)
        
        assert success  # Should be successful since concerns are addressable
        assert len(actions) > 0
        assert "testing" in str(actions).lower() or "timeline" in str(actions).lower()

    def test_conflict_resolution_high_expertise_disagreement(self):
        """Test conflict resolution with high expertise disagreement."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        # Add high-expertise disagreement with suggestions
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",  # High weight role
            participant_id="p1",
            position=VotingPosition.DISAGREE,
            confidence=0.9,
            concerns=["Architectural complexity"],
            suggestions=["Consider microservices approach"],
        )

        success, actions, remaining = self.engine.resolve_conflicts(consensus)
        
        assert "microservices" in str(actions).lower()

    def test_auto_resolve_minor_conflicts(self):
        """Test automatic resolution of minor conflicts."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
        )

        # Add a clarification request with suggestions
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="developer",
            participant_id="p1",
            position=VotingPosition.NEEDS_CLARIFICATION,
            confidence=0.5,
            suggestions=["Please clarify the implementation approach"],
        )

        # Add a weak disagreement without concerns
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="tester",
            participant_id="p2",
            position=VotingPosition.DISAGREE,
            confidence=0.3,  # Low confidence
            concerns=[],  # No specific concerns
        )

        resolved = self.engine.auto_resolve_minor_conflicts(consensus)
        
        assert resolved
        # Both votes should be converted to abstain
        assert all(vote.position == VotingPosition.ABSTAIN for vote in consensus.votes)

    def test_iterate_consensus(self):
        """Test consensus iteration process."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
            max_iterations=3,
        )

        # First iteration
        should_continue = self.engine.iterate_consensus(consensus)
        assert should_continue
        assert consensus.iterations == 1

        # Second iteration
        should_continue = self.engine.iterate_consensus(consensus)
        assert should_continue
        assert consensus.iterations == 2

        # Third iteration (reaches max)
        should_continue = self.engine.iterate_consensus(consensus)
        assert not should_continue
        assert consensus.iterations == 3
        assert consensus.status == ConsensusStatus.TIMEOUT

    def test_generate_consensus_report(self):
        """Test comprehensive consensus report generation."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
            required_roles=["system-architect", "lead-developer"],
            threshold=0.7,
        )

        # Add some votes
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",
            participant_id="p1",
            position=VotingPosition.AGREE,
            confidence=0.9,
        )

        self.engine.add_role_vote(
            consensus=consensus,
            role_name="backend-developer",
            participant_id="p2",
            position=VotingPosition.DISAGREE,
            confidence=0.6,
            concerns=["Performance implications"],
        )

        report = self.engine.generate_consensus_report(consensus)

        assert report["consensus_id"] == consensus.id
        assert report["conversation_id"] == "conv_123"
        assert report["decision"] == "Test decision"
        assert "metrics" in report
        assert "vote_distribution" in report
        assert "role_analysis" in report
        assert "conflict_resolution" in report

        # Check vote distribution
        assert report["vote_distribution"]["agree"] == 1
        assert report["vote_distribution"]["disagree"] == 1

        # Check role analysis
        assert "system-architect" in report["role_analysis"]["participating_roles"]
        assert "lead-developer" in report["role_analysis"]["missing_required_roles"]

    def test_consensus_with_required_roles(self):
        """Test consensus process with required role participation."""
        consensus = self.engine.create_consensus_process(
            conversation_id="conv_123",
            decision_topic="Test decision",
            required_roles=["system-architect", "lead-developer"],
            threshold=0.6,
        )

        # Add vote from system-architect only
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="system-architect",
            participant_id="p1",
            position=VotingPosition.AGREE,
            confidence=1.0,
        )

        # Even though score might be high, consensus not reached due to missing required role
        assert not consensus.check_consensus_reached()

        # Add vote from required lead-developer
        self.engine.add_role_vote(
            consensus=consensus,
            role_name="lead-developer",
            participant_id="p2",
            position=VotingPosition.AGREE,
            confidence=0.8,
        )

        # Now consensus should be reached
        assert consensus.check_consensus_reached()


class TestRoleVote:
    """Test cases for the RoleVote data model."""

    def test_role_vote_creation(self):
        """Test creating a role vote."""
        vote = RoleVote(
            role_name="system-architect",
            participant_id="p1",
            position=VotingPosition.AGREE,
            confidence=0.9,
            weight=1.5,
            rationale="Aligns with system design",
            concerns=["Performance considerations"],
            suggestions=["Use caching"],
        )

        assert vote.role_name == "system-architect"
        assert vote.position == VotingPosition.AGREE
        assert vote.confidence == 0.9
        assert vote.weight == 1.5
        assert "Performance" in vote.concerns[0]

    def test_role_vote_serialization(self):
        """Test role vote to_dict and from_dict methods."""
        original_vote = RoleVote(
            role_name="developer",
            participant_id="p1",
            position=VotingPosition.DISAGREE,
            confidence=0.7,
            concerns=["Timeline concern"],
            suggestions=["Add more time"],
        )

        # Serialize to dict
        vote_dict = original_vote.to_dict()
        assert vote_dict["role_name"] == "developer"
        assert vote_dict["position"] == "disagree"
        assert vote_dict["confidence"] == 0.7

        # Deserialize back
        restored_vote = RoleVote.from_dict(vote_dict)
        assert restored_vote.role_name == original_vote.role_name
        assert restored_vote.position == original_vote.position
        assert restored_vote.confidence == original_vote.confidence
        assert restored_vote.concerns == original_vote.concerns


class TestConsensusResult:
    """Test cases for the ConsensusResult data model."""

    def test_consensus_result_creation(self):
        """Test creating a consensus result."""
        consensus = ConsensusResult(
            conversation_id="conv_123",
            threshold=0.7,
            required_roles=["system-architect"],
            max_iterations=5,
        )

        assert consensus.conversation_id == "conv_123"
        assert consensus.threshold == 0.7
        assert consensus.status == ConsensusStatus.PENDING
        assert len(consensus.votes) == 0

    def test_add_vote_to_consensus(self):
        """Test adding votes to consensus result."""
        consensus = ConsensusResult()
        
        vote1 = RoleVote(role_name="developer", position=VotingPosition.AGREE)
        vote2 = RoleVote(role_name="tester", position=VotingPosition.DISAGREE)
        
        consensus.add_vote(vote1)
        consensus.add_vote(vote2)
        
        assert len(consensus.votes) == 2
        assert "developer" in consensus.participating_roles
        assert "tester" in consensus.participating_roles

    def test_vote_replacement_in_consensus(self):
        """Test that adding a new vote from same role replaces the old one."""
        consensus = ConsensusResult()
        
        vote1 = RoleVote(role_name="developer", position=VotingPosition.AGREE)
        vote2 = RoleVote(role_name="developer", position=VotingPosition.DISAGREE)
        
        consensus.add_vote(vote1)
        consensus.add_vote(vote2)
        
        assert len(consensus.votes) == 1
        assert consensus.votes[0].position == VotingPosition.DISAGREE

    def test_consensus_score_calculation(self):
        """Test the consensus score calculation in ConsensusResult."""
        consensus = ConsensusResult()
        
        # Add agreement vote
        vote1 = RoleVote(
            role_name="architect",
            position=VotingPosition.AGREE,
            confidence=1.0,
            weight=1.5,
        )
        consensus.add_vote(vote1)
        
        score = consensus.calculate_consensus_score()
        assert score == 1.0  # Full agreement

        # Add disagreement vote
        vote2 = RoleVote(
            role_name="developer",
            position=VotingPosition.DISAGREE,
            confidence=0.8,
            weight=1.0,
        )
        consensus.add_vote(vote2)
        
        score = consensus.calculate_consensus_score()
        # Expected: (1.5 * 1.0 - 1.0 * 0.8 * 0.5) / (1.5 + 1.0) = 0.84
        expected = (1.5 - 1.0 * 0.8 * 0.5) / (1.5 + 1.0)
        assert abs(score - expected) < 0.01

    def test_decision_rationale_generation(self):
        """Test decision rationale generation."""
        consensus = ConsensusResult(
            threshold=0.7,
            required_roles=["system-architect"],
        )
        
        # Add some votes
        vote1 = RoleVote(
            role_name="system-architect",
            position=VotingPosition.AGREE,
            confidence=0.9,
            weight=1.5,
        )
        
        vote2 = RoleVote(
            role_name="developer",
            position=VotingPosition.DISAGREE,
            confidence=0.7,
            concerns=["Performance impact"],
        )
        
        consensus.add_vote(vote1)
        consensus.add_vote(vote2)
        
        rationale = consensus.generate_decision_rationale()
        
        assert "Consensus Score:" in rationale
        assert "Vote Distribution:" in rationale
        assert "system-architect" in rationale
        assert "Performance impact" in rationale

    def test_consensus_serialization(self):
        """Test consensus result serialization."""
        consensus = ConsensusResult(
            conversation_id="conv_123",
            status=ConsensusStatus.REACHED,
            threshold=0.8,
            decision="Approved feature X",
        )
        
        # Serialize
        consensus_dict = consensus.to_dict()
        assert consensus_dict["conversation_id"] == "conv_123"
        assert consensus_dict["status"] == "reached"
        assert consensus_dict["threshold"] == 0.8
        
        # Deserialize
        restored = ConsensusResult.from_dict(consensus_dict)
        assert restored.conversation_id == consensus.conversation_id
        assert restored.status == consensus.status
        assert restored.threshold == consensus.threshold