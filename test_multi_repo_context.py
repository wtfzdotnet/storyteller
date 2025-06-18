"""Test multi-repository code context reading functionality."""

import os
import asyncio
import tempfile
from pathlib import Path

# Set dummy environment for testing
os.environ["GITHUB_TOKEN"] = "test_token"
os.environ["DEFAULT_LLM_PROVIDER"] = "github"

from multi_repo_context import (
    MultiRepositoryContextReader,
    RepositoryTypeDetector,
    IntelligentFileSelector,
    ContextCache,
)
from config import get_config


def test_repository_type_detector():
    """Test repository type detection."""
    
    detector = RepositoryTypeDetector()
    
    # Test frontend detection
    frontend_files = [
        "src/App.js", "src/components/Header.jsx", "package.json", 
        "public/index.html", "src/styles.css"
    ]
    result = detector.detect_repository_type({}, frontend_files)
    print(f"✓ Frontend detection: {result}")
    assert result == 'frontend'
    
    # Test backend detection
    backend_files = [
        "src/main/java/App.java", "pom.xml", "src/controllers/UserController.java",
        "src/models/User.java", "requirements.txt", "app.py"
    ]
    result = detector.detect_repository_type({}, backend_files)
    print(f"✓ Backend detection: {result}")
    assert result == 'backend'
    
    # Test language detection
    languages = detector.detect_languages(frontend_files + backend_files)
    print(f"✓ Language detection: {languages}")
    assert 'javascript' in languages
    assert 'python' in languages


def test_intelligent_file_selector():
    """Test intelligent file selection."""
    
    selector = IntelligentFileSelector()
    
    # Test frontend file selection
    frontend_files = [
        ("src/App.js", "file"),
        ("src/components/Header.jsx", "file"),
        ("package.json", "file"),
        ("public/index.html", "file"),
        ("src/utils/helper.js", "file"),
        ("node_modules/react/index.js", "file"),  # Should be ignored
        ("dist/bundle.js", "file"),  # Should be less important
    ]
    
    selected = selector.select_important_files('frontend', frontend_files, max_files=5)
    print(f"✓ Frontend file selection: {selected}")
    assert "package.json" in selected
    assert "src/App.js" in selected
    assert "node_modules/react/index.js" not in selected


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
    
    print("✓ Context cache working correctly")


async def test_multi_repository_context_reader():
    """Test the main multi-repository context reader (mock test)."""
    
    try:
        config = get_config()
        reader = MultiRepositoryContextReader(config)
        
        # This would normally make GitHub API calls, but we'll just test the structure
        print(f"✓ MultiRepositoryContextReader initialized with {len(config.repositories)} repositories")
        
        # Test repository keys
        repo_keys = list(config.repositories.keys())
        print(f"✓ Available repositories: {repo_keys}")
        
        # Validate configuration
        for key, repo_config in config.repositories.items():
            print(f"  - {key}: {repo_config.name} ({repo_config.type})")
        
        print("✓ Multi-repository context reader structure validated")
        
    except Exception as e:
        print(f"✗ Error in multi-repository context reader test: {e}")
        raise


def test_integration():
    """Run all tests."""
    
    print("Testing multi-repository code context reading functionality...")
    print("=" * 60)
    
    # Run synchronous tests
    test_repository_type_detector()
    test_intelligent_file_selector()
    test_context_cache()
    
    # Run async test
    asyncio.run(test_multi_repository_context_reader())
    
    print("=" * 60)
    print("✓ All multi-repository context tests passed!")


if __name__ == "__main__":
    test_integration()