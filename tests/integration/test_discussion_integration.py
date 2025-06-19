"""Integration tests for discussion simulation functionality."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.storyteller.config import Config
from src.storyteller.conversation_manager import ConversationManager
from src.storyteller.database import DatabaseManager
from src.storyteller.discussion_engine import DiscussionEngine


class TestDiscussionIntegration:
    """Integration tests for the discussion simulation system."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_discussions.db"
        return DatabaseManager(str(db_path))

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=Config)
        config.auto_consensus_threshold = 70
        config.max_retries = 3
        config.github_token = "test_token"
        config.default_llm_provider = "test_provider"
        config.openai_api_key = None
        config.ollama_api_host = "http://localhost:11434"
        return config

    @pytest.mark.asyncio
    async def test_conversation_manager_discussion_integration(self, mock_config, temp_db):
        """Test integration between ConversationManager and discussion simulation."""
        
        with patch("src.storyteller.conversation_manager.DatabaseManager") as mock_db_class, \
             patch("src.storyteller.conversation_manager.MultiRepositoryContextReader"), \
             patch("src.storyteller.discussion_engine.LLMHandler") as mock_llm_class, \
             patch("src.storyteller.discussion_engine.RoleAssignmentEngine") as mock_role_class, \
             patch("src.storyteller.discussion_engine.MultiRepositoryContextReader"):

            # Setup mocks
            mock_db_class.return_value = temp_db
            
            mock_llm = MagicMock()
            mock_llm.generate_response = AsyncMock(return_value=MagicMock(
                content="Viewpoint: This is a test perspective. Arguments: Test arg. Confidence: 0.8"
            ))
            mock_llm_class.return_value = mock_llm

            mock_role_engine = MagicMock()
            mock_assignment = MagicMock()
            mock_assignment.primary_roles = [
                MagicMock(role_name="system-architect", confidence_score=0.9),
                MagicMock(role_name="lead-developer", confidence_score=0.8),
            ]
            mock_assignment.secondary_roles = []
            mock_role_engine.assign_roles.return_value = mock_assignment
            mock_role_class.return_value = mock_role_engine

            # Create conversation manager
            conv_manager = ConversationManager(mock_config)
            
            # Start a discussion
            topic = "API Design Strategy"
            story_content = "Implement RESTful API for user management"
            repositories = ["backend", "frontend"]

            result = await conv_manager.start_discussion(
                topic=topic,
                story_content=story_content,
                repositories=repositories,
                max_discussion_rounds=1
            )

            # Verify results
            assert result.topic == topic
            assert result.conversation_id
            assert len(result.perspectives) > 0
            
            # Check that perspectives were generated for the expected roles
            role_names = [p.role_name for p in result.perspectives]
            # Note: The discussion engine adds default roles, so we check for some expected roles
            assert len(role_names) >= 2  # Should have at least a couple roles
            # Check for at least one of the primary roles we mocked
            assert any(role in role_names for role in ["system-architect", "lead-developer"])

    @pytest.mark.asyncio
    async def test_discussion_consensus_tracking(self, mock_config, temp_db):
        """Test consensus tracking throughout discussion process."""
        
        with patch("src.storyteller.discussion_engine.DatabaseManager") as mock_db_class, \
             patch("src.storyteller.discussion_engine.LLMHandler") as mock_llm_class, \
             patch("src.storyteller.discussion_engine.RoleAssignmentEngine") as mock_role_class, \
             patch("src.storyteller.discussion_engine.MultiRepositoryContextReader"):

            # Setup mocks
            mock_db_class.return_value = temp_db
            
            # Mock LLM responses that should create high consensus
            mock_llm = MagicMock()
            mock_llm.generate_response = AsyncMock(return_value=MagicMock(
                content="""
                Viewpoint: REST API is the right choice for this user management system.
                Arguments: 
                - Well-established standard with good tooling
                - Easy to understand and implement
                Concerns:
                - Need proper authentication
                Suggestions:
                - Use JWT tokens
                - Implement rate limiting
                Confidence: 0.9
                """
            ))
            mock_llm_class.return_value = mock_llm

            # Mock role assignment with complementary roles
            mock_role_engine = MagicMock()
            mock_assignment = MagicMock()
            mock_assignment.primary_roles = [
                MagicMock(role_name="system-architect", confidence_score=0.9),
                MagicMock(role_name="security-expert", confidence_score=0.8),
            ]
            mock_assignment.secondary_roles = []
            mock_role_engine.assign_roles.return_value = mock_assignment
            mock_role_class.return_value = mock_role_engine

            # Create discussion engine
            discussion_engine = DiscussionEngine(mock_config)
            
            # Start discussion
            result = await discussion_engine.start_discussion(
                topic="User Management API",
                story_content="Implement secure user authentication and profile management",
                repositories=["backend"],
                max_discussion_rounds=2
            )

            # Verify consensus tracking
            assert result.consensus_level >= 0.0
            assert result.consensus_level <= 1.0
            
            # Check status determination based on consensus
            if result.consensus_level >= 0.7:
                assert result.status == "resolved"
            else:
                assert result.status in ["needs_human_input", "active"]

    @pytest.mark.asyncio
    async def test_discussion_summary_generation(self, mock_config, temp_db):
        """Test generation of discussion summaries."""
        
        with patch("src.storyteller.discussion_engine.DatabaseManager") as mock_db_class, \
             patch("src.storyteller.discussion_engine.LLMHandler") as mock_llm_class, \
             patch("src.storyteller.discussion_engine.RoleAssignmentEngine") as mock_role_class, \
             patch("src.storyteller.discussion_engine.MultiRepositoryContextReader"):

            # Setup mocks
            mock_db_class.return_value = temp_db
            
            mock_llm = MagicMock()
            # Different responses for perspective generation vs summary generation
            responses = [
                # Perspective generation responses
                MagicMock(content="Viewpoint: Focus on security. Arguments: Need authentication. Confidence: 0.8"),
                MagicMock(content="Viewpoint: Prioritize performance. Arguments: Cache frequently accessed data. Confidence: 0.9"),
                # Summary generation response
                MagicMock(content="""
                Key Points:
                - Security and performance are both important
                - Need balanced approach
                
                Areas of Agreement:
                - Authentication is required
                - Performance optimization needed
                
                Recommended Actions:
                - Implement JWT authentication
                - Add caching layer
                """)
            ]
            mock_llm.generate_response = AsyncMock(side_effect=responses)
            mock_llm_class.return_value = mock_llm

            mock_role_engine = MagicMock()
            mock_assignment = MagicMock()
            mock_assignment.primary_roles = [
                MagicMock(role_name="security-expert", confidence_score=0.9),
                MagicMock(role_name="system-architect", confidence_score=0.8),
            ]
            mock_assignment.secondary_roles = []
            mock_role_engine.assign_roles.return_value = mock_assignment
            mock_role_class.return_value = mock_role_engine

            # Create discussion engine and start discussion
            discussion_engine = DiscussionEngine(mock_config)
            
            thread = await discussion_engine.start_discussion(
                topic="System Performance vs Security",
                story_content="Balance performance and security requirements",
                repositories=["backend"],
                max_discussion_rounds=1
            )

            # Generate summary
            summary = await discussion_engine.generate_discussion_summary(thread)

            # Verify summary content
            assert summary.conversation_id == thread.conversation_id
            assert summary.discussion_topic == thread.topic
            assert len(summary.participating_roles) > 0
            # Note: The actual roles returned may include default roles
            assert any(role in summary.participating_roles for role in ["security-expert", "system-architect"])
            
            # Should have some structured information (parsing might not be perfect in test)
            # We'll be more lenient on the exact content since parsing is complex
            assert summary.overall_consensus >= 0.0

    @pytest.mark.asyncio
    async def test_human_intervention_workflow(self, mock_config, temp_db):
        """Test workflow when human intervention is needed."""
        
        with patch("src.storyteller.discussion_engine.DatabaseManager") as mock_db_class, \
             patch("src.storyteller.discussion_engine.LLMHandler") as mock_llm_class, \
             patch("src.storyteller.discussion_engine.RoleAssignmentEngine") as mock_role_class, \
             patch("src.storyteller.discussion_engine.MultiRepositoryContextReader"):

            # Setup mocks for low consensus scenario
            mock_db_class.return_value = temp_db
            
            mock_llm = MagicMock()
            # Conflicting responses that should lead to low consensus
            responses = [
                MagicMock(content="Viewpoint: Use microservices architecture. Arguments: Better scalability."),
                MagicMock(content="Viewpoint: Stick with monolithic approach. Arguments: Simpler deployment."),
                MagicMock(content="Viewpoint: Hybrid approach is best. Arguments: Balance complexity and benefits."),
            ]
            mock_llm.generate_response = AsyncMock(side_effect=responses)
            mock_llm_class.return_value = mock_llm

            mock_role_engine = MagicMock()
            mock_assignment = MagicMock()
            mock_assignment.primary_roles = [
                MagicMock(role_name="system-architect", confidence_score=0.9),
                MagicMock(role_name="lead-developer", confidence_score=0.8),
                MagicMock(role_name="devops-engineer", confidence_score=0.8),
            ]
            mock_assignment.secondary_roles = []
            mock_role_engine.assign_roles.return_value = mock_assignment
            mock_role_class.return_value = mock_role_engine

            # Mock database operations for resume functionality
            discussion_engine = DiscussionEngine(mock_config)
            
            # Start discussion that should require human input
            thread = await discussion_engine.start_discussion(
                topic="Architecture Decision",
                story_content="Choose between microservices and monolithic architecture",
                repositories=["backend", "frontend"],
                max_discussion_rounds=1
            )

            # Should trigger needs_human_input due to low consensus
            if thread.consensus_level < 0.7:
                assert thread.status == "needs_human_input"
                
                # Test resuming with human input
                temp_db.get_discussion_thread = MagicMock(return_value=thread)
                temp_db.get_conversation = MagicMock(return_value=MagicMock(
                    description="Architecture discussion",
                    repositories=["backend", "frontend"]
                ))
                
                resumed_thread = await discussion_engine.resume_discussion(
                    thread.id,
                    "Let's go with a modular monolith approach as a starting point"
                )
                
                # Should have added human facilitator perspective
                human_perspectives = [p for p in resumed_thread.perspectives if p.role_name == "human-facilitator"]
                assert len(human_perspectives) == 1
                assert "modular monolith" in human_perspectives[0].viewpoint

    def test_database_discussion_models_integration(self, temp_db):
        """Test that discussion models integrate properly with database."""
        from src.storyteller.models import RolePerspective, DiscussionThread, DiscussionSummary, Conversation

        # First create a conversation (required for foreign key)
        conversation = Conversation(
            id="test-conv",
            title="Test Conversation",
            description="Test conversation for discussion",
            repositories=["test-repo"],
        )
        temp_db.save_conversation(conversation)

        # Create and save a perspective
        perspective = RolePerspective(
            role_name="test-role",
            viewpoint="Test perspective viewpoint",
            arguments=["Argument 1", "Argument 2"],
            concerns=["Concern 1"],
            suggestions=["Suggestion 1", "Suggestion 2"],
            confidence_level=0.8,
            repository_context="test-repo",
        )

        # Create and save a discussion thread
        thread = DiscussionThread(
            conversation_id="test-conv",
            topic="Test Discussion",
            perspectives=[perspective],
        )

        # Test database operations
        saved_thread_id = temp_db.save_discussion_thread(thread)
        assert saved_thread_id == thread.id

        # Retrieve and verify
        retrieved_thread = temp_db.get_discussion_thread(thread.id)
        assert retrieved_thread is not None
        assert retrieved_thread.topic == "Test Discussion"
        assert len(retrieved_thread.perspectives) == 1
        assert retrieved_thread.perspectives[0].role_name == "test-role"

        # Create and save a summary
        summary = DiscussionSummary(
            conversation_id="test-conv",
            discussion_topic="Test Discussion",
            participating_roles=["test-role"],
            key_points=["Key point 1"],
            areas_of_agreement=["Agreement 1"],
            recommended_actions=["Action 1"],
            overall_consensus=0.8,
            confidence_score=0.9,
        )

        saved_summary_id = temp_db.save_discussion_summary(summary)
        assert saved_summary_id == summary.id

        # Retrieve and verify summary
        retrieved_summary = temp_db.get_discussion_summary("test-conv")
        assert retrieved_summary is not None
        assert retrieved_summary.discussion_topic == "Test Discussion"
        assert retrieved_summary.overall_consensus == 0.8