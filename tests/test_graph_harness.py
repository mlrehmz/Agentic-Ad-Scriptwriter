import unittest
from unittest.mock import patch

from langgraph.config import get_stream_writer
from langgraph.types import Command

import src.graph as graph_module
from src.harness import _stream_once


class CompiledGraphHarnessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.agents = [
            {
                "name": "ALEX",
                "persona": "Calm and direct.",
                "temperature": 0.4,
                "role": "lead",
            }
        ]
        self.plan = {
            "topic": "A quiet room",
            "scene_description": "Two people wait in a quiet room.",
            "genre": "drama",
            "script_style": "clear and restrained",
            "num_agents": 1,
            "agents": self.agents,
            "turn_order": ["ALEX"],
            "max_turns": 1,
            "interrupt_conditions": [],
        }
        self.actor_calls = 0

    async def fake_orchestrator(self, state):
        get_stream_writer()({"type": "plan", "data": self.plan})
        return {
            "plan": self.plan,
            "agents_list": self.agents,
            "conversation": [],
            "current_turn": 0,
            "interrupt_log": [],
            "plan_approved": False,
            "final_script": None,
        }

    async def fake_actor(self, state):
        self.actor_calls += 1
        get_stream_writer()(
            {"type": "line", "data": {"speaker": "ALEX", "text": "A test line."}}
        )
        return {
            "conversation": [{"agent": "ALEX", "line": "A test line."}],
            "current_turn": 1,
            "current_speaker": "ALEX",
            "interrupt_log": [],
        }

    async def fake_critic(self, state):
        get_stream_writer()({"type": "critic", "data": "Final test script."})
        return {"final_script": "Final test script."}

    async def run_graph(self, approve_plan, resume=None):
        config = {"configurable": {"thread_id": f"graph-test-{approve_plan}"}}
        with (
            patch.object(graph_module, "orchestrator_node", self.fake_orchestrator),
            patch.object(graph_module, "actor_node", self.fake_actor),
            patch.object(graph_module, "critic_node", self.fake_critic),
        ):
            graph = graph_module.build_graph(approve_plan=approve_plan)
            payload = {"topic": "A quiet room", "conversation": [], "interrupt_log": []}
            interrupt = await _stream_once(graph, payload, config)
            resumed_interrupt = None
            if resume is not None:
                resumed_interrupt = await _stream_once(graph, Command(resume=resume), config)
            snapshot = await graph.aget_state(config)
        return interrupt, resumed_interrupt, snapshot

    async def test_approval_pause_is_returned_and_resume_completes_graph(self):
        interrupt, resumed_interrupt, snapshot = await self.run_graph(True, "approve")

        self.assertTrue(interrupt)
        self.assertIsNone(resumed_interrupt)
        self.assertTrue(snapshot.values["plan_approved"])
        self.assertEqual(snapshot.values["final_script"], "Final test script.")
        self.assertEqual(self.actor_calls, 1)

    async def test_rejection_ends_without_running_actor(self):
        interrupt, resumed_interrupt, snapshot = await self.run_graph(True, "no")

        self.assertTrue(interrupt)
        self.assertIsNone(resumed_interrupt)
        self.assertFalse(snapshot.values["plan_approved"])
        self.assertIsNone(snapshot.values["final_script"])
        self.assertEqual(self.actor_calls, 0)

    async def test_graph_without_approval_reaches_critic(self):
        interrupt, resumed_interrupt, snapshot = await self.run_graph(False)

        self.assertIsNone(interrupt)
        self.assertIsNone(resumed_interrupt)
        self.assertEqual(snapshot.values["final_script"], "Final test script.")
        self.assertEqual(self.actor_calls, 1)


if __name__ == "__main__":
    unittest.main()
