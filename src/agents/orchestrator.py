"""
Orchestrator node:
  • Model:  deepseek-r1-distill-llama-70b  (reasoning model)
  • Job:    Deep-reason about the topic, output a structured JSON plan.
  • Strips <think>…</think> from the response before parsing.
  • Streams 'status' and 'plan' chunks via get_stream_writer().
  • Returns updated state fields; does NOT call interrupt() — that lives in
    the separate plan_approval node so the LLM call is never repeated on resume.
"""

from __future__ import annotations

import json
import re

from langgraph.config import get_stream_writer

from ..client import GroqClient
from ..prompts import ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER
from ..states import AgentGraphState

# Model used for deep reasoning
REASONING_MODEL = "deepseek-r1-distill-llama-70b"


def _strip_think_tags(text: str) -> str:
    """Remove <think>…</think> reasoning blocks emitted by deepseek-r1."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json(text: str) -> dict:
    """
    Try (in order):
      1. ```json … ``` fenced block
      2. First top-level { … } object
    Raises ValueError with context on failure.
    """
    # 1. fenced block
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))

    # 2. raw JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))

    raise ValueError(f"No JSON found in orchestrator response:\n{text[:600]}")


def orchestrator_node(state: AgentGraphState) -> dict:
    """LangGraph node: generate the production plan."""
    writer = get_stream_writer()
    client = GroqClient()

    writer({"type": "status", "data": "🎬  Orchestrator is reasoning about your scene…"})

    response = client.chat.completions.create(
        model=REASONING_MODEL,
        messages=[
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {
                "role": "user",
                "content": ORCHESTRATOR_USER.format(topic=state["topic"]),
            },
        ],
        temperature=0.6,
        max_tokens=2048,
    )

    raw: str = response.choices[0].message.content or ""
    cleaned = _strip_think_tags(raw)

    try:
        plan = _extract_json(cleaned)
    except (ValueError, json.JSONDecodeError) as exc:
        # Emit the raw text so the user can debug, then re-raise
        writer({"type": "error", "data": f"Orchestrator JSON parse failed: {exc}"})
        raise

    # Emit the plan for the harness to display / for the human gate
    writer({"type": "plan", "data": plan})
    writer({"type": "status", "data": "✅  Plan generated — awaiting your approval."})

    return {
        "plan": plan,
        "agents_list": plan.get("agents", []),
        "conversation": [],
        "current_turn": 0,
        "plan_approved": False,
        "final_script": None,
    }