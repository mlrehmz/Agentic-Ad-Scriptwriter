"""CLI entry point for the film script generator."""

from __future__ import annotations

import argparse
import asyncio

# Allow running as a script (no package context) or as a module.
try:
    from .harness import run
except ImportError:
    from harness import run


def main() -> None:
    """Parse CLI args and dispatch to the runtime harness."""
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
