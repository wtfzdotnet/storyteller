"""Unit tests for multi-repository context components without external API calls."""

import os

from multi_repo_context import (
    ContextCache,
    IntelligentFileSelector,
    RepositoryTypeDetector,
)

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"


def test_repository_type_detector():
    """Test repository type detection."""

    detector = RepositoryTypeDetector()

    # Test frontend detection
    frontend_files = [
        "src/App.js",
        "src/components/Header.jsx",
        "package.json",
        "public/index.html",
        "src/styles.css",
    ]
    result = detector.detect_repository_type({}, frontend_files)
    assert result == "frontend"

    # Test backend detection
    backend_files = [
        "src/main/java/App.java",
        "pom.xml",
        "src/controllers/UserController.java",
        "src/models/User.java",
        "requirements.txt",
        "app.py",
    ]
    result = detector.detect_repository_type({}, backend_files)
    assert result == "backend"


def test_intelligent_file_selector():
    """Test intelligent file selection."""

    selector = IntelligentFileSelector()

    # Test frontend file selection
    frontend_files = [
        ("package.json", "file"),
        ("src/App.js", "file"),
        ("src/components/Header.jsx", "file"),
        ("node_modules/react/index.js", "file"),
        ("build/static/js/main.js", "file"),
        ("public/favicon.ico", "file"),
        ("README.md", "file"),
    ]

    selected = selector.select_important_files("frontend", frontend_files, 4)

    # Should include important config and source files
    assert "package.json" in selected
    assert "src/App.js" in selected

    # Should exclude build artifacts and dependencies
    assert "node_modules/react/index.js" not in selected
    assert "build/static/js/main.js" not in selected

    # Should limit to requested count
    assert len(selected) <= 4


def test_context_cache():
    """Test context caching functionality."""

    cache = ContextCache(max_size=3)

    # Test set and get
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    assert cache.get("key1") == "value1"
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"

    # Test eviction
    cache.set("key4", "value4")
    assert cache.get("key1") is None  # Should be evicted
    assert cache.get("key4") == "value4"


def test_language_detection():
    """Test programming language detection."""

    detector = RepositoryTypeDetector()

    # Test JavaScript files
    js_files = ["app.js", "src/components/Header.jsx", "lib/utils.ts"]
    languages = detector.detect_languages(js_files)
    # Language detection returns lowercase keys
    assert "javascript" in languages or "typescript" in languages

    # Test Python files
    py_files = ["app.py", "src/models/user.py", "tests/test_api.py"]
    languages = detector.detect_languages(py_files)
    assert "python" in languages


if __name__ == "__main__":
    print("Running multi-repository context unit tests...")
    print("=" * 50)

    test_repository_type_detector()
    test_intelligent_file_selector()
    test_context_cache()
    test_language_detection()

    print("=" * 50)
    print("✓ All multi-repository context unit tests passed!")
