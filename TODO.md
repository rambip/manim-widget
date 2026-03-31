# manim-widget Roadmap

---

## File Structure

```
manim-widget/
├── src/
│   └── manim_widget/
│       ├── __init__.py        # exports ManimWidget
│       ├── widget.py          # ManimWidget class
│       ├── renderer.py        # CaptureRenderer
│       ├── serializer.py      # serialize_scene() and MobjectState builders
│       └── snapshot.py        # build_snapshot(), called at section boundaries
│       └── static/
│           └── index.js       # Built JS bundle (output of bun build)
├── js/
│   ├── package.json
│   └── src/
│       ├── index.js           # anywidget glue: receives scene_data, mounts player
│       └── player.js          # Scene instantiation, command executor, section UI
├── spec.json                  # JSON Schema — source of truth for the wire format
├── ROADMAP.md
└── pyproject.toml
```

`spec.json` is the contract between Python and JS. Any field added to the wire
format must be reflected there first.

No monkey-patching is needed. Animation parameters are extracted directly from
animation objects (see Section 2). Geometry is read via `get_points()` and
`get_center()` after each frame.

---

## JS package.json

```json
{
  "name": "manim-widget-js",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "bun build src/index.js --minify --format=esm --outdir=../src/manim_widget/static --naming-pattern=[name].js"
  },
  "dependencies": {
    "katex": "^0.16.22",
    "manim-web": "^0.3.16",
    "three": "^0.180.0"
  }
}
```

---

## V1

### Section 1 — `CaptureRenderer`

**Step 1.1 — Data structures**

```python
# renderer.py

class SectionRecord:
    name: str
    commands: list[dict]  # AddRecord | RemoveRecord | AnimateRecord | DataRecord

class CaptureRenderer:
    def __init__(self, fps: int):
        self.fps = fps
        self.registry: dict[int, Mobject] = {}  # id(mob) -> mob
        self.sections: list[SectionRecord] = []
        self._current: SectionRecord | None = None

    def open_section(self, name: str) -> None:
        self._current = SectionRecord(name=name, commands=[])
        self.sections.append(self._current)

    def init_scene(self, scene) -> None:
        pass

    def update_frame(self, scene, moving_mobjects=None, **kwargs) -> None:
        pass

    def scene_finished(self, scene) -> None:
        pass

    def play(self, scene, *args, **kwargs) -> None:
        # See Section 2.
        pass
```

**Step 1.2 — `ManimWidget`**

```python
# widget.py

class ManimWidget(AnyWidget, Scene):
    scene_data = traitlets.Unicode("").tag(sync=True)

    def __init__(self, fps: int = 10, **kwargs):
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)
        self._snapshots: dict[str, dict] = {}
        self._pending_snapshot: dict | None = None

        AnyWidget.__init__(self)
        Scene.__init__(self, renderer=self._renderer, **kwargs)

        self._renderer.init_scene(self)
        self.next_section("initial")
        self.construct()

        if self._pending_snapshot is not None:
            self._snapshots[self._pending_snapshot["name"]] = \
                self._pending_snapshot["snapshot"]

        data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            snapshots=self._snapshots,
        )
        self.scene_data = json.dumps(data)

    def next_section(self, name: str = "unnamed", **kwargs) -> None:
        if self._pending_snapshot is not None:
            self._snapshots[self._pending_snapshot["name"]] = \
                self._pending_snapshot["snapshot"]
        self._pending_snapshot = {"name": name, "snapshot": build_snapshot(self)}
        self._renderer.open_section(name)
        # Do NOT call Scene.next_section — we don't want video file output.

    def add(self, *mobjects):
        for mob in mobjects:
            self._renderer._current.commands.append({
                "cmd": "add",
                "id": short_id(mob),
                "state": serialize_mobject(mob),
            })
        Scene.add(self, *mobjects)

    def remove(self, *mobjects):
        for mob in mobjects:
            self._renderer._current.commands.append({
                "cmd": "remove", "id": short_id(mob),
            })
        Scene.remove(self, *mobjects)
```

**What goes in renderer vs widget:**
- **Renderer**: intercepts `play()`, maintains `registry`, classifies and emits
  `animate`/`data` commands, runs the dry animation loop.
- **Widget**: owns `_snapshots`, overrides `next_section()`, `add()`, `remove()`
  to emit commands for direct scene graph mutations outside of `play()`.

