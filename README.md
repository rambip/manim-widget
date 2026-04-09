# manim-widget

Interactive Manim widget for Jupyter/marimo notebooks.

## Installation

```bash
uv pip install -e .
```

## Browser Debug Flow (unbundled manim-web)

Use this when you want readable browser stack traces from `manim-web` TypeScript
sources while replaying one `ManimWidget` scene payload.

1. Start `manim-web` in Vite dev mode:

```bash
cd manim-web
npm run dev -- --host 127.0.0.1 --port 5173 --cors
```

2. In another terminal, start the Python debug server with your scene:

```bash
uv run python scripts/debug_scene_server.py your_module:YourSceneClass
```

3. Open `http://127.0.0.1:8765/`.

The page fetches `/scene.json` live on reload, imports `manim-web` from the Vite
server, and reuses `js/src/player.js` + `js/src/registry.js` directly. Runtime
errors and unhandled rejections are printed with stack traces and
`__MW_LAST_ANIM_DEBUG` context.
