# build123d Live Visualizer — Architecture Notes

## Live Update Loop
- **Front-end trigger** – `Run & Stream` button encodes the textarea contents into an SSE request (`/api/run?code=...`).
- **Server orchestration** – Express writes the snippet to `artifacts/<job>.py`, spawns the dedicated build123d Python interpreter, and relays stdout/stderr as Server-Sent Events (`log` events).
- **Completion signal** – When the Python runner finishes, Express emits a `complete` event containing the STL path (or an error message). The client loads the STL via `three.js` and refreshes the viewer.
- **Resilience** – Each run is isolated via UUIDs, making the log stream and artifacts easy to correlate while enabling multiple sequential runs without restarts.

## Artifact Flow
1. Client sends code → Express persists under `artifacts/<job>.py`.
2. Python runner executes snippet, requiring a `result` variable and exporting to `artifacts/<job>.stl`.
3. Express serves `/artifacts` statically so the browser can fetch STL files immediately.
4. Front-end STL loader retrieves the file, renders it, and exposes a download link; artifacts remain on disk for inspection or later cleanup.

## LLM Integration Options
- **OpenClaw Orchestrator** – Keep the current human-in-the-loop workflow where OpenClaw agents call the `/api/run` endpoint, enabling prompt-to-geometry iteration without exposing provider keys to the prototype.
- **Direct Provider Calls** – Embed provider SDK (OpenAI, Anthropic, etc.) within the server. The Express layer would accept natural-language prompts, forward them to an LLM, and pipe the generated build123d script straight into the runner before streaming results back.
- **Local Coding Agent** – Bundle a lightweight model (e.g., `llama.cpp`) or a deterministic templating agent that runs locally, translating UI prompts to build123d code without external network usage—aligned with offline or air-gapped deployments.

## Next-Step Roadmap
- Add job queueing plus cancellation support per run id (currently a single in-memory stream).
- Persist structured job metadata (prompt, status, artifact path) for replay and auditing.
- Harden sandboxing by running the Python process inside a constrained container or Firejail profile.
- Expand the viewer with assembly overlays (multiple STL layers, color coding, exploded views).
- Wire optional LLM prompt templates + history so designers can iterate conversationally.
- Author smoke tests covering the SSE endpoint and sample runner invocation.
