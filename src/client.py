"""Groq client wrapper with lazy singleton initialization."""

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

try:
    from .model_config import DEFAULT_GROQ_MODEL, groq_completion_options
except ImportError:
    from model_config import DEFAULT_GROQ_MODEL, groq_completion_options

class GroqClient:
    """Singleton facade around AsyncGroq with shared configuration."""
    _instance: "GroqClient | None" = None

    DEFAULT_MODEL = DEFAULT_GROQ_MODEL

    def __new__(cls) -> "GroqClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """Initialize the underlying Groq client using the API key."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not found in environment / .env")
        try:
            from groq import AsyncGroq
        except ImportError as exc:
            raise RuntimeError("Install the optional workflow dependencies to use Groq.") from exc
        self._client = AsyncGroq(api_key=api_key)

    @staticmethod
    def _content(response) -> str:
        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError("Groq returned an unreadable response.") from exc
        if not isinstance(content, str) or not content.strip():
            if getattr(choice, "finish_reason", None) == "length":
                raise RuntimeError(
                    "Groq used the completion token budget before returning visible text. "
                    "Increase max_completion_tokens or lower reasoning effort."
                )
            raise RuntimeError("Groq returned an empty response.")
        return content.strip()

    async def generate(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 1.0,
        max_completion_tokens: int = 512,
        reasoning_effort: str | None = None,
    ) -> str:
        """Generate a single completion from a plain user prompt."""
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            **groq_completion_options(model, max_completion_tokens, reasoning_effort),
        )
        return self._content(response)

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 1.0,
        max_completion_tokens: int = 1024,
        reasoning_effort: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        """Generate a completion from an explicit message list."""
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            **groq_completion_options(
                model,
                max_completion_tokens,
                reasoning_effort,
                response_format,
            ),
        )
        return self._content(response)


def get_client() -> GroqClient:
    """Return the shared GroqClient instance."""
    return GroqClient()
