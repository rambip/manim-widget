# Research Findings

## Architecture Overview

```
construct() → CustomRenderer intercepts play/add/remove → Serializer → JSON → JS widget
```

### Key Classes

| Python Class | Role |
|---|---|
| `manim.Scene` | Base scene, runs `construct()` |
| `CustomRenderer` | Intercepts animations, builds segments |
| `manim.Mobject` | Base mathematical object |
| `manim.VGroup` | Groups mobjects (has children, not points) |
| `manim.ValueTracker` | Tracks numeric value (not VMobject) |

---

## Renderer Call Chain

During `scene.play_internal()`, the renderer iterates through a time progression:

1. For each timestamp `t` in `time_progression`:
   - `scene.update_to_time(t)` is called
   - Then `renderer.render(self, t, self.moving_mobjects)` captures the frame

### `update_to_time()` Details

`scene.update_to_time(t)` is responsible for updating mobject and animation state per frame:

1. For each animation: `animation.update_mobjects(dt)` — triggers updaters on non-animation mobjects
2. Then: `animation.interpolate(alpha)` — interpolates the animation
3. Finally: `scene.update_mobjects(dt)` — runs all mobject updaters recursively

**Key insight**: Updaters run AFTER animation interpolation.

---

## Custom Renderer

`Scene` accepts a `renderer` kwarg. Subclass and override:
- `play(scene, animations)` — intercept animations
- `update_frame(scene, moving_mobjects)` — no-op for dry-run
- `init_scene(scene)` — setup
- `scene_finished(scene)` — finalize

---

## Mobject System

### get_family()

Recursively collects all submobjects including self.

```python
VGroup(Circle(), Circle(), Circle()).get_family()
# [VGroup, Circle, Circle, Circle]  — size 4
```

- Includes self
- Fully recursive
- No deduplication — same object added twice appears twice
- Caching only on `OpenGLMobject`, not base `Mobject`

### Points Data by Type

| Type | has points | is VMobject | family_size |
|---|---|---|---|
| Circle, Square, Line | True | True | 1 |
| Arrow | True | True | 2 (body + tip) |
| Text | False | True | 6 |
| VGroup | False | True | 1 + n_children |
| ValueTracker | True | False | 1 |

`Text` has `points=False` — only opacity and position changes are animatable.

### Transformation Matrix

**Important**: `model_matrix` (4x4 homogeneous transformation matrix) is ONLY available on `OpenGLMobject`. Regular `Mobject` does not store a transformation matrix.

For V1:
- Use `get_center()` for position
- Use `get_points()` for point arrays
- Rotation/scale tracked via side-channel patches

---

## Scene API

```python
Scene.play(*animations, **kwargs)
Scene.add(*mobjects) -> Self
Scene.remove(*mobjects) -> Self
Scene.next_section(name='unnamed', section_type=DefaultSectionType.NORMAL, skip_animations=False)
```

---

## Section System

`next_section()` delegates to `SceneFileWriter.next_section()`, creating a `Section`:

```python
class Section:
    type_: str
    video: str | None
    name: str
    skip_animations: bool
    partial_movie_files: list[str | None]  # one entry per play() call
```

An initial section is created automatically if `play()` is called before any `next_section()`.

### `skip_animations=True` Behavior

When `skip_animations=True`:
- Video rendering is skipped
- **Animation interpolation still runs** — mobjects end up in correct final state
- This means keyframes are still produced

---

## Animation System

### Key Subclasses

| Class | Behavior |
|---|---|
| `Create` | Draws mobject progressively |
| `FadeIn` / `FadeOut` | Opacity transitions |
| `Transform` | Interpolates points from source to target |
| `ReplacementTransform` | Same visually; target enters scene graph after |
| `Succession` | Sequential composition |
| `AnimationGroup` | Parallel composition |
| `Wait` | Passes time, no interpolation |

### `.animate` Construction

`mob.animate.shift(RIGHT)`:
1. Returns an `_AnimationBuilder` instance
2. `generate_target()` is called immediately — creates a copy stored in `mobject.target`
3. Method calls on builder are executed on `target` and recorded
4. On `scene.play(builder)`, `build()` creates a `_MethodAnimation` (subclass of `MoveToTarget`)
5. `finish()` applies methods to original mobject

JSON kind: `"MethodAnimation"`

### Key Attributes

```python
animation.run_time          # duration in seconds
animation.rate_func         # f(t: float) -> float
animation.mobject           # target mobject
animation.starting_mobject  # copy of initial state
```

### Animation Interpolation and Monkey-Patching

`Create`, `FadeIn`, `FadeOut`, `Write` do NOT call `rotate/scale/shift` — they manipulate submobject points directly. The monkey-patches on `VMobject` are sufficient.

---

## Transform vs ReplacementTransform

| Aspect | `Transform` | `ReplacementTransform` |
|---|---|---|
| During animation | Identical | Identical |
| After animation | Source stays in scene, visually = target | Source removed, target added |
| Target in scene graph | No | Yes |

Silent conversion is not safe:

```python
self.play(Transform(circle, square))
self.play(circle.animate.shift(RIGHT))  # works — circle still in scene

self.play(ReplacementTransform(circle, square))
self.play(circle.animate.shift(RIGHT))  # breaks — circle was removed
```

---

## ValueTracker

```python
vt = ValueTracker(0)
vt.get_value()   # 0.0
vt.set_value(5)
```

- Not a `VMobject`
- Value stored at `self.points[0, 0]`
- `get_value()` returns `float(self.points[0, 0])`
- `.animate.set_value()` uses `_AnimationBuilder`, compiled to `Animation` on `scene.play()`

