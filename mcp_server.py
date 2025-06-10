"""MCP (Model Context Protocol) Server for AI Story Management System."""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from automation.workflow_processor import WorkflowProcessor
from config import Config, get_config
from story_manager import StoryManager

logger = logging.getLogger(__name__)


@dataclass
class MCPRequest:
    """MCP protocol request."""

    id: str
    method: str
    params: Dict[str, Any]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class MCPResponse:
    """MCP protocol response."""

    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class MCPStoryServer:
    """MCP server for story management and expert role querying."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.story_manager = StoryManager(self.config)
        self.workflow_processor = WorkflowProcessor(self.config)
        self._handlers: Dict[str, Callable] = {}
        self._register_handlers()

    def _register_handlers(self):
        """Register MCP method handlers."""

        self._handlers = {
            # Story management methods
            "story/create": self._handle_create_story,
            "story/analyze": self._handle_analyze_story,
            "story/status": self._handle_story_status,
            # Expert role methods
            "role/query": self._handle_query_role,
            "role/list": self._handle_list_roles,
            "role/analyze_story": self._handle_role_analyze_story,
            # Repository methods
            "repository/list": self._handle_list_repositories,
            "repository/get_config": self._handle_get_repository_config,
            # System methods
            "system/health": self._handle_health_check,
            "system/capabilities": self._handle_capabilities,
            "system/validate": self._handle_validate_config,
            # New endpoints for Copilot/MCP integration
            "file/read": self._handle_file_read,
            "file/write": self._handle_file_write,
            "codebase/scan": self._handle_codebase_scan,
            "codebase/analyze": self._handle_codebase_analyze,
            "test/analyze": self._handle_test_analyze,
            "test/suggest": self._handle_test_suggest,
            "test/generate": self._handle_test_generate,
            "qa/strategy": self._handle_qa_strategy,
            "component/analyze": self._handle_component_analyze,
            "component/generate": self._handle_component_generate,
            "storybook/scan": self._handle_storybook_scan,
            "storybook/suggest": self._handle_storybook_suggest,
            "context/provide": self._handle_context_provide,
            "suggestion/improve": self._handle_suggestion_improve,
            "workflow/automate": self._handle_workflow_automate,
        }

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle an MCP request."""

        try:
            if request.method not in self._handlers:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32601,
                        "message": f"Method not found: {request.method}",
                        "data": {"available_methods": list(self._handlers.keys())},
                    },
                )

            handler = self._handlers[request.method]
            result = await handler(request.params)

            return MCPResponse(id=request.id, result=result)

        except Exception as e:
            logger.error(f"MCP request error: {e}")
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                    "data": {"method": request.method},
                },
            )

    async def _handle_create_story(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle story creation request."""

        content = params.get("content")
        if not content:
            raise ValueError("content parameter is required")

        result = await self.workflow_processor.create_story_workflow(
            content=content,
            repository=params.get("repository"),
            roles=params.get("roles"),
            context=params.get("context"),
        )

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
        }

    async def _handle_analyze_story(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle story analysis request."""

        content = params.get("content")
        if not content:
            raise ValueError("content parameter is required")

        result = await self.workflow_processor.analyze_story_workflow(
            content=content, roles=params.get("roles"), context=params.get("context")
        )

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
        }

    async def _handle_story_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle story status request."""

        story_id = params.get("story_id")
        if not story_id:
            raise ValueError("story_id parameter is required")

        result = self.workflow_processor.get_story_status_workflow(story_id)

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
        }

    async def _handle_query_role(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle expert role query request."""

        role_name = params.get("role_name")
        question = params.get("question")

        if not role_name or not question:
            raise ValueError("role_name and question parameters are required")

        # Get role definition
        role_definitions = self.story_manager.processor.role_definitions
        if role_name not in role_definitions:
            raise ValueError(f"Unknown role: {role_name}")

        role_definition = role_definitions[role_name]
        context = params.get("context", {})

        # Query the role
        response = (
            await self.story_manager.processor.llm_handler.analyze_story_with_role(
                story_content=question,
                role_definition=role_definition,
                role_name=role_name,
                context=context,
            )
        )

        return {
            "role_name": role_name,
            "question": question,
            "response": response.content,
            "model": response.model,
            "provider": response.provider,
            "metadata": response.metadata,
        }

    async def _handle_list_roles(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list roles request."""

        result = self.workflow_processor.list_roles_workflow()

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
        }

    async def _handle_role_analyze_story(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle role-specific story analysis request."""

        role_name = params.get("role_name")
        story_content = params.get("story_content")

        if not role_name or not story_content:
            raise ValueError("role_name and story_content parameters are required")

        # Get expert analysis from specific role
        analysis = await self.story_manager.processor.get_expert_analysis(
            story_content=story_content,
            role_name=role_name,
            context=params.get("context"),
        )

        return {
            "role_name": analysis.role_name,
            "analysis": analysis.analysis,
            "recommendations": analysis.recommendations,
            "concerns": analysis.concerns,
            "metadata": analysis.metadata,
        }

    async def _handle_list_repositories(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list repositories request."""

        result = self.workflow_processor.list_repositories_workflow()

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
        }

    async def _handle_get_repository_config(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle get repository configuration request."""

        repository_key = params.get("repository_key")
        if not repository_key:
            raise ValueError("repository_key parameter is required")

        repo_config = self.config.repositories.get(repository_key)
        if not repo_config:
            raise ValueError(f"Repository not found: {repository_key}")

        return {
            "repository_key": repository_key,
            "name": repo_config.name,
            "type": repo_config.type,
            "description": repo_config.description,
            "dependencies": repo_config.dependencies,
            "story_labels": repo_config.story_labels,
            "auto_assign": repo_config.auto_assign,
        }

    async def _handle_health_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check request."""

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "capabilities": list(self._handlers.keys()),
        }

    async def _handle_capabilities(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capabilities request."""

        return {
            "methods": {
                method: {
                    "description": self._get_method_description(method),
                    "parameters": self._get_method_parameters(method),
                }
                for method in self._handlers.keys()
            },
            "features": [
                "multi_expert_analysis",
                "repository_distribution",
                "github_integration",
                "role_querying",
                "story_management",
            ],
        }

    async def _handle_validate_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle configuration validation request."""

        result = await self.workflow_processor.validate_configuration_workflow()

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "error": result.error,
        }

    async def _handle_file_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file read request."""
        import os
        from pathlib import Path

        path = params.get("path")
        if not path:
            raise ValueError("path parameter is required")

        logger.info(f"[MCP] file/read: {path}")

        try:
            # Security: normalize path and ensure it's within current directory
            file_path = Path(path).resolve()
            current_dir = Path.cwd().resolve()

            if not str(file_path).startswith(str(current_dir)):
                return {
                    "success": False,
                    "message": "Access denied: path outside working directory",
                    "error": "SecurityError",
                }

            if not file_path.exists():
                return {
                    "success": False,
                    "message": f"File not found: {path}",
                    "error": "FileNotFound",
                }

            if not file_path.is_file():
                return {
                    "success": False,
                    "message": f"Path is not a file: {path}",
                    "error": "NotAFile",
                }

            # Read file content
            content = file_path.read_text(encoding="utf-8")

            return {
                "success": True,
                "message": f"Successfully read file: {path}",
                "data": {
                    "path": str(file_path.relative_to(current_dir)),
                    "content": content,
                    "size": len(content),
                    "lines": content.count("\n") + 1 if content else 0,
                },
            }

        except UnicodeDecodeError:
            return {
                "success": False,
                "message": f"Cannot read binary file as text: {path}",
                "error": "BinaryFile",
            }
        except PermissionError:
            return {
                "success": False,
                "message": f"Permission denied: {path}",
                "error": "PermissionDenied",
            }
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return {
                "success": False,
                "message": f"Error reading file: {str(e)}",
                "error": "ReadError",
            }

    async def _handle_file_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file write request."""
        import os
        from pathlib import Path

        path = params.get("path")
        content = params.get("content")
        if not path or content is None:
            raise ValueError("path and content parameters are required")

        logger.info(f"[MCP] file/write: {path}")

        try:
            # Security: normalize path and ensure it's within current directory
            file_path = Path(path).resolve()
            current_dir = Path.cwd().resolve()

            if not str(file_path).startswith(str(current_dir)):
                return {
                    "success": False,
                    "message": "Access denied: path outside working directory",
                    "error": "SecurityError",
                }

            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            file_path.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "message": f"Successfully wrote file: {path}",
                "data": {
                    "path": str(file_path.relative_to(current_dir)),
                    "size": len(content),
                    "lines": content.count("\n") + 1 if content else 0,
                },
            }

        except PermissionError:
            return {
                "success": False,
                "message": f"Permission denied: {path}",
                "error": "PermissionDenied",
            }
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            return {
                "success": False,
                "message": f"Error writing file: {str(e)}",
                "error": "WriteError",
            }

    async def _handle_codebase_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle codebase scan request."""
        import fnmatch
        from pathlib import Path

        logger.info("[MCP] codebase/scan")

        try:
            pattern = params.get("pattern", "*")
            max_files = params.get("max_files", 100)
            include_dirs = params.get("include_dirs", False)

            current_dir = Path.cwd()
            files = []

            # Common exclusion patterns
            exclude_patterns = [
                "__pycache__",
                "*.pyc",
                ".git",
                "node_modules",
                ".env",
                "venv",
                ".venv",
                "dist",
                "build",
                "*.log",
            ]

            def should_exclude(path_str):
                return any(
                    fnmatch.fnmatch(path_str, pattern) for pattern in exclude_patterns
                )

            # Scan files recursively
            for file_path in current_dir.rglob(pattern):
                relative_path = file_path.relative_to(current_dir)
                path_str = str(relative_path)

                # Skip excluded patterns
                if should_exclude(path_str):
                    continue

                if file_path.is_file() or (include_dirs and file_path.is_dir()):
                    files.append(
                        {
                            "path": path_str,
                            "type": "directory" if file_path.is_dir() else "file",
                            "size": (
                                file_path.stat().st_size
                                if file_path.is_file()
                                else None
                            ),
                            "extension": (
                                file_path.suffix if file_path.is_file() else None
                            ),
                        }
                    )

                    if len(files) >= max_files:
                        break

            # Group by file type
            file_types = {}
            for file_info in files:
                ext = file_info.get("extension", "no_extension")
                if ext not in file_types:
                    file_types[ext] = 0
                file_types[ext] += 1

            return {
                "success": True,
                "message": f"Scanned codebase with pattern: {pattern}",
                "data": {
                    "pattern": pattern,
                    "total_files": len(files),
                    "files": files,
                    "file_types": file_types,
                    "truncated": len(files) >= max_files,
                },
            }

        except Exception as e:
            logger.error(f"Error scanning codebase: {e}")
            return {
                "success": False,
                "message": f"Error scanning codebase: {str(e)}",
                "error": "ScanError",
            }

    async def _handle_codebase_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle codebase analyze request."""
        import ast
        import re
        from pathlib import Path

        logger.info("[MCP] codebase/analyze")

        try:
            scope = params.get("scope", ".")
            include_metrics = params.get("include_metrics", True)
            include_dependencies = params.get("include_dependencies", True)

            current_dir = Path.cwd()
            scope_path = (current_dir / scope).resolve()

            if not str(scope_path).startswith(str(current_dir)):
                return {
                    "success": False,
                    "message": "Access denied: scope outside working directory",
                    "error": "SecurityError",
                }

            analysis = {
                "scope": scope,
                "metrics": {},
                "dependencies": {},
                "structure": {},
            }

            # Basic metrics
            if include_metrics:
                python_files = list(scope_path.rglob("*.py"))
                total_lines = 0
                total_functions = 0
                total_classes = 0

                for py_file in python_files:
                    try:
                        content = py_file.read_text(encoding="utf-8")
                        total_lines += content.count("\n")

                        # Parse AST for functions and classes
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                total_functions += 1
                            elif isinstance(node, ast.ClassDef):
                                total_classes += 1
                    except:
                        continue

                analysis["metrics"] = {
                    "total_python_files": len(python_files),
                    "total_lines": total_lines,
                    "total_functions": total_functions,
                    "total_classes": total_classes,
                }

            # Dependencies analysis
            if include_dependencies:
                deps = set()

                # Check requirements.txt
                req_file = current_dir / "requirements.txt"
                if req_file.exists():
                    for line in req_file.read_text().splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Extract package name (before ==, >=, etc.)
                            pkg = re.split(r"[><=!]", line)[0].strip()
                            if pkg:
                                deps.add(pkg)

                # Check Python imports
                python_files = list(scope_path.rglob("*.py"))
                for py_file in python_files[:10]:  # Limit to first 10 files
                    try:
                        content = py_file.read_text(encoding="utf-8")
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.Import, ast.ImportFrom)):
                                if isinstance(node, ast.Import):
                                    for alias in node.names:
                                        deps.add(alias.name.split(".")[0])
                                elif node.module:
                                    deps.add(node.module.split(".")[0])
                    except:
                        continue

                analysis["dependencies"] = {
                    "total_dependencies": len(deps),
                    "dependencies": sorted(list(deps)[:20]),  # Top 20
                }

            return {
                "success": True,
                "message": f"Analyzed codebase scope: {scope}",
                "data": analysis,
            }

        except Exception as e:
            logger.error(f"Error analyzing codebase: {e}")
            return {
                "success": False,
                "message": f"Error analyzing codebase: {str(e)}",
                "error": "AnalysisError",
            }

    async def _handle_test_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle test analyze request."""
        import re
        from pathlib import Path

        logger.info("[MCP] test/analyze")

        try:
            path = params.get("path", ".")
            current_dir = Path.cwd()
            target_path = (current_dir / path).resolve()

            if not str(target_path).startswith(str(current_dir)):
                return {
                    "success": False,
                    "message": "Access denied: path outside working directory",
                    "error": "SecurityError",
                }

            analysis = {
                "path": path,
                "test_files": [],
                "test_coverage": {},
                "test_patterns": {},
            }

            # Find test files
            test_patterns = ["test_*.py", "*_test.py", "tests.py"]
            test_files = []

            if target_path.is_file():
                # Analyze single file
                if any(target_path.match(pattern) for pattern in test_patterns):
                    test_files.append(target_path)
            else:
                # Scan directory
                for pattern in test_patterns:
                    test_files.extend(target_path.rglob(pattern))

            # Analyze test files
            total_tests = 0
            test_functions = []

            for test_file in test_files:
                try:
                    content = test_file.read_text(encoding="utf-8")

                    # Count test functions
                    test_func_pattern = r"def\s+(test_\w+|async\s+def\s+test_\w+)"
                    matches = re.findall(test_func_pattern, content)
                    file_tests = len(matches)
                    total_tests += file_tests

                    # Extract test function names
                    for match in matches:
                        func_name = match.replace("async def ", "").replace("def ", "")
                        test_functions.append(func_name)

                    analysis["test_files"].append(
                        {
                            "file": str(test_file.relative_to(current_dir)),
                            "test_count": file_tests,
                            "size": len(content),
                        }
                    )

                except Exception as e:
                    logger.warning(f"Error analyzing test file {test_file}: {e}")

            # Basic coverage estimation (presence of test files vs source files)
            if target_path.is_dir():
                source_files = list(target_path.rglob("*.py"))
                source_files = [
                    f
                    for f in source_files
                    if not any(f.match(p) for p in test_patterns)
                ]

                coverage_ratio = len(test_files) / max(len(source_files), 1)
                analysis["test_coverage"] = {
                    "source_files": len(source_files),
                    "test_files": len(test_files),
                    "coverage_ratio": round(coverage_ratio, 2),
                    "status": (
                        "good"
                        if coverage_ratio > 0.8
                        else "moderate" if coverage_ratio > 0.5 else "low"
                    ),
                }

            analysis["test_patterns"] = {
                "total_tests": total_tests,
                "test_functions": test_functions[:10],  # First 10
                "patterns_found": [
                    p for p in test_patterns if any(f.match(p) for f in test_files)
                ],
            }

            return {
                "success": True,
                "message": f"Analyzed tests for: {path}",
                "data": analysis,
            }

        except Exception as e:
            logger.error(f"Error analyzing tests: {e}")
            return {
                "success": False,
                "message": f"Error analyzing tests: {str(e)}",
                "error": "TestAnalysisError",
            }

    async def _handle_test_suggest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle test suggest request."""
        import ast
        from pathlib import Path

        logger.info("[MCP] test/suggest")

        try:
            path = params.get("path")
            if not path:
                return {
                    "success": False,
                    "message": "path parameter is required",
                    "error": "MissingParameter",
                }

            current_dir = Path.cwd()
            target_path = (current_dir / path).resolve()

            if not str(target_path).startswith(str(current_dir)):
                return {
                    "success": False,
                    "message": "Access denied: path outside working directory",
                    "error": "SecurityError",
                }

            if not target_path.exists():
                return {
                    "success": False,
                    "message": f"Path not found: {path}",
                    "error": "PathNotFound",
                }

            suggestions = {
                "path": path,
                "test_suggestions": [],
                "missing_tests": [],
                "recommendations": [],
            }

            if target_path.is_file() and target_path.suffix == ".py":
                # Analyze single Python file
                content = target_path.read_text(encoding="utf-8")

                try:
                    tree = ast.parse(content)

                    # Find functions and classes that could be tested
                    functions = []
                    classes = []

                    for node in ast.walk(tree):
                        if isinstance(
                            node, ast.FunctionDef
                        ) and not node.name.startswith("_"):
                            functions.append(node.name)
                        elif isinstance(node, ast.ClassDef):
                            classes.append(node.name)
                            # Find public methods in classes
                            for class_node in node.body:
                                if isinstance(
                                    class_node, ast.FunctionDef
                                ) and not class_node.name.startswith("_"):
                                    functions.append(f"{node.name}.{class_node.name}")

                    # Generate test suggestions
                    test_file_name = f"test_{target_path.stem}.py"

                    suggestions["test_suggestions"] = [
                        {
                            "type": "unit_test",
                            "target": func,
                            "test_name": f"test_{func.replace('.', '_')}",
                            "priority": (
                                "high" if func in ["__init__", "main"] else "medium"
                            ),
                        }
                        for func in functions
                    ]

                    suggestions["missing_tests"] = [
                        f"test_{func.replace('.', '_')}" for func in functions
                    ]

                    suggestions["recommendations"] = [
                        f"Create {test_file_name} for comprehensive testing",
                        f"Add unit tests for {len(functions)} functions/methods",
                        "Consider edge cases and error handling tests",
                        "Add integration tests if applicable",
                    ]

                    if classes:
                        suggestions["recommendations"].append(
                            f"Add class-specific tests for {len(classes)} classes"
                        )

                except SyntaxError:
                    suggestions["recommendations"] = [
                        "File has syntax errors - fix before adding tests"
                    ]

            else:
                # Directory analysis
                suggestions["recommendations"] = [
                    "Scan directory for untested Python files",
                    "Create test directory structure",
                    "Add __init__.py files for test packages",
                ]

            return {
                "success": True,
                "message": f"Generated test suggestions for: {path}",
                "data": suggestions,
            }

        except Exception as e:
            logger.error(f"Error suggesting tests: {e}")
            return {
                "success": False,
                "message": f"Error suggesting tests: {str(e)}",
                "error": "TestSuggestionError",
            }

    async def _handle_test_generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle test generate request."""
        import os
        import re
        from pathlib import Path

        logger.info("[MCP] test/generate")

        try:
            # Extract parameters
            file_path = params.get("file_path")
            test_type = params.get("test_type", "unit")  # unit, integration, e2e
            framework = params.get(
                "framework", "pytest"
            )  # pytest, unittest, jest, vitest
            coverage_target = params.get("coverage_target", 80)

            if not file_path:
                return {
                    "success": False,
                    "error": "Missing required parameter: file_path",
                }

            file_path = Path(file_path)
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                }

            # Read and analyze source file
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Initialize variables
            functions = []
            classes = []
            exports = []

            # Generate test file path
            if file_path.suffix == ".py":
                test_dir = file_path.parent / "tests"
                test_file = test_dir / f"test_{file_path.stem}.py"

                # Extract functions and classes for testing
                functions = re.findall(r"^def (\w+)\(.*?\):", content, re.MULTILINE)
                classes = re.findall(r"^class (\w+).*?:", content, re.MULTILINE)

                # Generate Python test template
                test_content = self._generate_python_tests(
                    file_path, functions, classes, framework, test_type
                )

            elif file_path.suffix in [".js", ".ts", ".jsx", ".tsx"]:
                test_dir = file_path.parent / "__tests__"
                test_file = test_dir / f"{file_path.stem}.test{file_path.suffix}"

                # Extract exports and functions for testing
                exports = re.findall(
                    r"export (?:default )?(?:function |class |const |let |var )?(\w+)",
                    content,
                )
                functions = re.findall(
                    r"(?:function |const |let )\s*(\w+)\s*[=\(]", content
                )

                # Generate JavaScript/TypeScript test template
                test_content = self._generate_js_tests(
                    file_path, exports, functions, framework, test_type
                )
            else:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_path.suffix}",
                }

            # Create test directory if it doesn't exist
            test_dir.mkdir(exist_ok=True)

            # Generate test scenarios based on analysis
            test_scenarios = self._generate_test_scenarios(content, test_type)

            return {
                "success": True,
                "test_file_path": str(test_file),
                "test_content": test_content,
                "test_scenarios": test_scenarios,
                "framework": framework,
                "test_type": test_type,
                "coverage_target": coverage_target,
                "metadata": {
                    "source_file": str(file_path),
                    "functions_found": (
                        functions if file_path.suffix == ".py" else exports
                    ),
                    "classes_found": classes if file_path.suffix == ".py" else [],
                    "generated_at": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error generating tests: {e}")
            return {
                "success": False,
                "error": f"Test generation failed: {str(e)}",
            }

    async def _handle_qa_strategy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle QA strategy request."""
        import os
        from pathlib import Path

        logger.info("[MCP] qa/strategy")

        try:
            # Extract parameters
            project_path = params.get("project_path", ".")
            scope = params.get("scope", "full")  # full, component, feature
            risk_level = params.get("risk_level", "medium")  # low, medium, high
            timeline = params.get("timeline", "standard")  # fast, standard, thorough

            project_path = Path(project_path)
            if not project_path.exists():
                return {
                    "success": False,
                    "error": f"Project path not found: {project_path}",
                }

            # Analyze project structure
            project_analysis = self._analyze_project_for_qa(project_path)

            # Generate QA strategy based on analysis
            strategy = self._generate_qa_strategy(
                project_analysis, scope, risk_level, timeline
            )

            return {
                "success": True,
                "qa_strategy": strategy,
                "project_analysis": project_analysis,
                "parameters": {
                    "scope": scope,
                    "risk_level": risk_level,
                    "timeline": timeline,
                },
                "recommendations": self._get_qa_recommendations(
                    project_analysis, risk_level
                ),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating QA strategy: {e}")
            return {
                "success": False,
                "error": f"QA strategy generation failed: {str(e)}",
            }

    async def _handle_component_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle component analyze request."""
        import re
        from pathlib import Path

        logger.info("[MCP] component/analyze")

        try:
            # Extract parameters
            component_path = params.get("component_path")
            analysis_type = params.get(
                "analysis_type", "full"
            )  # full, props, structure, dependencies

            if not component_path:
                return {
                    "success": False,
                    "error": "Missing required parameter: component_path",
                }

            component_path = Path(component_path)
            if not component_path.exists():
                return {
                    "success": False,
                    "error": f"Component file not found: {component_path}",
                }

            # Read component file
            with open(component_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Analyze component based on file type
            if component_path.suffix in [".jsx", ".tsx", ".js", ".ts"]:
                analysis = self._analyze_react_component(content, component_path)
            elif component_path.suffix == ".vue":
                analysis = self._analyze_vue_component(content, component_path)
            elif component_path.suffix == ".py":
                analysis = self._analyze_python_component(content, component_path)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported component type: {component_path.suffix}",
                }

            # Add metadata
            analysis["metadata"] = {
                "file_path": str(component_path),
                "file_size": component_path.stat().st_size,
                "analysis_type": analysis_type,
                "analyzed_at": datetime.utcnow().isoformat(),
            }

            return {
                "success": True,
                "component_analysis": analysis,
            }

        except Exception as e:
            logger.error(f"Error analyzing component: {e}")
            return {
                "success": False,
                "error": f"Component analysis failed: {str(e)}",
            }

    async def _handle_component_generate(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle component generate request."""
        from pathlib import Path

        logger.info("[MCP] component/generate")

        try:
            # Extract parameters
            component_name = params.get("component_name")
            component_type = params.get("component_type", "react")  # react, vue, python
            props = params.get("props", [])
            output_path = params.get("output_path", ".")
            template_type = params.get(
                "template_type", "basic"
            )  # basic, form, list, modal

            if not component_name:
                return {
                    "success": False,
                    "error": "Missing required parameter: component_name",
                }

            # Generate component based on type
            if component_type == "react":
                component_content = self._generate_react_component(
                    component_name, props, template_type
                )
                file_extension = ".jsx"
            elif component_type == "vue":
                component_content = self._generate_vue_component(
                    component_name, props, template_type
                )
                file_extension = ".vue"
            elif component_type == "python":
                component_content = self._generate_python_component(
                    component_name, props, template_type
                )
                file_extension = ".py"
            else:
                return {
                    "success": False,
                    "error": f"Unsupported component type: {component_type}",
                }

            # Create output file path
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            file_path = output_dir / f"{component_name}{file_extension}"

            # Generate supporting files
            supporting_files = self._generate_supporting_files(
                component_name, component_type, template_type
            )

            return {
                "success": True,
                "component_file": str(file_path),
                "component_content": component_content,
                "supporting_files": supporting_files,
                "metadata": {
                    "component_name": component_name,
                    "component_type": component_type,
                    "template_type": template_type,
                    "props": props,
                    "generated_at": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error generating component: {e}")
            return {
                "success": False,
                "error": f"Component generation failed: {str(e)}",
            }

    async def _handle_storybook_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Storybook scan request."""
        import re
        from pathlib import Path

        logger.info("[MCP] storybook/scan")

        try:
            # Extract parameters
            project_path = params.get("project_path", ".")
            scan_type = params.get(
                "scan_type", "stories"
            )  # stories, components, config

            project_path = Path(project_path)
            if not project_path.exists():
                return {
                    "success": False,
                    "error": f"Project path not found: {project_path}",
                }

            # Scan for Storybook files and configuration
            storybook_data = self._scan_storybook_files(project_path, scan_type)

            return {
                "success": True,
                "storybook_scan": storybook_data,
                "scan_type": scan_type,
                "scanned_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error scanning Storybook: {e}")
            return {
                "success": False,
                "error": f"Storybook scan failed: {str(e)}",
            }

    async def _handle_storybook_suggest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Storybook suggest request."""
        from pathlib import Path

        logger.info("[MCP] storybook/suggest")

        try:
            # Extract parameters
            component_path = params.get("component_path")
            suggestion_type = params.get(
                "suggestion_type", "stories"
            )  # stories, docs, addon

            if not component_path:
                return {
                    "success": False,
                    "error": "Missing required parameter: component_path",
                }

            component_path = Path(component_path)
            if not component_path.exists():
                return {
                    "success": False,
                    "error": f"Component file not found: {component_path}",
                }

            # Generate Storybook suggestions
            suggestions = self._generate_storybook_suggestions(
                component_path, suggestion_type
            )

            return {
                "success": True,
                "storybook_suggestions": suggestions,
                "component_path": str(component_path),
                "suggestion_type": suggestion_type,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating Storybook suggestions: {e}")
            return {
                "success": False,
                "error": f"Storybook suggestion generation failed: {str(e)}",
            }

    async def _handle_context_provide(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle context provide request."""
        from pathlib import Path

        logger.info("[MCP] context/provide")

        try:
            context_type = params.get("context_type", "project")
            scope = params.get("scope", ".")

            current_dir = Path.cwd()
            context = {
                "context_type": context_type,
                "timestamp": datetime.utcnow().isoformat(),
                "project_info": {},
                "codebase_summary": {},
                "expert_roles": [],
            }

            # Project information
            if context_type in ["project", "all"]:
                # Read README for project context
                readme_files = ["README.md", "README.rst", "README.txt", "readme.md"]
                readme_content = None

                for readme_name in readme_files:
                    readme_path = current_dir / readme_name
                    if readme_path.exists():
                        try:
                            readme_content = readme_path.read_text(encoding="utf-8")
                            break
                        except:
                            continue

                # Check for package.json, requirements.txt, etc.
                project_files = {
                    "python": "requirements.txt",
                    "node": "package.json",
                    "docker": "Dockerfile",
                    "config": "pyproject.toml",
                }

                detected_tech = []
                for tech, filename in project_files.items():
                    if (current_dir / filename).exists():
                        detected_tech.append(tech)

                context["project_info"] = {
                    "name": current_dir.name,
                    "has_readme": readme_content is not None,
                    "readme_preview": readme_content[:500] if readme_content else None,
                    "technologies": detected_tech,
                    "structure": "storyteller" in str(current_dir).lower(),
                }

            # Codebase summary
            if context_type in ["code", "all"]:
                python_files = list(current_dir.rglob("*.py"))
                test_files = [f for f in python_files if "test" in f.name]
                source_files = [f for f in python_files if "test" not in f.name]

                context["codebase_summary"] = {
                    "total_python_files": len(python_files),
                    "source_files": len(source_files),
                    "test_files": len(test_files),
                    "main_modules": [
                        f.stem for f in source_files if f.parent == current_dir
                    ][:10],
                    "test_coverage_estimate": len(test_files)
                    / max(len(source_files), 1),
                }

            # Expert roles available
            if context_type in ["roles", "all"]:
                roles = self.story_manager.get_available_roles()
                context["expert_roles"] = roles[:20]  # First 20 roles

            # Storyteller-specific context
            if "storyteller" in str(current_dir).lower():
                context["storyteller_context"] = {
                    "is_storyteller_project": True,
                    "available_repositories": list(self.config.repositories.keys()),
                    "mcp_server_active": True,
                    "expert_analysis_enabled": True,
                }

            return {
                "success": True,
                "message": f"Provided {context_type} context",
                "data": context,
            }

        except Exception as e:
            logger.error(f"Error providing context: {e}")
            return {
                "success": False,
                "message": f"Error providing context: {str(e)}",
                "error": "ContextError",
            }

    async def _handle_suggestion_improve(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle suggestion improve request."""
        import ast
        import re
        from pathlib import Path

        logger.info("[MCP] suggestion/improve")

        try:
            target = params.get("target", ".")
            improvement_type = params.get("type", "general")

            current_dir = Path.cwd()
            target_path = (current_dir / target).resolve()

            if not str(target_path).startswith(str(current_dir)):
                return {
                    "success": False,
                    "message": "Access denied: target outside working directory",
                    "error": "SecurityError",
                }

            suggestions = {
                "target": target,
                "improvement_type": improvement_type,
                "suggestions": [],
                "priorities": [],
            }

            if target_path.is_file() and target_path.suffix == ".py":
                # Analyze Python file for improvements
                content = target_path.read_text(encoding="utf-8")
                lines = content.splitlines()

                # Code quality suggestions
                code_suggestions = []

                # Check for long lines
                long_lines = [i + 1 for i, line in enumerate(lines) if len(line) > 100]
                if long_lines:
                    code_suggestions.append(
                        {
                            "type": "formatting",
                            "issue": f"Long lines found at lines: {long_lines[:5]}",
                            "suggestion": "Consider breaking long lines (>100 chars) for readability",
                            "priority": "medium",
                        }
                    )

                # Check for missing docstrings
                try:
                    tree = ast.parse(content)
                    functions_without_docs = []

                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                            if not (
                                node.body
                                and isinstance(node.body[0], ast.Expr)
                                and isinstance(node.body[0].value, ast.Constant)
                            ):
                                functions_without_docs.append(node.name)

                    if functions_without_docs:
                        code_suggestions.append(
                            {
                                "type": "documentation",
                                "issue": f"Missing docstrings: {functions_without_docs[:3]}",
                                "suggestion": "Add docstrings to improve code documentation",
                                "priority": "medium",
                            }
                        )

                except SyntaxError:
                    code_suggestions.append(
                        {
                            "type": "syntax",
                            "issue": "Syntax errors detected",
                            "suggestion": "Fix syntax errors before applying other improvements",
                            "priority": "high",
                        }
                    )

                # Check for TODO/FIXME comments
                todo_pattern = re.compile(r"#.*?(TODO|FIXME|XXX|HACK)", re.IGNORECASE)
                todos = []
                for i, line in enumerate(lines):
                    if todo_pattern.search(line):
                        todos.append(f"Line {i+1}: {line.strip()}")

                if todos:
                    code_suggestions.append(
                        {
                            "type": "maintenance",
                            "issue": f"Found {len(todos)} TODO/FIXME comments",
                            "suggestion": "Address pending TODO items",
                            "priority": "low",
                            "details": todos[:3],
                        }
                    )

                suggestions["suggestions"] = code_suggestions

            elif target_path.is_file() and target_path.name in [
                "README.md",
                "USAGE.md",
            ]:
                # Documentation improvements
                content = target_path.read_text(encoding="utf-8")

                doc_suggestions = []

                # Check for common documentation elements
                if "## Installation" not in content and "## Setup" not in content:
                    doc_suggestions.append(
                        {
                            "type": "documentation",
                            "suggestion": "Add installation/setup instructions",
                            "priority": "high",
                        }
                    )

                if "## Usage" not in content and "## Examples" not in content:
                    doc_suggestions.append(
                        {
                            "type": "documentation",
                            "suggestion": "Add usage examples",
                            "priority": "high",
                        }
                    )

                if len(content) < 500:
                    doc_suggestions.append(
                        {
                            "type": "documentation",
                            "suggestion": "Consider expanding documentation with more details",
                            "priority": "medium",
                        }
                    )

                suggestions["suggestions"] = doc_suggestions

            else:
                # General project improvements
                general_suggestions = [
                    {
                        "type": "testing",
                        "suggestion": "Add comprehensive test coverage",
                        "priority": "high",
                    },
                    {
                        "type": "documentation",
                        "suggestion": "Improve inline code documentation",
                        "priority": "medium",
                    },
                    {
                        "type": "architecture",
                        "suggestion": "Consider code organization and modularity",
                        "priority": "medium",
                    },
                ]
                suggestions["suggestions"] = general_suggestions

            # Prioritize suggestions
            high_priority = [
                s for s in suggestions["suggestions"] if s.get("priority") == "high"
            ]
            medium_priority = [
                s for s in suggestions["suggestions"] if s.get("priority") == "medium"
            ]
            low_priority = [
                s for s in suggestions["suggestions"] if s.get("priority") == "low"
            ]

            suggestions["priorities"] = {
                "high": len(high_priority),
                "medium": len(medium_priority),
                "low": len(low_priority),
                "recommendations": [s["suggestion"] for s in high_priority[:3]],
            }

            return {
                "success": True,
                "message": f"Generated improvement suggestions for: {target}",
                "data": suggestions,
            }

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return {
                "success": False,
                "message": f"Error generating suggestions: {str(e)}",
                "error": "SuggestionError",
            }

    async def _handle_workflow_automate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow automate request."""
        logger.info("[MCP] workflow/automate")

        try:
            workflow = params.get("workflow")
            if not workflow:
                raise ValueError("workflow parameter is required")

            workflow_params = params.get("params", {})

            # Define available automation workflows
            available_workflows = {
                "story_create": {
                    "description": "Create a story with expert analysis",
                    "required_params": ["content"],
                    "optional_params": ["repository", "roles"],
                },
                "test_setup": {
                    "description": "Set up basic test structure",
                    "required_params": [],
                    "optional_params": ["target_dir"],
                },
                "code_quality": {
                    "description": "Run code quality checks (black, isort, flake8)",
                    "required_params": [],
                    "optional_params": ["fix"],
                },
                "documentation": {
                    "description": "Generate or update documentation",
                    "required_params": ["type"],
                    "optional_params": ["target"],
                },
            }

            if workflow not in available_workflows:
                return {
                    "success": False,
                    "message": f"Unknown workflow: {workflow}",
                    "error": "UnknownWorkflow",
                    "data": {"available_workflows": list(available_workflows.keys())},
                }

            workflow_config = available_workflows[workflow]

            # Check required parameters
            missing_params = [
                param
                for param in workflow_config["required_params"]
                if param not in workflow_params
            ]

            if missing_params:
                return {
                    "success": False,
                    "message": f"Missing required parameters: {missing_params}",
                    "error": "MissingParameters",
                    "data": {"required": workflow_config["required_params"]},
                }

            # Execute workflow
            result = {"workflow": workflow, "steps": [], "status": "completed"}

            if workflow == "story_create":
                # Delegate to existing story creation workflow
                story_result = await self.workflow_processor.create_story_workflow(
                    content=workflow_params["content"],
                    repository=workflow_params.get("repository"),
                    roles=workflow_params.get("roles"),
                )

                result["steps"] = [
                    {"step": "story_analysis", "status": "completed"},
                    {"step": "expert_review", "status": "completed"},
                    {
                        "step": "github_issue",
                        "status": "completed" if story_result.success else "failed",
                    },
                ]
                result["story_result"] = {
                    "success": story_result.success,
                    "message": story_result.message,
                    "data": story_result.data,
                }

            elif workflow == "code_quality":
                # Simulate code quality workflow
                fix_issues = workflow_params.get("fix", False)
                result["steps"] = [
                    {
                        "step": "black_format",
                        "status": "completed" if fix_issues else "check",
                    },
                    {
                        "step": "isort_imports",
                        "status": "completed" if fix_issues else "check",
                    },
                    {"step": "flake8_lint", "status": "check"},
                ]
                result["message"] = "Code quality workflow simulated"

            elif workflow == "test_setup":
                # Simulate test setup workflow
                result["steps"] = [
                    {"step": "create_test_dir", "status": "simulated"},
                    {"step": "add_init_files", "status": "simulated"},
                    {"step": "create_test_template", "status": "simulated"},
                ]
                result["message"] = "Test setup workflow simulated"

            elif workflow == "documentation":
                # Simulate documentation workflow
                doc_type = workflow_params["type"]
                result["steps"] = [
                    {"step": f"generate_{doc_type}", "status": "simulated"},
                    {"step": "update_readme", "status": "simulated"},
                ]
                result["message"] = f"Documentation workflow for {doc_type} simulated"

            return {
                "success": True,
                "message": f"Workflow '{workflow}' automated successfully",
                "data": result,
            }

        except Exception as e:
            logger.error(f"Error automating workflow: {e}")
            return {
                "success": False,
                "message": f"Error automating workflow: {str(e)}",
                "error": "WorkflowError",
            }

    def _get_method_description(self, method: str) -> str:
        """Get description for a method."""

        descriptions = {
            "story/create": "Create a new story with expert analysis and GitHub issues",
            "story/analyze": "Analyze a story without creating GitHub issues",
            "story/status": "Get the status of a story by ID",
            "role/query": "Query a specific expert role with a question",
            "role/list": "List all available expert roles",
            "role/analyze_story": "Get analysis from a specific role for a story",
            "repository/list": "List all configured repositories",
            "repository/get_config": "Get configuration for a specific repository",
            "system/health": "Check system health status",
            "system/capabilities": "Get system capabilities and available methods",
            "system/validate": "Validate system configuration",
            "file/read": "Read the contents of a file in the codebase",
            "file/write": "Write content to a file in the codebase",
            "codebase/scan": "Scan the codebase for files, structure, or patterns",
            "codebase/analyze": "Analyze the codebase for metrics, dependencies, or issues",
            "test/analyze": "Analyze test coverage and quality for the codebase or file",
            "test/suggest": "Suggest new tests or improvements for the codebase or file",
            "test/generate": "Generate new tests for the codebase or file",
            "qa/strategy": "Suggest or analyze QA strategies for the project",
            "component/analyze": "Analyze a component for structure, usage, or best practices",
            "component/generate": "Generate a new component or suggest improvements",
            "storybook/scan": "Scan Storybook stories for coverage and structure",
            "storybook/suggest": "Suggest new Storybook stories or improvements",
            "context/provide": "Provide context for Copilot or LLM workflows",
            "suggestion/improve": "Suggest improvements for code, tests, or documentation",
            "workflow/automate": "Automate a workflow or process in the codebase",
        }

        return descriptions.get(method, "No description available")

    def _get_method_parameters(self, method: str) -> Dict[str, Any]:
        """Get parameter schema for a method."""

        schemas = {
            "story/create": {
                "content": {
                    "type": "string",
                    "required": True,
                    "description": "Story content",
                },
                "repository": {
                    "type": "string",
                    "required": False,
                    "description": "Target repository",
                },
                "roles": {
                    "type": "array",
                    "required": False,
                    "description": "Expert roles to use",
                },
                "context": {
                    "type": "object",
                    "required": False,
                    "description": "Additional context",
                },
            },
            "story/analyze": {
                "content": {
                    "type": "string",
                    "required": True,
                    "description": "Story content",
                },
                "roles": {
                    "type": "array",
                    "required": False,
                    "description": "Expert roles to use",
                },
                "context": {
                    "type": "object",
                    "required": False,
                    "description": "Additional context",
                },
            },
            "story/status": {
                "story_id": {
                    "type": "string",
                    "required": True,
                    "description": "Story ID",
                }
            },
            "role/query": {
                "role_name": {
                    "type": "string",
                    "required": True,
                    "description": "Expert role name",
                },
                "question": {
                    "type": "string",
                    "required": True,
                    "description": "Question to ask the role",
                },
                "context": {
                    "type": "object",
                    "required": False,
                    "description": "Additional context",
                },
            },
            "role/analyze_story": {
                "role_name": {
                    "type": "string",
                    "required": True,
                    "description": "Expert role name",
                },
                "story_content": {
                    "type": "string",
                    "required": True,
                    "description": "Story content",
                },
                "context": {
                    "type": "object",
                    "required": False,
                    "description": "Additional context",
                },
            },
            "repository/get_config": {
                "repository_key": {
                    "type": "string",
                    "required": True,
                    "description": "Repository key",
                }
            },
            "file/read": {
                "path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to file to read",
                },
            },
            "file/write": {
                "path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to file to write",
                },
                "content": {
                    "type": "string",
                    "required": True,
                    "description": "Content to write to file",
                },
            },
            "codebase/scan": {
                "pattern": {
                    "type": "string",
                    "required": False,
                    "description": "Glob or regex pattern to scan for",
                },
            },
            "codebase/analyze": {
                "scope": {
                    "type": "string",
                    "required": False,
                    "description": "Scope or directory to analyze",
                },
            },
            "test/analyze": {
                "path": {
                    "type": "string",
                    "required": False,
                    "description": "File or directory to analyze tests for",
                },
            },
            "test/suggest": {
                "path": {
                    "type": "string",
                    "required": False,
                    "description": "File or directory to suggest tests for",
                },
            },
            "test/generate": {
                "path": {
                    "type": "string",
                    "required": False,
                    "description": "File or directory to generate tests for",
                },
            },
            "qa/strategy": {
                "scope": {
                    "type": "string",
                    "required": False,
                    "description": "Scope or area for QA strategy",
                },
            },
            "component/analyze": {
                "component": {
                    "type": "string",
                    "required": True,
                    "description": "Component name or path",
                },
            },
            "component/generate": {
                "spec": {
                    "type": "object",
                    "required": True,
                    "description": "Specification for component generation",
                },
            },
            "storybook/scan": {
                "pattern": {
                    "type": "string",
                    "required": False,
                    "description": "Pattern to scan Storybook stories",
                },
            },
            "storybook/suggest": {
                "component": {
                    "type": "string",
                    "required": False,
                    "description": "Component to suggest stories for",
                },
            },
            "context/provide": {
                "context_type": {
                    "type": "string",
                    "required": False,
                    "description": "Type of context to provide (code, test, etc.)",
                },
            },
            "suggestion/improve": {
                "target": {
                    "type": "string",
                    "required": False,
                    "description": "Target code, test, or doc to improve",
                },
            },
            "workflow/automate": {
                "workflow": {
                    "type": "string",
                    "required": True,
                    "description": "Workflow or process to automate",
                },
                "params": {
                    "type": "object",
                    "required": False,
                    "description": "Parameters for workflow automation",
                },
            },
        }

        return schemas.get(method, {})

    def _generate_python_tests(
        self, file_path, functions, classes, framework, test_type
    ):
        """Generate Python test template."""

        test_content = f"""\"\"\"Test module for {file_path.name}.\"\"\"

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from {file_path.stem} import {", ".join(classes + functions[:5])}


class Test{file_path.stem.title()}:
    \"\"\"Test class for {file_path.stem} module.\"\"\"

    def setup_method(self):
        \"\"\"Set up test fixtures before each test method.\"\"\"
        pass

    def teardown_method(self):
        \"\"\"Tear down test fixtures after each test method.\"\"\"
        pass

"""

        # Add test methods for each function
        for func in functions[:10]:  # Limit to first 10 functions
            test_content += f"""
    def test_{func}_success(self):
        \"\"\"Test {func} with valid input.\"\"\"
        # Arrange
        # TODO: Set up test data
        
        # Act
        # TODO: Call {func} with test data
        result = {func}()
        
        # Assert
        # TODO: Assert expected behavior
        assert result is not None

    def test_{func}_error_handling(self):
        \"\"\"Test {func} error handling.\"\"\"
        # TODO: Test error conditions
        pass
"""

        # Add test methods for each class
        for cls in classes[:5]:  # Limit to first 5 classes
            test_content += f"""
    def test_{cls.lower()}_initialization(self):
        \"\"\"Test {cls} initialization.\"\"\"
        # Arrange & Act
        instance = {cls}()
        
        # Assert
        assert instance is not None

    def test_{cls.lower()}_methods(self):
        \"\"\"Test {cls} main methods.\"\"\"
        # TODO: Test class methods
        pass
"""

        return test_content

    def _generate_js_tests(self, file_path, exports, functions, framework, test_type):
        """Generate JavaScript/TypeScript test template."""

        import_path = f"./{file_path.stem}"

        test_content = f"""/**
 * Test suite for {file_path.name}
 */

import {{ describe, it, expect, beforeEach, afterEach }} from '{framework}';
"""

        # Add imports based on exports
        if exports:
            test_content += (
                f"import {{ {', '.join(exports[:10])} }} from '{import_path}';\n"
            )

        test_content += f"""

describe('{file_path.stem}', () => {{
    beforeEach(() => {{
        // Setup before each test
    }});

    afterEach(() => {{
        // Cleanup after each test
    }});
"""

        # Add test cases for each export/function
        for func in (exports + functions)[:10]:  # Limit to first 10
            test_content += f"""
    describe('{func}', () => {{
        it('should work with valid input', () => {{
            // Arrange
            // TODO: Set up test data
            
            // Act
            // TODO: Call {func} with test data
            const result = {func}();
            
            // Assert
            // TODO: Assert expected behavior
            expect(result).toBeDefined();
        }});

        it('should handle errors properly', () => {{
            // TODO: Test error conditions
            expect(() => {{
                // Call with invalid input
            }}).toThrow();
        }});
    }});
"""

        test_content += "\n});\n"
        return test_content

    def _generate_test_scenarios(self, content, test_type):
        """Generate test scenarios based on code analysis."""

        scenarios = []

        # Basic scenarios based on test type
        if test_type == "unit":
            scenarios.extend(
                [
                    "Test function with valid inputs",
                    "Test function with invalid inputs",
                    "Test function with edge cases",
                    "Test function error handling",
                    "Test function return values",
                ]
            )
        elif test_type == "integration":
            scenarios.extend(
                [
                    "Test component integration",
                    "Test data flow between components",
                    "Test external dependencies",
                    "Test configuration handling",
                    "Test error propagation",
                ]
            )
        elif test_type == "e2e":
            scenarios.extend(
                [
                    "Test complete user workflow",
                    "Test system behavior",
                    "Test performance requirements",
                    "Test reliability requirements",
                    "Test security requirements",
                ]
            )

        # Add specific scenarios based on code patterns
        if "async def" in content or "await" in content:
            scenarios.append("Test asynchronous operations")
            scenarios.append("Test concurrent execution")

        if "class" in content:
            scenarios.append("Test class initialization")
            scenarios.append("Test class methods")
            scenarios.append("Test class inheritance")

        if "import" in content or "from" in content:
            scenarios.append("Test dependency injection")
            scenarios.append("Test module imports")

        if "Exception" in content or "Error" in content:
            scenarios.append("Test exception handling")
            scenarios.append("Test error recovery")

        return scenarios[:15]  # Limit to 15 scenarios

    def _analyze_project_for_qa(self, project_path):
        """Analyze project structure for QA strategy generation."""

        analysis = {
            "project_type": "unknown",
            "languages": [],
            "frameworks": [],
            "test_frameworks": [],
            "complexity": "medium",
            "file_count": 0,
            "test_coverage": "unknown",
            "dependencies": [],
            "critical_paths": [],
        }

        try:
            # Count files and detect languages
            for file_path in project_path.rglob("*"):
                if file_path.is_file():
                    analysis["file_count"] += 1

                    suffix = file_path.suffix.lower()
                    if suffix == ".py":
                        if "python" not in analysis["languages"]:
                            analysis["languages"].append("python")
                    elif suffix in [".js", ".jsx", ".ts", ".tsx"]:
                        if "javascript" not in analysis["languages"]:
                            analysis["languages"].append("javascript")
                    elif suffix in [".java"]:
                        if "java" not in analysis["languages"]:
                            analysis["languages"].append("java")
                    elif suffix in [".cs"]:
                        if "csharp" not in analysis["languages"]:
                            analysis["languages"].append("csharp")

            # Detect frameworks and project type
            if (project_path / "package.json").exists():
                analysis["project_type"] = "nodejs"
                try:
                    import json

                    with open(project_path / "package.json") as f:
                        package_data = json.load(f)
                        deps = {
                            **package_data.get("dependencies", {}),
                            **package_data.get("devDependencies", {}),
                        }

                        if "react" in deps:
                            analysis["frameworks"].append("react")
                        if "vue" in deps:
                            analysis["frameworks"].append("vue")
                        if "angular" in deps:
                            analysis["frameworks"].append("angular")
                        if "jest" in deps:
                            analysis["test_frameworks"].append("jest")
                        if "vitest" in deps:
                            analysis["test_frameworks"].append("vitest")
                        if "cypress" in deps:
                            analysis["test_frameworks"].append("cypress")

                        analysis["dependencies"] = list(deps.keys())[:20]  # Limit to 20
                except:
                    pass

            elif (project_path / "requirements.txt").exists() or (
                project_path / "pyproject.toml"
            ).exists():
                analysis["project_type"] = "python"
                analysis["frameworks"].append("python")

                # Check for common Python frameworks
                if (project_path / "manage.py").exists():
                    analysis["frameworks"].append("django")
                if any(project_path.rglob("*flask*")):
                    analysis["frameworks"].append("flask")
                if any(project_path.rglob("*fastapi*")):
                    analysis["frameworks"].append("fastapi")

            # Detect test frameworks and coverage
            if any(project_path.rglob("test_*.py")) or any(
                project_path.rglob("*_test.py")
            ):
                analysis["test_frameworks"].append("pytest")
            if any(project_path.rglob("*.test.js")) or any(
                project_path.rglob("*.test.ts")
            ):
                analysis["test_frameworks"].append("jest")

            # Determine complexity based on file count and structure
            if analysis["file_count"] < 50:
                analysis["complexity"] = "low"
            elif analysis["file_count"] < 200:
                analysis["complexity"] = "medium"
            else:
                analysis["complexity"] = "high"

            # Identify critical paths
            critical_files = ["main.py", "app.py", "index.js", "App.js", "server.js"]
            for file_name in critical_files:
                critical_path = list(project_path.rglob(file_name))
                if critical_path:
                    analysis["critical_paths"].append(str(critical_path[0]))

        except Exception as e:
            logger.warning(f"Error analyzing project: {e}")

        return analysis

    def _generate_qa_strategy(self, project_analysis, scope, risk_level, timeline):
        """Generate QA strategy based on project analysis."""

        strategy = {
            "testing_phases": [],
            "test_types": [],
            "coverage_targets": {},
            "tools_recommended": [],
            "timeline_estimates": {},
            "risk_mitigation": [],
        }

        # Base testing phases
        if timeline == "fast":
            strategy["testing_phases"] = ["unit", "integration"]
        elif timeline == "standard":
            strategy["testing_phases"] = ["unit", "integration", "system"]
        else:  # thorough
            strategy["testing_phases"] = [
                "unit",
                "integration",
                "system",
                "acceptance",
                "performance",
            ]

        # Test types based on project analysis
        languages = project_analysis.get("languages", [])
        frameworks = project_analysis.get("frameworks", [])

        if "python" in languages:
            strategy["test_types"].extend(
                ["unit_tests", "integration_tests", "api_tests"]
            )
            strategy["tools_recommended"].extend(
                ["pytest", "coverage", "black", "flake8"]
            )

        if "javascript" in languages:
            strategy["test_types"].extend(
                ["unit_tests", "component_tests", "e2e_tests"]
            )
            strategy["tools_recommended"].extend(
                ["jest", "cypress", "eslint", "prettier"]
            )

        if "react" in frameworks:
            strategy["test_types"].append("component_tests")
            strategy["tools_recommended"].extend(["react-testing-library", "storybook"])

        # Coverage targets based on risk level
        if risk_level == "low":
            strategy["coverage_targets"] = {"unit": 70, "integration": 50, "e2e": 30}
        elif risk_level == "medium":
            strategy["coverage_targets"] = {"unit": 80, "integration": 70, "e2e": 50}
        else:  # high
            strategy["coverage_targets"] = {"unit": 90, "integration": 85, "e2e": 70}

        # Timeline estimates
        complexity = project_analysis.get("complexity", "medium")
        base_time = {"low": 2, "medium": 5, "high": 10}[complexity]

        strategy["timeline_estimates"] = {
            "setup": f"{base_time} days",
            "unit_tests": f"{base_time * 2} days",
            "integration_tests": f"{base_time * 1.5} days",
            "e2e_tests": f"{base_time} days",
            "documentation": f"{base_time * 0.5} days",
        }

        # Risk mitigation strategies
        if risk_level in ["medium", "high"]:
            strategy["risk_mitigation"].extend(
                [
                    "Implement CI/CD pipeline with automated testing",
                    "Set up code coverage monitoring",
                    "Establish test data management strategy",
                    "Create rollback procedures",
                ]
            )

        if risk_level == "high":
            strategy["risk_mitigation"].extend(
                [
                    "Implement security testing",
                    "Add performance testing",
                    "Set up monitoring and alerting",
                    "Establish disaster recovery procedures",
                ]
            )

        return strategy

    def _get_qa_recommendations(self, project_analysis, risk_level):
        """Get QA recommendations based on project analysis."""

        recommendations = []

        # General recommendations
        if not project_analysis.get("test_frameworks"):
            recommendations.append(
                {
                    "priority": "high",
                    "category": "tooling",
                    "title": "Set up testing framework",
                    "description": "No testing framework detected. Consider adding pytest for Python or Jest for JavaScript.",
                }
            )

        if project_analysis.get("file_count", 0) > 100 and not any(
            "ci" in f for f in project_analysis.get("critical_paths", [])
        ):
            recommendations.append(
                {
                    "priority": "high",
                    "category": "automation",
                    "title": "Implement CI/CD pipeline",
                    "description": "Large codebase detected. Set up automated testing and deployment pipeline.",
                }
            )

        # Language-specific recommendations
        if "python" in project_analysis.get("languages", []):
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "code_quality",
                    "title": "Add Python linting",
                    "description": "Use black, flake8, and isort for consistent code formatting and quality.",
                }
            )

        if "javascript" in project_analysis.get("languages", []):
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "code_quality",
                    "title": "Add JavaScript linting",
                    "description": "Use ESLint and Prettier for code quality and formatting.",
                }
            )

        # Risk-level specific recommendations
        if risk_level == "high":
            recommendations.extend(
                [
                    {
                        "priority": "high",
                        "category": "security",
                        "title": "Security testing",
                        "description": "Implement security scanning and vulnerability assessment.",
                    },
                    {
                        "priority": "high",
                        "category": "performance",
                        "title": "Performance testing",
                        "description": "Add load testing and performance monitoring.",
                    },
                ]
            )

        # Framework-specific recommendations
        if "react" in project_analysis.get("frameworks", []):
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "testing",
                    "title": "Component testing",
                    "description": "Use React Testing Library for component testing and Storybook for component documentation.",
                }
            )

        return recommendations

    def _analyze_react_component(self, content, component_path):
        """Analyze React/JavaScript component."""
        import re

        analysis = {
            "component_type": "unknown",
            "props": [],
            "state": [],
            "hooks": [],
            "methods": [],
            "imports": [],
            "exports": [],
            "jsx_elements": [],
            "complexity": "low",
            "issues": [],
            "suggestions": [],
        }

        try:
            # Detect component type
            if "class" in content and "extends" in content:
                analysis["component_type"] = "class"
            elif "function" in content or "const" in content and "=>" in content:
                analysis["component_type"] = "function"

            # Extract imports
            imports = re.findall(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]", content)
            analysis["imports"] = imports

            # Extract props (for function components)
            props_match = re.findall(r"function\s+\w+\(\{([^}]+)\}\)", content)
            if props_match:
                props = [p.strip() for p in props_match[0].split(",")]
                analysis["props"] = props

            # Extract hooks
            hooks = re.findall(r"use(\w+)\(", content)
            analysis["hooks"] = list(set(hooks))

            # Extract JSX elements
            jsx_elements = re.findall(r"<(\w+)", content)
            analysis["jsx_elements"] = list(set(jsx_elements))

            # Extract methods (for class components)
            methods = re.findall(r"(\w+)\s*=\s*\([^)]*\)\s*=>\s*{", content)
            analysis["methods"] = methods

            # Calculate complexity
            lines = content.split("\n")
            analysis["complexity"] = self._calculate_component_complexity(
                content, lines
            )

            # Identify issues and suggestions
            analysis["issues"] = self._identify_component_issues(content, analysis)
            analysis["suggestions"] = self._generate_component_suggestions(
                content, analysis
            )

        except Exception as e:
            logger.warning(f"Error analyzing React component: {e}")

        return analysis

    def _analyze_vue_component(self, content, component_path):
        """Analyze Vue component."""
        import re

        analysis = {
            "component_type": "vue",
            "props": [],
            "data": [],
            "computed": [],
            "methods": [],
            "template_elements": [],
            "script_content": "",
            "style_content": "",
            "complexity": "low",
            "issues": [],
            "suggestions": [],
        }

        try:
            # Extract script section
            script_match = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
            if script_match:
                analysis["script_content"] = script_match.group(1)

            # Extract template elements
            template_match = re.search(
                r"<template[^>]*>(.*?)</template>", content, re.DOTALL
            )
            if template_match:
                template_content = template_match.group(1)
                elements = re.findall(r"<(\w+)", template_content)
                analysis["template_elements"] = list(set(elements))

            # Extract props, data, methods from script
            script_content = analysis["script_content"]

            # Props
            props_match = re.search(r"props:\s*\[(.*?)\]", script_content, re.DOTALL)
            if props_match:
                props = re.findall(r"['\"](\w+)['\"]", props_match.group(1))
                analysis["props"] = props

            # Methods
            methods_match = re.search(r"methods:\s*{(.*?)}", script_content, re.DOTALL)
            if methods_match:
                methods = re.findall(r"(\w+)\s*\(", methods_match.group(1))
                analysis["methods"] = methods

            # Calculate complexity
            lines = content.split("\n")
            analysis["complexity"] = self._calculate_component_complexity(
                content, lines
            )

        except Exception as e:
            logger.warning(f"Error analyzing Vue component: {e}")

        return analysis

    def _analyze_python_component(self, content, component_path):
        """Analyze Python component/class."""
        import ast
        import re

        analysis = {
            "component_type": "python_class",
            "classes": [],
            "functions": [],
            "methods": [],
            "imports": [],
            "dependencies": [],
            "complexity": "low",
            "issues": [],
            "suggestions": [],
        }

        try:
            # Parse AST for detailed analysis
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "methods": [
                            method.name
                            for method in node.body
                            if isinstance(method, ast.FunctionDef)
                        ],
                        "attributes": [],
                    }
                    analysis["classes"].append(class_info)

                elif isinstance(node, ast.FunctionDef):
                    if not any(
                        node.name in cls["methods"] for cls in analysis["classes"]
                    ):
                        analysis["functions"].append(node.name)

                elif isinstance(node, ast.Import):
                    analysis["imports"].extend([alias.name for alias in node.names])

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis["imports"].append(node.module)

            # Calculate complexity
            lines = content.split("\n")
            analysis["complexity"] = self._calculate_component_complexity(
                content, lines
            )

            # Identify issues and suggestions
            analysis["issues"] = self._identify_python_component_issues(
                content, analysis
            )
            analysis["suggestions"] = self._generate_python_component_suggestions(
                content, analysis
            )

        except Exception as e:
            logger.warning(f"Error analyzing Python component: {e}")

        return analysis

    def _calculate_component_complexity(self, content, lines):
        """Calculate component complexity."""

        # Simple complexity calculation based on various factors
        score = 0

        # Line count
        line_count = len([line for line in lines if line.strip()])
        if line_count > 100:
            score += 3
        elif line_count > 50:
            score += 2
        elif line_count > 20:
            score += 1

        # Nesting level (approximate)
        max_indent = 0
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent)

        if max_indent > 20:
            score += 3
        elif max_indent > 12:
            score += 2
        elif max_indent > 8:
            score += 1

        # Conditional statements
        conditionals = (
            content.count("if ") + content.count("else") + content.count("switch")
        )
        if conditionals > 10:
            score += 2
        elif conditionals > 5:
            score += 1

        # Return complexity level
        if score >= 6:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"

    def _identify_component_issues(self, content, analysis):
        """Identify issues in React/JS components."""

        issues = []

        # Large component
        if len(content.split("\n")) > 200:
            issues.append(
                {
                    "type": "size",
                    "severity": "warning",
                    "message": "Component is very large (>200 lines). Consider breaking it down.",
                }
            )

        # Too many props
        if len(analysis.get("props", [])) > 10:
            issues.append(
                {
                    "type": "props",
                    "severity": "warning",
                    "message": "Component has many props (>10). Consider using prop objects or context.",
                }
            )

        # Missing key prop
        if "map(" in content and "key=" not in content:
            issues.append(
                {
                    "type": "performance",
                    "severity": "error",
                    "message": "Missing 'key' prop in mapped elements.",
                }
            )

        # Inline styles
        if "style={{" in content:
            issues.append(
                {
                    "type": "style",
                    "severity": "info",
                    "message": "Consider using CSS classes instead of inline styles.",
                }
            )

        return issues

    def _identify_python_component_issues(self, content, analysis):
        """Identify issues in Python components."""

        issues = []

        # Large class
        if len(content.split("\n")) > 300:
            issues.append(
                {
                    "type": "size",
                    "severity": "warning",
                    "message": "Class is very large (>300 lines). Consider breaking it down.",
                }
            )

        # Too many methods
        for cls in analysis.get("classes", []):
            if len(cls.get("methods", [])) > 20:
                issues.append(
                    {
                        "type": "methods",
                        "severity": "warning",
                        "message": f"Class {cls['name']} has many methods (>20). Consider refactoring.",
                    }
                )

        # Missing docstrings
        if '"""' not in content and "'''" not in content:
            issues.append(
                {
                    "type": "documentation",
                    "severity": "warning",
                    "message": "Missing docstrings. Add documentation for classes and methods.",
                }
            )

        return issues

    def _generate_component_suggestions(self, content, analysis):
        """Generate suggestions for React/JS components."""

        suggestions = []

        # Performance optimizations
        if analysis["component_type"] == "function" and "memo" not in content:
            suggestions.append(
                {
                    "type": "performance",
                    "priority": "medium",
                    "suggestion": "Consider using React.memo() for performance optimization if component re-renders frequently.",
                }
            )

        # Hook optimizations
        if "useCallback" not in content and len(analysis.get("methods", [])) > 3:
            suggestions.append(
                {
                    "type": "performance",
                    "priority": "medium",
                    "suggestion": "Consider using useCallback() for function props to prevent unnecessary re-renders.",
                }
            )

        # Testing
        suggestions.append(
            {
                "type": "testing",
                "priority": "high",
                "suggestion": "Add unit tests for component props, state changes, and user interactions.",
            }
        )

        # Accessibility
        if "aria-" not in content and "role=" not in content:
            suggestions.append(
                {
                    "type": "accessibility",
                    "priority": "medium",
                    "suggestion": "Add ARIA attributes for better accessibility.",
                }
            )

        return suggestions

    def _generate_python_component_suggestions(self, content, analysis):
        """Generate suggestions for Python components."""

        suggestions = []

        # Type hints
        if ":" not in content or "->" not in content:
            suggestions.append(
                {
                    "type": "typing",
                    "priority": "medium",
                    "suggestion": "Add type hints for better code documentation and IDE support.",
                }
            )

        # Error handling
        if "try:" not in content and "except" not in content:
            suggestions.append(
                {
                    "type": "error_handling",
                    "priority": "high",
                    "suggestion": "Add proper error handling with try-except blocks.",
                }
            )

        # Logging
        if "logger" not in content and "logging" not in content:
            suggestions.append(
                {
                    "type": "logging",
                    "priority": "medium",
                    "suggestion": "Add logging for debugging and monitoring purposes.",
                }
            )

        # Testing
        suggestions.append(
            {
                "type": "testing",
                "priority": "high",
                "suggestion": "Add unit tests for all public methods and edge cases.",
            }
        )

        return suggestions

    def _generate_react_component(self, component_name, props, template_type):
        """Generate React component code."""

        props_interface = ""
        props_destructure = ""

        if props:
            props_interface = f"""interface {component_name}Props {{
{chr(10).join(f"  {prop}: any;" for prop in props)}
}}

"""
            props_destructure = f"{{ {', '.join(props)} }}: {component_name}Props"
        else:
            props_destructure = ""

        if template_type == "basic":
            return f"""{props_interface}const {component_name} = ({props_destructure}) => {{
  return (
    <div className="{component_name.lower()}">
      <h2>{component_name}</h2>
      {self._generate_react_template_content(template_type, props)}
    </div>
  );
}};

export default {component_name};
"""
        elif template_type == "form":
            return f"""{props_interface}import {{ useState }} from 'react';

const {component_name} = ({props_destructure}) => {{
  const [formData, setFormData] = useState({{}});

  const handleSubmit = (e) => {{
    e.preventDefault();
    // Handle form submission
    console.log('Form submitted:', formData);
  }};

  const handleChange = (e) => {{
    setFormData({{
      ...formData,
      [e.target.name]: e.target.value
    }});
  }};

  return (
    <div className="{component_name.lower()}">
      <h2>{component_name}</h2>
      <form onSubmit={{handleSubmit}}>
        {self._generate_react_template_content(template_type, props)}
        <button type="submit">Submit</button>
      </form>
    </div>
  );
}};

export default {component_name};
"""
        elif template_type == "list":
            return f"""{props_interface}const {component_name} = ({props_destructure}) => {{
  const items = props?.items || [];

  return (
    <div className="{component_name.lower()}">
      <h2>{component_name}</h2>
      <ul>
        {{items.map((item, index) => (
          <li key={{index}}>{{item}}</li>
        ))}}
      </ul>
    </div>
  );
}};

export default {component_name};
"""
        else:
            return self._generate_react_component(component_name, props, "basic")

    def _generate_vue_component(self, component_name, props, template_type):
        """Generate Vue component code."""

        props_definition = ""
        if props:
            props_list = "', '".join(props)
            props_definition = f"  props: ['{props_list}'],"

        template_content = self._generate_vue_template_content(template_type, props)

        return f"""<template>
  <div class="{component_name.lower()}">
    <h2>{component_name}</h2>
    {template_content}
  </div>
</template>

<script>
export default {{
  name: '{component_name}',
{props_definition}
  data() {{
    return {{
      // Component data
    }};
  }},
  methods: {{
    // Component methods
  }}
}};
</script>

<style scoped>
.{component_name.lower()} {{
  /* Component styles */
}}
</style>
"""

    def _generate_python_component(self, component_name, props, template_type):
        """Generate Python component/class code."""

        init_params = ""
        init_assignments = ""

        if props:
            init_params = ", " + ", ".join(f"{prop}: Any = None" for prop in props)
            init_assignments = "\\n".join(
                f"        self.{prop} = {prop}" for prop in props
            )

        if template_type == "basic":
            return f'''"""
{component_name} component.
"""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class {component_name}:
    """
    {component_name} component for handling specific functionality.
    """

    def __init__(self{init_params}):
        """
        Initialize {component_name}.
        
        Args:
{chr(10).join(f"            {prop}: {prop} parameter" for prop in props) if props else "            No parameters"}
        """
{init_assignments}
        logger.info(f"{component_name} initialized")

    def process(self) -> Any:
        """
        Main processing method.
        
        Returns:
            Processing result
        """
        try:
            # Implement main logic here
            result = self._perform_operation()
            return result
        except Exception as e:
            logger.error(f"Error in {component_name}.process(): {{e}}")
            raise

    def _perform_operation(self) -> Any:
        """
        Perform the main operation.
        
        Returns:
            Operation result
        """
        # TODO: Implement operation logic
        return None

    def __str__(self) -> str:
        """String representation of {component_name}."""
        return f"{component_name}({', '.join(f'{prop}={{getattr(self, prop, None)}}' for prop in props) if props else ''})"

    def __repr__(self) -> str:
        """Developer representation of {component_name}."""
        return self.__str__()
'''
        elif template_type == "dataclass":
            return f'''"""
{component_name} data component.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class {component_name}:
    """
    {component_name} data component.
    """
{chr(10).join(f"    {prop}: Any = None" for prop in props) if props else "    # No fields defined"}

    def validate(self) -> bool:
        """
        Validate component data.
        
        Returns:
            True if valid, False otherwise
        """
        # TODO: Implement validation logic
        return True

    def to_dict(self) -> dict:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {{
{chr(10).join(f'            "{prop}": self.{prop},' for prop in props) if props else "            # No fields to convert"}
        }}

    @classmethod
    def from_dict(cls, data: dict) -> "{component_name}":
        """
        Create instance from dictionary.
        
        Args:
            data: Dictionary data
            
        Returns:
            {component_name} instance
        """
        return cls(
{chr(10).join(f'            {prop}=data.get("{prop}"),' for prop in props) if props else "            # No fields to initialize"}
        )
'''
        else:
            return self._generate_python_component(component_name, props, "basic")

    def _generate_react_template_content(self, template_type, props):
        """Generate React template content based on type."""

        if template_type == "form":
            return """
        <input
          type="text"
          name="example"
          placeholder="Enter value"
          onChange={handleChange}
        />"""
        elif template_type == "list":
            return ""
        else:
            return f"""
      <p>This is the {template_type} component.</p>
      {chr(10).join(f"      <p>{prop}: {{{prop}}}</p>" for prop in props) if props else ""}"""

    def _generate_vue_template_content(self, template_type, props):
        """Generate Vue template content based on type."""

        if template_type == "form":
            return """
    <form @submit.prevent="handleSubmit">
      <input v-model="formData.example" placeholder="Enter value" />
      <button type="submit">Submit</button>
    </form>"""
        elif template_type == "list":
            return """
    <ul>
      <li v-for="(item, index) in items" :key="index">{{ item }}</li>
    </ul>"""
        else:
            return f"""
    <p>This is the {template_type} component.</p>
    {chr(10).join(f"    <p>{prop}: {{{{ {prop} }}}}</p>" for prop in props) if props else ""}"""

    def _generate_supporting_files(self, component_name, component_type, template_type):
        """Generate supporting files for the component."""

        supporting_files = {}

        if component_type == "react":
            # Generate test file
            supporting_files[
                f"{component_name}.test.jsx"
            ] = f"""import {{ render, screen }} from '@testing-library/react';
import {component_name} from './{component_name}';

describe('{component_name}', () => {{
  test('renders component', () => {{
    render(<{component_name} />);
    expect(screen.getByText('{component_name}')).toBeInTheDocument();
  }});
}});
"""

            # Generate story file
            supporting_files[
                f"{component_name}.stories.jsx"
            ] = f"""import type {{ Meta, StoryObj }} from '@storybook/react';
import {{ {component_name} }} from './{component_name}';

const meta: Meta<typeof {component_name}> = {{
  title: 'Components/{component_name}',
  component: {component_name},
  parameters: {{
    layout: 'centered',
  }},
  tags: ['autodocs'],
  argTypes: {{
{self._generate_arg_types(props)}
  }},
}};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {{
  args: {{
{self._generate_default_args(props)}
  }},
}};

export const Interactive: Story = {{
  args: {{
{self._generate_interactive_args(props)}
  }},
}};
"""

        elif component_type == "python":
            # Generate test file
            supporting_files[
                f"test_{component_name.lower()}.py"
            ] = f'''"""
Tests for {component_name} component.
"""

import pytest
from {component_name.lower()} import {component_name}


class Test{component_name}:
    """Test class for {component_name}."""

    def test_initialization(self):
        """Test {component_name} initialization."""
        component = {component_name}()
        assert component is not None

    def test_process(self):
        """Test {component_name} process method."""
        component = {component_name}()
        result = component.process()
        # Add assertions based on expected behavior
        assert result is not None or result is None  # Update as needed
'''

        return supporting_files
