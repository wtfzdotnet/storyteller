"""Multi-repository code context reading and intelligence."""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import Config, get_config
from github_handler import GitHubHandler

logger = logging.getLogger(__name__)


@dataclass
class FileContext:
    """Context information for a single file."""

    repository: str
    path: str
    content: str
    file_type: str
    language: Optional[str] = None
    size: int = 0
    importance_score: float = 0.0
    summary: Optional[str] = None


@dataclass
class RepositoryContext:
    """Context information for a repository."""

    repository: str
    repo_type: str
    description: str
    structure: Dict[str, Any] = field(default_factory=dict)
    key_files: List[FileContext] = field(default_factory=list)
    languages: Dict[str, int] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    file_count: int = 0
    context_summary: Optional[str] = None


@dataclass
class MultiRepositoryContext:
    """Aggregated context from multiple repositories."""

    repositories: List[RepositoryContext] = field(default_factory=list)
    cross_repository_insights: Dict[str, Any] = field(default_factory=dict)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    total_files_analyzed: int = 0
    context_quality_score: float = 0.0


class RepositoryTypeDetector:
    """Detects and categorizes repository types based on content."""

    LANGUAGE_PATTERNS = {
        "python": [".py", "requirements.txt", "setup.py", "pyproject.toml"],
        "javascript": [".js", ".jsx", ".ts", ".tsx", "package.json", "node_modules"],
        "java": [".java", "pom.xml", "build.gradle", ".gradle"],
        "go": [".go", "go.mod", "go.sum"],
        "rust": [".rs", "Cargo.toml", "Cargo.lock"],
        "c++": [".cpp", ".hpp", ".cc", ".h", "CMakeLists.txt"],
        "c#": [".cs", ".csproj", ".sln"],
        "php": [".php", "composer.json"],
        "ruby": [".rb", "Gemfile", "Rakefile"],
    }

    FRAMEWORK_PATTERNS = {
        "react": ["package.json", ".jsx", ".tsx", "src/App.js", "src/App.tsx"],
        "vue": ["package.json", ".vue", "vue.config.js"],
        "angular": ["package.json", ".ts", "angular.json"],
        "django": ["manage.py", "settings.py", "urls.py", "models.py"],
        "flask": ["app.py", "requirements.txt", "flask"],
        "fastapi": ["main.py", "requirements.txt", "fastapi"],
        "spring": ["pom.xml", ".java", "application.properties"],
        "express": ["package.json", "app.js", "server.js", "express"],
    }

    REPO_TYPE_PATTERNS = {
        "frontend": [
            "src/components",
            "src/views",
            "public/",
            "static/",
            "package.json",
            ".html",
            ".css",
            ".scss",
            ".jsx",
            ".tsx",
            ".vue",
        ],
        "backend": [
            "api/",
            "src/main",
            "controllers/",
            "models/",
            "services/",
            "requirements.txt",
            "pom.xml",
            "go.mod",
            ".java",
            ".py",
            ".go",
        ],
        "mobile": [
            "android/",
            "ios/",
            "App.js",
            "android/app",
            "ios/Runner",
            ".dart",
            ".swift",
            ".kt",
            ".java",
        ],
        "documentation": ["docs/", "README.md", ".md", ".rst", "mkdocs.yml", "conf.py"],
        "devops": [
            "Dockerfile",
            "docker-compose.yml",
            ".yml",
            ".yaml",
            "terraform/",
            "ansible/",
            "k8s/",
            "kubernetes/",
        ],
        "data": [
            "notebooks/",
            ".ipynb",
            "data/",
            "datasets/",
            "models/",
            "requirements.txt",
            ".py",
            ".r",
            ".sql",
        ],
    }

    def detect_repository_type(
        self, structure: Dict[str, Any], files: List[str]
    ) -> str:
        """Detect repository type based on file structure and contents."""

        scores = {}

        # Score based on file patterns
        for repo_type, patterns in self.REPO_TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if pattern.endswith("/"):
                    # Directory pattern
                    if any(pattern.rstrip("/") in f for f in files):
                        score += 2
                elif "." in pattern:
                    # File extension pattern
                    if any(f.endswith(pattern) for f in files):
                        score += 1
                else:
                    # Specific file pattern
                    if any(pattern in f for f in files):
                        score += 3

            scores[repo_type] = score

        # Return the type with the highest score
        if scores:
            return max(scores, key=scores.get)

        return "unknown"

    def detect_languages(self, files: List[str]) -> Dict[str, int]:
        """Detect programming languages used in the repository."""

        language_counts = {}

        for file_path in files:
            for language, patterns in self.LANGUAGE_PATTERNS.items():
                for pattern in patterns:
                    if file_path.endswith(pattern) or pattern in file_path:
                        language_counts[language] = language_counts.get(language, 0) + 1
                        break

        return language_counts

    def detect_frameworks(
        self, files: List[str], file_contents: Dict[str, str]
    ) -> List[str]:
        """Detect frameworks used in the repository."""

        frameworks = []

        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if pattern.endswith(".json") and pattern in file_contents:
                    # Check package.json contents
                    if framework in file_contents[pattern].lower():
                        frameworks.append(framework)
                elif any(pattern in f for f in files):
                    frameworks.append(framework)
                    break

        return frameworks


