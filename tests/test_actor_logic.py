import unittest

from src.actor_logic import find_interrupt, select_speaker


class ActorLogicTests(unittest.TestCase):
    def test_after_turn_interrupt(self):
        interrupt = find_interrupt([{
            "type": "after_n_turns", "after_turn": 2, "keyword": None,
            "agent_name": "ALEX", "reason": "shift the mood",
        }], 2, None)
        self.assertEqual(interrupt["agent_name"], "ALEX")

    def test_keyword_interrupt(self):
        interrupt = find_interrupt([{
            "type": "on_keyword", "after_turn": None, "keyword": "betrayal",
            "agent_name": "MORGAN", "reason": "call it out",
        }], 1, "That was a betrayal.")
        self.assertEqual(interrupt["agent_name"], "MORGAN")

    def test_keyword_interrupt_fires_only_once(self):
        condition = {
            "type": "on_keyword", "after_turn": None, "keyword": "betrayal",
            "agent_name": "MORGAN", "reason": "call it out",
        }
        log = [{"turn": 1, "agent_name": "MORGAN", "type": "on_keyword", "reason": "call it out", "keyword": "betrayal"}]
        self.assertIsNone(find_interrupt([condition], 2, "betrayal again", log))

    def test_same_keyword_rule_for_another_speaker_remains_eligible(self):
        first = {"type": "on_keyword", "after_turn": None, "keyword": "help", "agent_name": "ALEX", "reason": "call out"}
        second = {**first, "agent_name": "SAM"}
        log = [{"turn": 1, "agent_name": "ALEX", "type": "on_keyword", "reason": "call out", "keyword": "help"}]
        result = find_interrupt([first, second], 2, "help again", log)
        self.assertEqual(result["agent_name"], "SAM")

    def test_later_turn_rule_is_not_hidden_by_an_earlier_rule(self):
        first = {"type": "after_n_turns", "after_turn": 2, "keyword": None, "agent_name": "ALEX", "reason": "shift"}
        later = {**first, "after_turn": 4}
        log = [{"turn": 2, "agent_name": "ALEX", "type": "after_n_turns", "reason": "shift", "keyword": None, "after_turn": 2}]
        result = find_interrupt([later], 4, None, log)
        self.assertEqual(result["after_turn"], 4)

    def test_interrupt_speaker_wins_and_empty_order_is_safe(self):
        plan = {"turn_order": ["ALEX", "MORGAN"]}
        interrupt = {"agent_name": "CASEY"}
        self.assertEqual(select_speaker(plan, 0, interrupt), "CASEY")
        self.assertEqual(select_speaker({"turn_order": []}, 0, None), "")


if __name__ == "__main__":
    unittest.main()
