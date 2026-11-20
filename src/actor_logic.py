"""Pure speaker and interruption rules for the dialogue loop."""

from __future__ import annotations

from typing import Dict, List, Optional

try:
    from .states import AgentConfig, InterruptCondition, InterruptEvent
except ImportError:
    from states import AgentConfig, InterruptCondition, InterruptEvent


def format_conversation(conversation: List[Dict[str, str]], max_lines: int = 10) -> str:
    if not conversation:
        return "(no dialogue yet)"
    recent = conversation[-max_lines:]
    return "\n".join(f"{item['agent']}: {item['line']}" for item in recent)


def get_agent_map(agents: List[AgentConfig]) -> Dict[str, AgentConfig]:
    return {agent["name"].upper(): agent for agent in agents}


def normalize_condition(condition: InterruptCondition) -> InterruptCondition:
    normalized = dict(condition)
    condition_type = normalized.get("type")
    if not condition_type:
        if normalized.get("after_turn") is not None:
            condition_type = "after_n_turns"
        elif normalized.get("keyword"):
            condition_type = "on_keyword"
        else:
            condition_type = "after_n_turns"
    normalized["type"] = condition_type
    return normalized


def find_interrupt(
    conditions: List[InterruptCondition],
    current_turn: int,
    last_line: Optional[str],
    interrupt_log: Optional[List[InterruptEvent]] = None,
) -> Optional[InterruptCondition]:
    for condition in conditions:
        normalized = normalize_condition(condition)
        condition_type = normalized.get("type", "")
        if any(
            item.get("type") == condition_type
            and item.get("agent_name", "").upper() == normalized.get("agent_name", "").upper()
            and item.get("keyword") == normalized.get("keyword")
            and item.get("after_turn") == normalized.get("after_turn")
            and item.get("reason") == normalized.get("reason")
            for item in interrupt_log or []
        ):
            continue
        if condition_type == "after_n_turns" and normalized.get("after_turn") == current_turn:
            return normalized
        if condition_type == "on_keyword":
            keyword = normalized.get("keyword")
            if keyword and last_line and keyword.lower() in last_line.lower():
                return normalized
    return None


def select_speaker(plan: dict, current_turn: int, interrupt: Optional[InterruptCondition]) -> str:
    if interrupt:
        return interrupt.get("agent_name", "").upper()
    turn_order = plan.get("turn_order", [])
    if not turn_order:
        return ""
    return turn_order[current_turn % len(turn_order)].upper()


def build_interrupt_note(interrupt: Optional[InterruptCondition]) -> str:
    if not interrupt:
        return ""
    reason = interrupt.get("reason", "")
    keyword = interrupt.get("keyword")
    if keyword:
        return f"INTERRUPT NOTE: This is an on_keyword cut-in triggered by '{keyword}'. Reason: {reason}\n"
    return f"INTERRUPT NOTE: This is an after_n_turns cut-in. Reason: {reason}\n"


def build_interrupt_event(turn: int, interrupt: InterruptCondition, speaker: str) -> InterruptEvent:
    return {
        "turn": turn,
        "agent_name": speaker,
        "type": interrupt.get("type", "after_n_turns"),
        "reason": interrupt.get("reason", ""),
        "keyword": interrupt.get("keyword"),
        "after_turn": interrupt.get("after_turn"),
    }
