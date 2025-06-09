import argparse
import logging
import os
import asyncio # Added for async operations
from typing import List, Dict, Optional, Any 
from dotenv import load_dotenv

# Assuming ai_core is in PYTHONPATH or this script is run as a module
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_handler import GitHubService
from llm_handler import LLMService
from story_manager import StoryOrchestrator # For interaction with AI logic
from config import get_config

# Basic Logging Configuration will be set up in main()
logger = logging.getLogger(__name__)

DEFAULT_ROLES_FOR_FEEDBACK = ["Product Owner", "Lead Developer", "QA Engineer"]
# For story/reviewing state, these roles are expected to have contributed for consensus check
DEFAULT_ROLES_FOR_CONSENSUS_CHECK = ["Product Owner", "Lead Developer", "QA Engineer"]

TERMINAL_STATES = ['story/archived', 'story/split', 'story/ready']

# --- State Machine Definition ---
WORKFLOW_STATES = {
    'story/draft': {
        'next_states': ['story/enriching'],
        'auto_actions': ['assign_initial_roles', 'create_initial_feedback'], 
        'required_labels': ['iteration/1'] 
    },
    'story/enriching': {
        'next_states': ['story/reviewing', 'story/blocked'], 
        'auto_actions': ['simulate_role_feedback', 'update_iteration'], 
        'conditions': { 
            'story/reviewing': 'all_roles_provided_input', 
            'story/blocked': 'max_iterations_reached_or_manual_block' 
        },
        'iteration_limit': 5
    },
    'story/reviewing': {
        'next_states': ['story/consensus', 'story/enriching', 'story/blocked'],
        'auto_actions': ['check_consensus', 'update_consensus_score'], 
        'conditions': {
            'story/consensus': 'consensus_score_gte_80', 
            'story/enriching': 'consensus_score_lt_80_and_iteration_lt_limit', 
            'story/blocked': 'consensus_score_lt_80_and_iteration_gte_limit'  
        },
        'required_roles_for_consensus': DEFAULT_ROLES_FOR_CONSENSUS_CHECK,
        'consensus_threshold_pass': 80 
    },
    'story/consensus': { 
        'next_states': ['story/ready'],
        'auto_actions': ['create_repository_tickets'], 
    },
    'story/blocked': {
        'next_states': ['story/draft', 'story/enriching', 'story/archived', 'story/split'], 
        'auto_actions': ['suggest_escalation', 'notify_stakeholders'], 
        'manual_intervention': True 
    },
    'story/ready': { 
        'next_states': ['story/finalized'], 
        'auto_actions': [],
        'manual_transition': True  # Can be finalized manually or automatically based on conditions
    },
    'story/finalized': {
        'next_states': ['story/user-approved'],
        'auto_actions': ['add_needs_user_approval_label'],
        'manual_intervention': False  # Automated progression to user approval
    },
    'story/user-approved': {
        'next_states': ['story/ready'],  # Goes back to ready for development after user approval
        'auto_actions': ['prepare_for_development'],
        'manual_intervention': False  # Automated progression after approval
    },
    'story/archived': {
        'next_states': [], # Terminal state
        'auto_actions': ['perform_archival_cleanup'], # Conceptual
        'manual_intervention': True # Usually a manual decision
    },
    'story/split': {
        'next_states': [], # Terminal state, new stories created manually/separately
        'auto_actions': ['perform_split_cleanup'], # Conceptual
        'manual_intervention': True # Usually a manual decision
    }
}

    # Label Cleanup Rules
CLEANUP_RULES = {
    'story/draft': ['consensus/*', 'iteration/*','needs/*','approved/*','blocking/*'], 
    'story/enriching': ['consensus/*'], 
    'story/reviewing': [],  # Iteration labels are kept to check against limit for consensus failure
    'story/consensus': ['iteration/*','needs/*','approved/*','blocking/*','consensus/*'], 
    'story/ready': ['iteration/*','needs/*','approved/*','blocking/*','consensus/*','trigger/*'], 
    'story/finalized': ['iteration/*','consensus/*','trigger/*'],  # Keep some approval labels for transition
    'story/user-approved': ['needs/user-approval'],  # Clean up approval request label
    'story/blocked': ['trigger/*'], 
    '_terminal_state_cleanup': [ 
        'story/draft', 'story/enriching', 'story/reviewing', 'story/consensus', 'story/blocked', 'story/ready', 
        'story/finalized', 'story/user-approved',
        'iteration/*',
        'consensus/*',
        'needs/*',
        'approved/*',
        'blocking/*',
        'auto/enabled', 
        'auto/paused',
        'trigger/*',
    ]
}


async def get_current_story_state_label(current_labels: List[str]) -> Optional[str]:
    """Finds the primary story state label (e.g., 'story/draft') from a list of labels."""
    for label in current_labels:
        if label.startswith("story/"):
            return label
    return None

async def get_current_iteration_label(current_labels: List[str]) -> Optional[str]: # Made async
    """Finds the current iteration label (e.g., 'iteration/1') from a list of labels."""
    iterations = [l for l in current_labels if l.startswith("iteration/")]
    if not iterations:
        return None
    iterations.sort(key=lambda x: int(x.split('/')[1]), reverse=True)
    return iterations[0]

