"""Central model IDs for the optional Groq workflow."""

import os
from typing import Any

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_STUDIO_MODEL = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
GROQ_ORCHESTRATOR_MODEL = os.getenv("GROQ_ORCHESTRATOR_MODEL", "openai/gpt-oss-120b")
GROQ_ACTOR_MODEL = os.getenv("GROQ_ACTOR_MODEL", GROQ_STUDIO_MODEL)
GROQ_CRITIC_MODEL = os.getenv("GROQ_CRITIC_MODEL", "openai/gpt-oss-120b")


def groq_completion_options(
    model: str,
    max_completion_tokens: int,
    reasoning_effort: str | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Groq options shared by the Studio and graph clients."""
    options: dict[str, Any] = {"max_completion_tokens": max_completion_tokens}
    if model.startswith("openai/gpt-oss-"):
        options["reasoning_effort"] = reasoning_effort or "low"
        options["include_reasoning"] = False
    if response_format is not None:
        options["response_format"] = response_format
    return options
