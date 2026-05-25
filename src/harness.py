"""CLI harness to run the film script generator with custom streaming."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any, Dict

from langgraph.types import Command

# Allow running as a script (no package context) or as a module.
try:
    from .graph import build_graph
except ImportError:
    from graph import build_graph


def _print_custom_chunk(chunk: Dict[str, Any]) -> None:
    chunk_type = chunk.get("type")
    data = chunk.get("data")

    if chunk_type == "status":
        print(data)
        return

    if chunk_type == "plan":
        print("\n=== PLAN ===")
        print(json.dumps(data, indent=2))
        print("=== END PLAN ===\n")
        return

    if chunk_type == "line":
        speaker = data.get("speaker") if isinstance(data, dict) else None
        text = data.get("text") if isinstance(data, dict) else None
        if speaker and text:
            print(f"{speaker}: {text}")
        return

    if chunk_type == "critic":
        print("\n=== FINAL SCRIPT ===")
        print(data)
        print("=== END SCRIPT ===")
        return


async def _stream_once(graph, payload, config) -> Any:
    interrupt_payload = None
    async for chunk in graph.astream(payload, config, stream_mode="custom"):
        if isinstance(chunk, dict) and "__interrupt__" in chunk:
            interrupt_payload = chunk["__interrupt__"]
            continue
        if isinstance(chunk, dict) and "type" in chunk:
            _print_custom_chunk(chunk)
    return interrupt_payload


async def run(topic: str, approve_plan: bool) -> None:
    graph = build_graph(approve_plan=approve_plan)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    payload: Any = {
        "topic": topic,
        "conversation": [],
        "interrupt_log": [],
    }
    while True:
        interrupt_payload = await _stream_once(graph, payload, config)
        if not interrupt_payload:
            break

        approval = input("Approve the plan? (y/n): ").strip().lower()
        payload = Command(resume=approval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent film script generator")
    parser.add_argument("--topic", type=str, help="Short film or ad topic")
    parser.add_argument(
        "--approve-plan",
        action="store_true",
        help="Require human approval after the plan is generated",
    )
    args = parser.parse_args()

    topic = args.topic or input("Enter a film topic: ").strip()
    asyncio.run(run(topic, args.approve_plan))


if __name__ == "__main__":
    main()
