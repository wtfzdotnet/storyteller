"""LLM Handler for AI Story Management System."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response from the LLM provider."""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass


class GitHubModelsProvider(LLMProvider):
    """GitHub Models LLM provider implementation."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://models.inference.ai.azure.com"
        self.default_model = "gpt-4o-mini"

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using GitHub Models API."""

        model = model or self.default_model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": model,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"GitHub Models API error: {response.status} - {error_text}"
                    )

                data = await response.json()

                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=model,
                    provider="github",
                    usage=data.get("usage"),
                    metadata={"response_data": data},
                )

    def get_default_model(self) -> str:
        return self.default_model


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.default_model = "gpt-4"

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using OpenAI API."""

        try:
            import openai
        except ImportError:
            raise ImportError(
                "OpenAI package not available. Install with: pip install openai"
            )

        model = model or self.default_model

        client = openai.AsyncOpenAI(api_key=self.api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2000),
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=model,
                provider="openai",
                usage=response.usage.__dict__ if response.usage else None,
                metadata={"response_data": response.__dict__},
            )
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")

    def get_default_model(self) -> str:
        return self.default_model


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation."""

    def __init__(self, api_host: str = "http://localhost:11434"):
        self.api_host = api_host.rstrip("/")
        self.default_model = "llama2"

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using Ollama API."""

        model = model or self.default_model

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 2000),
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_host}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Ollama API error: {response.status} - {error_text}"
                    )

                data = await response.json()

                return LLMResponse(
                    content=data["response"],
                    model=model,
                    provider="ollama",
                    metadata={"response_data": data},
                )

    def get_default_model(self) -> str:
        return self.default_model


class LLMHandler:
    """Main handler for LLM interactions."""

    def __init__(self, config: Config):
        self.config = config
        self.providers: Dict[str, LLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available LLM providers based on configuration."""

        # GitHub Models (using GitHub token)
        if self.config.github_token:
            self.providers["github"] = GitHubModelsProvider(self.config.github_token)

        # OpenAI
        if self.config.openai_api_key:
            self.providers["openai"] = OpenAIProvider(self.config.openai_api_key)

        # Ollama
        self.providers["ollama"] = OllamaProvider(self.config.ollama_api_host)

        if not self.providers:
            raise ValueError("No LLM providers available. Check your configuration.")

    def get_provider(self, provider_name: Optional[str] = None) -> LLMProvider:
        """Get an LLM provider by name or default."""

        provider_name = provider_name or self.config.default_llm_provider

        if provider_name not in self.providers:
            available = ", ".join(self.providers.keys())
            raise ValueError(
                f"Provider '{provider_name}' not available. Available: {available}"
            )

        return self.providers[provider_name]

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        retry_count: int = 0,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response with retry logic."""

        try:
            llm_provider = self.get_provider(provider)
            return await llm_provider.generate_response(
                prompt=prompt, system_prompt=system_prompt, model=model, **kwargs
            )
        except Exception as e:
            if retry_count < self.config.max_retries:
                logger.warning(f"LLM request failed (attempt {retry_count + 1}): {e}")
                await asyncio.sleep(2**retry_count)  # Exponential backoff
                return await self.generate_response(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    provider=provider,
                    model=model,
                    retry_count=retry_count + 1,
                    **kwargs,
                )
            else:
                logger.error(
                    f"LLM request failed after {self.config.max_retries} retries: {e}"
                )
                raise

    async def analyze_story_with_role(
        self,
        story_content: str,
        role_definition: str,
        role_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Analyze a story from a specific expert role perspective."""

        system_prompt = f"""You are a {role_name} expert role analyzing a user story for the Recipe Authority Platform.

Role Definition:
{role_definition}

Your task is to analyze the provided user story from your expert perspective and provide:
1. Analysis of the story from your domain expertise
2. Specific recommendations or considerations
3. Potential risks or issues you foresee
4. Suggestions for improvement or additional requirements

Be concise but thorough in your analysis. Focus on aspects most relevant to your expertise area."""

        prompt = f"""User Story to Analyze:
{story_content}"""

        if context:
            prompt += f"\n\nAdditional Context:\n{context}"

        return await self.generate_response(prompt=prompt, system_prompt=system_prompt)

    async def synthesize_expert_analyses(
        self, story_content: str, expert_analyses: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Synthesize multiple expert analyses into a comprehensive story analysis with repository context."""

        system_prompt = """You are synthesizing multiple expert analyses of a user story for the Recipe Authority Platform.

Your task is to:
1. Combine insights from all expert analyses
2. Identify common themes and concerns
3. Resolve any conflicting recommendations
4. Create a comprehensive, actionable analysis
5. Provide clear next steps and recommendations
6. Consider repository context and technical stack implications
7. Analyze cross-repository dependencies and impacts

Focus on creating a coherent, actionable synthesis that developers can use effectively.
Pay special attention to repository-specific technical details and cross-repository integration concerns."""

        analyses_text = "\n\n".join(
            [
                f"=== {analysis['role_name']} Analysis ===\n{analysis['analysis']}"
                for analysis in expert_analyses
            ]
        )

        prompt_parts = [
            f"Original User Story:\n{story_content}",
            "",
            f"Expert Analyses:\n{analyses_text}",
        ]

        # Add repository context if available
        if context and "repository_contexts" in context:
            repo_contexts = context["repository_contexts"]
            if repo_contexts:
                repo_context_text = "\n".join([
                    f"Repository: {ctx.get('repository', 'Unknown')} ({ctx.get('repo_type', 'unknown')})\n"
                    f"- Description: {ctx.get('description', 'No description')}\n"
                    f"- Key Technologies: {', '.join(ctx.get('key_technologies', [])[:5])}\n"
                    f"- Dependencies: {', '.join(ctx.get('dependencies', [])[:5])}\n"
                    f"- Important Files: {', '.join([f['path'] for f in ctx.get('important_files', [])[:3]])}"
                    for ctx in repo_contexts
                ])
                prompt_parts.extend([
                    "",
                    f"Repository Context:\n{repo_context_text}"
                ])

        # Add cross-repository insights if available
        if context and "cross_repository_insights" in context:
            insights = context["cross_repository_insights"]
            if insights:
                insights_text = "\n".join([
                    f"- Shared Technologies: {', '.join(insights.get('shared_languages', []))}",
                    f"- Common Patterns: {', '.join(insights.get('common_patterns', []))}",
                    f"- Integration Points: {', '.join(insights.get('integration_points', []))}"
                ])
                prompt_parts.extend([
                    "",
                    f"Cross-Repository Insights:\n{insights_text}"
                ])

        prompt_parts.append("\nPlease provide a comprehensive synthesis of these expert analyses, incorporating the repository context and cross-repository considerations.")

        prompt = "\n".join(prompt_parts)
        return await self.generate_response(prompt=prompt, system_prompt=system_prompt)
