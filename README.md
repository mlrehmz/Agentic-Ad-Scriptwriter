# Agentic ADs Scriptwriter

Multi-agent short-film/ad script generator built with LangGraph and Groq. The orchestrator
creates a structured plan, the actors generate dialogue turn by turn, and the critic
refines it into a polished script.

## Requirements

- Python 3.13 or newer
- Groq API key set as `GROQ_API_KEY`

## Environment

Create a `.env` file in the repo root:

```
GROQ_API_KEY=your_api_key_here
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```
uv sync
```

Or:

```
pip install -e .
```

## Run

```
python -m src.main
```

Or:

```
python src/main.py
```

Require human approval after the plan is generated:

```
python src/main.py --approve-plan
```

The legacy harness entry still works:

```
python -m src.harness
```

## How It Works

1. The orchestrator produces a JSON plan (scene setup, agent personas, turn order).
2. Actors generate one line at a time, optionally overridden by interrupt rules.
3. The critic converts the raw dialogue into a screenplay-style script.

The CLI entry (`src/main.py`) is intentionally separate from the runtime harness
(`src/harness.py`) to keep IO concerns isolated from the graph execution code.

## Project Layout

```
src/
	main.py        # CLI entry point
	harness.py     # Streaming runtime + run() loop
	graph.py       # LangGraph assembly
	agents/        # Orchestrator, actor, critic nodes
	prompts.py     # Prompt templates
	states.py      # Shared graph state
```


## Configuration

- Update model IDs in [src/agents/orchestrator.py](src/agents/orchestrator.py) and
	[src/agents/critic.py](src/agents/critic.py) if you want to swap providers.
- Customize prompts in [src/prompts.py](src/prompts.py) to change agent behavior.

## Tests

```
pytest
```