**Tests for Section 1:**
- Instantiating `ManimWidget` with an empty `construct()` produces valid JSON
  with one section named `"initial"` and an empty `construct` list.
- `next_section("foo")` produces two sections; the second snapshot reflects
  the state after the first section's animations.
- `self.add(circle)` outside `play()` emits an `AddCommand` in `construct`.

---

### Section 2 — Animation interception

**Step 2.1 — Compiling animations**

The `.animate` builder syntax produces `_AnimationBuilder` objects, not
`Animation` objects. Call `scene.compile_animations()` at the top of `play()`
to resolve all builders into proper `Animation` instances before doing anything
else:

```python
def play(self, scene, *args, **kwargs):
    animations = scene.compile_animations(*args, **kwargs)
    ...
```

`compile_animations` calls `prepare_animation()` on each argument, which
converts any `_AnimationBuilder` (i.e. `mob.animate.shift(RIGHT)`) into a
`_MethodAnimation`. After this call, every element in `animations` is a plain
`Animation` with `.mobject`, `.run_time`, and inspectable attributes.
All param extraction in Steps 2.2 and 2.3 operates on this compiled list.

**Step 2.2 — Classify the call**

```python
has_updaters = any(
    len(mob.updaters) > 0
    for mob in scene.get_mobjects()
) and not kwargs.get("suspend_mobject_updating", False)
```

`has_updaters=True` → `DataCommand` path (Step 2.4).
Otherwise → `AnimateCommand` path (Step 2.3).

**Step 2.3 — `AnimateCommand` path**

For each animation, build a descriptor:

```python
{
    "type": type(anim).__name__,
    "id": short_id(anim.mobject),
    "rate_func": RATE_FUNC_NAMES[anim.rate_func],  # reverse lookup dict
    "params": extract_params(anim),
}
```

Emit pre-commands before the `AnimateCommand`:

| Animation | Pre-command |
|---|---|
| `ReplacementTransform(A, B)` | `add(B, opacity=0)` |
| `TransformFromCopy(A, B)` | `add(A_copy, opacity=1)`, `add(B, opacity=0)` |
| `FadeTransform(A, B)` | `add(B, opacity=0)` |

Emit the `AnimateCommand`.

Advance mobject state to end of animation in dry mode:

```python
for anim in animations:
    anim.begin()
    anim.finish()
scene.update_mobjects(0)
```

Emit post-commands after the `AnimateCommand`:

| Animation | Post-command |
|---|---|
| `FadeOut(A)` | `remove(A)` |
| `Uncreate(A)` | `remove(A)` |
| `Unwrite(A)` | `remove(A)` |
| `ReplacementTransform(A, B)` | `remove(A)` |
| `TransformFromCopy(A, B)` | `remove(A_copy)` |
| `FadeTransform(A, B)` | `remove(A)` |

Param extraction per animation type:

| Animation | Params | Source |
|---|---|---|
| `Shift` / `Rotate` / `Scale` | `vector` / `angle`+`axis` / `scale_factor` | recorded method args on `_MethodAnimation` |
| `Transform`, `ReplacementTransform`, `TransformFromCopy`, `FadeTransform` | `target_id` | `short_id(anim.target)` |
| `FadeToColor` | `color` | `anim.color.to_hex()` |
| `MoveAlongPath` | `path_id` | `short_id(anim.path)` |
| `ChangeDecimalToValue` | `value` | `anim.target_number` |
| `AnimationGroup`, `Succession`, `LaggedStart` | `animations` (recursive) | `anim.animations` |
| `LaggedStart` | also `lag_ratio` | `anim.lag_ratio` |
| `Wait` and all others | *(none)* | — |

**Step 2.4 — `DataCommand` path**

Determine tracked mobjects: all mobjects with non-empty `.updaters` plus all
animation target mobjects. Register new ones in `self.registry`.

Run frame by frame:

```python
n_frames = ceil(run_time * self.fps)
frames = []
for i in range(n_frames):
    scene.update_to_time(i / self.fps)
    frame = {}
    for mob in tracked_mobjects:
        entry = {"position": mob.get_center().tolist(),
                 "opacity": mob.get_opacity()}
        pts = mob.get_points()
        if len(pts) > 0:
            entry["points"] = pts.tolist()
        if isinstance(mob, ValueTracker):
            entry["value"] = mob.get_value()
        frame[short_id(mob)] = entry
    frames.append(frame)
scene.update_to_time(run_time)  # advance to final state for subsequent snapshots
```

