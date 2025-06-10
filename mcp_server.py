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
        }

        return schemas.get(method, {})


class MCPStoryProtocolHandler:
    """Protocol handler for MCP story server integration."""

    def __init__(self, config: Optional[Config] = None):
        self.server = MCPStoryServer(config)

    async def handle_json_request(self, request_json: str) -> str:
        """Handle a JSON-formatted MCP request."""

        try:
            request_data = json.loads(request_json)

            request = MCPRequest(
                id=request_data.get("id", "unknown"),
                method=request_data.get("method", ""),
                params=request_data.get("params", {}),
            )

            response = await self.server.handle_request(request)

            return json.dumps(asdict(response), default=str)

        except json.JSONDecodeError as e:
            error_response = MCPResponse(
                id="unknown",
                error={"code": -32700, "message": f"Parse error: {str(e)}"},
            )
            return json.dumps(asdict(error_response), default=str)
        except Exception as e:
            error_response = MCPResponse(
                id="unknown",
                error={"code": -32603, "message": f"Internal error: {str(e)}"},
            )
            return json.dumps(asdict(error_response), default=str)

    async def start_stdio_server(self):
        """Start MCP server using stdio transport."""

        logger.info("Starting MCP story server on stdio...")

        import sys

        try:
            while True:
                # Read JSON-RPC request from stdin
                line = sys.stdin.readline()
                if not line:
                    break

                # Process request
                response_json = await self.handle_json_request(line.strip())

                # Write response to stdout
                sys.stdout.write(response_json + "\n")
                sys.stdout.flush()

        except KeyboardInterrupt:
            logger.info("MCP server stopped by user")
        except Exception as e:
            logger.error(f"MCP server error: {e}")

    async def start_websocket_server(self, host: str = "localhost", port: int = 8765):
        """Start MCP server using WebSocket transport."""

        try:
            import websockets
        except ImportError:
            raise ImportError("WebSocket support requires: pip install websockets")

        logger.info(f"Starting MCP story server on ws://{host}:{port}")

        async def handle_websocket(websocket, path):
            try:
                async for message in websocket:
                    response_json = await self.handle_json_request(message)
                    await websocket.send(response_json)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

        await websockets.serve(handle_websocket, host, port)
        logger.info(f"MCP server running on ws://{host}:{port}")

        # Keep server running
        await asyncio.Future()  # Run forever


# CLI command for running MCP server
async def run_mcp_server(
    transport: str = "stdio", host: str = "localhost", port: int = 8765
):
    """Run the MCP story server."""

    handler = MCPStoryProtocolHandler()

    if transport == "stdio":
        await handler.start_stdio_server()
    elif transport == "websocket":
        await handler.start_websocket_server(host, port)
    else:
        raise ValueError(f"Unsupported transport: {transport}")


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "websocket":
        asyncio.run(run_mcp_server("websocket"))
    else:
        asyncio.run(run_mcp_server("stdio"))