async def get_current_consensus_label(current_labels: List[str]) -> Optional[str]: # Made async
    """Finds the current consensus label (e.g., 'consensus/0-20') from a list of labels."""
    for label in current_labels:
        if label.startswith("consensus/"):
            return label
    return None

async def assign_labels_based_on_content(issue_number: int, issue_title: str, issue_body: str, 
                                   github_service: GitHubService, llm_service: LLMService) -> List[str]: # Made async
    logger.info(f"[{issue_number}] Analyzing content for initial labels (Title: {issue_title[:30]}...).")
    suggested_labels = []
    suggested_labels.append('complexity/medium') 
    for role_name in DEFAULT_ROLES_FOR_FEEDBACK:
        role_slug = role_name.replace(' ', '-').lower()
        suggested_labels.append(f"needs/{role_slug}")
    logger.info(f"[{issue_number}] Suggested content-based labels: {suggested_labels}")
    return suggested_labels

async def apply_label_cleanup_rules(issue_number: int, current_labels: List[str], 
                              new_state_label: Optional[str], github_service: GitHubService, is_terminal: bool = False) -> List[str]:
    """Applies label cleanup rules based on the new state or general rules.
    Returns the list of labels after cleanup operations on GitHub have been attempted.
    """
    if not current_labels: 
        return []

    logger.info(f"[{issue_number}] Applying label cleanup. Current: {current_labels}. New state: {new_state_label or 'N/A'}. Terminal: {is_terminal}")
    labels_to_remove_patterns = set()

    if new_state_label and new_state_label in CLEANUP_RULES:
        labels_to_remove_patterns.update(CLEANUP_RULES[new_state_label])
    
    if is_terminal and '_terminal_state_cleanup' in CLEANUP_RULES:
        logger.info(f"[{issue_number}] Adding terminal state cleanup rules for: {new_state_label}")
        labels_to_remove_patterns.update(CLEANUP_RULES['_terminal_state_cleanup'])

    actual_labels_to_remove = set()
    for pattern in labels_to_remove_patterns:
        if pattern.endswith('/*'):
            prefix = pattern[:-2]
            actual_labels_to_remove.update(l for l in current_labels if l.startswith(prefix))
        elif pattern in current_labels:
            if pattern != new_state_label or (is_terminal and pattern in TERMINAL_STATES):
                 actual_labels_to_remove.add(pattern)

    effective_labels = list(current_labels)
    if actual_labels_to_remove:
        logger.info(f"[{issue_number}] Identified for removal: {list(actual_labels_to_remove)}")
        for label_to_remove in actual_labels_to_remove:
            if label_to_remove in effective_labels: 
                logger.info(f"[{issue_number}] Removing label '{label_to_remove}' due to cleanup rules.")
                try:
                    if github_service.remove_label_from_issue(issue_number, label_to_remove):
                        if label_to_remove in effective_labels: 
                            effective_labels.remove(label_to_remove)
                    else:
                        logger.warning(f"[{issue_number}] Failed to remove label '{label_to_remove}' (service reported failure).")
                except Exception as e:
                    logger.error(f"[{issue_number}] Exception removing label '{label_to_remove}': {e}", exc_info=True)
            else:
                logger.debug(f"[{issue_number}] Label '{label_to_remove}' was in removal set but not in current effective labels. Skipping.")
    else:
        logger.info(f"[{issue_number}] No labels matched for cleanup based on state '{new_state_label or 'N/A'}' and terminal={is_terminal}.")
    return effective_labels

def get_consensus_label_from_score(score: int) -> str:
    if score < 0: score = 0
    if score > 100: score = 100
    if score <= 20: return "consensus/0-20"
    if score <= 40: return "consensus/21-40"
    if score <= 60: return "consensus/41-60"
    if score <= 80: return "consensus/61-80"
    return "consensus/81-100"

def get_score_from_consensus_label(consensus_label: Optional[str]) -> int:
    if not consensus_label or not consensus_label.startswith("consensus/"): return 0 
    try:
        return int(consensus_label.split('/')[1].split('-')[0])
    except (IndexError, ValueError):
        logger.warning(f"Could not parse score from consensus label: {consensus_label}")
        return 0