class IntelligentFileSelector:
    """Selects the most relevant files for context based on repository type."""

    IMPORTANT_FILES = {
        "frontend": [
            "package.json",
            "src/App.js",
            "src/App.tsx",
            "src/App.vue",
            "src/main.js",
            "src/main.ts",
            "src/index.js",
            "public/index.html",
            "webpack.config.js",
            "vite.config.js",
            "angular.json",
        ],
        "backend": [
            "requirements.txt",
            "package.json",
            "pom.xml",
            "go.mod",
            "Cargo.toml",
            "main.py",
            "app.py",
            "server.js",
            "main.go",
            "src/main/java",
            "models.py",
            "api.py",
            "routes.py",
            "controllers/",
        ],
        "mobile": [
            "package.json",
            "pubspec.yaml",
            "android/app/build.gradle",
            "ios/Podfile",
            "App.js",
            "lib/main.dart",
            "src/main",
        ],
        "documentation": ["README.md", "docs/", "mkdocs.yml", "conf.py", "index.md"],
        "devops": [
            "Dockerfile",
            "docker-compose.yml",
            "kubernetes/",
            "terraform/",
            "ansible/",
            ".github/workflows/",
            "Makefile",
            "scripts/",
        ],
    }

    IMPORTANT_EXTENSIONS = {
        "frontend": [".js", ".jsx", ".ts", ".tsx", ".vue", ".html", ".css", ".scss"],
        "backend": [".py", ".java", ".go", ".js", ".ts", ".rb", ".php", ".cs"],
        "mobile": [".dart", ".swift", ".kt", ".java", ".js", ".jsx"],
        "documentation": [".md", ".rst", ".txt"],
        "devops": [".yml", ".yaml", ".json", ".toml", ".sh", ".ps1"],
    }

    def select_important_files(
        self, repo_type: str, files: List[Tuple[str, str]], max_files: int = 20
    ) -> List[str]:
        """Select the most important files for context based on repository type."""

        important_patterns = self.IMPORTANT_FILES.get(repo_type, [])
        important_extensions = self.IMPORTANT_EXTENSIONS.get(repo_type, [])

        scored_files = []

        for file_path, file_type in files:
            if file_type != "file":
                continue

            score = 0

            # Score based on important file patterns
            for pattern in important_patterns:
                if pattern in file_path:
                    score += 10
                elif file_path.endswith(pattern):
                    score += 8

            # Score based on important extensions
            for ext in important_extensions:
                if file_path.endswith(ext):
                    score += 5

            # Boost score for root-level files
            if "/" not in file_path.strip("/"):
                score += 3

            # Reduce score for deep nested files
            depth = file_path.count("/")
            if depth > 3:
                score -= depth

            # Boost score for common important files
            filename = Path(file_path).name.lower()
            if filename in [
                "readme.md",
                "package.json",
                "requirements.txt",
                "dockerfile",
            ]:
                score += 15

            if score > 0:
                scored_files.append((file_path, score))

        # Sort by score and return top files
        scored_files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in scored_files[:max_files]]


