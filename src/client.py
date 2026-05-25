import os
from pathlib import Path
from groq import AsyncGroq
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


class GroqClient:
    _instance: "GroqClient | None" = None

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __new__(cls) -> "GroqClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
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
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


def get_client() -> GroqClient:
    return GroqClient()