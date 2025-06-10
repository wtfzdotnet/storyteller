"""
Simplified workflow processor for the story management system.

This simplified version handles basic label management without complex state machines.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config
from github_handler import GitHubService
from llm_handler import LLMService
from story_manager import StoryOrchestrator

logger = logging.getLogger(__name__)


async def process_story_state(
    issue_number: int,
    trigger_event: str,
    action: Optional[str] = None,
    current_labels_str: str = "",
    comment_body: Optional[str] = None,
    actor: Optional[str] = None,
    github_service: Optional[GitHubService] = None,
    llm_service: Optional[LLMService] = None,
    story_orchestrator: Optional[StoryOrchestrator] = None,
    config: Optional[Any] = None,
) -> None:
    """
    Simplified workflow processing.

    Only handles basic label cleanup and minimal automation.
    The new simplified approach doesn't need complex state machines.
    """
    logger.info(f"[{issue_number}] Simplified workflow processing: {trigger_event}")

    if not github_service:
        logger.error("GitHub service not provided")
        return

    try:
        # Get current issue
        issue_result = await github_service.get_issue(issue_number)
        if not issue_result.success:
            logger.error(f"[{issue_number}] Could not fetch issue")
            return

        issue = issue_result.data
        current_labels = [label.name for label in issue.labels]

        logger.info(f"[{issue_number}] Current labels: {current_labels}")

        # Simple processing based on trigger
        if trigger_event == "issues" and action == "labeled":
            await _handle_label_added(issue_number, current_labels, github_service)
        elif trigger_event == "issues" and action == "unlabeled":
            await _handle_label_removed(issue_number, current_labels, github_service)
        elif trigger_event == "issue_comment" and action == "created":
            await _handle_comment_added(issue_number, comment_body, github_service)
        else:
            logger.info(
                f"[{issue_number}] No action needed for trigger: {trigger_event}"
            )

    except Exception as e:
        logger.error(f"[{issue_number}] Error in simplified workflow processing: {e}")


async def _handle_label_added(
    issue_number: int, current_labels: List[str], github_service: GitHubService
) -> None:
    """Handle when a label is added to an issue."""
    logger.info(f"[{issue_number}] Label added, current labels: {current_labels}")

    # Clean up conflicting labels
    await _cleanup_conflicting_labels(issue_number, current_labels, github_service)


async def _handle_label_removed(
    issue_number: int, current_labels: List[str], github_service: GitHubService
) -> None:
    """Handle when a label is removed from an issue."""
    logger.info(f"[{issue_number}] Label removed, current labels: {current_labels}")

    # Ensure required labels are present
    await _ensure_required_labels(issue_number, current_labels, github_service)


async def _handle_comment_added(
    issue_number: int, comment_body: Optional[str], github_service: GitHubService
) -> None:
    """Handle when a comment is added to an issue."""
    if not comment_body:
        return

    logger.info(f"[{issue_number}] Comment added: {comment_body[:100]}...")

    # In simplified approach, we don't process comments for automation
    # The AI processing happens locally before creating the issue


async def _cleanup_conflicting_labels(
    issue_number: int, current_labels: List[str], github_service: GitHubService
) -> None:
    """Remove conflicting labels when new ones are added."""
    conflicting_groups = [
        ["ready-for-development", "in-development", "completed", "blocked"],
        ["priority/low", "priority/medium", "priority/high", "priority/critical"],
        ["complexity/simple", "complexity/medium", "complexity/complex"],
    ]

    for group in conflicting_groups:
        present_labels = [label for label in group if label in current_labels]
        if len(present_labels) > 1:
            # Keep the last one (most recently added) and remove others
            labels_to_remove = present_labels[:-1]
            for label in labels_to_remove:
                logger.info(f"[{issue_number}] Removing conflicting label: {label}")
                await github_service.remove_label_from_issue(issue_number, label)


async def _ensure_required_labels(
    issue_number: int, current_labels: List[str], github_service: GitHubService
) -> None:
    """Ensure required labels are present."""
    # If it's a story but has no state label, add ready-for-development
    if "story" in current_labels:
        state_labels = [
            "ready-for-development",
            "in-development",
            "completed",
            "blocked",
        ]
        has_state = any(label in current_labels for label in state_labels)

        if not has_state:
            logger.info(
                f"[{issue_number}] Adding default state label: ready-for-development"
            )
            await github_service.add_label_to_issue(
                issue_number, "ready-for-development"
            )


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description="Simplified workflow processor")
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--trigger-event", required=True)
    parser.add_argument("--action")
    parser.add_argument("--current-labels", default="")
    parser.add_argument("--comment-body")
    parser.add_argument("--actor")
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load environment
    load_dotenv()

    async def main():
        config = get_config()
        github_service = GitHubService()

        await process_story_state(
            issue_number=args.issue_number,
            trigger_event=args.trigger_event,
            action=args.action,
            current_labels_str=args.current_labels,
            comment_body=args.comment_body,
            actor=args.actor,
            github_service=github_service,
            config=config,
        )

    asyncio.run(main())
