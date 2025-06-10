"""Integration tests for the AI Story Management System."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

from automation.workflow_processor import WorkflowProcessor
from config import get_config
from mcp_server import MCPRequest, MCPStoryServer
from story_manager import StoryManager, StoryRequest


def setup_test_environment():
    """Setup test environment with mock configuration."""
    os.environ["GITHUB_TOKEN"] = "test_token_integration"
    os.environ["DEFAULT_LLM_PROVIDER"] = "github"

    # Clear config cache
    if hasattr(get_config, "_config"):
        delattr(get_config, "_config")


def test_configuration_integration():
    """Test configuration loading with all components."""
    setup_test_environment()

    config = get_config()
    assert config.github_token == "test_token_integration"
    assert len(config.repositories) == 3  # storyteller, backend, frontend
    assert "storyteller" in config.repositories
    assert "backend" in config.repositories
    assert "frontend" in config.repositories

    print("✓ Configuration integration test passed")


def test_role_loading_integration():
    """Test role loading integration."""
    setup_test_environment()

    story_manager = StoryManager()
    roles = story_manager.get_available_roles()

    assert len(roles) >= 20  # Should have many expert roles
    assert "system-architect" in roles
    assert "lead-developer" in roles
    assert "ai-expert" in roles
    assert "professional-chef" in roles

    print("✓ Role loading integration test passed")


def test_workflow_processor_integration():
    """Test workflow processor integration."""
    setup_test_environment()

    processor = WorkflowProcessor()

    # Test repository listing
    result = processor.list_repositories_workflow()
    assert result.success
    assert len(result.data["repositories"]) == 3

    # Test role listing
    result = processor.list_roles_workflow()
    assert result.success
    assert result.data["total_count"] >= 20

    print("✓ Workflow processor integration test passed")


async def test_mcp_server_integration():
    """Test MCP server integration."""
    setup_test_environment()

    server = MCPStoryServer()

    # Test health check
    request = MCPRequest(id="test_health", method="system/health", params={})

    response = await server.handle_request(request)
    assert response.error is None
    assert response.result["status"] == "healthy"

    # Test capabilities
    request = MCPRequest(
        id="test_capabilities", method="system/capabilities", params={}
    )

    response = await server.handle_request(request)
    assert response.error is None
    assert "methods" in response.result
    assert len(response.result["methods"]) > 0

    # Test list roles
    request = MCPRequest(id="test_list_roles", method="role/list", params={})

    response = await server.handle_request(request)
    assert response.error is None
    assert response.result["success"]

    # Test list repositories
    request = MCPRequest(id="test_list_repos", method="repository/list", params={})

    response = await server.handle_request(request)
    assert response.error is None
    assert response.result["success"]

    print("✓ MCP server integration test passed")


async def test_story_analysis_mock():
    """Test story analysis with mocked LLM responses."""
    setup_test_environment()

    # Mock LLM responses
    mock_analysis_response = """
    As a System Architect, I analyze this story:
    
    **Analysis**: This story requires careful consideration of authentication patterns.
    
    **Recommendations**:
    - Implement OAuth 2.0 with JWT tokens
    - Use secure session management
    - Consider multi-factor authentication
    
    **Concerns**:
    - Security implications need careful review
    - Scalability considerations for user sessions
    """

    mock_synthesis_response = """
    # Comprehensive Story Analysis
    
    Based on expert analysis, this authentication story requires:
    
    ## Key Requirements
    - Secure authentication implementation
    - Scalable session management
    - Proper security measures
    
    ## Recommendations
    - Use industry-standard OAuth 2.0
    - Implement proper session handling
    - Add comprehensive security testing
    """

    with patch("llm_handler.LLMHandler.generate_response") as mock_llm:
        # Mock content analysis
        mock_llm.return_value = Mock(
            content='{"recommended_roles": ["system-architect", "security-expert"], "target_repositories": ["backend"], "complexity": "medium", "themes": ["authentication"], "reasoning": "Authentication requires security expertise"}'
        )

        # Create story manager
        story_manager = StoryManager()

        # Mock individual expert analyses
        with patch.object(
            story_manager.processor, "get_expert_analysis"
        ) as mock_expert:
            mock_expert.return_value = Mock(
                role_name="system-architect",
                analysis=mock_analysis_response,
                recommendations=["Implement OAuth 2.0", "Use secure sessions"],
                concerns=["Security implications", "Scalability considerations"],
                metadata={"model": "gpt-4", "provider": "github"},
            )

            # Mock synthesis
            with patch.object(
                story_manager.processor, "synthesize_analyses"
            ) as mock_synthesis:
                mock_synthesis.return_value = mock_synthesis_response

                # Test story analysis
                story_request = StoryRequest(
                    content="Create user authentication system for recipe platform",
                    target_repositories=["backend"],
                    required_roles=["system-architect", "security-expert"],
                )

                processed_story = await story_manager.processor.process_story(
                    story_request
                )

                assert processed_story.story_id is not None
                assert processed_story.original_content == story_request.content
                assert len(processed_story.expert_analyses) >= 1
                assert processed_story.synthesized_analysis == mock_synthesis_response
                assert "backend" in processed_story.target_repositories

                print("✓ Story analysis mock test passed")


async def test_mcp_story_analysis_mock():
    """Test MCP story analysis with mocked responses."""
    setup_test_environment()

    with patch("llm_handler.LLMHandler.analyze_story_with_role") as mock_role_analysis:
        mock_role_analysis.return_value = Mock(
            content="Expert analysis response from the role",
            model="gpt-4",
            provider="github",
            metadata={"usage": {"tokens": 100}},
        )

        server = MCPStoryServer()

        # Test role query
        request = MCPRequest(
            id="test_role_query",
            method="role/query",
            params={
                "role_name": "system-architect",
                "question": "How should we implement user authentication?",
                "context": {"project": "recipe-platform"},
            },
        )

        response = await server.handle_request(request)
        assert response.error is None
        assert response.result["role_name"] == "system-architect"
        assert "response" in response.result

        print("✓ MCP story analysis mock test passed")


def test_cli_command_structure():
    """Test CLI command structure and help."""
    import subprocess
    import sys

    # Test main help
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
        cwd="/home/runner/work/storyteller/storyteller",
    )
    assert result.returncode == 0
    assert "AI-Powered Story Management System" in result.stdout

    # Test story subcommands
    result = subprocess.run(
        [sys.executable, "main.py", "story", "--help"],
        capture_output=True,
        text=True,
        cwd="/home/runner/work/storyteller/storyteller",
    )
    assert result.returncode == 0
    assert "Story creation and management commands" in result.stdout

    # Test MCP subcommands
    result = subprocess.run(
        [sys.executable, "main.py", "mcp", "--help"],
        capture_output=True,
        text=True,
        cwd="/home/runner/work/storyteller/storyteller",
    )
    assert result.returncode == 0
    assert "MCP" in result.stdout

    print("✓ CLI command structure test passed")


async def test_error_handling():
    """Test error handling in various components."""
    setup_test_environment()

    server = MCPStoryServer()

    # Test invalid method
    request = MCPRequest(id="test_invalid", method="invalid/method", params={})

    response = await server.handle_request(request)
    assert response.error is not None
    assert response.error["code"] == -32601  # Method not found

    # Test missing parameters
    request = MCPRequest(
        id="test_missing_params",
        method="role/query",
        params={},  # Missing required parameters
    )

    response = await server.handle_request(request)
    assert response.error is not None

    print("✓ Error handling test passed")


async def test_configuration_validation():
    """Test configuration validation functionality."""
    setup_test_environment()

    processor = WorkflowProcessor()

    result = await processor.validate_configuration_workflow()

    # Should succeed with test configuration
    assert result.success
    assert "repositories" in result.data
    assert "role_files" in result.data

    print("✓ Configuration validation test passed")


async def run_all_integration_tests():
    """Run all integration tests."""
    print("Running integration tests...")

    # Synchronous tests
    test_configuration_integration()
    test_role_loading_integration()
    test_workflow_processor_integration()
    test_cli_command_structure()

    # Asynchronous tests
    await test_mcp_server_integration()
    await test_story_analysis_mock()
    await test_mcp_story_analysis_mock()
    await test_error_handling()
    await test_configuration_validation()

    print("\n✅ All integration tests passed!")


if __name__ == "__main__":
    asyncio.run(run_all_integration_tests())