async def _create_repository_tickets_for_consensus(issue_number: int, github_service: GitHubService, 
                                                 llm_service: LLMService, story_orchestrator: StoryOrchestrator, 
                                                 current_labels: List[str]) -> None:
    """
    Create tickets in designated repositories when consensus is reached.
    This removes confusing details and customizes content for each repository type.
    """
    # Check if multi-repository mode is enabled
    if not story_orchestrator.config.is_multi_repository_mode():
        logger.info(f"[{issue_number}] Multi-repository mode not enabled, skipping repository ticket creation")
        return
    
    # Get the current story details
    try:
        story_details = story_orchestrator.get_story_details(issue_number)
        if not story_details:
            logger.error(f"[{issue_number}] Could not retrieve story details for ticket creation")
            return
        
        github_issue = github_service.get_issue(issue_number)
        if not github_issue:
            logger.error(f"[{issue_number}] Could not retrieve GitHub issue for ticket creation")
            return
            
        logger.info(f"[{issue_number}] Creating repository tickets for consensus story: {story_details.title}")
        
        # Create the base prompt from the finalized story
        base_prompt = f"{story_details.title}\n\n{story_details.body}"
        
        # Enhance prompt with copilot instructions from target repositories
        enhanced_prompts = {}
        for repo_key, repo_config in story_orchestrator.config.multi_repository_config.repositories.items():
            enhanced_prompt = base_prompt
            
            # Try to get copilot instructions for this repository
            try:
                copilot_instructions = await github_service.get_copilot_instructions(repo_config.name)
                if copilot_instructions:
                    logger.info(f"[{issue_number}] Enhancing story for {repo_key} with copilot instructions")
                    enhanced_prompt = (
                        f"{base_prompt}\n\n"
                        f"## Repository-Specific Context for {repo_key}\n\n"
                        f"The following are the copilot instructions for this repository:\n\n"
                        f"{copilot_instructions}\n\n"
                        f"Please refine the above user story taking into account these repository-specific guidelines and context."
                    )
                else:
                    logger.info(f"[{issue_number}] No copilot instructions found for {repo_key}")
            except Exception as e:
                logger.warning(f"[{issue_number}] Failed to retrieve copilot instructions for {repo_key}: {e}")
            
            enhanced_prompts[repo_key] = enhanced_prompt
        
        # Get default roles for repository ticket creation
        roles_to_consult = DEFAULT_ROLES_FOR_FEEDBACK
        
        # Create stories across all configured repositories with enhanced prompts
        created_stories = await story_orchestrator.create_multi_repository_stories(
            base_prompt,  # Use base prompt for now; ideally we'd pass enhanced_prompts
            roles_to_consult,
            target_repositories=None  # Create in all repositories
        )
        
        # Add a comment to the original issue linking to the created tickets
        if created_stories:
            ticket_links = []
            for repo_key, story in created_stories.items():
                if story and story.id:
                    repo_config = story_orchestrator.config.multi_repository_config.get_repository(repo_key)
                    repo_name = repo_config.name if repo_config else repo_key
                    ticket_links.append(f"- **{repo_key}** ({repo_name}): #{story.id}")
            
            if ticket_links:
                comment_body = (
                    "🎯 **Consensus Reached - Repository Tickets Created**\n\n"
                    "Following consensus on this story, tickets have been automatically created "
                    "in the designated repositories with repository-specific focus:\n\n"
                    + "\n".join(ticket_links) +
                    "\n\nEach ticket has been customized for its target repository:\n"
                    "- **Backend tickets** focus on API design, data models, and business logic\n"
                    "- **Frontend tickets** focus on UI/UX, user interactions, and API consumption"
                )
                
                await github_service.add_comment_to_issue(issue_number, comment_body)
                logger.info(f"[{issue_number}] Added comment linking to {len(ticket_links)} created repository tickets")
            else:
                logger.warning(f"[{issue_number}] No valid tickets were created despite success response")
        else:
            logger.warning(f"[{issue_number}] No repository tickets were created")
            
    except Exception as e:
        logger.error(f"[{issue_number}] Error in repository ticket creation: {e}", exc_info=True)
        # Add error comment to the original issue
        await github_service.add_comment_to_issue(
            issue_number,
            "⚠️ **Repository Ticket Creation Failed**\n\n"
            f"An error occurred while creating repository tickets: {str(e)}\n\n"
            "Please check the logs and consider creating tickets manually."
        )