Emit:
```python
{"cmd": "data", "duration": run_time, "frames": frames}
```

Note: `scene.update_to_time(t)` may not be directly accessible from inside
`renderer.play()` since we bypass the normal render loop. If needed, call
`animation.interpolate(alpha)` and `scene.update_mobjects(dt)` manually per
frame as a fallback.

**Tests for Section 2:**
- `self.play(Create(circle))` emits one `animate` command with `type: "Create"`.
- `self.play(circle.animate.shift(RIGHT))` emits `type: "Shift"` with correct
  `vector` param after builder compilation.
- `self.play(FadeOut(circle))` emits `animate` then `remove`.
- `self.play(ReplacementTransform(A, B))` emits `add(B, opacity=0)` then
  `animate` then `remove(A)`.
- A play call where any mobject has updaters emits `data` not `animate`.
- `DataCommand` frame count equals `ceil(run_time * fps)`.

---

### Section 3 — Mobject registry and ID assignment

**Step 3.1 — `short_id`**

```python
_id_map: dict[int, str] = {}
_counter = 0

def short_id(mob: Mobject) -> str:
    key = id(mob)
    if key not in _id_map:
        global _counter
        _id_map[key] = base62_encode(_counter)
        _counter += 1
    return _id_map[key]
```

`id(mob)` is stable for the duration of `construct()` because `registry` holds
references, preventing GC from reusing the same address.

**Tests for Section 3:**
- Same mobject always gets the same short ID within one run.
- Two different mobjects never share an ID.
- IDs are short strings (≤ 4 chars for typical scenes).

---

### Section 4 — Snapshot and serialization

**Step 4.1 — `build_snapshot`**

Iterates `scene.mobjects` recursively via `get_family()` and serializes each
into a `MobjectState` dict keyed by `short_id(mob)`.

Serialization per type (all fields defined in `spec.json`):

| Kind | Key fields |
|---|---|
| VMobject subtypes | `points`, `position`, `color`, `fill_color`, `fill_opacity`, `stroke_color`, `stroke_width`, `stroke_opacity`, `opacity`, `z_index` |
| Text / MarkupText / Paragraph | `text`, `position`, `opacity`, `color`, `font_size` |
| MathTex / Tex | `latex` (via `get_tex_string()`), `position`, `opacity`, `color`, `font_size` |
| VGroup | `children` (list of `short_id` for direct submobjects), `position`, `opacity` |
| ValueTracker | `value` (via `get_value()`). Not rendered; included for updater cross-references |

VGroup children are always independently present as top-level entries in the
same snapshot.

**Step 4.2 — `serialize_scene`**

```python
def serialize_scene(fps, sections, snapshots) -> dict:
    return {
        "version": 1,
        "fps": fps,
        "sections": [
            {
                "name": s.name,
                "snapshot": snapshots.get(s.name),
                "construct": s.commands,
            }
            for s in sections
        ]
    }
```

**Unsupported sections** are not implemented in V1. They will be introduced in
V2 when the updater data budget check is added. For now, all sections are
emitted regardless of complexity.

**Tests for Section 4:**
- Output validates against `spec.json` using `jsonschema.validate()` — this
  should be run after every integration test.
- Snapshot of an empty scene is `{}`.
- Snapshot of `VGroup(circle, square)` contains three entries: the group and
  both children.
- `MathTex(r"e^{i\pi}+1=0")` snapshot contains `latex` string, not SVG paths.
- After `FadeOut(circle)`, circle is absent from the next section's snapshot.

---

### Section 5 — JS widget

**Step 5.1 — `index.js` (anywidget glue)**

Minimal entry point. Receives `scene_data` from the Python model, parses it,
and hands it to the player:

```js
// index.js
import { mountPlayer } from './player.js';

export function render({ model, el }) {
    const data = JSON.parse(model.get('scene_data'));
    mountPlayer(el, data);
    model.on('change:scene_data', () => {
        const updated = JSON.parse(model.get('scene_data'));
        mountPlayer(el, updated);
    });
}
```

**Step 5.2 — `player.js` (scene + command executor)**

