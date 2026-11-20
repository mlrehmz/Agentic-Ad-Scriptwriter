# Ad Studio

A local-first creative studio for short advertisements. Start with a concise brief, compare three creative directions, shape one with targeted rewrites, challenge it with an audience objection, compare it with a one-prompt baseline, and export a compact campaign pack.

The default mock engine is deterministic and fully offline. It uses only the Python standard library. Its copy is illustrative and does not claim product facts beyond the brief.

## Run the no-key demo

Requires Python 3.13 or newer.

```sh
python -m src.studio
```

Open <http://127.0.0.1:8765>. Use the mock engine to explore without a key, account, network connection, GPU, or model download. The server binds to localhost only. Press Ctrl+C to stop it.

## Writing engines

### Hosted Groq

Set `GROQ_API_KEY` and optionally `GROQ_MODEL`, then choose **Groq · hosted** in the studio. The studio defaults to `openai/gpt-oss-20b`. Hosted generation sends the brief and copy to Groq. Set `GROQ_MODEL` for the studio, or `GROQ_ORCHESTRATOR_MODEL`, `GROQ_ACTOR_MODEL`, and `GROQ_CRITIC_MODEL` to override the legacy graph. The graph defaults to `openai/gpt-oss-120b` for planning and editing and `openai/gpt-oss-20b` for actor turns. Groq lists GPT-OSS 20B and 120B as replacements for the repository’s retired Llama model IDs. Model availability depends on the account and provider; errors are shown in the studio. No hosted call is made by the default demo.

### Local GGUF with llama.cpp

Install the optional runtime and provide a model file you already have:

```sh
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
export LLAMA_CPP_MODEL_PATH=/absolute/path/to/model.gguf
python -m src.studio
```

The app never downloads model weights. The runtime may need a native compiler or platform-specific setup; this path has not been verified on another machine. The first use loads the chosen file into memory. This machine's Intel UHD 620 is integrated graphics, so the Python runtime uses CPU by default unless separately configured. A small quantized GGUF is the practical starting point; context and speed depend on the selected file and available RAM.

### Local voice preview

Install eSpeak NG and the optional TTS wrapper on Fedora, then start the studio:

```sh
sudo dnf install espeak-ng
pip install '.[voice]'
python -m src.studio
```

The studio lists voices found by `pyttsx3` and lets you select a system voice. Voice preview appears only when `pyttsx3` and a system engine are available. Voices and languages come from that operating system's installed speech engine. The app does not fetch voices. Character labels are omitted from the spoken copy. One selected system voice reads the whole script; separate voice assignment and timed pause controls are not implemented. The WAV is generated in a temporary directory and returned to the browser for playback or download. This has not been verified on the current machine, so audio availability will be determined at runtime.

## Existing LangGraph workflow

The original CLI workflow remains available as an optional extra:

```sh
pip install '.[workflow]'
export GROQ_API_KEY=...
python -m src.main --topic "A short ad about ..."
```

The Studio's mock/local/hosted writer interface is separate from the legacy graph. The graph still provides the original planner, sequential persona actors, critic, progress events, and optional human plan approval. It is not used by the default local demo.

## Feedback and privacy

Battle Arena votes are held in browser local storage and are not sent to the server. The studio does not save briefs between sessions. The hosted mode sends generation prompts to Groq. Errors do not include prompt text or API keys in server logs.

Checks show textual presence of the requested CTA and required points, exact matches for prohibited phrases, and an approximate speaking duration. They are simple guardrails, not legal review or evidence that an advertisement will perform.

## Development checks

Create and activate a project virtual environment with `uv`, then install the test extra:

```sh
uv venv
source .venv/bin/activate
uv pip install -e '.[test]'
pytest
```

The test suite uses pytest. The default Studio and its mock engine need no API key; hosted model checks need a Groq API key.