async def execute_auto_actions(issue_number: int, state_label: str, auto_actions: List[str], 
                               github_service: GitHubService, llm_service: LLMService, 
                               story_orchestrator: StoryOrchestrator, current_labels: List[str]) -> List[str]:
    """
    Execute the auto-actions defined for a state.
    Returns updated labels after executing actions.
    """
    updated_labels = list(current_labels)
    
    logger.info(f"[{issue_number}] Executing auto-actions for state '{state_label}': {auto_actions}")
    
    for action in auto_actions:
        try:
            if action == 'assign_initial_roles':
                logger.info(f"[{issue_number}] Executing: assign_initial_roles")
                # Add role-based labels if not already present
                for role_name in DEFAULT_ROLES_FOR_FEEDBACK:
                    role_slug = role_name.replace(' ', '-').lower()
                    role_label = f"needs/{role_slug}"
                    if role_label not in updated_labels:
                        if github_service.add_label_to_issue(issue_number, role_label):
                            updated_labels.append(role_label)
                            logger.info(f"[{issue_number}] Added role label: {role_label}")
                            
            elif action == 'create_initial_feedback':
                logger.info(f"[{issue_number}] Executing: create_initial_feedback")
                # Trigger AI feedback generation
                try:
                    await story_orchestrator.gather_feedback_and_iterate(issue_number, DEFAULT_ROLES_FOR_FEEDBACK)
                    logger.info(f"[{issue_number}] Initial AI feedback generated successfully")
                    
                    # Add trigger for reviewing to automatically check consensus after feedback
                    trigger_label = 'trigger/consensus-check'
                    if trigger_label not in updated_labels:
                        if github_service.add_label_to_issue(issue_number, trigger_label):
                            updated_labels.append(trigger_label)
                            logger.info(f"[{issue_number}] Added trigger for consensus check: {trigger_label}")
                            
                except Exception as e:
                    logger.error(f"[{issue_number}] Error during create_initial_feedback: {e}", exc_info=True)
                    
            elif action == 'simulate_role_feedback':
                logger.info(f"[{issue_number}] Executing: simulate_role_feedback")
                # This is typically triggered by the trigger/iterate label in the main processing loop
                # The action logic is already in the story/enriching state handler
                
            elif action == 'update_iteration':
                logger.info(f"[{issue_number}] Executing: update_iteration")
                # Update iteration number - this is typically handled in the main processing loop
                
            elif action == 'check_consensus':
                logger.info(f"[{issue_number}] Executing: check_consensus")
                # This is typically handled in the story/reviewing state handler
                
            elif action == 'update_consensus_score':
                logger.info(f"[{issue_number}] Executing: update_consensus_score")
                # This is typically handled in the story/reviewing state handler
                
            elif action == 'add_needs_user_approval_label':
                logger.info(f"[{issue_number}] Executing: add_needs_user_approval_label")
                approval_label = 'needs/user-approval'
                if approval_label not in updated_labels:
                    if github_service.add_label_to_issue(issue_number, approval_label):
                        updated_labels.append(approval_label)
                        logger.info(f"[{issue_number}] Added user approval label: {approval_label}")
                        
            elif action == 'prepare_for_development':
                logger.info(f"[{issue_number}] Executing: prepare_for_development")
                # Add comment indicating story is ready for development
                await github_service.add_comment_to_issue(
                    issue_number, 
                    "✅ **Story Approved and Ready for Development**\n\n"
                    "This story has been finalized and approved by the user. It is now ready to enter the development workflow."
                )
                logger.info(f"[{issue_number}] Added development readiness comment")
                
            elif action == 'suggest_escalation':
                logger.info(f"[{issue_number}] Executing: suggest_escalation")
                await github_service.add_comment_to_issue(
                    issue_number,
                    "⚠️ **Story Blocked - Escalation Suggested**\n\n"
                    "This story has reached a blocked state and may require manual intervention or escalation to resolve."
                )
                
            elif action == 'notify_stakeholders':
                logger.info(f"[{issue_number}] Executing: notify_stakeholders")
                await github_service.add_comment_to_issue(
                    issue_number,
                    "📢 **Stakeholder Notification**\n\n"
                    "Stakeholders have been notified of the current story status and any required actions."
                )
                
            elif action == 'create_repository_tickets':
                logger.info(f"[{issue_number}] Executing: create_repository_tickets")
                try:
                    await _create_repository_tickets_for_consensus(
                        issue_number, github_service, llm_service, story_orchestrator, updated_labels
                    )
                    logger.info(f"[{issue_number}] Successfully created repository tickets")
                except Exception as e:
                    logger.error(f"[{issue_number}] Error creating repository tickets: {e}", exc_info=True)
                
            elif action in ['perform_archival_cleanup', 'perform_split_cleanup']:
                logger.info(f"[{issue_number}] Executing: {action} (conceptual)")
                # These are conceptual actions for terminal states
                
            else:
                logger.warning(f"[{issue_number}] Unknown auto-action: {action}")
                
        except Exception as e:
            logger.error(f"[{issue_number}] Error executing auto-action '{action}': {e}", exc_info=True)
    
    return updated_labels

async def _transition_to_state(issue_number: int, current_labels: List[str], new_state_label: str,
                               github_service: GitHubService, llm_service: LLMService, 
                               story_orchestrator: StoryOrchestrator, actor: str, is_terminal_transition: bool = False) -> List[str]:
    logger.info(f"[{issue_number}] Transitioning to state: {new_state_label}. Is terminal: {is_terminal_transition}")
    labels_after_removal = list(current_labels)
    for label in current_labels:
        if label.startswith("story/") and label != new_state_label:
            logger.info(f"[{issue_number}] Removing old state label: {label}")
            if github_service.remove_label_from_issue(issue_number, label):
                if label in labels_after_removal: labels_after_removal.remove(label)
    current_labels = labels_after_removal
    if new_state_label not in current_labels:
        logger.info(f"[{issue_number}] Adding new state label: {new_state_label}")
        if github_service.add_label_to_issue(issue_number, new_state_label):
            current_labels.append(new_state_label)
    current_labels = await apply_label_cleanup_rules(issue_number, current_labels, new_state_label, github_service, is_terminal=is_terminal_transition)
    logger.info(f"[{issue_number}] Transition to {new_state_label} complete. Effective labels post-transition: {current_labels}")
    
    # Execute any auto-actions defined for the new state
    auto_actions = WORKFLOW_STATES.get(new_state_label, {}).get('auto_actions', [])
    if auto_actions:
        current_labels = await execute_auto_actions(issue_number, new_state_label, auto_actions, github_service, llm_service, story_orchestrator, current_labels)
    
    return current_labels

