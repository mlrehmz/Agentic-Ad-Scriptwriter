# Agentic ADs Scriptwriter 

Multi-agent short-film/Ad script generator built with LangGraph and Groq. The orchestrator
creates a structured plan, the actors generate dialogue turn by turn, and the
critic refines it into a polished script.

## Requirements

- Python 3.13 or newer
- Groq API key set as `GROQ_API_KEY`

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
python -m src.harness
```

Or:

```
python src/harness.py
```

Require human approval after the plan is generated:

```
python src/harness.py --approve-plan
```

## Configuration

- Update model IDs in [src/agents/orchestrator.py](src/agents/orchestrator.py) and
	[src/agents/critic.py](src/agents/critic.py) if you want to swap providers.

- Customize prompts in [src/prompts.py](src/prompts.py) to change agent behavior. 
