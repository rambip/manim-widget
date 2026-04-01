# manim-widget Roadmap 

This roadmap is the implementation contract for V1.

It has been updated with concrete behavior confirmed from local Manim internals, current failing tests in this repo, and strategies to preserve Python state purity.

---

## 0) Ground Rules

- `spec.json` is the wire-format contract between Python and JS.
- If a field changes, update `spec.json` first, then Python/JS.
- No video output in V1; dry-run only.
- Do not call `Scene.next_section()` from our widget override.
- **Rule R1 (Virtual Adds):** The Renderer and Serializer must treat Python Mobjects as read-only during transitions. Any state required for initialization (like starting at 0 opacity for a target mobject) must be encoded as metadata in the JSON command (`hidden`), never by mutating the Python mobject's attributes.

---

## 1) Current State (as of now)

### Passing
- short-id behavior basics
- empty scene JSON envelope
- basic section scaffolding and serializer shape

### Failing
- `Scene.play(...)` crashes because custom renderer lacks `time`
- animation interception is still stubbed
- `add.state` is currently `{}` (not a proper `MobjectState`)
- snapshot serialization is still placeholder (`{"id": ...}`)

### Immediate blocker
`Scene.play()` reads `self.time`, which maps to `self.renderer.time`.
Without `renderer.time`, all play-based tests fail before command capture starts.

---

## 2) File Structure

```text
manim-widget/
├── src/
│   └── manim_widget/
│       ├── __init__.py
│       ├── widget.py          # ManimWidget class + section control + add/remove overrides
│       ├── renderer.py        # CaptureRenderer + play interception
│       ├── serializer.py      # serialize_scene(...)
│       ├── snapshot.py        # short_id, build_snapshot, serialize_mobject
│       └── static/
│           └── index.js
├── js/
│   ├── package.json
│   └── src/
│       ├── index.js
│       └── player.js
├── spec.json
└── pyproject.toml
```

---

## 3) V1 Section A - Renderer Compatibility (must do first)

Goal: make custom renderer minimally compatible with `Scene.play` runtime,
without invoking Manim's video/file-writer pipeline.

### A.1 Required renderer fields

Implement in `CaptureRenderer.__init__`:

```python
self.fps = fps
self.time = 0.0
self.num_plays = 0
self.skip_animations = False
self.static_image = None
self.camera = _DummyCamera(use_z_index=False)

self.registry: dict[int, Mobject] = {}
self.sections: list[SectionRecord] = []
self._current: SectionRecord | None = None
```

Notes:
- `time` is mandatory for `Scene.time` property.
- `num_plays` is used in progress labels by Scene internals.
- `skip_animations` influences Scene wait/progression behavior.
- `camera.use_z_index` is required by mobject family extraction paths.

### A.2 Renderer methods

Keep no-op methods for dry mode:

```python
def init_scene(self, scene: Scene) -> None:
    self.time = 0.0
    self.num_plays = 0

def update_frame(self, scene: Scene, moving_mobjects=None, **kwargs) -> None:
    return None

def scene_finished(self, scene: Scene) -> None:
    return None
```

---

## 4) V1 Section B - Animation Interception in `renderer.play`

Goal: one `scene.play(...)` call -> one command record:
- `animate` (no active updater influence)
- `data` (updater-driven frame payload)

### B.1 Compile animations first

Always begin with:

```python
animations = scene.compile_animations(*args, **kwargs)
```

Reason:
- `.animate` gives `_AnimationBuilder`; compile converts to `_MethodAnimation`.
- Descriptor extraction must operate on compiled animation objects.

### B.2 Determine run time and updater route

```python
run_time = scene.get_run_time(animations)
suspend = kwargs.get("suspend_mobject_updating", False)
has_updaters = any(len(m.updaters) > 0 for m in scene.get_mobjects()) and not suspend
```

Route:
- `has_updaters == False` -> animate path
- `has_updaters == True` -> data path

### B.3 Correct lifecycle (critical)

The lifecycle to preserve for each animation:

1. `animation._setup_scene(scene)`
2. `animation.begin()`
3. interpolation/update loop (or direct finish in animate path)
4. `animation.finish()`
5. `animation.clean_up_from_scene(scene)`

Important:
- `Create` registration happens in `_setup_scene`, not `begin`.
- Remover effects (`FadeOut`) finalize in `clean_up_from_scene`.

### B.4 Animate command path

#### B.4.1 Emit pre-commands (Virtual Add Strategy)

Before recording the `animate` command, emit required pre-registration. **Do NOT mutate Python state (like setting `B.opacity = 0`).** Use the `hidden` flag to instruct JS to override the initial state:

