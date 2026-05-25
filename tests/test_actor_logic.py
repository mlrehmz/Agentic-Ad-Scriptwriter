from src.agents.actor import _find_interrupt, _select_speaker


def test_find_interrupt_after_n_turns() -> None:
    conditions = [
        {
            "type": "after_n_turns",
            "after_turn": 2,
            "keyword": None,
            "agent_name": "ALEX",
            "reason": "shift the mood",
        }
    ]
    interrupt = _find_interrupt(conditions, current_turn=2, last_line=None)
    assert interrupt is not None
    assert interrupt["agent_name"] == "ALEX"


def test_find_interrupt_on_keyword() -> None:
    conditions = [
        {
            "type": "on_keyword",
            "after_turn": None,
            "keyword": "betrayal",
            "agent_name": "MORGAN",
            "reason": "call it out",
        }
    ]
    interrupt = _find_interrupt(conditions, current_turn=1, last_line="That was a betrayal.")
    assert interrupt is not None
    assert interrupt["agent_name"] == "MORGAN"


def test_select_speaker_interrupt_wins() -> None:
    plan = {"turn_order": ["ALEX", "MORGAN"]}
    interrupt = {
        "type": "after_n_turns",
        "after_turn": 0,
        "keyword": None,
        "agent_name": "CASEY",
        "reason": "cut in",
    }
    speaker = _select_speaker(plan, current_turn=0, interrupt=interrupt)
    assert speaker == "CASEY"
