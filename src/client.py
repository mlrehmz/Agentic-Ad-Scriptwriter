"""Groq client wrapper with lazy singleton initialization."""

import os
from pathlib import Path

from dotenv import load_dotenv
from groq import AsyncGroq

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


class GroqClient:
    """Singleton facade around AsyncGroq with shared configuration."""
    _instance: "GroqClient | None" = None

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

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
        self._client = AsyncGroq(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 1.0,
        max_tokens: int = 512,
    ) -> str:
        """Generate a single completion from a plain user prompt."""
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 1.0,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a completion from an explicit message list."""
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


def get_client() -> GroqClient:
    """Return the shared GroqClient instance."""
    return GroqClient()