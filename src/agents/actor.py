"""
Actor node:
  • Model: configured in src/model_config.py
  • Job: Sequential dialogue turns based on the orchestrator plan.
  • Handles logic-based interrupts (after_n_turns, on_keyword).
  • Streams each line via get_stream_writer().
"""

from __future__ import annotations

from langgraph.config import get_stream_writer

# Allow running as a script (no package context) or as a module.
try:
    from ..client import get_client
    from ..prompts import ACTOR_SYSTEM, ACTOR_USER
    from ..states import AgentGraphState
    from ..actor_logic import build_interrupt_event, build_interrupt_note, find_interrupt, format_conversation, get_agent_map, select_speaker
    from ..model_config import GROQ_ACTOR_MODEL
except ImportError:
    from client import get_client
    from prompts import ACTOR_SYSTEM, ACTOR_USER
    from states import AgentGraphState
    from actor_logic import build_interrupt_event, build_interrupt_note, find_interrupt, format_conversation, get_agent_map, select_speaker
    from model_config import GROQ_ACTOR_MODEL

ACTOR_MODEL = GROQ_ACTOR_MODEL


async def actor_node(state: AgentGraphState) -> dict:
    """LangGraph node: generate the next line of dialogue."""
    writer = get_stream_writer()
    client = get_client()

    plan = state.get("plan")
    if not plan:
        raise ValueError("Actor node has no plan; generation stopped.")

    conversation = list(state.get("conversation", []))
    current_turn = int(state.get("current_turn", 0))
    agents_list = state.get("agents_list", [])
    agent_map = get_agent_map(agents_list)

    last_line = conversation[-1]["line"] if conversation else None
    interrupt_conditions = plan.get("interrupt_conditions") or []
    interrupt = find_interrupt(interrupt_conditions, current_turn, last_line, state.get("interrupt_log", []))
    speaker = select_speaker(plan, current_turn, interrupt)

    if not speaker:
        raise ValueError("No speaker resolved for this turn; check the turn order.")

    agent = agent_map.get(speaker) or agent_map.get(speaker.upper())
    if not agent:
        raise ValueError(f"Agent '{speaker}' is missing from the plan; generation stopped.")

    interrupt_note = build_interrupt_note(interrupt)
    conversation_so_far = format_conversation(conversation)

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
        max_completion_tokens=768,
        reasoning_effort="low",
    )

    cleaned_line = (line or "").strip()
    if not cleaned_line:
        raise ValueError(f"Agent '{agent['name']}' returned an empty line.")
    new_line = {"agent": agent["name"], "line": cleaned_line}

    interrupt_event = None
    if interrupt:
        interrupt_event = build_interrupt_event(current_turn, interrupt, agent["name"])

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
