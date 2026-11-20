# Privacy and data handling

## Offline Studio

- The default mock engine runs on the local machine and needs no API key.
- The server binds to `127.0.0.1` by default.
- Briefs are held in the page and request memory; the Studio does not save them between sessions.
- The first-visit still-life image is a local repository asset. No image service is called at runtime.
- Battle Arena votes are stored in browser `localStorage` and are not sent to the server.

## Hosted generation

When Groq is selected, the Studio sends the brief and relevant script text to the Groq API. Review Groq’s current data terms before using real product or customer information. The API key is read from `GROQ_API_KEY`; keep it in the shell environment or an ignored `.env` file. Never commit a real key.

## Local generation and voice

The GGUF model runs through the optional local `llama-cpp-python` runtime using a file path configured by `LLAMA_CPP_MODEL_PATH`. Voice preview uses the host’s speech engine. The app does not download model weights or voice assets.

## Scope

This page describes the behavior implemented in this repository. It is not a promise about data retention by optional third-party providers or operating-system services.
