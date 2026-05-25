"""
Shared graph state — every node reads and writes this TypedDict.

Reducers:
  • conversation  — replaced wholesale each actor turn (actor returns full list)
  • Everything else — last-write wins (default LangGraph behaviour)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


# ── sub-types ──────────────────────────────────────────────────────────────

class AgentConfig(TypedDict):
    """One speaker in the plan."""
    name: str                 # e.g. "ALEX", "DETECTIVE MORGAN"
    persona: str              # full personality / speech-pattern description
    temperature: float        # 0.3 (methodical) → 1.0 (passionate)
    role: str                 # narrative role, e.g. "protagonist", "antagonist"


class InterruptCondition(TypedDict):
    """Logic-based interrupt: after a given turn, a specific agent cuts in."""
    after_turn: int           # inject this agent INSTEAD OF the normal next speaker
    agent_name: str
    reason: str               # why they interrupt here (stored for critic context)


class Plan(TypedDict):
    """Structured production plan emitted by the orchestrator."""
    topic: str
    scene_description: str    # vivid 2-3 sentence scene setup
    genre: str                # drama, comedy, thriller, romance, sci-fi …
    script_style: str         # tonal description, e.g. "gritty noir with dark humour"
    num_agents: int
    agents: List[AgentConfig]
    turn_order: List[str]     # cycling list of agent names (4-6 entries)
    max_turns: int            # total dialogue turns (8-16)
    interrupt_conditions: List[InterruptCondition]


# ── root state ─────────────────────────────────────────────────────────────

class AgentGraphState(TypedDict):
    # ── input ──
    topic: str

    # ── orchestrator output ──
    plan: Optional[Plan]
    agents_list: List[AgentConfig]      # convenience copy of plan["agents"]

    # ── actor loop ──
    conversation: List[Dict[str, str]]  # [{"agent": name, "line": text}, …]
    current_turn: int

    # ── human gate ──
    plan_approved: bool

    # ── critic output ──
    final_script: Optional[str]