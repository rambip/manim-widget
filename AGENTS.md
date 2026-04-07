# manim-widget - Agent Context

## Vision

`manim-widget` provides a Jupyter-compatible interactive Manim viewer without rendering video first. The Python side captures scene intent/state as JSON, and the JavaScript side replays it with `manim-web` in the browser.

Primary target is **marimo**, while staying compatible with any `anywidget` frontend (JupyterLab, VS Code notebooks, etc.).

---

## Current Project Status

- V2 wire format is now the active contract (`spec.json`, `version: 2`).
- Python capture/serialization has been migrated to V2.
- **Snapshot format simplified**: `snapshot` now uses integer `state_ref` indices instead of inline state objects.
- VGroup representation unified: single `VGroupState` with `children: ["mob_id", ...]` for both snapshot and state bank contexts.
- JS runtime updated to resolve `state_ref` from snapshot before restoring mobjects.

See `TODO.md` for current priorities.

---

## Goals (priority order)

### G1 - Fast iteration
Time from notebook execution to visible playback should be minimal. No video rendering pipeline in the loop.

### G2 - Browser-native interactivity
Playback and camera interactions run in JS without Python round-trips.

### G3 - Section-aware navigation
`next_section()` boundaries are preserved. Each section has a section-entry snapshot so the player can jump directly.

### G4 - Deterministic data contract
`spec.json` is the wire contract between Python and JS. Output should be deterministic and schema-valid.

### G5 - Clear unsupported behavior
When features are unsupported, surface predictable warnings/errors instead of silent degradation.

---

## Vocabulary

- **Scene**: full execution of `construct()`.
- **Section**: named region delimited by `next_section()`.
- **State bank**: section-local list of serialized mobject states (`states`) addressed by integer `state_ref`.
- **Snapshot**: section-entry full map of `mob_id -> serialized state` used for direct section restore.
- **Command stream**: section operations (`add`, `remove`, `animate`, `data`, `rebind`).
- **Dry-run**: execute scene logic to capture structured playback data only (no video file output).

---

## Architecture

### Python side (`src/manim_widget/`)

- `widget.py`
  - Defines `ManimWidget` and trait payload (`scene_data`).
  - Owns section lifecycle and emits section snapshots + command streams.
  - Uses renderer registry active set for section-entry snapshots.
- `renderer.py`
  - Custom capture renderer integrated with Manim `Scene.play` lifecycle.
  - Emits V2 commands/descriptors for animate/update flows.
  - Maintains section-local deduplicated state banks (`states`) and allocates `state_ref` values.
  - Emits `rebind` for replacement semantics.
- `snapshot.py`
  - Short-id generation and mobject serialization primitives.
  - Note: legacy snapshot helpers may still exist; current section snapshots are widget/renderer-driven.
- `serializer.py`
  - Produces top-level V2 envelope consumed by JS.

### JavaScript side (`js/src/`)

- `index.js`
  - anywidget entry point and DOM/UI wiring.
  - Creates scene, registry, player, and binds controls.
- `registry.js`
  - Runtime mobject registry keyed by stable IDs.
- `player.js`
  - Restores section snapshots and executes command streams.
  - Must resolve `state_ref` through section `states` and apply `rebind` semantics.
  - Animation adapter layer should remain defensive against class-vs-factory exports.
- `test_cli.js`
  - CLI entry point for JS integration testing.
  - Uses happy-dom to provide browser-like environment.
  - Mocks manim-web to avoid WebGL dependencies.
  - Plays scene spec from stdin and reports errors to stderr.
  - Use `--output-ids` to output JSON with mobject IDs at end of each section.

### Bundled runtime (`src/manim_widget/static/index.js`)

- Built from `js/src/*` via Bun.
- This is what packaged widget users execute.

---

## Data Model (V2)

Top-level payload shape:

```json
{
  "version": 2,
  "fps": 10,
  "sections": [
    {
      "name": "initial",
      "snapshot": {},
      "states": [
        { "kind": "Circle" }
      ],
      "construct": [
        { "cmd": "add", "id": "0", "state_ref": 0 },
        {
          "cmd": "animate",
          "duration": 1.0,
          "animations": [
            {
              "type": "simple",
              "kind": "Create",
              "id": "0",
              "rate_func": "smooth",
              "params": {}
            }
          ]
        }
      ]
    }
  ]
}
```

