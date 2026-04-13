# AGENTS.md

## Vision

`manim-widget` provides an interactive Manim viewer without rendering video. The Python side captures scene intent as JSON; the JS side replays it using `manim-web` in the browser. Primary target is **marimo**, compatible with any `anywidget` frontend.

---

## Goals (priority order)

- **G1 – Fast iteration.** No video rendering pipeline. Notebook execution → visible playback immediately.
- **G2 – Browser-native interactivity.** Playback and camera interactions run in JS without Python round-trips.
- **G3 – Section-aware navigation.** Each section has an entry snapshot enabling cheap direct jumps — no replaying from the start.
- **G4 – Deterministic data contract.** `spec.json` is the wire contract. Always modify it first, then update code and tests together.
- **G5 – Clear unsupported behavior.** Surface predictable warnings/errors; never degrade silently.

---

## Vocabulary

- **Scene**: full execution of `construct()`.
- **Section**: named region delimited by `next_section()`.
- **State bank**: section-local deduplicated list of serialized mobject states (`states`), addressed by integer `state_ref`.
- **Snapshot**: section-entry map of `mob_id → state_ref`. Enables O(1) section jumps without replaying prior sections.
- **Command stream** (`construct`): ordered section operations — `add`, `remove`, `rebind` and the more complex `animate`.
- **Dry-run**: execute scene logic to capture playback data only; no video output.

---

## Architecture

### Python (`src/manim_widget/`)

- **`widget.py`** — Defines `ManimWidget` and the `scene_data` trait payload. Owns section lifecycle, emits section snapshots and command streams. Uses renderer registry for section-entry snapshots.
- **`renderer.py`** — Custom capture renderer integrated with Manim's `Scene.play` lifecycle. Emits commands and animation descriptors. Maintains per-section deduplicated state banks and allocates `state_ref` values. Handles `rebind` for replacement-style transforms.
- **`snapshot.py`** — Short-id generation and mobject serialization primitives.

### JavaScript (`js/src/`)

- **`index.js`** — anywidget entry point. Creates scene, registry, player, wires controls.
- **`registry.js`** — Runtime mobject registry keyed by stable IDs.
- **`player.js`** — Restores section snapshots and executes command streams. Resolves `state_ref` through `section.states` before restoring mobjects. Animation adapter must handle both constructor-style and factory-style exports from `manim-web`.
- **`test_cli.js`** — CLI integration test entry point. Uses `happy-dom` for a browser-like environment and `manim-web` headless mode (scene graph only, no pixel output). Reads scene spec from stdin, reports errors to stderr. `--output-ids` emits JSON with mobject IDs at end of each section.

### Bundled runtime (`src/manim_widget/static/index.js`)

Built from `js/src/*` via Bun. This is what packaged widget users execute. Rebuild after any JS source change with `bun run build`.

### manim-web

`manim-web` is a git submodule and a maintained fork. Upstream PRs are sent when bugs are found. The JS side of `manim-widget` may eventually move into `manim-web` directly, making the JSON spec a first-class concept there.

---

## Data Contract

`spec.json` is the single source of truth. When changing payload shape: update `spec.json` first, then code, then tests.

### Top-level shape

```json
{
  "version": 2,
  "sections": [ ... ]
}
```

### Section

```json
{
  "name": "intro",
  "snapshot": { "mob_id": 0 },
  "states": [ { "kind": "VMobject", ... } ],
  "construct": [ ... ]
}
```

- `snapshot`: `mob_id → state_ref` for all root mobjects at section entry. Null only when `unsupported: true`. VGroup children are **not** listed separately — they are referenced via `VGroupState.children`.
- `states`: deduplicated per-section bank. All commands, frames, and snapshots reference it by integer index.
- `construct`: ordered command list.

### Commands

| cmd | purpose |
|---|---|
| `add` | bind `id → state_ref` in scene graph |
| `remove` | free `id` from registry (emitted after `FadeOut`, `ReplacementTransform`) |
| `rebind` | remap `source_id → target_id` (emitted after `ReplacementTransform`) |
| `animate` | one `scene.play()`; contains both parralel animations and updaters for specific objects|

### Animation descriptors

Families: `SimpleAnimation`, `TransformAnimation` (`Transform`, `MoveToTarget`), `WaitAnimation`, `PairAnimation`, `GroupAnimation`.

- Chained `.animate.*` calls are emitted as `MoveToTarget` using the final `target_mobject` state. They are never decomposed per method.
- `ReplacementTransform` lowers to `Transform` descriptor + `rebind` command.

### Mobject states

| kind | notes |
|---|---|
| `VMobject` | bezier points as 3n+1 array; multi-subpath serialized as `VGroup` of children |
| `VGroup` | `children: [state_ref, ...]` — uniform representation everywhere |
| `MathTexSource` | latex string + 4 corner points for transform support |
| `ValueTracker` | scalar `value` only; not rendered |

---

## Integration Notes

- `manim-web` animation exports: beware of class-vs-factory shape differences across runtime paths. Keep adapter logic in `player.js` defensive.
- `Rotate` / `ScaleInPlace` constructors in `manim-web` expect options objects. Beware positional arg assumptions.
- Transform cleanup timing: beware null races on `threeObject.visible` if target objects are freed too early.
- Point arrays that are not `3n+1` will raise a JS-side playback error by design.

---

## Testing

### Python (`tests/test_widget.py`)

- Prefer exhaustive deterministic tests asserting full JSON payloads.
- Validate schema compatibility against `spec.json`.
- Validate updater/data frames use `state_ref` indirection (not inline state).

### JS integration (`tests/test_js_integration.py`)

Runs `js/src/test_cli.js` via `bun`. Uses `manim-web` headless mode — no WebGL/Three.js required.

Coverage includes: simple scenes (Create, FadeIn), multi-section navigation, VGroup handling, error conditions (invalid point arrays, missing state refs).

---

## Tooling

- Python: `uv`
- JS deps/build: `bun`
- Widget bridge: `anywidget`

```sh
uv run pytest -q
uv run pytest -q tests/test_widget.py
uv run pytest -q tests/test_js_integration.py
bun run build                        # from js/ — rebuild static bundle
bun run cli < scene-spec.json        # from js/ — manual JS runtime test
```

---

## Repository Structure

```
manim-widget/
  src/manim_widget/
    __init__.py
    widget.py
    renderer.py
    snapshot.py
    static/index.js       # bundled JS runtime
  js/src/
    index.js
    player.js
    registry.js
    test_cli.js
  tests/
    test_widget.py
    test_js_integration.py
  spec.json
  pyproject.toml
  AGENTS.md
```

---

## Implementation Guidelines

- `spec.json` changes first, always.
- Python mobjects are source of truth for end-state; transition hints belong in command metadata.
- Prefer explicit serializer/adapter logic over implicit conversion.
- Preserve deterministic ordering in emitted JSON.
- Keep CLI test mocks contract-accurate with real `manim-web` signatures.