`mountPlayer(el, data)` is responsible for everything visual:

1. Instantiate a manim-web `Scene` with a Three.js canvas, append to `el`.
2. Build a section index. Render a navigation bar listing section names.
3. Auto-play the first section by calling `executeSection(sections[0])`.

`executeSection(section)`:

1. Clear the scene.
2. Cold-start from `section.snapshot`: for each entry, instantiate the correct
   manim-web class by `kind`, apply all state fields, add to scene.
3. Walk `section.construct` and dispatch by `cmd`:
   - `add`: instantiate mobject, apply state, register in local map.
   - `remove`: remove from scene, delete from map.
   - `animate`: call `await scene.play(...)` with the appropriate manim-web
     animation constructors. Transform animations look up the pre-registered
     target by `target_id`. Composition types (`AnimationGroup`, `Succession`,
     `LaggedStart`) are built recursively from their `animations` param.
   - `data`: drive the scene frame by frame via `requestAnimationFrame`,
     applying each `FrameState` to the mobject directly (points, position,
     opacity, value).

**Step 5.3 — Camera**

Attach Three.js `OrbitControls` to the manim-web camera after scene init.
Python never touches the camera in V1.

**Tests for Section 5:**
- Mounting with a minimal valid JSON renders a canvas without errors.
- Clicking a section name cold-starts that section without JS errors.
- A `data` command with N frames drives exactly N `requestAnimationFrame`
  updates.

---

### Section 6 — End-to-end integration tests

Run these after all sections are wired together. Each test validates the emitted
JSON with `jsonschema` before checking visual behaviour.

**E2E 1 — Create + shift + FadeOut**
```python
class S(ManimWidget):
    def construct(self):
        c = Circle()
        self.play(Create(c))
        self.play(c.animate.shift(RIGHT))
        self.play(FadeOut(c))
```
Check: three `animate` commands, final `remove`, validates against spec,
renders in marimo.

**E2E 2 — ReplacementTransform**
```python
class S(ManimWidget):
    def construct(self):
        a, b = Circle(), Square()
        self.add(a)
        self.play(ReplacementTransform(a, b))
        self.play(b.animate.shift(UP))
```
Check: `add(B, opacity=0)` before animate, `remove(A)` after, B animates
correctly afterward.

**E2E 3 — Updater / ValueTracker**
```python
class S(ManimWidget):
    def construct(self):
        vt = ValueTracker(0)
        dot = Dot()
        dot.add_updater(lambda m: m.move_to(RIGHT * vt.get_value()))
        self.add(dot)
        self.play(vt.animate.set_value(3))
```
Check: `data` command emitted (not `animate`), frame count =
`ceil(run_time * fps)`, dot position varies across frames.

**E2E 4 — Multi-section jump**
```python
class S(ManimWidget):
    def construct(self):
        self.play(Create(Circle()))
        self.next_section("second")
        self.play(Create(Square()))
```
Check: two sections with independent snapshots, clicking "second" in JS
cold-starts from the correct state without replaying section one.

**E2E 5 — MathTex**
```python
class S(ManimWidget):
    def construct(self):
        t = MathTex(r"e^{i\pi}+1=0")
        self.play(Write(t))
```
Check: snapshot contains `latex` string, no SVG paths, KaTeX renders correctly
in JS.

---

## V2

- **Unsupported sections**: after collecting frames for a `DataCommand`, compute
  payload size (`n_frames × n_mobjects × avg_points × 24 bytes`). If it exceeds
  a configurable threshold (default 2 MB), mark the section `unsupported` with
  reason `"updater data exceeds budget (X MB)"` and emit `snapshot: null,
  construct: []`. JS renders an inline warning banner for these sections.

- **`FadeTransformPieces`**: submobject-level cross-fade. Implement after
  `FadeTransform` is stable.

- **`Restore`**: capture saved state at `mob.save_state()` call time, store as
  an invisible pre-registered mobject, treat `Restore` as `Transform` to that
  saved state.

- **Compression for `DataCommand`**: omit frames where all values are within
  tolerance of the previous frame; JS holds the last known value until the next
  explicit frame.

- **Asynchronous `construct()`**: run `construct()` in a background thread,
  emit the widget immediately with a loading spinner, push `scene_data` when
  done. Requires thread-safe traitlet updates and graceful error surfacing.