class ContextCache:
    """Simple in-memory cache for repository contexts."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        if key in self._cache:
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        if key in self._cache:
            # Update existing item
            self._access_order.remove(key)
        elif len(self._cache) >= self.max_size:
            # Remove least recently used item
            oldest = self._access_order.pop(0)
            del self._cache[oldest]

        self._cache[key] = value
        self._access_order.append(key)

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._access_order.clear()


class MultiRepositoryContextReader:
    """Main class for reading and aggregating context from multiple repositories."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.github_handler = GitHubHandler(self.config)
        self.type_detector = RepositoryTypeDetector()
        self.file_selector = IntelligentFileSelector()
        self.cache = ContextCache()

    async def get_repository_context(
        self, repository_key: str, max_files: int = 20, use_cache: bool = True
    ) -> Optional[RepositoryContext]:
        """Get context for a single repository."""

        cache_key = f"repo_context_{repository_key}_{max_files}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Using cached context for {repository_key}")
                return cached

        repo_config = self.config.repositories.get(repository_key)
        if not repo_config:
            logger.warning(f"Repository configuration not found: {repository_key}")
            return None

        try:
            # Get repository structure
            structure = await self.github_handler.get_repository_structure(
                repo_config.name
            )

            if "error" in structure:
                error_msg = structure["error"]
                logger.error(
                    f"Failed to get structure for {repo_config.name}: {error_msg}"
                )
                return None

            # List repository files
            files = await self.github_handler.list_repository_files(
                repo_config.name,
                recursive=True,
                file_extensions=[
                    ".py",
                    ".js",
                    ".jsx",
                    ".ts",
                    ".tsx",
                    ".java",
                    ".go",
                    ".md",
                    ".json",
                    ".yml",
                    ".yaml",
                ],
            )

            # Detect repository type and languages
            file_paths = [f[0] for f in files]
            detected_type = self.type_detector.detect_repository_type(
                structure, file_paths
            )
            detected_languages = self.type_detector.detect_languages(file_paths)

            # Select important files
            important_files = self.file_selector.select_important_files(
                detected_type, files, max_files
            )

            # Read content of important files
            key_file_contexts = []
            for file_path in important_files[
                :max_files
            ]:  # Limit to prevent API rate limiting
                content = await self.github_handler.get_file_content(
                    repo_config.name, file_path
                )
                if content:
                    file_context = FileContext(
                        repository=repo_config.name,
                        path=file_path,
                        content=content,
                        file_type=Path(file_path).suffix,
                        language=self._detect_file_language(file_path),
                        size=len(content),
                        importance_score=self._calculate_importance_score(
                            file_path, detected_type
                        ),
                    )
                    key_file_contexts.append(file_context)

            # Create repository context
            repo_context = RepositoryContext(
                repository=repo_config.name,
                repo_type=detected_type,
                description=repo_config.description,
                structure=structure,
                key_files=key_file_contexts,
                languages=detected_languages,
                dependencies=repo_config.dependencies,
                file_count=len(files),
            )

            # Cache the result
            if use_cache:
                self.cache.set(cache_key, repo_context)

            logger.info(
                f"Generated context for {repository_key}: "
                f"{len(key_file_contexts)} files, type: {detected_type}"
            )
            return repo_context

        except Exception as e:
            logger.error(f"Error getting repository context for {repository_key}: {e}")
            return None

    async def get_multi_repository_context(
        self, repository_keys: Optional[List[str]] = None, max_files_per_repo: int = 15
    ) -> MultiRepositoryContext:
        """Get aggregated context from multiple repositories."""

        if repository_keys is None:
            repository_keys = list(self.config.repositories.keys())

        # Get context for each repository concurrently
        tasks = [
            self.get_repository_context(repo_key, max_files_per_repo)
            for repo_key in repository_keys
        ]

        repo_contexts = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failed contexts
        valid_contexts = [
            ctx for ctx in repo_contexts if isinstance(ctx, RepositoryContext)
        ]

        # Build dependency graph
        dependency_graph = {}
        for repo_key in repository_keys:
            repo_config = self.config.repositories.get(repo_key)
            if repo_config:
                dependency_graph[repo_key] = repo_config.dependencies

        # Calculate cross-repository insights
        cross_insights = self._calculate_cross_repository_insights(valid_contexts)

        # Calculate total files analyzed
        total_files = sum(len(ctx.key_files) for ctx in valid_contexts)

        # Calculate quality score
        quality_score = self._calculate_context_quality_score(valid_contexts)

        multi_context = MultiRepositoryContext(
            repositories=valid_contexts,
            cross_repository_insights=cross_insights,
            dependency_graph=dependency_graph,
            total_files_analyzed=total_files,
            context_quality_score=quality_score,
        )

        logger.info(
            f"Generated multi-repository context: {len(valid_contexts)} repositories, "
            f"{total_files} files"
        )
        return multi_context

    def _detect_file_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""

        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".hpp": "cpp",
            ".h": "c",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby",
            ".md": "markdown",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".vue": "vue",
        }

        suffix = Path(file_path).suffix.lower()
        return extension_map.get(suffix)

    def _calculate_importance_score(self, file_path: str, repo_type: str) -> float:
        """Calculate importance score for a file."""

        score = 0.0
        filename = Path(file_path).name.lower()

        # Base score for key files
        if filename in ["readme.md", "package.json", "requirements.txt", "dockerfile"]:
            score += 10.0
        elif filename.startswith("readme"):
            score += 8.0
        elif filename in ["main.py", "app.py", "index.js", "main.go"]:
            score += 7.0

        # Adjust based on repository type
        if repo_type == "frontend":
            if any(x in file_path for x in ["src/", "components/", "views/"]):
                score += 3.0
        elif repo_type == "backend":
            if any(x in file_path for x in ["api/", "models/", "services/"]):
                score += 3.0

        # Reduce score for deeply nested files
        depth = file_path.count("/")
        score -= depth * 0.5

        return max(0.0, score)

    def _calculate_cross_repository_insights(
        self, contexts: List[RepositoryContext]
    ) -> Dict[str, Any]:
        """Calculate insights across multiple repositories."""

        insights = {
            "shared_languages": {},
            "common_patterns": [],
            "dependency_relationships": [],
            "technology_stack": {},
            "code_quality_indicators": {},
        }

        # Analyze shared languages
        all_languages = {}
        for ctx in contexts:
            for lang, count in ctx.languages.items():
                all_languages[lang] = all_languages.get(lang, 0) + count

        insights["shared_languages"] = all_languages

        # Identify common patterns
        all_files = []
        for ctx in contexts:
            all_files.extend([f.path for f in ctx.key_files])

        common_patterns = []
        if any("package.json" in f for f in all_files):
            common_patterns.append("Node.js ecosystem")
        if any("requirements.txt" in f for f in all_files):
            common_patterns.append("Python ecosystem")
        if any("dockerfile" in f.lower() for f in all_files):
            common_patterns.append("Containerized deployment")

        insights["common_patterns"] = common_patterns

        # Analyze technology stack
        tech_stack = {}
        for ctx in contexts:
            tech_stack[ctx.repository] = {
                "type": ctx.repo_type,
                "languages": list(ctx.languages.keys()),
                "file_count": ctx.file_count,
            }

        insights["technology_stack"] = tech_stack

        return insights

    def _calculate_context_quality_score(
        self, contexts: List[RepositoryContext]
    ) -> float:
        """Calculate overall quality score for the context."""

        if not contexts:
            return 0.0

        total_score = 0.0

        for ctx in contexts:
            repo_score = 0.0

            # Score based on number of files analyzed
            if len(ctx.key_files) >= 10:
                repo_score += 3.0
            elif len(ctx.key_files) >= 5:
                repo_score += 2.0
            else:
                repo_score += 1.0

            # Score based on language detection
            if ctx.languages:
                repo_score += 2.0

            # Score based on repository type detection
            if ctx.repo_type != "unknown":
                repo_score += 2.0

            # Score based on key files found
            key_files = [f.path for f in ctx.key_files]
            if any("readme" in f.lower() for f in key_files):
                repo_score += 1.0
            if any(f.endswith(".json") for f in key_files):
                repo_score += 1.0

            total_score += repo_score

        # Normalize to 0-100 scale
        max_possible_score = len(contexts) * 9.0  # 9 is max score per repo
        return (
            (total_score / max_possible_score) * 100.0
            if max_possible_score > 0
            else 0.0
        )
