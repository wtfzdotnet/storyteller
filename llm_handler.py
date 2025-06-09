import abc
import enum
import json
import logging
import os  # Added for explicit getenv for safety, though config should handle it.

import aiohttp
import ollama
import openai

from config import DEFAULT_LLM_PROVIDER, GITHUB_TOKEN, OLLAMA_API_HOST, OPENAI_API_KEY

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class LLMProvider(enum.Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    GITHUB = "github"


class BaseLLMConnector(abc.ABC):
    @abc.abstractmethod
    async def get_response(self, prompt: str, model: str = None) -> str:
        """
        Abstract method to get a response from an LLM.

        Args:
            prompt: The input prompt for the LLM.
            model: The specific model to use (optional).

        Returns:
            The LLM's response as a string.
        """
        pass


class OpenAILLMConnector(BaseLLMConnector):
    def __init__(self, api_key: str, default_model: str = "gpt-3.5-turbo"):
        if not api_key:
            logging.error("OpenAI API key is required.")
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.default_model = default_model
        logging.info(f"OpenAILLMConnector initialized with model: {self.default_model}")

    async def get_response(self, prompt: str, model: str = None) -> str:
        current_model = model if model else self.default_model
        try:
            logging.info(
                f"Sending prompt to OpenAI model {current_model}: '{prompt[:50]}...'"
            )
            response = await self.client.chat.completions.create(
                model=current_model, messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content
            if content is None:
                logging.warning("OpenAI response content is None.")
                return ""
            logging.info(f"Received response from OpenAI model {current_model}.")
            return content.strip()
        except openai.APIError as e:
            logging.error(f"OpenAI API error: {e}")
            raise  # Re-raise the exception to be handled by the caller
        except Exception as e:
            logging.error(f"An unexpected error occurred with OpenAI: {e}")
            raise


class OllamaLLMConnector(BaseLLMConnector):
    def __init__(self, host_url: str, default_model: str = "llama3"):
        if not host_url:
            logging.error("Ollama host URL is required.")
            raise ValueError("Ollama host URL is required.")
        self.client = ollama.AsyncClient(host=host_url)
        self.default_model = default_model
        logging.info(
            f"OllamaLLMConnector initialized with host: {host_url}, model: {self.default_model}"
        )

    async def get_response(self, prompt: str, model: str = None) -> str:
        current_model = model if model else self.default_model
        try:
            logging.info(
                f"Sending prompt to Ollama model {current_model} at {self.client._host}: '{prompt[:50]}...'"
            )

            # Check model existence (basic check, actual availability depends on Ollama server)
            # This is a synchronous call, ideally should be async or handled differently
            # For now, keeping it simple. A more robust check would be an async API call if available.
            # models_info = ollama.list(client=self.client) # ollama.list is sync
            # if not any(m['name'].startswith(current_model) for m in models_info['models']):
            #     logging.error(f"Ollama model '{current_model}' not found on the server.")
            #     raise ValueError(f"Ollama model '{current_model}' not found on the server.")

            response = await self.client.chat(
                model=current_model, messages=[{"role": "user", "content": prompt}]
            )
            content = response["message"]["content"]
            logging.info(f"Received response from Ollama model {current_model}.")
            return content.strip()
        except ollama.ResponseError as e:  # ollama.py library specific errors
            logging.error(
                f"Ollama API response error (model: {current_model}, host: {self.client._host}): {e.error}"
            )
            if (
                "model not found" in e.error.lower()
            ):  # Check if this is how model not found is reported
                logging.error(
                    f"Ensure the model '{current_model}' is pulled and available on the Ollama server at {self.client._host}."
                )
            raise ValueError(f"Ollama API error: {e.error}") from e
        except Exception as e:  # Catch other potential errors like connection errors
            logging.error(
                f"An unexpected error occurred with Ollama (model: {current_model}, host: {self.client._host}): {e}"
            )
            raise


class GitHubLLMConnector(BaseLLMConnector):
    def __init__(
        self,
        github_token: str,
        default_model: str = "gpt-4o-mini",
        github_repository: str = None,
    ):
        if not github_token:
            logging.error("GitHub token is required for GitHub models API.")
            raise ValueError("GitHub token is required for GitHub models API.")
        self.github_token = github_token
        self.default_model = default_model
        # GitHub models API endpoint - using the standard OpenAI-compatible endpoint
        # This endpoint is commonly used for GitHub's AI models service
        self.base_url = "https://models.inference.ai.azure.com"
        self.github_repository = github_repository or os.environ.get(
            "GITHUB_REPOSITORY"
        )
        logging.info(f"GitHubLLMConnector initialized with model: {self.default_model}")
        if self.github_repository:
            logging.info(f"GitHub repository context enabled: {self.github_repository}")

    async def get_response(
        self, prompt: str, model: str = None, repository_references: list = None
    ) -> str:
        current_model = model if model else self.default_model

        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Content-Type": "application/json",
        }

        messages = [{"role": "user", "content": prompt}]

        # If repository references are provided, use GitHub repository-based prompt feature
        if repository_references and self.github_repository:
            repository_context = self._format_repository_context(repository_references)
            # Replace standard message with repository context message
            messages = [
                {
                    "role": "system",
                    "content": f"You are a specialized expert team working on a recipe management application. Use the context in this repository to provide expert guidance.\n\nRepository: {self.github_repository}\nReference: {repository_context}\n\nQuestion: {prompt}",
                }
            ]
            logging.info(
                f"Using repository-based prompt with references: {repository_context}"
            )

        payload = {
            "messages": messages,
            "model": current_model,
            "temperature": 0.7,
            "max_tokens": 4000,
        }

        try:
            logging.info(
                f"Sending prompt to GitHub model {current_model}: '{prompt[:50]}...'"
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = (
                            result.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        if not content:
                            logging.warning(
                                "GitHub models API response content is empty."
                            )
                            return ""
                        logging.info(
                            f"Received response from GitHub model {current_model}."
                        )
                        return content.strip()
                    else:
                        error_text = await response.text()
                        logging.error(
                            f"GitHub models API error {response.status}: {error_text}"
                        )
                        raise ValueError(
                            f"GitHub models API error {response.status}: {error_text}"
                        )
        except aiohttp.ClientError as e:
            logging.error(f"GitHub models API connection error: {e}")
            raise ValueError(f"GitHub models API connection error: {e}") from e
        except Exception as e:
            logging.error(f"An unexpected error occurred with GitHub models API: {e}")
            raise

    def _format_repository_context(self, repository_references):
        """Format repository references for GitHub Models API"""
        if isinstance(repository_references, list):
            return ", ".join(repository_references)
        return str(repository_references)


class LLMService:
    def __init__(
        self,
        provider_name: str = None,
        openai_api_key: str = None,
        ollama_host: str = None,
        github_token: str = None,
        github_repository: str = None,
    ):

        self.provider_name = (provider_name or DEFAULT_LLM_PROVIDER).lower()
        self.connector: BaseLLMConnector = None  # Type hint
        self.github_repository = github_repository or os.environ.get(
            "GITHUB_REPOSITORY"
        )

        logging.info(
            f"Initializing LLMService with effective provider: {self.provider_name}"
        )

        if self.provider_name == LLMProvider.OPENAI.value:
            key = openai_api_key or OPENAI_API_KEY
            if not key:
                logging.error(
                    "OpenAI provider selected, but API key is not configured."
                )
                raise ValueError("OpenAI API key is required for the OpenAI provider.")
            self.connector = OpenAILLMConnector(api_key=key)
            logging.info("Using OpenAI LLM Connector.")
        elif self.provider_name == LLMProvider.OLLAMA.value:
            host = ollama_host or OLLAMA_API_HOST
            if not host:  # Should be caught by default in config, but check again
                logging.error(
                    "Ollama provider selected, but host URL is not configured."
                )
                raise ValueError("Ollama host URL is required for the Ollama provider.")
            self.connector = OllamaLLMConnector(host_url=host)
            logging.info(f"Using Ollama LLM Connector with host: {host}")
        elif self.provider_name == LLMProvider.GITHUB.value:
            token = github_token or GITHUB_TOKEN
            if not token:
                logging.error(
                    "GitHub provider selected, but GitHub token is not configured."
                )
                raise ValueError("GitHub token is required for the GitHub provider.")
            self.connector = GitHubLLMConnector(
                github_token=token, github_repository=self.github_repository
            )
            logging.info("Using GitHub LLM Connector.")
            if self.github_repository:
                logging.info(
                    f"GitHub repository context enabled: {self.github_repository}"
                )
        else:
            logging.error(f"Unsupported LLM provider: {self.provider_name}")
            raise ValueError(
                f"Unsupported LLM provider: {self.provider_name}. Choose from 'openai', 'ollama', or 'github'."
            )

    async def query_llm(
        self, prompt: str, model: str = None, repository_references: list = None
    ) -> str:
        """
        Queries the configured LLM with the given prompt.

        Args:
            prompt: The input prompt for the LLM.
            model: The specific model to use (optional, overrides connector's default).
            repository_references: List of repository file paths to reference (for GitHub Models).

        Returns:
            The LLM's response as a string.
        """
        if not self.connector:
            logging.error("LLM connector not initialized.")
            # This state should ideally not be reached if constructor logic is sound.
            raise RuntimeError(
                "LLMService was not properly initialized with a connector."
            )

        logging.debug(
            f"LLMService querying connector with prompt: '{prompt[:50]}...' and model: {model}"
        )
        try:
            # Use repository references only with GitHub connector
            if self.provider_name == LLMProvider.GITHUB.value and repository_references:
                return await self.connector.get_response(
                    prompt, model=model, repository_references=repository_references
                )
            else:
                return await self.connector.get_response(prompt, model=model)
        except Exception as e:
            logging.error(f"LLMService failed to get response from connector: {e}")
            # Depending on desired behavior, could return a default error message or None
            # For now, re-raising to make the caller aware of the issue.
            raise


# Example usage (for testing purposes, typically you'd call this from another module)
async def main_test():
    # This is a basic test function.
    # Ensure you have environment variables set for this to work,
    # e.g., in a .env file or directly in your environment.
    # Create a .env file in the root of the project (where you run the script from)
    # Example .env:
    # OPENAI_API_KEY="your_openai_key"
    # GITHUB_TOKEN="your_github_token" # Not used here, but for config
    # GITHUB_REPOSITORY="owner/repo" # Not used here, but for config
    # DEFAULT_LLM_PROVIDER="openai" # or "ollama"
    # OLLAMA_API_HOST="http://localhost:11434" # if using ollama

    # To run this test, you might need to adjust your PYTHONPATH or run it as a module
    # e.g., python -m ai.ai_core.llm_handler

    print("Starting LLM Handler Test...")

    # Test with default provider from config
    try:
        print(f"\n--- Testing with DEFAULT_LLM_PROVIDER ({DEFAULT_LLM_PROVIDER}) ---")
        llm_service_default = LLMService()
        # Ollama specific: ensure you have a model like 'llama3' pulled: `ollama pull llama3`
        # OpenAI specific: ensure your API key is valid and has credits.
        # GitHub specific: uses GitHub models API
        if DEFAULT_LLM_PROVIDER == "ollama":
            test_model_default = "llama3"
        elif DEFAULT_LLM_PROVIDER == "github":
            test_model_default = "gpt-4o-mini"
        else:  # openai
            test_model_default = "gpt-3.5-turbo"
        response_default = await llm_service_default.query_llm(
            f"Hello from the default provider! Tell me a fun fact about {DEFAULT_LLM_PROVIDER}.",
            model=test_model_default,
        )
        print(f"Response from {DEFAULT_LLM_PROVIDER}: {response_default}")
    except Exception as e:
        print(f"Error testing default provider ({DEFAULT_LLM_PROVIDER}): {e}")

    # Test OpenAI explicitly (if key is available)
    if OPENAI_API_KEY:
        try:
            print("\n--- Testing with OpenAI Provider Explicitly ---")
            llm_service_openai = LLMService(
                provider_name="openai", openai_api_key=OPENAI_API_KEY
            )
            response_openai = await llm_service_openai.query_llm(
                "Hello from OpenAI! What is 2+2?", model="gpt-3.5-turbo"
            )
            print(f"Response from OpenAI: {response_openai}")
        except Exception as e:
            print(f"Error testing OpenAI provider: {e}")
    else:
        print("\nSkipping explicit OpenAI test as OPENAI_API_KEY is not set.")

    # Test Ollama explicitly (if host is available and server is running)
    # Ensure Ollama server is running: `ollama serve`
    # Ensure a model is pulled: `ollama pull llama3` (or other model like 'mistral')
    if (
        OLLAMA_API_HOST
    ):  # Assuming OLLAMA_API_HOST is set, e.g. to http://localhost:11434
        try:
            print("\n--- Testing with Ollama Provider Explicitly ---")
            # You might need to specify a model that you have downloaded for Ollama, e.g., "llama3" or "mistral"
            llm_service_ollama = LLMService(
                provider_name="ollama", ollama_host=OLLAMA_API_HOST
            )
            response_ollama = await llm_service_ollama.query_llm(
                "Hello from Ollama! Why is the sky blue?", model="llama3"
            )  # or "mistral"
            print(f"Response from Ollama (llama3): {response_ollama}")
        except Exception as e:
            # More specific error message if Ollama server is not reachable
            if "Connection refused" in str(e) or (
                hasattr(e, "error") and "dial tcp" in str(e.error)
            ):
                print(
                    f"Error testing Ollama provider: Could not connect to Ollama server at {OLLAMA_API_HOST}. Ensure Ollama is running."
                )
            elif "model not found" in str(e).lower():
                print(
                    f"Error testing Ollama provider: Model not found. Ensure you have pulled the model (e.g., `ollama pull llama3`). Details: {e}"
                )
            else:
                print(f"Error testing Ollama provider: {e}")
    else:
        print(
            "\nSkipping explicit Ollama test as OLLAMA_API_HOST is not configured in .env or environment."
        )

    # Test GitHub explicitly (if token is available)
    if GITHUB_TOKEN:
        try:
            print("\n--- Testing with GitHub Provider Explicitly ---")
            llm_service_github = LLMService(
                provider_name="github", github_token=GITHUB_TOKEN
            )
            response_github = await llm_service_github.query_llm(
                "Hello from GitHub! What is the capital of France?", model="gpt-4o-mini"
            )
            print(f"Response from GitHub: {response_github}")
        except Exception as e:
            print(f"Error testing GitHub provider: {e}")
    else:
        print("\nSkipping explicit GitHub test as GITHUB_TOKEN is not set.")


if __name__ == "__main__":
    # This allows running the test function directly if the script is executed.
    # For this to work, you need to be in the directory above 'ai' and run as 'python -m ai.ai_core.llm_handler'
    # or adjust PYTHONPATH.
    import asyncio

    # Note: load_dotenv() from config.py should have been called when llm_handler is imported.
    # If running this script directly in a way that config.py isn't processed first by an import,
    # you might need to call load_dotenv() here too.
    # from dotenv import load_dotenv
    # load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env')) # if .env is in ai/
    # Assuming .env is in the project root, and this script is run from project root as module
    from dotenv import load_dotenv

    # Adjust path to .env if necessary, assuming .env is in the project root (two levels up from this file)
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        print(f"Loaded .env file from: {dotenv_path}")
    else:
        print(
            f".env file not found at {dotenv_path}, relying on environment variables."
        )

    asyncio.run(main_test())
