# Architecture and domain model

## Product boundary

The repository contains two related but separate workflows:

1. **Ad Studio** is the browser product for writing short advertisements.
2. **LangGraph CLI** is an experimental screenplay writers’ room retained from the original project.

The CLI does not currently power the Studio. Keeping that distinction explicit avoids implying that the screenplay graph generates Studio ad campaigns.

## Ad Studio flow

```mermaid
sequenceDiagram
  actor Writer
  participant Browser
  participant HTTP as Local HTTP adapter
  participant Domain as Advertising domain
  participant Engine as Text provider

  Writer->>Browser: Enter product brief
  Browser->>HTTP: Generate request
  HTTP->>Domain: Parse and validate AdBrief
  Domain-->>HTTP: Validated brief
  HTTP->>Engine: Generate or compose directions
  Engine-->>HTTP: Three directions
  HTTP-->>Browser: Directions and checks
  Writer->>Browser: Select and refine a script
  Browser->>HTTP: Rewrite / objection / campaign request
  HTTP->>Domain: Validate request and compose result
  HTTP-->>Browser: Reviewable draft or campaign pack
```

## Domain concepts

- **AdBrief**: the product facts, audience, benefit, creative settings, required points, and prohibited claims. Its parser validates required text, duration, and list inputs.
- **CreativeDirection**: a named route with a concept, hook, and full script. The Studio compares three routes.
- **ScriptDraft**: editable copy with explicit accept/undo behavior in the browser.
- **CampaignPack**: a selected main script plus optional cutdown, alternate hooks, alternate calls to action, and textual checks.
- **WritingProvider**: an adapter for offline mock generation, Groq hosted generation, or local `llama.cpp` generation.

The current code models `AdBrief` as a validated dataclass. Direction, draft, and campaign-pack data are currently represented as dictionaries at the HTTP and browser interfaces; stronger domain types are a future refactor candidate.

## LangGraph workflow

```mermaid
flowchart LR
  S([Start]) --> O[Orchestrator: create and validate plan]
  O --> G{Approval enabled?}
  G -->|Yes| I[Human approval interrupt]
  I -->|Reject| E([End])
  I -->|Approve| A[Actor turn]
  G -->|No| A
  A --> R{Turn limit reached?}
  R -->|No| A
  R -->|Yes| C[Critic: format screenplay]
  C --> F([Final script])
```

The compiled graph streams typed `custom` and `updates` events in LangGraph v2 format. The harness observes interrupt updates and resumes the same thread with `Command(resume=...)`. Plan validation runs before the graph accepts the generated plan. The graph currently uses `InMemorySaver`; checkpoints are lost when the process exits.

## Key implementation seams

- `src/advertising/brief.py` owns the brief’s domain fields and validation.
- `src/studio.py` contains the local HTTP adapter, provider adapters, and use-case functions.
- `src/studio.js` owns browser interaction and draft state.
- `src/studio.css` owns the visual system and responsive layout.
- `src/agents/` contains LangGraph planning, actor, and critic nodes.
- `src/harness.py` owns CLI streaming and human approval/resume.

The Studio uses only the Python standard library for offline operation. Optional provider libraries are installed through project extras.
