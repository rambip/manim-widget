# `manim-widget` V1 Roadmap

## Phase 1: Python Engine & Interception ✅

The goal here is to run Manim silently while capturing exact object hierarchy and transforms.

### 1.1: Matrix Trapper (Monkey-Patching) ✅
Manim doesn't inherently store a relative transformation matrix for non-OpenGL mobjects. We must inject one and intercept transformations.
* **Subtask**: Patch `Mobject.__init__` to inject `self._local_matrix = np.eye(4)`.
* **Subtask**: Patch `shift`, `rotate`, and `scale`. Compute the corresponding $4 \times 4$ matrix, multiply it into `_local_matrix`, and call the original method.
* **Tricky Part**: Calling the original method is crucial! Manim's internal layout engines (like `.next_to()`) rely on the actual points array being updated.

### 1.2: The Geometry Sentinel ✅
* **Subtask**: Patch `become`, `apply_function`, `put_start_and_end_on`, and `set_points`.
* **Subtask**: Inside these patches, set `self._dirty_geometry = True`.

### 1.3: Presence Tracking ✅
* **Subtask**: Patch `Scene.add` and `Scene.remove` to maintain a Python `set` of `active_mob_ids`.
* **Tricky Part**: `VGroup.add()` doesn't inherently put things in the Scene; it just parents them. `active_mob_ids` should only track top-level mobjects added to the `Scene` directly, OR recursively track all children of added objects.

---

## Phase 2: Serialization & Dry-Run Custom Renderer ✅

> **Note**: Section snapshots are handled in `ManimWidget` (via `next_section` patching), not in the renderer. The `CaptureRenderer` only handles segment/keyframes.

### 2.1: CaptureRenderer ✅
* **`CaptureRenderer`** (`renderer.py`) replaces `DryRunRenderer`. Tracks `fps`, `time`, sections, segments, keyframes, and a mobject registry (`set[Mobject]`).
* **`Section`**, **`Segment`**, **`Keyframe`** dataclasses store all captured data.
* `init_scene(scene)` — resets all state for a new scene.
* `start_section(name)` — opens a new section.
* `play(scene, *animations, **kwargs)` — the core interception point:
  - Filters out `Wait` animations (no segment created for waits alone).
  - For each real animation, calls `get_all_mobjects()` with `AttributeError` fallback to `anim.mobject` (required for `FadeIn`/`Create` which lack `target_copy`).
  - Tracks mobjects in `registry` and mobjects with updaters in `_updater_mob_ids`.
  - Advances time in `fps`-grained steps, calling `scene.update_mobjects(dt)`.
  - For mobjects with updaters: captures keyframes with position/rotation/scale; checks `_dirty_geometry` to mark section unsupported.
  - Appends segment to current section.
* `update_frame(scene, moving_mobjects, dt)` — updates moving mobjects (not used during capture but required by renderer interface).
* `get_frame()` — no-op (no video output).
* `scene_finished(scene)` — resets time.

### 2.2: Serializer ✅
* **`serialize_scene(fps, mobjects, sections, snapshots)`** (`serializer.py`) — produces the JSON blob.
* `_short_id(int)` — MD5 hash of `str(id(mob))`, truncated to 8 chars.
* `_kind_name(mob)` — `type(mob).__name__`.
* `_get_children_ids(mob)` — short IDs of all members via `get_family()` (excludes self).
* `_build_mobject_entry(mob)` — registry entry with `id`, `kind`, `children`, `tex_string`, `value`.
* `_build_animation_entry(anim)` — uses `get_all_mobjects()` with `AttributeError` fallback; extracts `rate_func` name.
* `_build_segment_entry(segment)` — run_time, animations list, keyframes list.
* `_build_section_entry(section, snapshot)` — name, supported, reason, snapshot, segments.
* Registry expansion: `serialize_scene` walks `mobjects` via `get_family()` to include all nested children in the flat mobject registry.

### 2.3: ManimWidget ✅
* **`ManimWidget`** (`__init__.py`) — subclasses `AnyWidget` and `Scene`.
* `scene_data = traitlets.Unicode("").tag(sync=True)` — the JSON traitlet pushed to JS.
* `_fps`, `_renderer = CaptureRenderer(fps)`, `_snapshots`, `_pending_snapshot`, `_construct_fn`.
* `set_construct_fn(fn)` — registers the user's scene construction function.
* `_on_next_section(name)` — called by patched `Scene.next_section`; captures mobject state snapshot, stores pending.
* `_capture_snapshot()` — iterates renderer registry, captures `get_center()`, `get_fill_opacity()`, `get_color()` per mobject.
* `construct()` — the dry-run orchestrator: applies patches → inits renderer → `next_section("initial")` → calls `construct_fn()` → flushes pending snapshot → serializes → pushes to `scene_data`.

