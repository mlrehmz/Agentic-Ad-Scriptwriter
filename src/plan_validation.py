"""Runtime checks for model-created LangGraph plans."""

from __future__ import annotations

from typing import Any


def validate_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Plan must be a JSON object.")
    required = ("topic", "scene_description", "genre", "script_style", "num_agents", "agents", "turn_order", "max_turns", "interrupt_conditions")
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError("Plan is missing: " + ", ".join(missing))
    if any(not isinstance(value[key], str) or not value[key].strip() for key in required[:4]):
        raise ValueError("Plan topic, scene, genre, and style must be non-empty text.")
    agents = value["agents"]
    if not isinstance(agents, list) or not 2 <= len(agents) <= 4:
        raise ValueError("Plan must contain 2 to 4 agents.")
    names: set[str] = set()
    for agent in agents:
        if not isinstance(agent, dict) or any(not isinstance(agent.get(key), str) or not agent[key].strip() for key in ("name", "persona", "role")):
            raise ValueError("Each agent needs a name, persona, and role.")
        name = agent["name"].strip().upper()
        if name in names:
            raise ValueError("Agent names must be unique.")
        names.add(name)
        temperature = agent.get("temperature")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0.0 <= temperature <= 2.0:
            raise ValueError(f"Agent {name} has an invalid temperature.")
    if value["num_agents"] != len(agents):
        raise ValueError("num_agents must match the agents list.")
    order = value["turn_order"]
    if not isinstance(order, list) or not 1 <= len(order) <= 6 or any(not isinstance(name, str) or name.strip().upper() not in names for name in order):
        raise ValueError("Turn order must contain 1 to 6 configured agent names.")
    if isinstance(value["max_turns"], bool) or not isinstance(value["max_turns"], int) or not 1 <= value["max_turns"] <= 16:
        raise ValueError("max_turns must be between 1 and 16.")
    conditions = value["interrupt_conditions"]
    if not isinstance(conditions, list) or len(conditions) > 2:
        raise ValueError("Plan may contain at most two interrupt rules.")
    for condition in conditions:
        if not isinstance(condition, dict) or condition.get("type") not in {"after_n_turns", "on_keyword"}:
            raise ValueError("Interrupt rule has an unsupported type.")
        if str(condition.get("agent_name", "")).upper() not in names:
            raise ValueError("Interrupt rule must name a configured agent.")
        if not isinstance(condition.get("reason"), str) or not condition["reason"].strip():
            raise ValueError("Interrupt rule needs a reason.")
        if condition["type"] == "after_n_turns" and not (isinstance(condition.get("after_turn"), int) and not isinstance(condition.get("after_turn"), bool) and 0 <= condition["after_turn"] < value["max_turns"]):
            raise ValueError("Turn interrupt must point inside the turn limit.")
        if condition["type"] == "on_keyword" and not (isinstance(condition.get("keyword"), str) and condition["keyword"].strip()):
            raise ValueError("Keyword interrupt needs a keyword.")
    return value
