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
- **Command stream** (`construct`): ordered section operations — `register`, `remove`, `rebind` and the more complex `animate`.
- **Dry-run**: execute scene logic to capture playback data only; no video output.

---

## Architecture

### Python (`src/manim_widget/`)

- **`widget.py`** — Defines `ManimWidget` and the `data` trait payload (`SceneData`). Owns section lifecycle, emits section snapshots and command streams. Uses renderer registry for section-entry snapshots.
- **`renderer.py`** — Custom capture renderer integrated with Manim's `Scene.play` lifecycle. Emits commands and animation descriptors. Maintains per-section deduplicated state banks and allocates `state_ref` values. Handles `rebind` for replacement-style transforms.
- **`snapshot.py`** — Short-id generation and mobject serialization primitives.

### JavaScript (`js/src/`) — **edit source here, never `src/manim_widget/static/index.js` directly**

- **`index.js`** — anywidget entry point. Creates scene, registry, player, wires controls.
- **`registry.js`** — Runtime mobject registry keyed by stable IDs.
- **`player.js`** — Restores section snapshots and executes command streams. Resolves `state_ref` through `section.states` before restoring mobjects. Animation adapter must handle both constructor-style and factory-style exports from `manim-web`.
- **`test_cli.js`** — CLI integration test entry point. Uses `happy-dom` for a browser-like environment and `manim-web` headless mode (scene graph only, no pixel output). Reads scene spec from stdin; always outputs `sectionIds` (registry + scene IDs per section) and `sectionEndStates` in the result JSON.

### Bundled runtime (`src/manim_widget/static/index.js`)

Built from `js/src/*` via Bun with the typia transform applied. This is what packaged widget users execute. Rebuild after any JS source change with `cd js && bun run build.ts`.

### manim-web

`manim-web` is a git submodule at `manim-web/` (repo root). **Always read its source from `manim-web/src/`, never from `js/node_modules/manim-web/`.** The node_modules copy is a build artifact and may be stale. Upstream PRs are sent when bugs are found. The JS side of `manim-widget` may eventually move into `manim-web` directly, making the JSON spec a first-class concept there.

---

## Data Contract

`spec.json` is the single source of truth. When changing payload shape: update `spec.json` first, then code, then tests.

### Top-level shape

```json
{
  "version": 2,
  "states": [ { "kind": "VMobject", ... }, ... ],
  "sections": [ ... ]
}
```

- `states`: global deduplicated bank shared across all sections. All commands, frames, and snapshots reference entries by integer index.

### Section

```json
{
  "name": "intro",
  "snapshot": { "mob_id": 0 },
  "construct": [ ... ]
}
```

- `snapshot`: `mob_id → state_ref` into the global `states` bank, for all root mobjects at section entry. Group children are **not** listed separately — they are referenced via `GroupState.children`.
- `construct`: ordered command list.

### Commands

| cmd | purpose |
|---|---|
| `register` | bind `id → state_ref` in scene graph and show in scene |
| `remove` | free `id` from registry (emitted after `FadeOut`, `ReplacementTransform`) |
| `rebind` | remap `source_id → target_id` (emitted after `ReplacementTransform`) |
| `animate` | one `scene.play()` with no active mobject updaters; contains animation descriptors |
| `updater` | one `scene.play()` where at least one mobject or `camera.frame` has active updaters; contains a `frames` array (one entry per FPS tick) where each frame maps `mob_id → {state_ref}` |

The special id `#camera` is used in both `snapshot` and `updater` frames to carry `CameraState`. In `animate` commands, camera changes are emitted as a `MoveToTarget` descriptor with `id: "#camera"`. `#camera` is not a real mobject — it routes to `_applyCameraState` in the JS player.

### Animation descriptors

Families: `SimpleAnimation`, `TransformAnimation` (`Transform`, `MoveToTarget`), `WaitAnimation`, `PairAnimation`, `GroupAnimation`.

- Chained `.animate.*` calls are emitted as `MoveToTarget` using the final `target_mobject` state. They are never decomposed per method.
- `ReplacementTransform` lowers to `Transform` descriptor + `rebind` command.

### Mobject states

| kind | notes |
|---|---|
| `VMobject` | bezier points as 3n+1 array; multi-subpath serialized as `Group` of children |
| `Group` | `children: [state_ref, ...]` — uniform representation for VGroup and Arrow |
| `MathTexSource` | latex string + 4 corner points for transform support |
| `ValueTracker` | scalar `value` only; not rendered |
| `Camera` | `{points: [UL,UR,DR,DL], focal_distance}` — camera frame corners; `focal_distance==0` means 2D |
| `Derived` | `{from: state_ref, points?}` — positional overlay referencing a content state (used for ImageMobject placement) |

---

## Integration Notes

- `manim-web` animation exports: beware of class-vs-factory shape differences across runtime paths. Keep adapter logic in `player.js` defensive.
- `Rotate` / `ScaleInPlace` constructors in `manim-web` expect options objects. Beware positional arg assumptions.
- Transform cleanup timing: beware null races on `threeObject.visible` if target objects are freed too early.
- Point arrays that are not `3n+1` will raise a JS-side playback error by design.
- `_applyState` must apply points based on capability (`setPoints3D`) rather than `state.kind === "VMobject"`. Arrow/VGroup restore creates a body VMobject from VGroup state points; kind-gating drops body points and renders only tips.
- Headless JS tests (`happy-dom`) can hang if image loading promises never resolve. Keep image-finalization logic non-blocking (timeouts/fallbacks) in `player.js`.
- `JSRunner` pre-builds `test_cli.js` into `js/node_modules/.cache/manim-widget-test/` once per session.
- Renderer command emission should prefer behavior/animation semantics over concrete class checks. Class-targeting can miss valid intro-animation mobjects (e.g., non-VMobject types).
- Player ordering for textured/async mobjects matters: apply serialized geometry/state mutations before `scene.add(...)`. Mutating after add may only change logical state (`bbox`, `scaleVector`) without immediate visible sync in `manim-web` async render paths (e.g., `MathTexImage`).

