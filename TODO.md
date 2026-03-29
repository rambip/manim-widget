# `manim-widget` V1 Roadmap

## Phase 1: Python Engine & Interception

The goal here is to run Manim silently while capturing exact object hierarchy and transforms.

### 1.1: Matrix Trapper (Monkey-Patching)
Manim doesn't inherently store a relative transformation matrix for non-OpenGL mobjects. We must inject one and intercept transformations.
* **Subtask**: Patch `Mobject.__init__` to inject `self._local_matrix = np.eye(4)`.
* **Subtask**: Patch `shift`, `rotate`, and `scale`. Compute the corresponding $4 \times 4$ matrix, multiply it into `_local_matrix`, and call the original method.
* **Tricky Part**: Calling the original method is crucial! Manim's internal layout engines (like `.next_to()`) rely on the actual points array being updated.

```python
# Code Snippet: Matrix Trapper
import numpy as np
from manim.utils.space_ops import rotation_matrix

def patch_transformations(cls):
    orig_init = cls.__init__
    orig_shift = cls.shift
    
    def new_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        self._local_matrix = np.eye(4)
        self._dirty_geometry = False
        
    def new_shift(self, vector, **kwargs):
        m = np.eye(4)
        m[:3, 3] = vector
        self._local_matrix = m @ self._local_matrix
        return orig_shift(self, vector, **kwargs)
        
    # ... similarly for rotate and scale
    
    cls.__init__ = new_init
    cls.shift = new_shift
```

### 1.2: The Geometry Sentinel
* **Subtask**: Patch `become`, `apply_function`, `put_start_and_end_on`, and `set_points`.
* **Subtask**: Inside these patches, set `self._dirty_geometry = True`.

### 1.3: Presence Tracking
* **Subtask**: Patch `Scene.add` and `Scene.remove` to maintain a Python `set` of `active_mob_ids`.
* **Tricky Part**: `VGroup.add()` doesn't inherently put things in the Scene; it just parents them. `active_mob_ids` should only track top-level mobjects added to the `Scene` directly, OR recursively track all children of added objects.

---

## Phase 2: Serialization & Dry-Run Custom Renderer

### 2.1: Building the Registry
* **Subtask**: On `scene_finished`, walk through all mobjects created (using a patched `__new__` or tracking via `init_scene`).
* **Subtask**: Serialize `kind` (class name), `id` (hash/stringified memory address), and `children` IDs (via `get_family()`).
* **Tricky Part**: MathTex parsing. You need to extract `mob.get_tex_string()`. If Manim splits the formula for coloring, V1 might need to fallback to SVG paths if we can't reliably map KaTeX substrings to the exact layout Manim expects.

### 2.2: Section Snapshots
* **Subtask**: Hook into `Scene.next_section()`.
* **Subtask**: Dump the current `active_mob_ids`. Everything else in the registry goes into `pending_ids`.
* **Subtask**: Iterate the registry and dump `matrix`, `color`, and `opacity`.

### 2.3: Segment & Updater Keyframes
* **Subtask**: Override `CustomRenderer.play()`. Inside the time progression loop, for each frame, check mobjects with active updaters.
* **Subtask**: If a mobject with an updater has `_dirty_geometry == True`, abort the keyframe capture and mark the section as `"supported": false`.
* **Subtask**: Otherwise, append the current `_local_matrix` to the keyframes.

```json
// Updated JSON Schema (Matrix + Active/Pending Logic)
{
  "fps": 10,
  "mobjects": [
    { "id": "vg_1", "kind": "VGroup", "children": ["c_1", "c_2"], "tex_string": null }
  ],
  "sections": [
    {
      "name": "setup",
      "supported": true,
      "snapshot": {
        "active_ids": ["vg_1", "c_1", "c_2"],
        "pending_ids": ["sq_1"],
        "states": {
          "c_1": { "matrix": [...], "opacity": 1.0, "color": "#fff" },
          "sq_1": { "matrix": [...], "opacity": 0.0, "color": "#ff0" }
        }
      },
      "segments": [ ... ]
    }
  ]
}
```

---

## Phase 3: JavaScript Player (manim-web + Three.js)

### 3.1: Scene Graph Reconstruction
* **Subtask**: Parse `mobjects` registry. Instantiate Three.js/manim-web objects.
* **Subtask**: Link parents and children based on the `children` array to form a true Scene Graph.
* **Tricky Part**: Three.js opacity cascading. Group opacity isn't native in basic Three.js materials; you may need to apply opacity recursively to children when animating a `VGroup`'s fade.

### 3.2: Matrix Application
* **Subtask**: Set `mesh.matrixAutoUpdate = false` for all objects.
* **Subtask**: Apply the flat $16$-element array to `mesh.matrix.fromArray()`.
* **Subtask**: Call `mesh.updateMatrixWorld(true)`.

### 3.3: Lifecycle & Section Jumper
* **Subtask**: Implement `loadSection(index)`. Clear the Three.js scene (but keep objects in memory). Read `snapshot.active_ids` and add *only* those to the scene. Set matrices for everything (including pending).

```javascript
// Code Snippet: Fast Section Jumping
function loadSection(sectionData, registry) {
    scene.clear();
    
    // Set 'future' state for ALL objects
    for (const [id, state] of Object.entries(sectionData.snapshot.states)) {
        const mob = registry.get(id);
        mob.matrix.fromArray(state.matrix);
        mob.matrixWorldNeedsUpdate = true;
        // material updates...
    }
    
    // Only add active ones to the renderer
    sectionData.snapshot.active_ids.forEach(id => {
        scene.add(registry.get(id));
    });
}
```

### 3.4: Animation Sequencer
* **Subtask**: Map `animations.kind` to JS functions.
* **Subtask**: For `Create`/`FadeIn`/`Write`: Ensure the `mob_id` is moved from `pending` to the `scene` before interpolation starts.
* **Subtask**: Map Manim's string `rate_func` (e.g., `"smooth"`) to `manim-web`'s rate functions.

---

## Phase 4: anywidget Integration

### 4.1: The Bridge
* **Subtask**: Create `class ManimWidget(anywidget.AnyWidget, Scene)`.
* **Subtask**: Bind `json_data = traitlets.Unicode("").tag(sync=True)`.
* **Tricky Part**: `construct()` is blocking. If users run `construct()` in a notebook cell, you want the widget to display *immediately*, show a loading state, and then push the JSON once the dry-run finishes.

### 4.2: UI Overlay
* **Subtask**: Build a minimal HTML overlay over the WebGL canvas.
* **Subtask**: Add a Play/Pause button and a scrubber.
* **Subtask**: Conditional rendering: If `section.supported === false`, overlay a big red warning banner: *"Section uses unsupported geometry updates. Fallback to video required."*

---

## Phase 5: V2 (Future Pipeline)

- **`Transform` support**: Inline target geometry in the animation payload. Handle temporary mobject lifetimes bounded to a segment.
- **Smarter unsupported detection**: AST analysis of updater bodies for earlier, more precise warnings rather than relying solely on the `_dirty_geometry` runtime flag.
- **Video fallback for unsupported sections**: Automatically trigger the real Cairo/OpenGL renderer for unsupported sections and seamlessly swap the JS canvas for an HTML `<video>` tag.
- **`always_redraw`**: Stream compressed point-array deltas per frame (via MsgPack) instead of hard-failing.
- **Binary serialization**: Replace JSON string passing with MsgPack via `traitlets.Bytes()` to prevent browser memory bloat on complex scenes.
- **marimo integration**: Utilize `marimo`'s reactive graph to auto-trigger the dry-run `construct()` when slider/input cells change.
