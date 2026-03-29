# manim-widget — Agent Context

## Vision

There is currently no Jupyter-compatible widget that lets you view and interact with a Manim scene without rendering the whole thing to video first. The goal is a lightweight, interactive widget that uses **manim-web** (Three.js-based) to provide a near-instantaneous authoring experience directly inside a notebook.

Primary target is **marimo**, but must work in any `anywidget`-compatible environment (JupyterLab, VS Code).

---

## Goals (priority order)

### G1 — Speed
Time between "user clicks run" and "animation starts playing" must be minimal. The dry-run (see Architecture) produces a single JSON blob. No video rendering, no round-trips.

### G2 — 3D camera control
JavaScript owns the camera entirely. Users orbit, zoom, and pan in real time via Three.js controls with no Python round-trip.

### G3 — Sections & Segments
Users define sections via `next_section()`. Within sections, `self.play()` calls are recorded as **Segments**. JS handles playback sequencing and section jumping autonomously. Each section carries its own scene snapshot so JS can start from any section without replaying prior ones.

### G4 — Unsupported section warnings
When a section uses unsupported features (geometry-level updaters, `always_redraw`, `Transform`), it is marked as unsupported in the JSON. The widget surfaces a clear inline message. No automatic video fallback in V1.

### G5 — Small JSON & KaTeX
Keep payloads minimal. Ship raw LaTeX strings for `MathTex`, rendered in the browser via KaTeX. No SVG paths unless necessary.

---

## Vocabulary

- **Scene** — The full `construct()` execution.
- **Section** — A named group of segments, delimited by `next_section()`.
- **Segment** — A single `self.play()` or `self.wait()` call. Primary unit of timing.
- **Mobject** — A mathematical object with a stable short ID in a flat registry.
- **VGroup** — A logical collection of Mobject IDs. JS propagates transforms to all children.
- **Dry-run** — Execution of `construct()` at reduced frame rate (default 10 fps, configurable) to collect keyframes without producing video.

---

## Architecture

### Python side

**`widget.py`**: Subclasses `anywidget.AnyWidget` and `manim.Scene`. Runs `construct()` as a dry-run, collects output via the custom renderer, serializes to JSON, pushes via a `Unicode` traitlet.

**`renderer.py`**: Subclasses Manim's renderer. Intercepts `play()`, `wait()`, `add()`, `remove()` to build the Segment and Section lists without writing any video frames.

**`serializer.py`**: Walks the renderer's collected data. Builds the flat Mobject registry via `Mobject.get_family()`. Serializes sections, snapshots, segments, animations, and keyframes.

**Monkey-patching** (applied at widget init, before `construct()`):
- `VMobject.rotate` → accumulates `_track_rotation` side-channel
- `VMobject.scale` → accumulates `_track_scale` side-channel
- `VMobject.shift` / `move_to` → no side-channel needed; position recovered via `get_center()`
- `VMobject.apply_function`, `become`, `put_start_and_end_on` → set `_dirty_geometry = True`

The patches are transparent to the user. Standard Manim code runs unchanged.

### JavaScript side

Receives the JSON blob, parses the flat registry, and drives manim-web.

Builds as a single ESM bundle (`src/manim_widget/static/index.js`) with `manim-web` and `three` inlined (no `--external`), so Python packaging can ship one self-contained widget asset.

**Mobject Registry**: Flat `Map` of all mobjects by ID, including sub-mobjects of VGroups.

**Player**: Sequences segments within a section. Restores scene state from the section snapshot for section jumping.

**Camera**: Three.js OrbitControls, fully autonomous.

---

## Updater Strategy

During the dry-run, updaters are called at each time step (injecting `dt = 1/fps`). After each step, the serializer reads per-mobject state:

| Property | Source |
|---|---|
| `position` | `mob.get_center()` |
| `rotation` | `mob._track_rotation` (side-channel) |
| `scale` | `mob._track_scale` (side-channel) |
| `opacity` | `mob.get_fill_opacity()` |
| `color` | `mob.get_color()` |

If `_dirty_geometry` is set on any mobject touched by an updater, the entire section is marked `"supported": false`.

---

## Supported Animations (V1)