---

## Testing

### Python (`tests/test_widget.py`)

- Prefer exhaustive deterministic tests asserting full JSON payloads.
- Validate schema compatibility against `spec.json`.
- Validate updater/data frames use `state_ref` indirection (not inline state).

### JS integration (`tests/test_js_integration.py`)

Uses `tests/js_runner.py` (`check(SceneClass)` / `check_data(scene_data)`) to validate scenes through `js/src/test_cli.js` headlessly. If you need more debug info, extend `test_cli.js` and `JSResult` — don't add Python-side logging.

Coverage includes: simple scenes (Create, FadeIn), multi-section navigation, VGroup handling, error conditions (invalid point arrays, missing state refs), and ImageMobject intro animation playback.

Runtime note: this suite is relatively slow (often around ~1 minute locally). Use reasonable command/test timeouts to avoid false hangs/failures.

### Examples (`examples/`)

**No star imports.** Marimo forbids `from manim import *`. Always import names explicitly: `from manim import Circle, Create, DEGREES, ...`.

Each example is a marimo notebook that must define at least one `test_*` function taking a `runner` fixture. The `runner` fixture is provided by the root `conftest.py` and wraps `JSRunner`. Run with:

```sh
uv run pytest -q examples/*.py
```

A pre-commit hook (`scripts/check_example_tests.py`) enforces that every marimo example has a test function. `JSRunner._strip_timing()` collapses animation durations to one frame before headless runs — tests validate correctness, not timing.

---

## Tooling

- Python: `uv`
- JS deps/build: `bun`
- Widget bridge: `anywidget`

```sh
uv run pytest -q tests/test_widget.py
uv run pytest -q tests/test_js_integration.py
uv run pytest -q examples/*.py
```

### JS build and CLI test

**All bun commands must be run from `js/`** — `tsconfig.json` and node_modules live there.

Both build scripts use `conditions: ["source"]`, which resolves `manim-web` directly from `manim-web/src/` (the `"source"` export condition in its `package.json`). No separate manim-web build step is needed.

**Production bundle** — rebuilds `src/manim_widget/static/index.js`:
```sh
cd js && bun run build.ts
```

**Test bundle** — rebuilds `js/node_modules/.cache/manim-widget-test/test_cli.js`:
```sh
cd js && bun run build-test.ts
```
`JSRunner.__init__` calls this automatically, so running the Python test suite rebuilds it as needed. Set `MANIM_WIDGET_JS_DEBUG=1` to skip bundling and run against TypeScript source directly for readable stack traces.

To validate a scene from the command line:

```sh
uv run python tests/js_runner.py examples/boolean_operations.py BooleanOperations
uv run python tests/js_runner.py --json < scene.json   # pre-serialized JSON on stdin
```

Marimo notebooks work the same way — pass the `.py` file and the class name defined inside it:

```sh
uv run python tests/js_runner.py examples/polygon_on_axes.py PolygonOnAxes
uv run python tests/js_runner.py examples/point_with_trace.py PointWithTrace
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
    js_runner.py
  examples/               # marimo notebooks; each must have a test_* function
  scripts/
    check_example_tests.py  # pre-commit hook
  conftest.py             # pytest session fixture (JSRunner)
  spec.json
  pyproject.toml
  AGENTS.md
```

---

## PEP 316 Contract Syntax

Invariants are expressed in docstrings. The checker is optional; the docstrings serve as machine-readable specs for Hypothesis tests and human reviewers.

```python
def sort(a: list[int]) -> None:
    """Sort a list in-place.

    pre: isinstance(a, list)
    post[a]: forall(range(len(a) - 1), lambda i: a[i] <= a[i + 1])
    post[a]: len(a) == len(__old__.a)
    post[a]: forall(__old__.a, lambda x: a.count(x) == __old__.a.count(x))
    """

def intern(self, state: MobjectState) -> int:
    """Insert or return dedup'd index.

    pre: self._current is not None
    post: 0 <= __return__ < len(self._current.states)
    post: self.intern(state) == self.intern(state)                   # idempotent
    post: implies(__return__ == len(__old__.self._current.states),   # new entry only
                  len(self._current.states) == len(__old__.self._current.states) + 1)
    """
```

Key rules:
- `pre:` / `post:` — standard precondition / postcondition.
- `post[var]:` — postcondition that may side-effect `var` (use when the function mutates something).
- `__return__` — the return value inside a `post:` clause.
- `__old__` — snapshot of `self` (or any binding) captured before the call; access via `__old__.attr`.
- `implies(cond, expr)` — logical implication; `expr` is only checked when `cond` is true.
- `forall(iterable, predicate)` — universal quantifier; equivalent to `all(predicate(x) for x in iterable)`.
- Do **not** write `cond implies expr` (plain text); always use the `implies()` function form.
- Pydantic field validators encode structural invariants (point format, enum literals); PEP 316 clauses encode semantic / relational ones that span across call sites.

---

## Implementation Guidelines

- `spec.json` changes first, always.
- Python mobjects are source of truth for end-state; transition hints belong in command metadata.
- Prefer explicit serializer/adapter logic over implicit conversion.
- Preserve deterministic ordering in emitted JSON.
- Keep CLI test mocks contract-accurate with real `manim-web` signatures.
