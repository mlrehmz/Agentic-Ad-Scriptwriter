"""
Critic node:
    • Model: llama-3.3-70b-versatile
  • Job: Refine raw dialogue into a structured, production-ready script.
  • Streams the final script via get_stream_writer().
"""

from __future__ import annotations

from typing import List

from langgraph.config import get_stream_writer

# Allow running as a script (no package context) or as a module.
try:
    from ..client import get_client
    from ..prompts import CRITIC_SYSTEM, CRITIC_USER
    from ..states import AgentGraphState, InterruptEvent
except ImportError:
    from client import get_client
    from prompts import CRITIC_SYSTEM, CRITIC_USER
    from states import AgentGraphState, InterruptEvent

CRITIC_MODEL = "llama-3.3-70b-versatile"


def _format_conversation(conversation: List[dict[str, str]]) -> str:
    """Flatten the conversation into a readable, line-by-line transcript."""
    if not conversation:
        return "(no dialogue)"
    return "\n".join(f"{item['agent']}: {item['line']}" for item in conversation)


def _format_interrupts(interrupt_log: List[InterruptEvent]) -> str:
    """Summarize interrupt events for the critic prompt."""
    if not interrupt_log:
        return "None"
    lines = []
    for item in interrupt_log:
        if item.get("keyword"):
            lines.append(
                f"Turn {item['turn']}: {item['agent_name']} interrupted on keyword '{item['keyword']}' — {item['reason']}"
            )
        else:
            lines.append(
                f"Turn {item['turn']}: {item['agent_name']} interrupted after_n_turns — {item['reason']}"
            )
    return "\n".join(lines)


async def critic_node(state: AgentGraphState) -> dict:
    """LangGraph node: refine the scene into a polished script."""
    writer = get_stream_writer()
    client = get_client()

    plan = state.get("plan") or {}
    conversation = state.get("conversation", [])
    interrupt_log = state.get("interrupt_log", [])

    prompt = CRITIC_USER.format(
        topic=state.get("topic", ""),
        scene_description=plan.get("scene_description", ""),
        genre=plan.get("genre", ""),
        script_style=plan.get("script_style", ""),
        interrupt_notes=_format_interrupts(interrupt_log),
        conversation=_format_conversation(conversation),
    )

    refined = await client.chat(
        [
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        model=CRITIC_MODEL,
        temperature=0.4,
        max_tokens=2048,
    )

    final_script = (refined or "").strip()
    writer({"type": "critic", "data": final_script})

    return {"final_script": final_script}
