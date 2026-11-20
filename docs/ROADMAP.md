# Roadmap and current limitations

This is a set of candidate improvements, not a release schedule.

## Implemented

- Local-first browser Studio with deterministic mock generation.
- Validated `AdBrief` domain model.
- Three-direction comparison, targeted rewrites, accept/undo, audience objection, Battle Arena vote, and campaign-pack export.
- Textual checks for required copy, prohibited phrase matches, and estimated duration.
- Optional Groq and local GGUF writing providers; optional local speech preview.
- Separate LangGraph CLI workflow with plan validation, actor loop, streamed updates, optional human plan approval, resume handling, and compiled-graph integration tests.
- Focused tests for Studio behavior, provider boundaries, plan validation, actor logic, and graph approval/resume paths.

## Candidate next steps

1. **Improve copy quality.** Replace repetitive template output with a reviewed prompt/evaluation set and compare quality across mock and hosted engines.
2. **Strengthen context and claim handling.** Keep user and model-generated text clearly separated from instructions, add limits to dynamic prompt fields, and show each flagged claim beside the triggering text.
3. **Persist graph checkpoints.** Select a durable checkpointer only after choosing the intended deployment environment; the current graph uses process-local memory.
4. **Improve campaign workflow.** Add a polished print/export format and make duration/claim feedback more actionable.
5. **Broaden verification.** Add browser tests for keyboard-only use, long copy, generation errors/retry, edited briefs, responsive layouts, and hosted/local-provider behavior.
6. **Prepare public release details.** Choose and add an appropriate license before inviting outside contributions.

## Known limitations

- Mock copy is illustrative and can be repetitive; it is useful for exercising the workflow, not as finished advertising copy.
- Text matching does not establish that product claims are true, and estimated duration is only a rough reading-time heuristic.
- Groq and local GGUF providers depend on provider access, model availability, host setup, and network or hardware conditions.
- Local voice availability varies by operating system and installed speech engine.
- Studio briefs are not saved between sessions.
- The LangGraph CLI is a separate screenplay workflow and has no durable checkpoint storage yet.
