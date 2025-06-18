"""Assignment automation engine for copilot-sve-agent with workload balancing."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from config import Config

logger = logging.getLogger(__name__)


class AssignmentReason(Enum):
    """Reason for assignment decision."""
    
    AUTO_ELIGIBLE = "auto_eligible"
    MANUAL_OVERRIDE = "manual_override"
    WORKLOAD_LIMIT = "workload_limit"
    BLOCKED_DEPENDENCY = "blocked_dependency"
    COMPLEXITY_THRESHOLD = "complexity_threshold"


class StoryComplexity(Enum):
    """Story complexity levels for assignment decisions."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class AssignmentDecision:
    """Decision result for story assignment."""
    
    should_assign: bool
    assignee: Optional[str] = None
    reason: AssignmentReason = AssignmentReason.AUTO_ELIGIBLE
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkloadInfo:
    """Information about current assignee workload."""
    
    assignee: str
    active_stories: int
    pending_stories: int
    last_assignment: Optional[datetime] = None
    blocked_stories: int = 0


class AssignmentEngine:
    """Engine for automated copilot-sve-agent assignment with workload balancing."""
    
    def __init__(self, config: Config):
        self.config = config
        self.max_concurrent_assignments = 5  # Prevent overwhelming the agent
        self.assignment_history: List[Dict[str, Any]] = []
        
    def determine_story_complexity(
        self, 
        story_content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> StoryComplexity:
        """Determine story complexity based on content and metadata."""
        
        content_lower = story_content.lower()
        
        # High complexity indicators
        high_complexity_keywords = [
            "architecture", "migration", "migrate", "security", "performance", 
            "integration", "complex", "multiple repositories", "system-wide",
            "redesign", "entire", "zero downtime", "refactor", "overhaul"
        ]
        
        # Medium complexity indicators  
        medium_complexity_keywords = [
            "api", "database", "authentication", "workflow", "business logic"
        ]
        
        high_score = sum(1 for keyword in high_complexity_keywords if keyword in content_lower)
        medium_score = sum(1 for keyword in medium_complexity_keywords if keyword in content_lower)
        
        # Check metadata for complexity hints
        if metadata:
            estimated_hours = metadata.get("estimated_hours", 0)
            story_points = metadata.get("story_points", 0)
            target_repos = metadata.get("target_repositories", [])
            
            # Multiple repositories increase complexity
            if len(target_repos) > 1:
                high_score += 1
                
            # High time estimates indicate complexity
            if estimated_hours and estimated_hours > 20:
                high_score += 1
            elif estimated_hours and estimated_hours > 8:
                medium_score += 1
                
            if story_points and story_points > 8:
                high_score += 1
            elif story_points and story_points > 3:
                medium_score += 1
        
        # Determine complexity level
        if high_score >= 2:
            return StoryComplexity.HIGH
        elif high_score >= 1 or medium_score >= 2:
            return StoryComplexity.MEDIUM
        else:
            return StoryComplexity.LOW

    def check_assignment_eligibility(
        self,
        story_content: str,
        story_metadata: Optional[Dict[str, Any]] = None,
        manual_override: bool = False
    ) -> AssignmentDecision:
        """Check if a story should be assigned to copilot-sve-agent."""
        
        if manual_override:
            return AssignmentDecision(
                should_assign=True,
                assignee="copilot-sve-agent",
                reason=AssignmentReason.MANUAL_OVERRIDE,
                explanation="Manual override requested"
            )
        
        # Check story complexity
        complexity = self.determine_story_complexity(story_content, story_metadata)
        
        # For now, auto-assign low and medium complexity stories
        # High complexity requires manual review
        if complexity == StoryComplexity.HIGH:
            return AssignmentDecision(
                should_assign=False,
                reason=AssignmentReason.COMPLEXITY_THRESHOLD,
                explanation=f"Story complexity ({complexity.value}) exceeds auto-assignment threshold",
                metadata={"complexity": complexity.value}
            )
        
        # Check workload balancing
        workload_check = self._check_workload_constraints()
        if not workload_check.should_assign:
            return workload_check
            
        # Check for blocking dependencies
        if story_metadata:
            dependencies = story_metadata.get("dependencies", [])
            if dependencies:
                # For now, assume dependencies are handled elsewhere
                # This could be expanded to check actual dependency status
                pass
        
        return AssignmentDecision(
            should_assign=True,
            assignee="copilot-sve-agent",
            reason=AssignmentReason.AUTO_ELIGIBLE,
            explanation=f"Story eligible for auto-assignment (complexity: {complexity.value})",
            metadata={"complexity": complexity.value}
        )
    
    def _check_workload_constraints(self) -> AssignmentDecision:
        """Check if copilot-sve-agent has capacity for new assignments."""
        
        # Get current workload (simplified implementation)
        # In a real system, this would query GitHub API or database
        current_workload = self._get_current_workload("copilot-sve-agent")
        
        if current_workload.active_stories >= self.max_concurrent_assignments:
            return AssignmentDecision(
                should_assign=False,
                reason=AssignmentReason.WORKLOAD_LIMIT,
                explanation=f"Agent at capacity ({current_workload.active_stories}/{self.max_concurrent_assignments} active stories)",
                metadata={"current_workload": current_workload.active_stories}
            )
        
        return AssignmentDecision(
            should_assign=True,
            assignee="copilot-sve-agent",
            reason=AssignmentReason.AUTO_ELIGIBLE,
            explanation="Workload capacity available"
        )
    
    def _get_current_workload(self, assignee: str) -> WorkloadInfo:
        """Get current workload information for an assignee."""
        
        # Simplified implementation - in practice this would query:
        # - GitHub API for open issues assigned to the agent
        # - Database for story status information
        # - Possibly CI/CD pipeline status
        
        # For now, return mock data that respects chronological ordering
        return WorkloadInfo(
            assignee=assignee,
            active_stories=len([h for h in self.assignment_history if h.get("assignee") == assignee]),
            pending_stories=0,
            last_assignment=datetime.now(timezone.utc) if self.assignment_history else None
        )
    
    def process_assignment(
        self,
        story_id: str,
        story_content: str,
        story_metadata: Optional[Dict[str, Any]] = None,
        manual_override: bool = False
    ) -> AssignmentDecision:
        """Process assignment decision for a story."""
        
        logger.info(f"Processing assignment for story {story_id}")
        
        decision = self.check_assignment_eligibility(
            story_content=story_content,
            story_metadata=story_metadata,
            manual_override=manual_override
        )
        
        # Record assignment decision in history
        assignment_record = {
            "story_id": story_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision.should_assign,
            "assignee": decision.assignee,
            "reason": decision.reason.value,
            "explanation": decision.explanation,
            "metadata": decision.metadata
        }
        
        self.assignment_history.append(assignment_record)
        
        logger.info(
            f"Assignment decision for {story_id}: "
            f"{'ASSIGN' if decision.should_assign else 'SKIP'} "
            f"({decision.reason.value}) - {decision.explanation}"
        )
        
        return decision
    
    def get_assignment_queue(self) -> List[Dict[str, Any]]:
        """Get chronologically ordered assignment queue."""
        
        # Return assignments sorted by timestamp (chronological order)
        return sorted(
            [h for h in self.assignment_history if h["decision"]],
            key=lambda x: x["timestamp"]
        )
    
    def get_assignment_statistics(self) -> Dict[str, Any]:
        """Get assignment statistics for monitoring."""
        
        total_assignments = len(self.assignment_history)
        successful_assignments = len([h for h in self.assignment_history if h["decision"]])
        
        if total_assignments == 0:
            return {
                "total_processed": 0,
                "assigned": 0,
                "assignment_rate": 0.0,
                "reasons": {}
            }
        
        # Count assignment reasons
        reason_counts = {}
        for record in self.assignment_history:
            reason = record["reason"]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return {
            "total_processed": total_assignments,
            "assigned": successful_assignments,
            "assignment_rate": round(successful_assignments / total_assignments * 100, 2),
            "reasons": reason_counts,
            "current_workload": self._get_current_workload("copilot-sve-agent").active_stories
        }