Core commands:

- `add`: introduce mobject by `id` using `state_ref` into section `states`.
- `remove`: remove mobject by `id`.
- `animate`: high-level animation descriptors (`type` family + `kind`).
- `data`: updater-driven frame stream where per-mobject payload is `{ "state_ref": <int> }`.
- `rebind`: remap IDs after replacement-style transforms (`source_id -> target_id`).

Key semantics:

- `snapshot` is `{ mob_id: state_ref }` at section entry - integer indices into section's `states` array.
- `states` is a deduplicated per-section bank referenced by commands/frames/snapshot.
- VGroup uses single representation: `VGroupState` with `children: ["mob_id", ...]` for all contexts.
- JS runtime resolves snapshot values (integers) through section's `states` before restoring.
- No `hidden` semantics in V2.
- `ReplacementTransform` is represented as transform animation + `rebind` command.

---

## Supported/Important Behavior

- Supported descriptor families include simple animations (`Create`, `FadeIn`, `FadeOut`, `Write`) and transform (`Transform`, `ReplacementTransform` lowering to transform + `rebind`).
- Method animations (`.animate.shift`, `.animate.rotate`, `.animate.scale`, etc.) map to `type: "simple"` with explicit params.
- **Chained method animations** (`.animate.scale(0.5).next_to(...)`) are handled by emitting a Transform with the final `target_mobject` state. This correctly captures all method effects without needing to decode each method individually.
- Snapshot restoration at section boundaries remains core behavior.
- Invalid point-array shape (not `3n+1`) should raise JS-side playback error.

Known integration nuance:

- Some `manim-web` animation exports may appear class-like in one runtime path and factory-like in another.
- Adapter logic in `player.js` should not assume one shape.
- Chained `.animate` methods are emitted as Transform animations, which manim-web handles correctly.

---

## Testing Strategy

### Python tests

- Prefer fewer, more exhaustive deterministic tests asserting full JSON payloads.
- Validate schema compatibility against `spec.json`.
- Validate updater/data frames use `state_ref` indirection (not inline frame state).

### JS integration tests (`tests/test_js_integration.py`)

- Uses CLI script (`js/src/test_cli.js`) with happy-dom to test JS runtime without a browser.
- Mocks manim-web to avoid WebGL/Three.js dependencies.
- Takes scene spec JSON via stdin and plays through all sections/commands.
- Captures errors and warnings, exits non-zero on playback errors.
- Run with: `bun run src/test_cli.js < scene-spec.json`

Test coverage includes:
- Simple scenes (Create, FadeIn)
- Multi-section navigation
- VGroup handling
- Error conditions (invalid point arrays, missing state refs)

---

## Drift and Parity Risks

Two separate risks exist and both matter:

1. **Source vs bundled artifact drift**
   - JS integration tests run against `js/src/*` via CLI imports.
   - Users run `src/manim_widget/static/index.js` (the bundled version).
   - If bundle is stale, tests may pass while notebooks fail.

2. **Python V2 vs JS runtime skew**
   - Python emits V2 shape; JS path must handle command/state semantics.
   - Integration tests cover full replay path to detect contract mismatches.

Mitigation:

- Run `bun run build` after JS source changes.
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
      test_cli.js
    package.json
  tests/
    test_widget.py
    test_js_integration.py
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
- JS integration tests: `bun` + `happy-dom`

Useful commands:

- `uv run pytest -q`
- `uv run pytest -q tests/test_widget.py`
- `uv run pytest -q tests/test_js_integration.py`
- `bun run build` (from `js/`)
- `bun run cli < scene-spec.json` (from `js/`, for manual JS runtime testing)

---

## Implementation Guidelines

- Keep Python mobjects as source of truth for end-state; transition hints belong in command metadata.
- Prefer explicit serializer/adapter logic over implicit conversion.
- When changing payload shape, update `spec.json` and tests together.
- Preserve deterministic ordering in emitted JSON wherever possible.
- For JS animation adapters, prefer compatibility wrappers over runtime assumptions.

---

## External References

- `maloyan/manim-web` (animation/runtime behavior)
- `ManimCommunity/manim` (scene lifecycle and animation semantics)