### 2.4: `next_section` Patching ✅
* `_new_scene_next_section` patched onto `Scene.next_section` at module level.
* Calls original `next_section` then invokes `widget._on_next_section(name)`.
* Wired into both `apply_patches()` and `remove_patches()`.

### 2.5: Bugs Found & Fixed During Implementation
* **`has_updaters` doesn't exist** — Manim 3.x uses `get_updaters()` method. Changed `mob.has_updaters` → `bool(mob.get_updaters())`.
* **`FadeIn.get_all_mobjects()` crashes** — `FadeIn` doesn't have `target_copy` attribute. Added `try/except AttributeError` fallback to `anim.mobject` in both `renderer.py` and `serializer.py`.
* **`Wait` creates spurious segments** — `Wait` alone should not create a segment. Filter `Wait` out before creating a segment; skip segment creation entirely if only `Wait` animations are passed.
* **`hashlib.hexlify` doesn't exist** — was a pre-existing bug; `hashlib.md5(...).hexdigest()` is correct.
* **`Section` dataclass** — removed `active_ids`, `pending_ids`, `states` fields per architecture decision; those belong in `ManimWidget._snapshots`.

---

## Phase 3: JavaScript Player (manim-web + Three.js) ✅

Bundled via `bun build` into `static/index.js`, inlined into Python via `_JS_BUNDLE` read at import time.

### 3.1: Scene Graph Reconstruction ✅
* **Subtask**: Parse `mobjects` registry. Instantiate Three.js/manim-web objects.
* **Subtask**: Link parents and children based on the `children` array to form a true Scene Graph.
* **Tricky Part**: Three.js opacity cascading. Group opacity isn't native in basic Three.js materials; you may need to apply opacity recursively to children when animating a `VGroup`'s fade.

### 3.2: Matrix Application ✅
* **Subtask**: Set `mesh.matrixAutoUpdate = false` for all objects.
* **Subtask**: Apply the flat $16$-element array to `mesh.matrix.fromArray()`.
* **Subtask**: Call `mesh.updateMatrixWorld(true)`.

### 3.3: Lifecycle & Section Jumper ✅
* **Subtask**: Implement `loadSection(index)`. Clear the Three.js scene (but keep objects in memory). Read `snapshot.active_ids` and add *only* those to the scene. Set matrices for everything (including pending).

### 3.4: Animation Sequencer ✅
* **Subtask**: Map `animations.kind` to JS functions.
* **Subtask**: For `Create`/`FadeIn`/`Write`: Ensure the `mob_id` is moved from `pending` to the `scene` before interpolation starts.
* **Subtask**: Map Manim's string `rate_func` (e.g., `"smooth"`) to `manim-web`'s rate functions.

### 3.5: Bugs Found & Fixed During Implementation
* **`CaptureRenderer.camera` missing** — Manim's `Scene.get_moving_mobjects()` accesses `self.renderer.camera.use_z_index`. Added `_DummyCamera` class with `use_z_index = False`.
* **`Scene.__init__` with `renderer=None`** — Passing `None` as renderer caused `AttributeError` at `_capture_snapshot()`. Changed to pass `self._renderer` directly.
* **anywidget `_esm` file path** — anywidget resolves `_esm = "path"` relative to the installed package, not the source tree. Solution: read the bundled JS file at import time and inline it as `_esm = _JS_BUNDLE` (a string).

---

## Phase 4: anywidget Integration

### 4.1: The Bridge ✅
* **Subtask**: Create `class ManimWidget(anywidget.AnyWidget, Scene)`.
* **Subtask**: Bind `json_data = traitlets.Unicode("").tag(sync=True)`.

### 4.2: UI Overlay ✅
* **Subtask**: Build a minimal HTML overlay over the WebGL canvas.
* **Subtask**: Add a Play/Pause button and a scrubber.
* **Subtask**: Conditional rendering: If `section.supported === false`, overlay a big red warning banner: *"Section uses unsupported geometry updates. Fallback to video required."*

---

## Phase 5: V2 (Future Pipeline)

- **Asynchronous `construct()`**: Make `construct()` non-blocking. Display widget immediately with a loading state, then push JSON once the dry-run finishes.
- **`Transform` support**: Inline target geometry in the animation payload. Handle temporary mobject lifetimes bounded to a segment.
- **Smarter unsupported detection**: AST analysis of updater bodies for earlier, more precise warnings rather than relying solely on the `_dirty_geometry` runtime flag.
- **Video fallback for unsupported sections**: Automatically trigger the real Cairo/OpenGL renderer for unsupported sections and seamlessly swap the JS canvas for an HTML `<video>` tag.
- **`always_redraw`**: Stream compressed point-array deltas per frame (via MsgPack) instead of hard-failing.
- **Binary serialization**: Replace JSON string passing with MsgPack via `traitlets.Bytes()` to prevent browser memory bloat on complex scenes.
- **marimo integration**: Utilize `marimo`'s reactive graph to auto-trigger the dry-run `construct()` when slider/input cells change.