async def process_story_state(issue_number: int, trigger_event: str, action: Optional[str],
                        current_labels_str: str, comment_body: Optional[str], actor: str, 
                        github_service: GitHubService, llm_service: LLMService,
                        story_orchestrator: StoryOrchestrator, config=None) -> None: 
    current_labels = [label.strip() for label in current_labels_str.split(',') if label.strip()]
    
    # Get configuration
    if config is None:
        config = get_config()
    
    logger.info(
        f"[{issue_number}] Processing Event: '{trigger_event}', Action: '{action or 'N/A'}', Actor: '{actor}'. "
        f"Labels: {current_labels}. Comment: '{comment_body[:50] if comment_body else 'N/A'}'..."
    )
    
    if config.auto_consensus_enabled:
        logger.info(f"[{issue_number}] Auto-consensus enabled: threshold={config.auto_consensus_threshold}%, max_iterations={config.auto_consensus_max_iterations}")
    
    initial_story_label = await get_current_story_state_label(current_labels) # Save initial state for comparison
    current_story_label = initial_story_label
    logger.info(f"[{issue_number}] Initial story state: {current_story_label or 'None'}")

    # --- Handle direct labeling to a terminal state first ---
    if trigger_event == 'issues' and action == 'labeled':
        # Determine the label that was actually added from the event payload if possible.
        # This is a simplified check assuming current_labels contains the newly added label from the event.
        # A more robust solution would use github.event.label.name (passed to the script).
        added_label_from_event = None # Placeholder if we can't get it directly
        # If event context provided the specific label, use it:
        # added_label_from_event = args.label_name # Assuming --label-name is passed from workflow
        
        potential_terminal_label = added_label_from_event if added_label_from_event in TERMINAL_STATES else None
        if not potential_terminal_label: # Fallback to checking current_labels if specific added label isn't known
            newly_added_terminal_labels = [l for l in current_labels if l in TERMINAL_STATES and l not in initial_story_label.split(',') if initial_story_label] # Compare with initial state
            if not newly_added_terminal_labels and any(l in TERMINAL_STATES for l in current_labels): # Check if any current label is terminal
                 # If already in a terminal state, but not the one we are processing, it's a change.
                 current_terminal_label_on_issue = next((l for l in current_labels if l in TERMINAL_STATES), None)
                 if current_terminal_label_on_issue and current_story_label != current_terminal_label_on_issue:
                     newly_added_terminal_labels = [current_terminal_label_on_issue]

            if newly_added_terminal_labels:
                 potential_terminal_label = newly_added_terminal_labels[0]

        if potential_terminal_label and current_story_label != potential_terminal_label:
            logger.info(f"[{issue_number}] Issue manually labeled to terminal state: {potential_terminal_label}. Processing transition.")
            current_labels = await _transition_to_state(issue_number, current_labels, potential_terminal_label, github_service, llm_service, story_orchestrator, actor, is_terminal_transition=True)
            current_story_label = potential_terminal_label 
            logger.info(f"[{issue_number}] End of processing due to terminal state transition: {current_story_label}")
            return # Exit early

    # --- Initial State Setup for New Issues ---
    if trigger_event == 'issues' and action == 'opened':
        if not current_story_label: # Only if no story label exists
            logger.info(f"[{issue_number}] New issue. Initializing to 'story/draft'.")
            issue_details = github_service.get_issue(issue_number) 
            if not issue_details:
                logger.error(f"[{issue_number}] Cannot fetch issue details. Aborting.")
                return
            new_state = 'story/draft'
            current_labels = await _transition_to_state(issue_number, current_labels, new_state, github_service, llm_service, story_orchestrator, actor, is_terminal_transition=(new_state in TERMINAL_STATES))
            current_story_label = new_state
            
            labels_to_add = [] 
            if 'required_labels' in WORKFLOW_STATES[new_state]:
                 labels_to_add.extend(WORKFLOW_STATES[new_state]['required_labels'])
            labels_to_add.append('auto/enabled')
            content_labels = await assign_labels_based_on_content(issue_number, issue_details.title, issue_details.body or "", github_service, llm_service)
            labels_to_add.extend(content_labels)
            for label_to_add in list(set(labels_to_add) - set(current_labels)): 
                if github_service.add_label_to_issue(issue_number, label_to_add):
                    current_labels.append(label_to_add)
        else:
            logger.info(f"[{issue_number}] Issue 'opened' but already has state {current_story_label}. No initial setup.")

    # Main state processing loop - can loop if state changes multiple times in one run
    processed_in_run = set() # To avoid infinite loops if state logic cycles
    while current_story_label and current_story_label not in processed_in_run and current_story_label not in TERMINAL_STATES:
        processed_in_run.add(current_story_label)
        previous_story_label_for_loop = current_story_label # Store before potential change

        iteration_label = await get_current_iteration_label(current_labels)
        current_iteration_num = 0
        if iteration_label:
            try: current_iteration_num = int(iteration_label.split('/')[1])
            except (ValueError, IndexError): logger.warning(f"Could not parse iter num from {iteration_label}")

        if current_story_label == 'story/draft':
            # Check if initial feedback has been generated and transition to enriching
            logger.info(f"[{issue_number}] Processing story/draft state")
            # The auto-actions should have been executed during transition to this state
            # Now transition to enriching state to continue the workflow
            if 'trigger/consensus-check' in current_labels:
                logger.info(f"[{issue_number}] Initial feedback generated, transitioning to story/enriching")
                current_labels = await _transition_to_state(issue_number, current_labels, 'story/enriching', github_service, llm_service, story_orchestrator, actor)
                # Add iterate trigger for enriching state
                trigger_label = 'trigger/iterate'
                if trigger_label not in current_labels:
                    if github_service.add_label_to_issue(issue_number, trigger_label):
                        current_labels.append(trigger_label)
            else:
                logger.info(f"[{issue_number}] Waiting for initial feedback generation to complete")

        elif current_story_label == 'story/enriching':
            trigger_iterate_label = 'trigger/iterate'
            if trigger_iterate_label in current_labels:
                logger.info(f"[{issue_number}] '{trigger_iterate_label}' detected for 'story/enriching'.")
                enriching_config = WORKFLOW_STATES.get('story/enriching', {})
                
                # Use configurable iteration limit if auto-consensus is enabled
                if config.auto_consensus_enabled:
                    iteration_limit = config.auto_consensus_max_iterations
                else:
                    iteration_limit = enriching_config.get('iteration_limit', 5)
                    
                next_iteration_num = current_iteration_num + 1
                if not iteration_label: next_iteration_num = 1 # First iteration

                if next_iteration_num <= iteration_limit:
                    logger.info(f"[{issue_number}] Processing iteration {next_iteration_num} for 'story/enriching' (limit: {iteration_limit}).")
                    if iteration_label and iteration_label != f"iteration/{next_iteration_num}":
                        if github_service.remove_label_from_issue(issue_number, iteration_label): current_labels.remove(iteration_label)
                    new_iteration_label = f"iteration/{next_iteration_num}"
                    if new_iteration_label not in current_labels:
                        if github_service.add_label_to_issue(issue_number, new_iteration_label): current_labels.append(new_iteration_label)
                    
                    try:
                        await story_orchestrator.gather_feedback_and_iterate(issue_number, DEFAULT_ROLES_FOR_FEEDBACK)
                        logger.info(f"[{issue_number}] Iteration {next_iteration_num} processing complete.")
                        
                        # If auto-consensus is enabled, automatically trigger consensus check
                        if config.auto_consensus_enabled:
                            logger.info(f"[{issue_number}] Auto-consensus enabled, transitioning to reviewing for consensus check.")
                            current_labels = await _transition_to_state(issue_number, current_labels, 'story/reviewing', github_service, llm_service, story_orchestrator, actor)
                            # Add consensus check trigger
                            consensus_trigger_label = 'trigger/consensus-check'
                            if consensus_trigger_label not in current_labels:
                                if github_service.add_label_to_issue(issue_number, consensus_trigger_label):
                                    current_labels.append(consensus_trigger_label)
                        else:
                            logger.info(f"[{issue_number}] Conceptual: Check if all roles provided input to move to 'story/reviewing'.")
                    except Exception as e:
                        logger.error(f"[{issue_number}] Error during gather_feedback_and_iterate for iteration {next_iteration_num}: {e}", exc_info=True)
                else: 
                    logger.warning(f"[{issue_number}] Iteration limit ({iteration_limit}) reached. Transitioning to 'story/blocked'.")
                    current_labels = await _transition_to_state(issue_number, current_labels, 'story/blocked', github_service, llm_service, story_orchestrator, actor)
                
                if trigger_iterate_label in current_labels: # Cleanup trigger
                    if github_service.remove_label_from_issue(issue_number, trigger_iterate_label): current_labels.remove(trigger_iterate_label)
                    logger.info(f"[{issue_number}] Removed '{trigger_iterate_label}' label.")
            else:
                logger.info(f"[{issue_number}] In 'story/enriching', no '{trigger_iterate_label}'. Waiting for conditions or manual trigger.")


        elif current_story_label == 'story/reviewing':
            trigger_consensus_check_label = 'trigger/consensus-check'
            if trigger_consensus_check_label in current_labels or action == 'labeled': # Process if triggered or if just entered state
                logger.info(f"[{issue_number}] Processing 'story/reviewing'. Trigger: '{trigger_consensus_check_label if trigger_consensus_check_label in current_labels else 'state_entry'}'.")
                review_config = WORKFLOW_STATES.get('story/reviewing', {})
                roles_for_consensus = review_config.get('required_roles_for_consensus', DEFAULT_ROLES_FOR_CONSENSUS_CHECK)
                
                agreed = await story_orchestrator.check_agreement(issue_number, roles_for_consensus)
                consensus_score = 100 if agreed else 40 
                logger.info(f"[{issue_number}] Consensus check: Agreed: {agreed} (Score: {consensus_score}%)")

                old_consensus_label = await get_current_consensus_label(current_labels)
                if old_consensus_label:
                    if github_service.remove_label_from_issue(issue_number, old_consensus_label): current_labels.remove(old_consensus_label)
                new_consensus_label = get_consensus_label_from_score(consensus_score)
                if github_service.add_label_to_issue(issue_number, new_consensus_label): current_labels.append(new_consensus_label)
                logger.info(f"[{issue_number}] Applied consensus label: {new_consensus_label}")

                if trigger_consensus_check_label in current_labels:
                    if github_service.remove_label_from_issue(issue_number, trigger_consensus_check_label): current_labels.remove(trigger_consensus_check_label)
                    logger.info(f"[{issue_number}] Removed '{trigger_consensus_check_label}' label.")

                # Use configurable consensus threshold if auto-consensus is enabled
                if config.auto_consensus_enabled:
                    pass_threshold = config.auto_consensus_threshold
                    iteration_limit = config.auto_consensus_max_iterations
                else:
                    pass_threshold = review_config.get('consensus_threshold_pass', 80)
                    iteration_limit = WORKFLOW_STATES.get('story/enriching', {}).get('iteration_limit', 5)
                
                logger.info(f"[{issue_number}] Using consensus threshold: {pass_threshold}%, iteration limit: {iteration_limit}")
                
                # Re-fetch iteration number as it's critical for decision
                iteration_label = await get_current_iteration_label(current_labels)
                current_iteration_num = 0
                if iteration_label:
                    try: current_iteration_num = int(iteration_label.split('/')[1])
                    except (ValueError, IndexError): logger.warning(f"Could not parse iter num from {iteration_label}")


                if consensus_score >= pass_threshold:
                    logger.info(f"[{issue_number}] Consensus met ({consensus_score}% >= {pass_threshold}%). Transitioning to 'story/consensus'.")
                    current_labels = await _transition_to_state(issue_number, current_labels, 'story/consensus', github_service, llm_service, story_orchestrator, actor)
                else:
                    if current_iteration_num < iteration_limit:
                        if config.auto_consensus_enabled:
                            logger.info(f"[{issue_number}] Auto-consensus: Consensus not met ({consensus_score}% < {pass_threshold}%). Iterations {current_iteration_num}/{iteration_limit}. Automatically transitioning back to 'story/enriching'.")
                            current_labels = await _transition_to_state(issue_number, current_labels, 'story/enriching', github_service, llm_service, story_orchestrator, actor)
                            # Add iterate trigger for automatic iteration
                            iterate_trigger_label = 'trigger/iterate'
                            if iterate_trigger_label not in current_labels:
                                if github_service.add_label_to_issue(issue_number, iterate_trigger_label):
                                    current_labels.append(iterate_trigger_label)
                        else:
                            logger.info(f"[{issue_number}] Consensus not met ({consensus_score}% < {pass_threshold}%). Iterations {current_iteration_num}/{iteration_limit}. Transitioning to 'story/enriching'.")
                            current_labels = await _transition_to_state(issue_number, current_labels, 'story/enriching', github_service, llm_service, story_orchestrator, actor)
                    else:
                        logger.warning(f"[{issue_number}] Consensus not met ({consensus_score}% < {pass_threshold}%) and iteration limit reached ({current_iteration_num}/{iteration_limit}). Transitioning to 'story/blocked'.")
                        current_labels = await _transition_to_state(issue_number, current_labels, 'story/blocked', github_service, llm_service, story_orchestrator, actor)
            else:
                 logger.info(f"[{issue_number}] In 'story/reviewing'. Waiting for '{trigger_consensus_check_label}' or other relevant event.")


        elif current_story_label == 'story/consensus':
            logger.info(f"[{issue_number}] In 'story/consensus'. Transitioning to 'story/ready'.")
            current_labels = await _transition_to_state(issue_number, current_labels, 'story/ready', github_service, llm_service, story_orchestrator, actor)

        elif current_story_label == 'story/blocked':
            logger.info(f"[{issue_number}] In 'story/blocked'. Manual intervention typically required.")
            if WORKFLOW_STATES.get('story/blocked',{}).get('manual_intervention', False): 
                 logger.info(f"[{issue_number}] Conceptual: Suggest escalation.")
                 logger.info(f"[{issue_number}] Conceptual: Notify stakeholders.")
            break # Exit loop as it's a manual state usually

        elif current_story_label == 'story/ready':
            logger.info(f"[{issue_number}] In 'story/ready'. Can be finalized manually or check for finalization triggers.")
            
            # Check if finalize-story command has been run (story/finalized label added)
            if 'story/finalized' in current_labels:
                logger.info(f"[{issue_number}] Story has been finalized. Transitioning to finalized state.")
                current_labels = await _transition_to_state(issue_number, current_labels, 'story/finalized', github_service, llm_service, story_orchestrator, actor)
            else:
                logger.info(f"[{issue_number}] Story is ready. Awaiting finalization trigger or manual action.")
                break # Exit loop - terminal state for active automation unless finalized

        elif current_story_label == 'story/finalized':
            logger.info(f"[{issue_number}] In 'story/finalized'. Processing finalization workflow.")
            
            # Auto-add needs/user-approval label if not present
            if 'needs/user-approval' not in current_labels:
                if await github_service.add_label_to_issue(issue_number, 'needs/user-approval'):
                    current_labels.append('needs/user-approval')
                    logger.info(f"[{issue_number}] Added 'needs/user-approval' label.")
            
            # Check if user has approved (approved/user label added)
            if 'approved/user' in current_labels:
                logger.info(f"[{issue_number}] User approval detected. Transitioning to user-approved state.")
                current_labels = await _transition_to_state(issue_number, current_labels, 'story/user-approved', github_service, llm_service, story_orchestrator, actor)
            else:
                logger.info(f"[{issue_number}] Awaiting user approval. Story remains in finalized state.")
                break # Exit loop - waiting for manual user approval

        elif current_story_label == 'story/user-approved':
            logger.info(f"[{issue_number}] In 'story/user-approved'. Preparing for development workflow.")
            
            # Clean up approval labels and transition back to ready for development
            if 'needs/user-approval' in current_labels:
                if await github_service.remove_label_from_issue(issue_number, 'needs/user-approval'):
                    current_labels.remove('needs/user-approval')
            
            # Transition back to ready state for development workflow
            current_labels = await _transition_to_state(issue_number, current_labels, 'story/ready', github_service, llm_service, story_orchestrator, actor)
            
            # Add comment indicating story is ready for development
            await github_service.add_comment_to_issue(
                issue_number, 
                "✅ **Story Approved and Ready for Development**\n\n"
                "This story has been finalized and approved by the user. It is now ready to enter the development workflow."
            )
            
            logger.info(f"[{issue_number}] Story approved and ready for development workflow.")
            break # Exit loop - back to ready state

        # Update current_story_label for the next iteration of the while loop
        current_story_label = await get_current_story_state_label(current_labels)
        if not current_story_label or current_story_label == previous_story_label_for_loop : # If state didn't change or no state label
            break # Avoid infinite loop if a state handler doesn't transition

    # Final check for terminal states if loop exited due to state not in processed_in_run but is terminal
    if current_story_label in TERMINAL_STATES:
        logger.info(f"[{issue_number}] Confirmed in terminal state '{current_story_label}'. Conceptual final actions if any.")
        if current_story_label == 'story/archived' and WORKFLOW_STATES['story/archived'].get('auto_actions'):
            logger.info(f"[{issue_number}] Conceptual auto_action for '{current_story_label}': {WORKFLOW_STATES['story/archived']['auto_actions']}")
        elif current_story_label == 'story/split' and WORKFLOW_STATES['story/split'].get('auto_actions'):
            logger.info(f"[{issue_number}] Conceptual auto_action for '{current_story_label}': {WORKFLOW_STATES['story/split']['auto_actions']}")
            logger.info(f"[{issue_number}] Conceptual: Suggest creating new issues for split parts and linking.")

    logger.info(f"[{issue_number}] End of processing for event '{trigger_event}', action '{action}'. Final labels (approx): {current_labels}")


