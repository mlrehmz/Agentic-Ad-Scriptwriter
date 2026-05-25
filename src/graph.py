"""Graph assembly for the multi-agent film script generator."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

# Allow running as a script (no package context) or as a module.
try:
    from .agents.actor import actor_node
    from .agents.critic import critic_node
    from .agents.orchestrator import orchestrator_node, plan_approval_node
    from .states import AgentGraphState
except ImportError:
    from agents.actor import actor_node
    from agents.critic import critic_node
    from agents.orchestrator import orchestrator_node, plan_approval_node
    from states import AgentGraphState


def _should_continue(state: AgentGraphState) -> str:
    plan = state.get("plan") or {}
    max_turns = int(plan.get("max_turns", 0))
    current_turn = int(state.get("current_turn", 0))
    if current_turn >= max_turns:
        return "critic"
    return "actor"


def _plan_gate(state: AgentGraphState) -> str:
    return "actor" if state.get("plan_approved") else "end"


def build_graph(*, approve_plan: bool = False):
    builder = StateGraph(state_schema=AgentGraphState)

    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("actor", actor_node)
    builder.add_node("critic", critic_node)

    if approve_plan:
        builder.add_node("plan_approval", plan_approval_node)
        builder.add_edge(START, "orchestrator")
        builder.add_edge("orchestrator", "plan_approval")
        builder.add_conditional_edges(
            "plan_approval",
            _plan_gate,
            {
                "actor": "actor",
                "end": END,
            },
        )
    else:
        builder.add_edge(START, "orchestrator")
        builder.add_edge("orchestrator", "actor")

    builder.add_conditional_edges(
        "actor",
        _should_continue,
        {
            "actor": "actor",
            "critic": "critic",
        },
    )
    builder.add_edge("critic", END)

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)
