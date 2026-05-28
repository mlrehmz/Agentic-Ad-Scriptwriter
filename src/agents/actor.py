"""
Actor node:
  • Model: llama-3.1-8b-instant
  • Job: Sequential dialogue turns based on the orchestrator plan.
  • Handles logic-based interrupts (after_n_turns, on_keyword).
  • Streams each line via get_stream_writer().
"""

from __future__ import annotations

from typing import Dict, List, Optional

from langgraph.config import get_stream_writer

# Allow running as a script (no package context) or as a module.
try:
    from ..client import get_client
    from ..prompts import ACTOR_SYSTEM, ACTOR_USER
    from ..states import AgentConfig, AgentGraphState, InterruptCondition, InterruptEvent
except ImportError:
    from client import get_client
    from prompts import ACTOR_SYSTEM, ACTOR_USER
    from states import AgentConfig, AgentGraphState, InterruptCondition, InterruptEvent

ACTOR_MODEL = "llama-3.1-8b-instant"


def _format_conversation(conversation: List[Dict[str, str]], max_lines: int = 10) -> str:
    """Format the most recent dialogue lines for prompt context."""
    if not conversation:
        return "(no dialogue yet)"
    recent = conversation[-max_lines:]
    return "\n".join(f"{item['agent']}: {item['line']}" for item in recent)


def _get_agent_map(agents: List[AgentConfig]) -> Dict[str, AgentConfig]:
    """Build a case-insensitive lookup for agent configs by name."""
    return {agent["name"].upper(): agent for agent in agents}


def _normalize_condition(condition: InterruptCondition) -> InterruptCondition:
    """Ensure each interrupt condition has a concrete type set."""
    condition_type = condition.get("type")
    if not condition_type:
        if condition.get("after_turn") is not None:
            condition_type = "after_n_turns"
        elif condition.get("keyword"):
            condition_type = "on_keyword"
        else:
            condition_type = "after_n_turns"
    condition["type"] = condition_type
    return condition


def _find_interrupt(
    conditions: List[InterruptCondition],
    current_turn: int,
    last_line: Optional[str],
) -> Optional[InterruptCondition]:
    """Return the first interrupt rule that matches the current state."""
    if not conditions:
        return None

    for condition in conditions:
        normalized = _normalize_condition(condition)
        condition_type = normalized.get("type", "")
        if condition_type == "after_n_turns":
            if normalized.get("after_turn") == current_turn:
                return normalized
        elif condition_type == "on_keyword":
            keyword = normalized.get("keyword")
            if keyword and last_line and keyword.lower() in last_line.lower():
                return normalized

    return None


def _select_speaker(plan: dict, current_turn: int, interrupt: Optional[InterruptCondition]) -> str:
    """Pick the speaker for this turn, honoring any interrupt override."""
    if interrupt:
        return interrupt.get("agent_name", "").upper()

    turn_order = plan.get("turn_order", [])
    if not turn_order:
        return ""
    return turn_order[current_turn % len(turn_order)].upper()


def _build_interrupt_note(interrupt: Optional[InterruptCondition]) -> str:
    """Create a short, prompt-friendly note describing the interrupt."""
    if not interrupt:
        return ""
    reason = interrupt.get("reason", "")
    keyword = interrupt.get("keyword")
    if keyword:
        return f"INTERRUPT NOTE: This is an on_keyword cut-in triggered by '{keyword}'. Reason: {reason}\n"
    return f"INTERRUPT NOTE: This is an after_n_turns cut-in. Reason: {reason}\n"


def _build_interrupt_event(
    turn: int, interrupt: InterruptCondition, speaker: str
) -> InterruptEvent:
    """Capture an interrupt firing for later critic context."""
    return {
        "turn": turn,
        "agent_name": speaker,
        "type": interrupt.get("type", "after_n_turns"),
        "reason": interrupt.get("reason", ""),
        "keyword": interrupt.get("keyword"),
    }


async def actor_node(state: AgentGraphState) -> dict:
    """LangGraph node: generate the next line of dialogue."""
    writer = get_stream_writer()
    client = get_client()

    plan = state.get("plan")
    if not plan:
        writer({"type": "error", "data": "Actor node missing plan; skipping."})
        return {}

    conversation = list(state.get("conversation", []))
    current_turn = int(state.get("current_turn", 0))
    agents_list = state.get("agents_list", [])
    agent_map = _get_agent_map(agents_list)

    last_line = conversation[-1]["line"] if conversation else None
    interrupt_conditions = plan.get("interrupt_conditions") or []
    interrupt = _find_interrupt(interrupt_conditions, current_turn, last_line)
    speaker = _select_speaker(plan, current_turn, interrupt)

    if not speaker:
        writer({"type": "error", "data": "No speaker resolved for this turn; skipping."})
        return {}

    agent = agent_map.get(speaker) or agent_map.get(speaker.upper())
    if not agent:
        writer({"type": "error", "data": f"Agent '{speaker}' not found; skipping."})
        return {}

    interrupt_note = _build_interrupt_note(interrupt)
    conversation_so_far = _format_conversation(conversation)

    system_prompt = ACTOR_SYSTEM.format(
        name=agent["name"],
        role=agent["role"],
        genre=plan.get("genre", ""),
        script_style=plan.get("script_style", ""),
        persona=agent["persona"],
        scene_description=plan.get("scene_description", ""),
    )
    user_prompt = ACTOR_USER.format(
        conversation_so_far=conversation_so_far,
        interrupt_note=interrupt_note,
        speaker_name=agent["name"],
    )

    line = await client.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=ACTOR_MODEL,
        temperature=float(agent.get("temperature", 0.8)),
        max_tokens=256,
    )

    cleaned_line = (line or "").strip()
    new_line = {"agent": agent["name"], "line": cleaned_line}

    interrupt_event = None
    if interrupt:
        interrupt_event = _build_interrupt_event(current_turn, interrupt, agent["name"])

    writer(
        {
            "type": "line",
            "data": {
                "turn": current_turn,
                "speaker": agent["name"],
                "text": cleaned_line,
                "interrupt": bool(interrupt),
            },
        }
    )

    return {
        "conversation": [new_line],
        "current_turn": current_turn + 1,
        "current_speaker": agent["name"],
        "interrupt_log": [interrupt_event] if interrupt_event else [],
    }