---

## Updaters

Callables attached via `mob.add_updater(fn)`. Two signatures:

```python
lambda mob: ...         # no dt
lambda mob, dt: ...     # with elapsed time
```

During `scene.play()`, execution order per frame:
```
animation.interpolate(alpha) → updaters(dt)
```

Updaters run **after** animation interpolation. `suspend_mobject_updating=True` disables updaters for a given animation (default: `False`).

### Closure Introspection

```python
func.__code__.co_freevars   # names of captured variables
func.__closure__            # cells holding their values
```

Useful to distinguish updaters that depend only on time/constants from those that capture other mobjects.

---

## Dry-Run Mode

Manim has a `dry_run` config path:
- `renderer.render()` bypassed when `skip_rendering=True`
- `SceneFileWriter.write_frame()` bypassed when `write_to_movie=False`
- `Scene.play_internal()` still updates mobject state regardless of rendering flags

This means we can run `construct()` without producing video while still computing mobject state.

---

## manim-web Mobject Kinds

Full list of supported JavaScript constructors in manim-web:

### Core
- `Mobject`, `VMobject`, `VGroup`

### Geometry
- `Circle`, `Line`, `DashedLine`, `CubicBezier`
- `Rectangle`, `Square`, `RoundedRectangle`
- `Polygon`, `Triangle`, `RegularPolygon`, `Hexagon`, `Pentagon`, `Polygram`, `ArcPolygon`
- `Arrow`, `DoubleArrow`, `Vector`, `CurvedArrow`, `CurvedDoubleArrow`
- `Arc`, `ArcBetweenPoints`, `Ellipse`, `Annulus`, `AnnularSector`, `Sector`, `TangentialArc`
- `Dot`, `SmallDot`, `LargeDot`
- `BackgroundRectangle`, `SurroundingRectangle`, `Underline`, `Cross`
- `Angle`, `RightAngle`, `Star`

### Text & LaTeX
- `Text`, `Paragraph`, `MarkupText`
- `MathTex`, `MathTexSVG`, `Tex`
- `DecimalNumber`, `Integer`, `Variable`
- `Code`, `BulletedList`, `Title`, `MarkdownText`

### Graphing
- `NumberLine`, `UnitInterval`
- `Axes`, `NumberPlane`, `ComplexPlane`, `PolarPlane`, `ThreeDAxes`
- `FunctionGraph`, `ImplicitFunction`, `ParametricFunction`
- `BarChart`, `VectorField`, `StreamLines`

### 3D
- `Sphere`, `Cube`, `Box3D`, `Cylinder`, `Cone`, `Torus`
- `Line3D`, `Arrow3D`, `Vector3D`
- `Surface3D`, `ParametricSurface`, `TexturedSurface`
- `Polyhedron`, `Tetrahedron`, `Octahedron`, `Icosahedron`, `Dodecahedron`
- `Prism`, `Dot3D`, `ThreeDVMobject`

### Value Tracking
- `ValueTracker`, `ComplexValueTracker`

### Matrix & Table
- `Matrix`, `IntegerMatrix`, `DecimalMatrix`, `MobjectMatrix`
- `Table`, `MathTable`, `MobjectTable`, `IntegerTable`, `DecimalTable`

### Other
- `Brace`, `BraceBetweenPoints`, `ArcBrace`, `BraceLabel`, `BraceText`
- `SVGMobject`, `VMobjectFromSVGPath`
- `Graph`, `DiGraph`, `GenericGraph`
- `ImageMobject`
- `ScreenRectangle`, `FullScreenRectangle`, `FullScreenFadeRectangle`
- `PointCloudDot`, `Mobject1D`, `Mobject2D`
- `MandelbrotSet`, `NewtonFractal`
- `SampleSpace`, `DiceFace`

---

## manim-web Rate Functions

manim-web has built-in rate functions in `src/rate-functions/index.ts`:

| Python string | JS function |
|---|---|
| `linear` | `linear` |
| `smooth` | `smooth` |
| `rush_into` | `rushInto` |
| `rush_from` | `rushFrom` |
| `slow_into` | `slowInto` |
| `there_and_back` | `thereAndBack` |
| `wiggle` | `wiggle` |
| `ease_in_*` | `easeIn*` |
| `ease_out_*` | `easeOut*` |
| `ease_in_out_*` | `easeInOut*` |

A `RATE_FUNC_MAP` in `py2ts.cjs` translates Python string identifiers to JS functions for compatibility.

---

## Text & MathTex Serialization

- `Text`: `get_center()` works (inherited from Mobject). `points=False` — only opacity/position animatable.
- `MathTex`: LaTeX string retrieved via `self.get_tex_string()`. Rendered in JS via KaTeX.

---

## Serialization Reference

| Concern | Strategy |
|---|---|
| Mobject identity | `id(mobject)` → `short_id` |
| VGroup children | Collect via `get_family()` |
| Text / MathTex | Extract LaTeX string via `get_tex_string()`, render via KaTeX in JS |
| Arrow | Tip is a separate submobject in family |
| Segments | Each `play()` → `{ animations, run_time }` |
| Section boundaries | `next_section()` → new segment group |
| Transform targets | Target geometry inlined in animation payload (target may never have been `add()`ed) |
| Position | `get_center()` — works for all mobjects including Text |
| Transformation matrix | Only `OpenGLMobject` has `model_matrix`. Use `get_center()` for regular mobjects. |
