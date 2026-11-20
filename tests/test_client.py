import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.client import GroqClient
from src.model_config import DEFAULT_GROQ_MODEL


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = object.__new__(GroqClient)
        self.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="A short answer."))]
        ))
        self.client._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
        )

    async def test_generate_uses_provider_boundary_without_network(self):
        result = await self.client.generate("Say hello", model="test-model")
        self.assertEqual(result, "A short answer.")
        self.create.assert_awaited_once()
        self.assertEqual(self.create.await_args.kwargs["model"], "test-model")

    async def test_chat_preserves_messages(self):
        messages = [{"role": "user", "content": "Write one line"}]
        await self.client.chat(messages)
        self.assertEqual(self.create.await_args.kwargs["messages"], messages)

    async def test_chat_uses_groq_completion_and_reasoning_options(self):
        await self.client.chat(
            [{"role": "user", "content": "Write one line"}],
            model="openai/gpt-oss-20b",
            max_completion_tokens=768,
            reasoning_effort="low",
            response_format={"type": "json_object"},
        )
        kwargs = self.create.await_args.kwargs
        self.assertEqual(kwargs["max_completion_tokens"], 768)
        self.assertEqual(kwargs["reasoning_effort"], "low")
        self.assertIs(kwargs["include_reasoning"], False)
        self.assertNotIn("reasoning_format", kwargs)
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})
        self.assertNotIn("max_tokens", kwargs)

    async def test_empty_provider_content_is_actionable(self):
        self.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        )
        with self.assertRaisesRegex(RuntimeError, "empty response"):
            await self.client.chat([{"role": "user", "content": "Write"}])

    async def test_truncated_provider_content_explains_the_token_limit(self):
        self.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=""),
                    finish_reason="length",
                )
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "token budget"):
            await self.client.chat([{"role": "user", "content": "Write"}])

    def test_default_model_is_configured_and_not_retired(self):
        self.assertEqual(GroqClient.DEFAULT_MODEL, DEFAULT_GROQ_MODEL)
        self.assertNotIn("llama-3.3-70b-versatile", DEFAULT_GROQ_MODEL)
        self.assertNotIn("llama-3.1-8b-instant", DEFAULT_GROQ_MODEL)


if __name__ == "__main__":
    unittest.main()