| Animation | Handling |
|---|---|
| `Create`, `FadeIn`, `FadeOut`, `Write` | JS via manim-web |
| `ReplacementTransform` | JS via manim-web |
| `Shift`, `Rotate` via `.animate` | JS via manim-web |
| `Transform` | ❌ Hard error — user redirected to `ReplacementTransform` |
| `always_redraw` | ❌ Section marked unsupported |
| Geometry-level updaters | ❌ Section marked unsupported |

---

## JSON Schema

```json
{
  "fps": 10,
  "mobjects": [
    {
      "id": "a3f",
      "kind": "Circle",
      "matrix": [...],
      "opacity": 1.0,
      "color": "#ffffff",
      "children": [],
      "value": null
    }
  ],
  "sections": [
    {
      "name": "intro",
      "supported": true,
      "snapshot": [
        { "id": "a3f", "matrix": [...], "opacity": 1.0, "color": "#ffffff" }
      ],
      "segments": [
        {
          "run_time": 1.0,
          "animations": [
            { "kind": "Create", "mob_id": "a3f", "rate_func": "smooth" }
          ],
          "keyframes": [
            { "frame": 0, "mob_id": "a3f", "position": [0, 0, 0], "rotation": 0.0, "scale": 1.0 }
          ]
        }
      ]
    },
    {
      "name": "physics",
      "supported": false,
      "reason": "geometry-level update detected on mob_id a3f"
    }
  ]
}
```

**Notes:**
- `mobjects` is the global registry (initial state of all mobjects ever used).
- `snapshot` per section is the **full state** of every mobject — matrix, opacity, color. JS restores this to begin playback from any section without replaying prior ones.
- `keyframes` are only emitted for mobjects that have active updaters in that segment.
- `kind` drives which manim-web constructor JS calls. Known kinds: `Circle`, `Square`, `Line`, `Arrow`, `Text`, `MathTex`, `VGroup`, `ValueTracker`.

---

## Manim Internals Reference

### Renderer interface
Custom renderer subclasses Manim's base renderer and overrides:
- `play(scene, animations)` — record segment
- `update_frame(scene, moving_mobjects)` — no-op (no video)
- `init_scene(scene)` — setup
- `scene_finished(scene)` — finalize

### Mobject points data

| Type | has points | is VMobject | family_size |
|---|---|---|---|
| Circle, Square, Line | True | True | 1 |
| Arrow | True | True | 2 (body + tip) |
| Text | False | True | 6 |
| VGroup | False | True | 1 + n_children |
| ValueTracker | True | False | 1 |

`Text` has `points=False` — cannot be point-animated, only opacity/position.

### ValueTracker
- Is `Mobject` but NOT `VMobject`. Value stored in `points` array.
- `.animate.set_value()` uses `_AnimationBuilder`, compiled to `Animation` on `scene.play()`.

### Transform vs ReplacementTransform
- Visually identical during animation.
- After: `Transform` keeps source in scene graph (now visually = target). `ReplacementTransform` swaps source for target in scene graph.
- Silent conversion is **not safe** — breaks subsequent `source.animate.X()` calls.
- V1 strategy: hard error on `Transform`, require `ReplacementTransform`.

---

## Repository Structure

```
manim-widget/
  js/
    src/
      index.js       ← anywidget entry point
      registry.js    ← flat mobject Map
      player.js      ← segment sequencer, section jumping
    package.json     ← manim-web, three, katex
  python/
    manim_widget/
      __init__.py
      widget.py
      renderer.py
      serializer.py
    tests/
  pyproject.toml     ← uv, bundles js/dist/
  AGENTS.md
  TODO.md
```

---

## Tooling

| Concern | Tool |
|---|---|
| Python package manager | uv |
| JS bundler | bun |
| JS rendering | manim-web + three + katex |
| Widget bridge | anywidget |

---

## Style

- **Python**: PEP 8, strict type hints.
- **JS**: ES2020, no semicolons, readable over concise.
- **Logic**: If a transformation can be computed in JS, do it there.

---

## Reference Repositories

- **maloyan/manim-web** — Three.js Manim clone. `tool/py2ts.cjs` transpiler, mobject hierarchy, KaTeX/MathJax rendering.
- **ManimCommunity/manim** — Python side. `Mobject.get_family()`, OpenGL/Cairo renderer, `next_section()`, `ValueTracker`, rate functions.