- `ReplacementTransform(A, B)` -> `{"cmd": "add", "id": short_id(B), "state": serialize_mobject(B), "hidden": True}`
- `FadeTransform(A, B)` -> emit `add` for B with `hidden=True`
- `TransformFromCopy(A, B)` ->
  - `A_copy = A.copy()`
  - assign `short_id` to `A_copy`
  - emit `add` for `A_copy` with `hidden=False`
  - emit `add` for `B` with `hidden=True`
  
All pre-added mobjects must also be registered in `self.registry`.

#### B.4.2 Build descriptors

Emit one `animate` command:

```python
{
  "cmd": "animate",
  "duration": run_time,
  "animations": [descriptor(anim) for anim in animations],
}
```

Descriptor shape:

```python
{
  "type": type(anim).__name__,
  "id": short_id(anim.mobject),
  "rate_func": RATE_FUNC_NAMES.get(anim.rate_func, "smooth"),
  "params": extract_params(anim),
}
```

#### B.4.3 Advance scene state

For animate-path dry advancement:

```python
for anim in animations:
    anim._setup_scene(scene)
for anim in animations:
    anim.begin()
for anim in animations:
    anim.finish()
for anim in animations:
    anim.clean_up_from_scene(scene)
scene.update_mobjects(0)
```

Then update renderer clock/counter:

```python
self.time += run_time
self.num_plays += 1
```

#### B.4.4 Emit post-commands

Post command table:

- `FadeOut(A)` -> `remove(A)`
- `Uncreate(A)` -> `remove(A)`
- `Unwrite(A)` -> `remove(A)`
- `ReplacementTransform(A, B)` -> `remove(A)`
- `FadeTransform(A, B)` -> `remove(A)`
- `TransformFromCopy(A, B)` -> `remove(A_copy)`

### B.5 Data command path

Tracked mobjects:
- all mobjects with active updaters
- all animation primary mobjects

Initialize scene animation context:

```python
scene.animations = animations
scene.last_t = 0.0
for anim in animations:
    anim._setup_scene(scene)
for anim in animations:
    anim.begin()
```

Frame capture:

```python
n_frames = math.ceil(run_time * self.fps)
frames = []
for i in range(n_frames):
    t = (i + 1) / self.fps
    if t > run_time:
        t = run_time
    scene.update_to_time(t)
    frame = {}
    for mob in tracked:
        entry = {
            "position": mob.get_center().tolist(),
            "opacity": float(mob.get_opacity()),
        }
        pts = mob.get_points()
        if len(pts) > 0:
            entry["points"] = pts.tolist()
        if isinstance(mob, ValueTracker):
            entry["value"] = float(mob.get_value())
        frame[short_id(mob)] = entry
    frames.append(frame)

for anim in animations:
    anim.finish()
for anim in animations:
    anim.clean_up_from_scene(scene)
scene.update_mobjects(0)
```

Emit:

```python
{"cmd": "data", "duration": run_time, "frames": frames}
```

Then:

```python
self.time += run_time
self.num_plays += 1
```

### B.6 Parameter extraction details

Implement `extract_params(anim)` with strict, explicit cases.

1) `_MethodAnimation` (from `.animate`):
- detect `shift`, `rotate`, `scale` from `anim.methods`
- emit normalized params:
  - Shift -> `{"vector": [x, y, z]}`
  - Rotate -> `{"angle": a, "axis": [x, y, z]}`
  - Scale -> `{"scale_factor": s}`
- set descriptor `type` to logical operation (`Shift`/`Rotate`/`Scale`)

2) Transform families:
- `ReplacementTransform`: `target_id = short_id(anim.target_mobject)`
- `Transform`: `target_id = short_id(anim.target_mobject)`
- `FadeTransform`: target is `anim.to_add_on_completion`
- `TransformFromCopy`: **do not** use `anim.target_mobject` blindly because ctor inverts args. Use explicit source/target objects captured during pre-command planning.

3) Other known types:
- `FadeToColor` -> `color`
- `MoveAlongPath` -> `path_id`
- `ChangeDecimalToValue` -> `value`
- `AnimationGroup`/`Succession`/`LaggedStart` -> recursive child descriptors
- `LaggedStart` adds `lag_ratio`
- `Wait` -> no params

---

## 5) V1 Section C - Widget responsibilities (`widget.py`)

### C.1 `next_section`

Maintain current behavior but keep this invariant:
- snapshot stored for section N is state at section entry (before section N commands)

### C.2 `add` and `remove` overrides

`add` must emit full state, not `{}`:

```python
{
  "cmd": "add",
  "id": short_id(mob),
  "state": serialize_mobject(mob),
}
```

`remove`:

```python
{"cmd": "remove", "id": short_id(mob)}
```

`Scene.add/remove` should still be called to mutate Python scene state.

---

## 6) V1 Section D - Snapshot and Mobject serialization (`snapshot.py`)

### D.1 `short_id`

Keep base62 short ids and reset fixture support.

### D.2 `serialize_mobject(mob)`