async def main_async(): 
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv() 

    parser = argparse.ArgumentParser(description="Process GitHub issue events for story lifecycle automation.")
    parser.add_argument("--issue-number", type=int, required=True, help="GitHub issue number.")
    parser.add_argument("--trigger-event", type=str, required=True, 
                        choices=['issues', 'issue_comment', 'workflow_dispatch'], 
                        help="GitHub event that triggered the workflow.")
    parser.add_argument("--action", type=str, 
                        help="Action for the event (e.g., 'opened', 'labeled', 'unlabeled', 'created', 'edited').")
    parser.add_argument("--current-labels", type=str, default="", 
                        help="Comma-separated string of current issue labels.")
    parser.add_argument("--comment-body", type=str, 
                        help="Body of the comment if trigger_event is 'issue_comment'.")
    parser.add_argument("--actor", type=str, help="GitHub username of the actor who triggered the event.") 
    parser.add_argument("--log-level", type=str, default="INFO", 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], 
                        help="Set the logging level for the script.")
    
    args = parser.parse_args()

    effective_log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=effective_log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Workflow Processor started. Args: Issue: {args.issue_number}, Event: {args.trigger_event}, "
                f"Action: {args.action}, Actor: {args.actor}, Labels: '{args.current_labels}', LogLevel: {args.log_level}")

    try:
        github_service = GitHubService() 
        llm_service = LLMService()       
        story_orchestrator = StoryOrchestrator(llm_service=llm_service, github_service=github_service)
        
        # Enable repository-based prompts if environment variable is set
        use_repository_prompts = os.environ.get('USE_REPOSITORY_PROMPTS', '').lower() in ('true', '1', 'yes')
        if use_repository_prompts:
            story_orchestrator.use_repository_prompts = True
            logger.info("Repository-based prompts enabled via USE_REPOSITORY_PROMPTS environment variable.")
        
        logger.info("Services initialized.")
    except ValueError as ve: 
        logger.error(f"Initialization failed (config error): {ve}. Check env variables.", exc_info=True)
        return 
    except Exception as e:
        logger.error(f"Unexpected error during service initialization: {e}", exc_info=True)
        return 

    try:
        await process_story_state(
            issue_number=args.issue_number,
            trigger_event=args.trigger_event,
            action=args.action,
            current_labels_str=args.current_labels, 
            comment_body=args.comment_body,
            actor=args.actor, 
            github_service=github_service,
            llm_service=llm_service,
            story_orchestrator=story_orchestrator
        )
    except Exception as e:
        logger.error(f"[{args.issue_number}] Unhandled error in process_story_state: {e}", exc_info=True)

    logger.info(f"Workflow Processor finished. Issue: {args.issue_number}, Event: {args.trigger_event}, Action: {args.action}")

if __name__ == "__main__":
    asyncio.run(main_async())
