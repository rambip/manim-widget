# manim-widget - Agent Context

## Vision

`manim-widget` provides a Jupyter-compatible interactive Manim viewer without rendering video first. The Python side captures scene intent and state as JSON, and the JavaScript side replays it with `manim-web` in the browser.

Primary target is **marimo**, while staying compatible with any `anywidget` frontend (JupyterLab, VS Code notebooks, etc.).

---

## Current Project Status

- V1 core is complete and passing local tests.
- Current focus is pre-V2 hardening:
  - docs updates,
  - broader integration coverage,
  - source/bundle sync safeguards,
  - upstream issues for API shape inconsistencies.

See `TODO.md` for the current checklist and priorities.

---

## Goals (priority order)

### G1 - Fast iteration
Time from notebook execution to visible playback should be minimal. No video rendering pipeline in the loop.

### G2 - Browser-native interactivity
Playback and camera interactions run in JS without Python round-trips.

### G3 - Section-aware navigation
`next_section()` boundaries are preserved. Each section has a snapshot so the player can jump directly to sections.

### G4 - Deterministic data contract
`spec.json` is the wire contract between Python and JS. Changes must remain schema-valid.

### G5 - Clear unsupported behavior
When features are unsupported, surface predictable warnings/errors instead of silent degradation.

---

## Vocabulary

- **Scene**: full execution of `construct()`.
- **Section**: named region delimited by `next_section()`.
- **Command stream**: serialized list of `add` / `remove` / `animate` / `data` commands for a section.
- **Snapshot**: full mobject state at section entry.
- **Dry-run**: execute scene logic to capture structured playback data only (no video file output).

---

## Architecture

### Python side (`src/manim_widget/`)

- `widget.py`
  - Defines `ManimWidget` and trait payload (`scene_data`).
  - Owns section lifecycle and emits section snapshots + commands.
- `renderer.py`
  - Custom capture renderer compatible with Manim `Scene.play` lifecycle.
  - Intercepts play/update flow to emit `animate` or `data` commands.
- `snapshot.py`
  - Short-id generation and mobject serialization.
  - Builds section snapshots from scene families.
- `serializer.py`
  - Produces final JSON envelope consumed by JS.

### JavaScript side (`js/src/`)

- `index.js`
  - anywidget entry point and DOM/UI wiring.
  - Creates scene, registry, player, and binds controls.
- `registry.js`
  - Runtime mobject registry keyed by stable IDs.
- `player.js`
  - Snapshot restore + command execution.
  - Animation adapter layer to `manim-web` constructors/factories.

### Bundled runtime (`src/manim_widget/static/index.js`)

- Built from `js/src/*` via Bun.
- This is what packaged widget users execute.

---

## Data Model (V1)

Top-level payload shape:

```json
{
  "version": 1,
  "fps": 10,
  "sections": [
    {
      "name": "initial",
      "snapshot": {},
      "construct": [
        { "cmd": "add", "id": "0", "state": { "kind": "Circle" } },
        {
          "cmd": "animate",
          "duration": 1.0,
          "animations": [
            { "type": "Create", "id": "0", "rate_func": "smooth", "params": {} }
          ]
        }
      ]
    }
  ]
}
```

Core commands:

- `add`: introduce mobject state into JS scene.
- `remove`: remove mobject by id.
- `animate`: high-level animation descriptors.
- `data`: per-frame data for updater-driven sections.

---

## Supported/Important Behavior (V1)

- `Create`, `FadeIn`, `FadeOut`, `Write`, `ReplacementTransform`.
- `.animate.shift`, `.animate.rotate`, `.animate.scale` mapped through descriptor params.
- Snapshot restoration at section boundaries.
- Invalid point-array shape (not `3n+1`) raises JS error.

Known integration nuance:

- Some `manim-web` animation exports may appear class-like in one runtime path and factory-like in another.
- `Shift` currently has explicit compatibility handling in `player.js` for class-vs-factory shape.
- Pre-V2 work includes extending this hardening pattern to other animations.

---

## Testing Strategy

### Python tests

- Validate serialization/snapshot semantics and command stream correctness.

### Playwright integration (`tests/test_playwright_integration.py`)

- Spins local HTTP server.
- Serves JS modules and generated HTML scene pages.
- Captures browser console/page errors through a fixture.
- Verifies UI + runtime behavior, including playback error checks.

Important current gap being addressed:

- Source-vs-bundle parity and runtime import-shape parity (CDN/module path vs packaged bundle).

---

## Drift and Parity Risks

Two separate risks exist and both matter:

1. **Source vs bundled artifact drift**
   - Tests can run against `js/src/*` while users run `src/manim_widget/static/index.js`.
   - If bundle is stale, tests may pass while notebooks fail.

2. **Runtime export-shape drift**
   - Different module pipelines can expose animation APIs differently (class-like vs factory-like).
   - Adapter logic in `player.js` should avoid assuming one shape.

Mitigation direction:

- Add tests covering packaged bundle path.
- Enforce source/bundle sync checks in CI.
- Keep animation adapter defensive for both constructor and factory APIs.

---

## Repository Structure

```text
manim-widget/
  src/
    manim_widget/
      __init__.py
      widget.py
      renderer.py
      serializer.py
      snapshot.py
      static/
        index.js
  js/
    src/
      index.js
      player.js
      registry.js
    package.json
  tests/
    test_playwright_integration.py
  spec.json
  pyproject.toml
  TODO.md
  AGENTS.md
```

---

## Tooling

- Python env/deps: `uv`
- JS deps/build: `bun`
- Widget bridge: `anywidget`
- Browser integration tests: `pytest` + `pytest-playwright`

Useful commands:

- `uv run pytest -q`
- `uv run pytest -q tests/test_playwright_integration.py`
- `bun run build` (from `js/`)

---

## Implementation Guidelines

- Keep Python mobjects as source of truth for end-state; transition hints belong in command metadata.
- Prefer explicit serializer/adapter logic over implicit conversion.
- When changing payload shape, update `spec.json` and tests together.
- For JS animation adapters, prefer compatibility wrappers over runtime assumptions.

---

## External References

- `maloyan/manim-web` (animation/runtime behavior)
- `ManimCommunity/manim` (scene lifecycle and animation semantics)
