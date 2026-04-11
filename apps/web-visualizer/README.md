# build123d Live Visualizer Prototype

This prototype pairs a lightweight Express runner with a Vite + React front-end that streams runner logs and renders generated STL files inside a browser-based viewport.

## Prerequisites

- Node.js 18+
- Access to the existing `build123d` Python environment at `/Users/noahk/.openclaw/workspace/skills/build123d-cad/.venv/bin/python` (automatically used by the server).

## Getting Started

```bash
npm install
npm run dev
```

The shortcut above launches both the Express runner (`http://localhost:4000`) and the Vite dev server (`http://localhost:5173`).

### Manual split

```bash
npm run dev:server # terminal 1
npm run dev:client # terminal 2
```

The front-end proxies `/api` and `/artifacts` calls to the Express server when running in dev mode.

## Using the Prototype

1. Paste or edit build123d code inside the left panel. Ensure your geometry is assigned to a variable called `result`.
2. Click **Run & Stream**. The server writes your code to a scratch file, executes it inside the configured `build123d` virtualenv, and exports STL and STEP artifacts into `./artifacts`.
3. Logs and errors stream into the right-hand panel. When the export succeeds, the STL is loaded into the three.js viewport and download links become available for both STL and STEP.

### Sample Snippet

```python
from build123d import *

with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Rectangle(40, 20)
        Locations((0, 0))
        Circle(6)
    extrude(amount=12)

result = bp.part
```

All exported artifacts live inside the `artifacts/` folder, which is served statically for browser fetching.
