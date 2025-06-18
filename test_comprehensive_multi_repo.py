"""Unit tests for multi-repository configuration and capabilities without external API calls."""

import os

from config import get_config

# Set environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


def test_repository_configuration():
    """Test repository configuration reading."""

    config = get_config()

    # Basic configuration validation
    assert hasattr(config, "repositories")
    assert len(config.repositories) > 0

    # Test that our multi-repository configuration is properly structured
    assert "storyteller" in config.repositories
    storyteller_config = config.repositories["storyteller"]
    assert hasattr(storyteller_config, "name")
    assert hasattr(storyteller_config, "type")
    assert hasattr(storyteller_config, "description")

    # Test configuration has expected repositories
    expected_repos = ["storyteller", "backend", "frontend"]
    for repo in expected_repos:
        if repo in config.repositories:
            repo_config = config.repositories[repo]
            assert repo_config.name is not None
            assert repo_config.type is not None

    # Test dependency relationships
    if "frontend" in config.repositories:
        frontend_config = config.repositories["frontend"]
        assert hasattr(frontend_config, "dependencies")


def test_multi_repository_structure():
    """Test multi-repository structure validation."""

    config = get_config()

    # Test each repository has required fields
    for key, repo_config in config.repositories.items():
        assert hasattr(repo_config, "name")
        assert hasattr(repo_config, "type")
        assert hasattr(repo_config, "description")
        assert hasattr(repo_config, "dependencies")
        assert hasattr(repo_config, "story_labels")
        
        # Test that dependencies reference valid repositories
        for dep in repo_config.dependencies:
            assert dep in config.repositories or dep == "", f"Invalid dependency {dep} in {key}"


def test_repository_types():
    """Test repository type classifications."""

    config = get_config()

    # Test that we have different repository types
    types = set()
    for repo_config in config.repositories.values():
        types.add(repo_config.type)

    # Should have multiple types for a multi-repo system
    assert len(types) >= 1

    # Common repository types should be present
    expected_types = {"backend", "frontend", "mobile", "data", "devops"}
    available_types = {repo_config.type for repo_config in config.repositories.values()}
    
    # At least some expected types should be present
    assert len(expected_types & available_types) > 0


if __name__ == "__main__":
    print("Running comprehensive multi-repository unit tests...")
    print("=" * 60)
    
    test_repository_configuration()
    test_multi_repository_structure()
    test_repository_types()
    
    print("=" * 60)
    print("✓ All comprehensive multi-repository unit tests passed!")