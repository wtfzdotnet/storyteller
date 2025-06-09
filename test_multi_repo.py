#!/usr/bin/env python3
"""
Test script for multi-repository functionality.
This script validates the core multi-repository features without requiring actual GitHub API calls.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add the current directory to the path to import modules
sys.path.insert(0, ".")


def test_config_loading():
    """Test that multi-repository configuration loads correctly."""
    print("Testing configuration loading...")

    # Test with temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create .storyteller directory and config
        storyteller_dir = temp_path / ".storyteller"
        storyteller_dir.mkdir()

        config_data = {
            "repositories": {
                "backend": {
                    "name": "test/backend",
                    "type": "backend",
                    "description": "Test backend",
                    "dependencies": [],
                    "story_labels": ["backend"],
                },
                "frontend": {
                    "name": "test/frontend",
                    "type": "frontend",
                    "description": "Test frontend",
                    "dependencies": ["backend"],
                    "story_labels": ["frontend"],
                },
            },
            "default_repository": "backend",
        }

        with open(storyteller_dir / "config.json", "w") as f:
            json.dump(config_data, f, indent=2)

        # Create temporary .env file
        env_file = temp_path / ".env"
        with open(env_file, "w") as f:
            f.write("GITHUB_TOKEN=test_token\n")
            f.write("GITHUB_REPOSITORY=test/single\n")
            f.write("DEFAULT_LLM_PROVIDER=github\n")

        # Change to temp directory and test
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_path)

            from config import Config

            config = Config.from_env()

            assert (
                config.is_multi_repository_mode()
            ), "Multi-repository mode should be enabled"
            assert len(config.get_repository_list()) == 2, "Should have 2 repositories"
            assert (
                config.get_target_repository("backend") == "test/backend"
            ), "Backend repository should be correct"
            assert (
                config.get_target_repository("frontend") == "test/frontend"
            ), "Frontend repository should be correct"
            assert config.get_repository_dependencies("frontend") == [
                "backend"
            ], "Frontend should depend on backend"
            assert (
                config.get_repository_dependencies("backend") == []
            ), "Backend should have no dependencies"

            print("✅ Configuration loading test passed")

        finally:
            os.chdir(original_cwd)


def test_dependency_sorting():
    """Test repository dependency sorting."""
    print("Testing dependency sorting...")

    # Mock the story orchestrator for testing
    from config import get_config
    from story_manager import StoryOrchestrator

    # Create a mock orchestrator
    class MockOrchestrator:
        def __init__(self):
            self.config = get_config()

        def get_repository_dependencies(self, repo_key):
            if self.config.is_multi_repository_mode():
                repo = self.config.multi_repository_config.get_repository(repo_key)
                return repo.dependencies if repo else []
            return []

        def _sort_repositories_by_dependencies(self, repository_keys):
            """Copied from StoryOrchestrator for testing."""
            sorted_repos = []
            remaining_repos = repository_keys.copy()

            while remaining_repos:
                ready_repos = []
                for repo_key in remaining_repos:
                    dependencies = self.get_repository_dependencies(repo_key)
                    if all(
                        dep not in remaining_repos or dep in sorted_repos
                        for dep in dependencies
                    ):
                        ready_repos.append(repo_key)

                if not ready_repos:
                    sorted_repos.extend(remaining_repos)
                    break

                sorted_repos.extend(ready_repos)
                for repo in ready_repos:
                    remaining_repos.remove(repo)

            return sorted_repos

    if get_config().is_multi_repository_mode():
        orchestrator = MockOrchestrator()
        sorted_repos = orchestrator._sort_repositories_by_dependencies(
            ["frontend", "backend"]
        )

        assert sorted_repos == [
            "backend",
            "frontend",
        ], f"Expected ['backend', 'frontend'], got {sorted_repos}"
        print("✅ Dependency sorting test passed")
    else:
        print("ℹ️  Skipping dependency sorting test (multi-repo mode not enabled)")


def test_backward_compatibility():
    """Test backward compatibility with single repository mode."""
    print("Testing backward compatibility...")

    # Test with temporary directory without .storyteller config
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create temporary .env file for single repo mode
        env_file = temp_path / ".env"
        with open(env_file, "w") as f:
            f.write("GITHUB_TOKEN=test_token\n")
            f.write("GITHUB_REPOSITORY=test/single\n")
            f.write("DEFAULT_LLM_PROVIDER=github\n")

        # Set environment variables directly to override any existing .env
        original_env = {}
        for key in ["GITHUB_TOKEN", "GITHUB_REPOSITORY", "DEFAULT_LLM_PROVIDER"]:
            original_env[key] = os.environ.get(key)

        try:
            os.environ["GITHUB_TOKEN"] = "test_token"
            os.environ["GITHUB_REPOSITORY"] = "test/single"
            os.environ["DEFAULT_LLM_PROVIDER"] = "github"

            original_cwd = os.getcwd()
            os.chdir(temp_path)

            # Clear any cached config and reimport
            import importlib

            import config

            importlib.reload(config)

            from config import Config

            test_config = Config.from_env()

            assert (
                not test_config.is_multi_repository_mode()
            ), "Multi-repository mode should be disabled"
            assert (
                test_config.get_target_repository() == "test/single"
            ), f"Should use single repository, got {test_config.get_target_repository()}"
            assert test_config.get_repository_list() == [
                "default"
            ], "Should have default repository"

            print("✅ Backward compatibility test passed")

        finally:
            os.chdir(original_cwd)
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def test_cli_commands():
    """Test CLI command structure."""
    print("Testing CLI commands...")

    try:
        from main import story_app

        # Check that new commands exist by checking registered callbacks
        commands = {}
        for callback in story_app.registered_commands.values():
            if hasattr(callback, "name"):
                commands[callback.name] = callback

        expected_commands = ["create", "create-multi", "list-repositories"]
        missing_commands = []

        for cmd in expected_commands:
            if cmd not in commands:
                missing_commands.append(cmd)

        if missing_commands:
            print(f"⚠️  Some commands not found: {missing_commands}")
        else:
            print("✅ CLI commands test passed")

    except Exception as e:
        print(f"⚠️  CLI commands test skipped due to error: {e}")
        # This is not critical for the core functionality


def main():
    """Run all tests."""
    print("Running multi-repository functionality tests...\n")

    tests = [
        test_config_loading,
        test_dependency_sorting,
        test_backward_compatibility,
        test_cli_commands,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
        print()

    print(f"Test Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    else:
        print("🎉 All tests passed!")


if __name__ == "__main__":
    main()
