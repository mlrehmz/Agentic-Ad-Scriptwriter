"""
Orchestrator node:
    • Model:  configured in src/model_config.py
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
from langgraph.types import interrupt

# Allow running as a script (no package context) or as a module.
try:
    from ..client import get_client
    from ..prompts import ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER
    from ..states import AgentGraphState
    from ..model_config import GROQ_ORCHESTRATOR_MODEL
    from ..plan_validation import validate_plan
except ImportError:
    from client import get_client
    from prompts import ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER
    from states import AgentGraphState
    from model_config import GROQ_ORCHESTRATOR_MODEL
    from plan_validation import validate_plan

# Model used for deep reasoning
REASONING_MODEL = GROQ_ORCHESTRATOR_MODEL


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


async def orchestrator_node(state: AgentGraphState) -> dict:
    """LangGraph node: generate the production plan."""
    writer = get_stream_writer()
    client = get_client()

    writer({"type": "status", "data": "🎬  Orchestrator is reasoning about your scene…"})

    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM},
        {
            "role": "user",
            "content": ORCHESTRATOR_USER.format(topic=state["topic"]),
        },
    ]
    plan = None
    last_error = None
    for _ in range(2):
        request_options = {
            "model": REASONING_MODEL,
            "temperature": 0.6,
            "max_completion_tokens": 4096,
            "reasoning_effort": "medium",
        }
        if REASONING_MODEL.startswith("openai/gpt-oss-"):
            request_options["response_format"] = {"type": "json_object"}
        raw = await client.chat(messages, **request_options)
        try:
            plan = validate_plan(_extract_json(_strip_think_tags(raw)))
            break
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            messages = [
                {"role": "system", "content": ORCHESTRATOR_SYSTEM},
                {"role": "user", "content": ORCHESTRATOR_USER.format(topic=state["topic"])},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"Repair this plan as valid JSON matching the required schema. Validation error: {exc}"},
            ]
    if plan is None:
        writer({"type": "error", "data": f"The plan could not be validated after one repair: {last_error}"})
        raise ValueError("The generated plan is invalid. Please try again.") from last_error

    # Emit the plan for the harness to display / for the human gate
    writer({"type": "plan", "data": plan})
    writer({"type": "status", "data": "✅  Plan generated."})

    return {
        "plan": plan,
        "agents_list": plan.get("agents", []),
        "conversation": [],
        "current_turn": 0,
        "current_speaker": None,
        "interrupt_log": [],
        "plan_approved": False,
        "final_script": None,
    }


def plan_approval_node(state: AgentGraphState) -> dict:
    """LangGraph node: optional human approval before actors start."""
    writer = get_stream_writer()
    writer({"type": "status", "data": "⏸️  Awaiting plan approval."})

    approval = interrupt(
        {
            "prompt": "Approve the production plan? (y/n)",
            "plan": state.get("plan"),
        }
    )
    approved = str(approval).strip().lower() in {"y", "yes", "ok", "approve", "approved"}
    writer({"type": "status", "data": "✅  Plan approved." if approved else "❌  Plan rejected."})

    return {"plan_approved": approved}