Produce `MobjectState` variants from `spec.json`:

- VMobject-like:
  - `kind`, `points`, `position`, `opacity`
  - optional: `color`, `fill_color`, `fill_opacity`, `stroke_color`,
    `stroke_width`, `stroke_opacity`, `z_index`
- Text/Paragraph/MarkupText:
  - `kind`, `text`, `position`, `opacity`
  - optional: `color`, `font_size`, `z_index`
- MathTex/Tex:
  - `kind`, `latex`, `position`, `opacity`
  - optional: `color`, `font_size`, `z_index`
- VGroup:
  - `kind: "VGroup"`, `children`, `position`, `opacity`, optional `z_index`
- ValueTracker:
  - `kind: "ValueTracker"`, `value`

### D.3 `build_snapshot(scene)`

Use recursive families and strictly preserve iteration order. Manim uses array order as a fallback for Z-Index (painter's algorithm).

```python
result = {}
for root in scene.mobjects:
    for mob in root.get_family():
        if short_id(mob) not in result: # prevent overriding with same mob later
            result[short_id(mob)] = serialize_mobject(mob)
```

Children of groups are always top-level entries in snapshot map.

---

## 7) V1 Section E - Serializer (`serializer.py`)

Keep simple envelope:

```python
{
  "version": 1,
  "fps": fps,
  "sections": [
    {
      "name": s.name,
      "snapshot": snapshots.get(s.name, {}),
      "construct": s.commands,
    }
    for s in sections
  ],
}
```

V1 does not emit unsupported sections yet.

---

## 8) Chronological Implementation & Testing Plan

*Follow these steps sequentially. Do not proceed to the next step until the tests for the current step pass via `uv run pytest -q`.*

### Step 1: Renderer Compatibility Attrs + No-op Methods (Section A)
* **Action:** Implement `time`, `num_plays`, etc., in `CaptureRenderer`.
* **Tests needed here:**
    * Renderer compatibility smoke test: `self.play(Create(Circle()))` executes with custom renderer without throwing attribute missing errors.

### Step 2: `widget.add` Overrides (Section C)
* **Action:** Ensure `widget.add` emits `cmd=add` with real, typed state. (Uses a mocked or early version of `serialize_mobject`).
* **Tests needed here:**
    * `add` emits `cmd=add` with non-empty structured `state`.

### Step 3: `renderer.play` Compile/Classify + Animate Emission (Section B - Animate Path)
* **Action:** Implement animation compilation, run_time calculation, and `has_updaters=False` logic. Implement Virtual Adds (`hidden=True`).
* **Tests needed here:**
    * `Create` emits one animate descriptor type `Create`.
    * `.animate.shift` emits type `Shift` with vector.
    * `.animate.rotate` emits type `Rotate` with angle.
    * `FadeOut` emits animate descriptor then post-remove command.
    * `ReplacementTransform` emits pre-add target with `hidden=True`, animate descriptor, then post-remove source.

### Step 4: `renderer.play` Data Emission (Section B - Data Path)
* **Action:** Implement `has_updaters=True` logic. Build the frame capture loop.
* **Tests needed here:**
    * Updater scene correctly evaluates to `data` path instead of `animate`.
    * `len(frames) == ceil(duration * fps)`.
    * Data path final-state test: after data command, scene internal state reflects the correct end state.

### Step 5: Snapshots and Mobject Serialization (Section D)
* **Action:** Complete `serialize_mobject` for all supported types and implement `build_snapshot`.
* **Tests needed here:**
    * Lifecycle correctness test: `Create` without prior `add` appears in the *next* section's snapshot (proving `_setup_scene` works).
    * Second section snapshot diverges correctly from the first.
    * Empty scene -> valid envelope, one `initial` section, empty construct.
    * Validate produced payload against `spec.json` via `jsonschema.validate`.
    * Snapshot type coverage for `VGroup`, `MathTex`, `ValueTracker`.
    * Snapshot preserves Z-Index/Painter's algorithm ordering.

---

## 9) Known Pitfalls (do not regress)

- **Do not skip `_setup_scene`**: It is where `Create` gets inserted into `scene.mobjects`.
- **Do not rely on `finish()` for remover effects**: `clean_up_from_scene` performs removals.
- **Do not extract `TransformFromCopy` target blindly**: The constructor inverts args.
- **Do not emit placeholder add state (`{}`)**: JS needs full typed state.
- **Do not use `Scene.next_section` in widget class**.
- **Virtual Add Rule**: The Python mobject is the Source of Truth for the *end* of an animation; the Command Stream is the Source of Truth for the *transition*. Do not mutate Python mobject attributes (like opacity) just to satisfy transition start states.

---

## 10) V2 (unchanged direction)

- Unsupported sections by data-size budget threshold
- `FadeTransformPieces`
- `Restore` support
- `DataCommand` compression
- async/background `construct()`
