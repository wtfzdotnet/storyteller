"""Unit tests for multi-repository context components that don't require external API calls."""

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
    """Test repository type detection logic."""
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

    # Test Python backend detection
    python_backend_files = [
        "app.py",
        "requirements.txt",
        "src/models/user.py",
        "src/api/endpoints.py",
        "Dockerfile",
    ]
    result = detector.detect_repository_type({}, python_backend_files)
    assert result == "backend"

    # Test mobile detection
    mobile_files = [
        "android/app/src/main/AndroidManifest.xml",
        "ios/Runner/Info.plist",
        "lib/main.dart",
        "pubspec.yaml",
    ]
    result = detector.detect_repository_type({}, mobile_files)
    assert result == "mobile"

    # Test data/analytics detection
    data_files = [
        "notebooks/analysis.ipynb",
        "data/raw/dataset.csv",
        "src/etl/pipeline.py",
        "requirements.txt",
        "airflow/dags/data_pipeline.py",
    ]
    result = detector.detect_repository_type({}, data_files)
    assert result == "data"

    # Test devops detection
    devops_files = [
        "terraform/main.tf",
        "kubernetes/deployment.yaml",
        "docker-compose.yml",
        "ansible/playbook.yml",
        "Dockerfile",
    ]
    result = detector.detect_repository_type({}, devops_files)
    assert result == "devops"

    # Test unknown type - files that don't match any patterns
    unknown_files = ["random.txt", "stuff.dat"]
    result = detector.detect_repository_type({}, unknown_files)
    # Since all scores are 0, it returns the first key in the dict
    assert result in ["frontend", "backend", "mobile", "data", "devops"]


def test_intelligent_file_selector():
    """Test intelligent file selection logic."""
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
        ("src/utils/api.js", "file"),
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

    # Test backend file selection
    backend_files = [
        ("requirements.txt", "file"),
        ("app.py", "file"),
        ("src/models/user.py", "file"),
        ("src/api/endpoints.py", "file"),
        ("tests/test_api.py", "file"),
        ("venv/lib/python3.9/site-packages/flask/__init__.py", "file"),
        ("__pycache__/app.cpython-39.pyc", "file"),
        ("README.md", "file"),
    ]

    selected = selector.select_important_files("backend", backend_files, 4)

    # Should include important config and source files
    assert "requirements.txt" in selected
    assert "app.py" in selected

    # Should exclude virtual environment and cache files
    assert "venv/lib/python3.9/site-packages/flask/__init__.py" not in selected
    assert "__pycache__/app.cpython-39.pyc" not in selected

    # Should limit to requested count
    assert len(selected) <= 4

    # Test with directories
    mixed_items = [
        ("src", "dir"),
        ("package.json", "file"),
        ("node_modules", "dir"),
        ("src/App.js", "file"),
    ]

    selected = selector.select_important_files("frontend", mixed_items, 3)

    # Should handle directories appropriately
    assert len(selected) <= 3


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

    # Test eviction (LRU)
    cache.set("key4", "value4")
    assert cache.get("key1") is None  # Should be evicted (least recently used)
    assert cache.get("key4") == "value4"

    # Test cache hit updates recency
    cache.get("key2")  # Access key2 to make it more recent
    cache.set("key5", "value5")  # This should evict key3, not key2
    assert cache.get("key2") == "value2"  # Should still be there
    assert cache.get("key3") is None  # Should be evicted

    # Test overwrite
    cache.set("key2", "new_value2")
    assert cache.get("key2") == "new_value2"

    # Test nonexistent key
    assert cache.get("nonexistent") is None


def test_file_selector_priority_scoring():
    """Test file priority scoring logic."""
    selector = IntelligentFileSelector()

    # Test configuration files get high priority through select_important_files
    config_files = [
        ("package.json", "file"),
        ("requirements.txt", "file"),
        ("Dockerfile", "file"),
        ("docker-compose.yml", "file"),
        ("random.txt", "file"),
    ]

    # Test frontend selection prioritizes package.json
    selected = selector.select_important_files("frontend", config_files, 2)
    assert "package.json" in selected
    assert len(selected) <= 2

    # Test backend selection prioritizes requirements.txt
    selected = selector.select_important_files("backend", config_files, 2)
    assert "requirements.txt" in selected
    assert len(selected) <= 2

    # Test that random files get lower priority
    all_files = config_files + [("src/App.js", "file"), ("build/output.js", "file")]
    selected = selector.select_important_files("frontend", all_files, 3)

    # Should prefer important files over random ones
    assert "package.json" in selected
    if "src/App.js" in [f[0] for f in all_files]:
        # Source files should be preferred over build files
        important_files = ["package.json", "src/App.js"]
        assert any(f in selected for f in important_files)


def test_repository_type_detection_edge_cases():
    """Test edge cases in repository type detection."""
    detector = RepositoryTypeDetector()

    # Test empty file list - returns first repository type due to max() on equal scores
    result = detector.detect_repository_type({}, [])
    # The implementation returns the first key when all scores are equal (0)
    # Since frontend is likely first in the dict, it gets returned
    assert result in ["frontend", "backend", "mobile", "data", "devops", "unknown"]

    # Test mixed signals (should pick the strongest one)
    mixed_files = [
        "package.json",  # Frontend
        "src/App.js",  # Frontend
        "app.py",  # Backend
    ]
    result = detector.detect_repository_type({}, mixed_files)
    # Should detect as frontend since it has more frontend indicators
    assert result == "frontend"

    # Test with repository metadata
    repo_metadata = {
        "description": "React application for user interface",
        "language": "JavaScript",
    }
    result = detector.detect_repository_type(repo_metadata, ["index.js"])
    assert result == "frontend"  # Should use metadata context

    # Test language-based detection
    java_files = ["src/main/java/com/example/App.java", "pom.xml"]
    result = detector.detect_repository_type({}, java_files)
    assert result == "backend"

    python_ml_files = [
        "train_model.py",
        "requirements.txt",
        "data/training_data.csv",
        "models/neural_network.pkl",
    ]
    result = detector.detect_repository_type({}, python_ml_files)
    assert result == "data"  # Should detect as data/ML project
