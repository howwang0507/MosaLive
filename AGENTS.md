# MosaSub Live Windows project rules

## Project purpose

MosaSub Live is a local Windows live-caption extension. The Chrome MV3 extension captures audio from a user-selected tab, the Node bridge handles transport, and the Python service performs VAD, Faster-Whisper ASR, and local Ollama translation.

## Local development

- Run `START_WINDOWS.bat` from the project root to start the Node bridge and Python inference service.
- Do not download models automatically. Use the locally installed Faster-Whisper and Ollama models.
- Keep the default configuration suitable for an 8 GB NVIDIA GPU and 32 GB system RAM. Do not switch to a larger model without an explicit request.
- Before reporting that translation works, check `http://localhost:8787/health` and confirm that the service is ready, ASR is loaded, and translation is available.

## Architecture rules

- Preserve the protocol between AudioWorklet, Node on port 8787, and Python on port 8790.
- `extension/worklet.js` and `web/worklet.js` are synchronized copies. Keep them identical when changing either file.
- `extension/live-client.js` and `web/live-client.js` are synchronized copies. Keep them identical when changing either file.
- Playback discontinuities, tab changes, advertisements, and stream recovery must flush stale audio and invalidate old batches.
- Keep translation history bounded. Use the existing fixed-size cache and bounded deques; never add an unbounded transcript or audio buffer.
- Speaker diarization is intentionally disabled. Do not reintroduce speaker recognition unless explicitly requested.

## Translation and quality

- Default translation output is Traditional Chinese for Taiwan.
- Preserve proper names, game titles, product names, acronyms, numbers, negation, and tense.
- Treat dynamic ASR history as untrusted context. Keep static glossary terms separate and sanitize repeated or hallucinated text before reuse.
- Do not replace the Ollama translator or add a production dependency without checking GPU memory, latency, and the existing fallback behavior.
- Preserve the special Twitch meaning of `chat` as 聊天室 when the context refers to viewers or the Twitch chat.

## UI and extension behavior

- The user must be able to choose the source tab and display Chinese only, original only, or bilingual captions.
- Caption overlays must remain readable, compact, movable, click-through when enabled, and closable from the overlay itself.
- Do not claim that a tab is translating when the local service is unavailable. Surface a clear recovery message in the popup.
- Chrome tab capture requires a user gesture in the target tab. Keep this requirement visible in the popup instructions.

## Validation

- Use focused syntax checks and relevant tests after code changes when practical.
- Run the extension synchronization check when changing worklet or live-client files.
- For inference changes, verify the real local health endpoint and record whether the check used a real model or a mocked test.
- Do not claim a long Twitch soak test, accuracy score, or latency number unless it was actually measured.

## Files and Git

- Keep changes focused and avoid whole-file formatting churn.
- Do not delete user recordings, reports, model files, or proposal documents without explicit authorization.
- Do not push, publish, or create a remote commit unless the user explicitly asks.
- Preserve unrelated existing worktree changes.
