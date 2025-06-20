"""Consensus reaching algorithms for role-based decision making."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from .config import Config, get_config
    from .models import (
        ConsensusResult,
        ConsensusStatus,
        RoleVote,
        VotingPosition,
    )
except ImportError:
    # Fallback for existing tests
    from config import Config, get_config
    from models import (
        ConsensusResult,
        ConsensusStatus,
        RoleVote,
        VotingPosition,
    )

logger = logging.getLogger(__name__)


class ConsensusEngine:
    """Engine for implementing consensus reaching algorithms with weighted voting."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.role_weights = self._initialize_role_weights()

    def _initialize_role_weights(self) -> Dict[str, float]:
        """Initialize default weights for different roles."""
        return {
            # Strategic roles get higher weight
            "system-architect": 1.5,
            "lead-developer": 1.3,
            "product-owner": 1.4,
            "tech-lead": 1.3,
            # Domain experts get contextual weight
            "domain-expert": 1.2,
            "security-expert": 1.2,
            "devops-engineer": 1.1,
            "qa-engineer": 1.1,
            # Implementation roles get standard weight
            "backend-developer": 1.0,
            "frontend-developer": 1.0,
            "full-stack-developer": 1.0,
            # Perspective roles get moderate weight
            "optimistic-developer": 0.9,
            "pessimistic-developer": 0.9,
            # Standard weight for unlisted roles
            "default": 1.0,
        }

    def get_role_weight(self, role_name: str) -> float:
        """Get the consensus weight for a specific role."""
        return self.role_weights.get(role_name, self.role_weights["default"])

    def create_consensus_process(
        self,
        conversation_id: str,
        decision_topic: str,
        required_roles: Optional[List[str]] = None,
        threshold: Optional[float] = None,
        max_iterations: Optional[int] = None,
    ) -> ConsensusResult:
        """Create a new consensus process."""

        consensus_threshold = threshold or (
            self.config.auto_consensus_threshold / 100.0
        )
        max_iter = max_iterations or self.config.auto_consensus_max_iterations

        consensus = ConsensusResult(
            conversation_id=conversation_id,
            decision=decision_topic,
            threshold=consensus_threshold,
            required_roles=required_roles or [],
            max_iterations=max_iter,
        )

        logger.info(
            f"Created consensus process {consensus.id} for conversation {conversation_id} "
            f"with threshold {consensus_threshold:.2f}"
        )

        return consensus

    def add_role_vote(
        self,
        consensus: ConsensusResult,
        role_name: str,
        participant_id: str,
        position: VotingPosition,
        confidence: float = 0.8,
        rationale: str = "",
        concerns: Optional[List[str]] = None,
        suggestions: Optional[List[str]] = None,
    ) -> RoleVote:
        """Add a vote from a specific role to the consensus process."""

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

        weight = self.get_role_weight(role_name)

        vote = RoleVote(
            role_name=role_name,
            participant_id=participant_id,
            position=position,
            confidence=confidence,
            weight=weight,
            rationale=rationale,
            concerns=concerns or [],
            suggestions=suggestions or [],
        )

        consensus.add_vote(vote)

        logger.info(
            f"Added vote from {role_name} ({position.value}) to consensus {consensus.id}"
        )

        return vote

    def calculate_weighted_consensus(self, consensus: ConsensusResult) -> float:
        """Calculate the weighted consensus score using advanced algorithms."""
        return consensus.calculate_consensus_score()

    def check_consensus_status(self, consensus: ConsensusResult) -> ConsensusStatus:
        """Check the current status of the consensus process."""

        # Check if max iterations reached
        if consensus.iterations >= consensus.max_iterations:
            consensus.status = ConsensusStatus.TIMEOUT
            return consensus.status

        # Check if consensus threshold is reached
        if consensus.check_consensus_reached():
            consensus.status = ConsensusStatus.REACHED
            consensus.completed_at = datetime.now(timezone.utc)
            return consensus.status

        # Check if there are any votes at all
        if not consensus.votes:
            consensus.status = ConsensusStatus.PENDING
            return consensus.status

        # Check for failure conditions
        strong_disagreements = [
            v
            for v in consensus.votes
            if v.position == VotingPosition.DISAGREE and v.confidence > 0.7
        ]

        # If we have strong disagreements and low consensus score, mark as failed
        if strong_disagreements and consensus.achieved_score < 0.3:
            consensus.status = ConsensusStatus.FAILED
            consensus.completed_at = datetime.now(timezone.utc)
            return consensus.status

        # Otherwise, still in progress
        consensus.status = ConsensusStatus.IN_PROGRESS
        return consensus.status

    def resolve_conflicts(
        self, consensus: ConsensusResult
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Attempt to resolve conflicts in the consensus process.

        Returns:
            - success: Whether conflicts were resolved
            - resolution_actions: Actions taken to resolve conflicts
            - remaining_concerns: Concerns that still need attention
        """

        if consensus.status == ConsensusStatus.REACHED:
            return True, ["Consensus already reached"], []

        dissenting_votes = [
            v for v in consensus.votes if v.position == VotingPosition.DISAGREE
        ]

        if not dissenting_votes:
            return True, ["No conflicts to resolve"], []

        resolution_actions = []
        remaining_concerns = []

        # Analyze dissenting concerns
        all_concerns = []
        for vote in dissenting_votes:
            all_concerns.extend(vote.concerns)

        # Group similar concerns
        concern_groups = self._group_similar_concerns(all_concerns)

        for concern_group in concern_groups:
            # Check if the concern is addressable
            if self._is_addressable_concern(concern_group):
                resolution_actions.append(f"Address concern: {concern_group[0]}")
            else:
                remaining_concerns.extend(concern_group)

        # Check for role expertise conflicts
        high_expertise_disagreements = [
            v for v in dissenting_votes if v.weight > 1.0 and v.confidence > 0.8
        ]

        if high_expertise_disagreements:
            for vote in high_expertise_disagreements:
                if vote.suggestions:
                    resolution_actions.append(
                        f"Consider {vote.role_name} suggestion: {vote.suggestions[0]}"
                    )

        # Suggest mediation if conflicts remain
        if remaining_concerns and not resolution_actions:
            resolution_actions.append("Escalate to manual mediation")

        success = len(remaining_concerns) < len(all_concerns)

        logger.info(
            f"Conflict resolution for consensus {consensus.id}: "
            f"{'success' if success else 'partial'}, "
            f"{len(resolution_actions)} actions, "
            f"{len(remaining_concerns)} remaining concerns"
        )

        return success, resolution_actions, remaining_concerns

    def _group_similar_concerns(self, concerns: List[str]) -> List[List[str]]:
        """Group similar concerns together for resolution."""
        # Simple keyword-based grouping (could be enhanced with NLP)
        groups = []
        processed = set()

        for concern in concerns:
            if concern in processed:
                continue

            current_group = [concern]
            processed.add(concern)

            # Find similar concerns based on common keywords
            concern_words = set(concern.lower().split())

            for other_concern in concerns:
                if other_concern in processed:
                    continue

                other_words = set(other_concern.lower().split())

                # If they share significant keywords, group them
                common_words = concern_words.intersection(other_words)
                if len(common_words) >= 2:  # At least 2 common words
                    current_group.append(other_concern)
                    processed.add(other_concern)

            groups.append(current_group)

        return groups

    def _is_addressable_concern(self, concern_group: List[str]) -> bool:
        """Determine if a concern group is addressable through process changes."""
        # Check for common addressable concern patterns
        addressable_keywords = [
            "documentation",
            "testing",
            "review",
            "validation",
            "timeline",
            "resources",
            "communication",
            "process",
        ]

        for concern in concern_group:
            concern_lower = concern.lower()
            if any(keyword in concern_lower for keyword in addressable_keywords):
                return True

        return False

    def generate_consensus_report(self, consensus: ConsensusResult) -> Dict[str, any]:
        """Generate a comprehensive consensus report."""

        # Update rationale
        consensus.generate_decision_rationale()

        # Calculate additional metrics
        total_votes = len(consensus.votes)
        weighted_score = consensus.calculate_consensus_score()

        vote_distribution = {
            "agree": len(
                [v for v in consensus.votes if v.position == VotingPosition.AGREE]
            ),
            "disagree": len(
                [v for v in consensus.votes if v.position == VotingPosition.DISAGREE]
            ),
            "abstain": len(
                [v for v in consensus.votes if v.position == VotingPosition.ABSTAIN]
            ),
            "needs_clarification": len(
                [
                    v
                    for v in consensus.votes
                    if v.position == VotingPosition.NEEDS_CLARIFICATION
                ]
            ),
        }

        # Role participation analysis
        high_weight_roles = [v.role_name for v in consensus.votes if v.weight > 1.0]
        missing_required_roles = set(consensus.required_roles) - set(
            consensus.participating_roles
        )

        # Conflict analysis
        conflicts_resolved, resolution_actions, remaining_concerns = (
            self.resolve_conflicts(consensus)
        )

        report = {
            "consensus_id": consensus.id,
            "conversation_id": consensus.conversation_id,
            "status": consensus.status.value,
            "decision": consensus.decision,
            "rationale": consensus.rationale,
            "metrics": {
                "weighted_score": weighted_score,
                "threshold": consensus.threshold,
                "consensus_reached": consensus.check_consensus_reached(),
                "total_votes": total_votes,
                "iterations": consensus.iterations,
            },
            "vote_distribution": vote_distribution,
            "role_analysis": {
                "participating_roles": consensus.participating_roles,
                "required_roles": consensus.required_roles,
                "missing_required_roles": list(missing_required_roles),
                "high_weight_participants": high_weight_roles,
            },
            "conflict_resolution": {
                "conflicts_resolved": conflicts_resolved,
                "resolution_actions": resolution_actions,
                "remaining_concerns": remaining_concerns,
            },
            "timestamps": {
                "started_at": consensus.started_at.isoformat(),
                "completed_at": (
                    consensus.completed_at.isoformat()
                    if consensus.completed_at
                    else None
                ),
            },
        }

        logger.info(f"Generated consensus report for {consensus.id}")

        return report

    def iterate_consensus(self, consensus: ConsensusResult) -> bool:
        """
        Perform one iteration of the consensus process.

        Returns True if consensus should continue, False if it should stop.
        """

        consensus.iterations += 1

        # Check if we've reached the maximum iterations
        if consensus.iterations >= consensus.max_iterations:
            consensus.status = ConsensusStatus.TIMEOUT
            consensus.completed_at = datetime.now(timezone.utc)
            return False

        # Update status based on current votes
        status = self.check_consensus_status(consensus)

        # Stop if consensus is reached or failed
        if status in [
            ConsensusStatus.REACHED,
            ConsensusStatus.FAILED,
            ConsensusStatus.TIMEOUT,
        ]:
            return False

        return True

    def auto_resolve_minor_conflicts(self, consensus: ConsensusResult) -> bool:
        """
        Automatically resolve minor conflicts that don't require human intervention.

        Returns True if any conflicts were resolved.
        """

        resolved_any = False

        # Handle "needs clarification" votes
        clarification_votes = [
            v
            for v in consensus.votes
            if v.position == VotingPosition.NEEDS_CLARIFICATION
        ]

        for vote in clarification_votes:
            # If the role has provided suggestions, consider them addressed
            if vote.suggestions and len(vote.suggestions) > 0:
                # Convert to abstain (neutral) since clarification was provided
                vote.position = VotingPosition.ABSTAIN
                vote.rationale += (
                    " [Auto-resolved: clarification provided via suggestions]"
                )
                resolved_any = True

                logger.info(
                    f"Auto-resolved clarification request from {vote.role_name} "
                    f"in consensus {consensus.id}"
                )

        # Handle low-confidence disagreements
        weak_disagreements = [
            v
            for v in consensus.votes
            if v.position == VotingPosition.DISAGREE and v.confidence < 0.4
        ]

        for vote in weak_disagreements:
            # Convert weak disagreements to abstain if no strong concerns
            if not vote.concerns or len(vote.concerns) == 0:
                vote.position = VotingPosition.ABSTAIN
                vote.rationale += " [Auto-resolved: low confidence disagreement without specific concerns]"
                resolved_any = True

                logger.info(
                    f"Auto-resolved weak disagreement from {vote.role_name} "
                    f"in consensus {consensus.id}"
                )

        return resolved_any

    def trigger_manual_intervention(
        self,
        consensus: ConsensusResult,
        conversation_id: str,
        trigger_reason: str = "failed_consensus",
        intervention_type: str = "decision",
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional = None,
    ) -> str:
        """
        Trigger a manual intervention for a consensus process.

        Returns the intervention ID.
        """
        try:
            from .database import DatabaseManager
            from .models import ManualIntervention
        except ImportError:
            from database import DatabaseManager
            from models import ManualIntervention

        # Create manual intervention record
        intervention = ManualIntervention(
            conversation_id=conversation_id,
            consensus_id=consensus.id,
            trigger_reason=trigger_reason,
            intervention_type=intervention_type,
            original_decision=consensus.decision,
            affected_roles=consensus.participating_roles,
            metadata=metadata or {},
        )

        # Add initial audit entry
        intervention.add_audit_entry(
            action="intervention_triggered",
            details=f"Manual intervention triggered due to {trigger_reason}",
            actor="system",
        )

        # Store in database
        database = db or DatabaseManager()
        if database.store_manual_intervention(intervention):
            logger.info(
                f"Triggered manual intervention {intervention.id} for consensus {consensus.id}"
            )
            return intervention.id
        else:
            logger.error(
                f"Failed to store manual intervention for consensus {consensus.id}"
            )
            raise RuntimeError("Failed to store manual intervention")

    def resolve_manual_intervention(
        self,
        intervention_id: str,
        human_decision: str,
        human_rationale: str,
        intervener_id: str,
        intervener_role: str = "project-manager",
        override_data: Optional[Dict[str, Any]] = None,
        db: Optional = None,
    ) -> bool:
        """
        Resolve a manual intervention with human decision.

        Returns True if successful.
        """
        try:
            from .database import DatabaseManager
        except ImportError:
            from database import DatabaseManager

        database = db or DatabaseManager()
        intervention = database.get_manual_intervention(intervention_id)

        if not intervention:
            logger.error(f"Manual intervention {intervention_id} not found")
            return False

        if intervention.status != "pending":
            logger.error(f"Manual intervention {intervention_id} is not pending")
            return False

        # Update intervention with human decision
        intervention.human_decision = human_decision
        intervention.human_rationale = human_rationale
        intervention.intervener_id = intervener_id
        intervention.intervener_role = intervener_role
        intervention.status = "resolved"
        intervention.resolved_at = datetime.now(timezone.utc)

        if override_data:
            intervention.override_data = override_data

        # Add audit entry
        intervention.add_audit_entry(
            action="intervention_resolved",
            details=f"Manual intervention resolved with decision: {human_decision}",
            actor=f"{intervener_role}:{intervener_id}",
        )

        # Store updated intervention
        if database.store_manual_intervention(intervention):
            logger.info(
                f"Resolved manual intervention {intervention_id} with decision: {human_decision}"
            )
            return True
        else:
            logger.error(f"Failed to update manual intervention {intervention_id}")
            return False

    def check_consensus_requires_intervention(
        self, consensus: ConsensusResult
    ) -> Tuple[bool, str]:
        """
        Check if a consensus process requires manual intervention.

        Returns (requires_intervention, reason).
        """

        # Check for timeout
        if consensus.status == ConsensusStatus.TIMEOUT:
            return True, "timeout"

        # Check for failed consensus
        if consensus.status == ConsensusStatus.FAILED:
            return True, "failed_consensus"

        # Check for high-confidence disagreements from key roles
        high_weight_disagreements = [
            v
            for v in consensus.votes
            if v.position == VotingPosition.DISAGREE
            and v.weight > 1.0
            and v.confidence > 0.8
        ]

        if len(high_weight_disagreements) > 1:
            return True, "high_expertise_conflict"

        # Check for stalled progress (low consensus score after multiple iterations)
        if (
            consensus.iterations > 2
            and consensus.achieved_score < 0.4
            and consensus.status == ConsensusStatus.IN_PROGRESS
        ):
            return True, "stalled_progress"

        return False, ""
