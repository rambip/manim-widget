# manim-widget Roadmap 

This roadmap tracked V1 implementation and now tracks pre-V2 hardening.

## Current Mission

- Finalize and implement the V2 wire contract before runtime changes.
- Replace mixed inline state payloads with section-local `states` + integer `state_ref` references.
- Keep snapshots as section-entry live state only (no pre-registration semantics).
- Split identity operations from geometry operations (`rebind` command vs transform animation).
- Remove remaining `hidden` semantics from Python/JS runtime and tests.

---

# 0) Ground Rules

- `spec.json` is the wire-format contract between Python and JS.
- If a field changes, update `spec.json` first, then Python/JS.
- No video output in V1; dry-run only.
- Do not call `Scene.next_section()` from our widget override.
- **Rule R1 (Virtual Adds):** The Renderer and Serializer must treat Python Mobjects as read-only during transitions. Any state required for initialization (like starting at 0 opacity for a target mobject) must be encoded as metadata in the JSON command (`hidden`), never by mutating the Python mobject's attributes.

---

# 1) Current State (as of now)

### Passing
- short-id behavior basics
- empty scene JSON envelope
- basic section scaffolding and serializer shape
- renderer compatibility attrs (`time`, `num_plays`, etc.)
- `widget.add` overrides with real typed state
- animate path (`Create`, `FadeIn`, `FadeOut`, `Shift`, `Rotate`, `ReplacementTransform`)
- data path for updater-driven animations
- snapshot and mobject serialization for all supported types
- schema validation against `spec.json`
- lifecycle correctness and snapshot ordering tests
- **JS side implementation (manim-web player)**
- **MobjectRegistry with load/add/remove**
- **Player with snapshot restoration and command execution**
- **anywidget entry point with Play/Pause controls**
- **Smoke test for registry loading**


# 2.5) Consolidation

- [ ] Refresh docs for V1 behavior and known limitations
- [ ] Add regression tests for animation API shape differences (class vs factory export)
- [ ] Fix class-vs-factory handling for other animations (not only `Shift`)
- [ ] Check opacity and color default values
- [ ] Open issues upstream to simplify our edge-cases

---

# 2.6) Issue #2: `.animate` methods not converted to native animations

## Problem
`shape.animate.move_to(destination)` and other `.animate` methods produce `_MethodAnimation` type in JSON instead of native animation types like `Shift`.

## Root Cause
In `renderer.py:_descriptor_from_animation()`, the `methods` attribute of `_MethodAnimation` is iterated to detect animation type. Only `shift`, `rotate`, and `scale` are handled.

## Currently Handled Conversions
| `.animate` method | Output Animation | Notes |
|---|---|---|
| `shift(vector)` | `Shift` | Direct mapping |
| `rotate(angle)` | `Rotate` | Direct mapping |
| `scale(factor)` | `Scale` | Direct mapping |
| `move_to(point)` | `Shift` | Computes `target_center - mobject_center` |

## Analyzed Methods (from testing)
| Method | Can Map To | Shift Vector | Notes |
|---|---|---|---|
| `shift(v)` | `Shift` | `v` | Already works |
| `move_to(p)` | `Shift` | `target_c - mobj_c` | Fixed |
| `next_to(m, d)` | `Shift` | Computed | Works via target-center diff |
| `to_corner(c)` | `Shift` | Computed | Works via target-center diff |
| `to_edge(e)` | `Shift` | Computed | Works via target-center diff |
| `align_to(m, a)` | `Shift` | `[0,0,0]` | Align doesn't move, only aligns |
| `flip()` | **Cannot** | N/A | Changes points, not just position |
| `scale_to_fit_width(w)` | **Cannot** | `[0,0,0]` | Resizes, not moves |
| `scale_to_fit_height(h)` | **Cannot** | `[0,0,0]` | Resizes, not moves |
| `set_width(w)` | **Cannot** | `[0,0,0]` | Resizes, not moves |
| `set_height(h)` | **Cannot** | `[0,0,0]` | Resizes, not moves |

## Methods That Can Use `Shift` (position-only)
These can be converted to `Shift` by computing the vector from `target_mobject.get_center() - mobject.get_center()`:
- `move_to`
- `next_to`
- `to_corner`
- `to_edge`
- `align_to` (when aligned to direction, not edge)

## Methods That Need Fallback to `data` Command
These change geometry (size, shape) not just position:
- `flip` - reflection changes point arrangement
- `scale_to_fit_width`, `scale_to_fit_height` - size changes
- `set_width`, `set_height` - size changes

## Implementation Status
- [x] `move_to` → `Shift` (fixed)
- [ ] `next_to`, `to_corner`, `to_edge`, `align_to` → `Shift` (same pattern)
- [ ] `flip` → fallback to data path or mark unsupported
- [ ] size-changing methods → fallback to data path or mark unsupported

---

# 2) V2 

- Unsupported sections by data-size budget threshold
- `FadeTransformPieces`
- `Restore` support
- `DataCommand` compression
- async/background `construct()`
- Text serialization: `text` and `font_size` fields (blocked by multi-subpath SVG mobjects like Text)
- Remove `kind` from serialized state shape (replace with a clearer discriminator or schema-safe alternative)

## Missing Animations (found in manim-web but not in spec.json)

These animations exist in manim-web but are not yet in the `AnimationType` enum in spec.json:

| Animation | Category | Status |
|---|---|---|
| `FadeTransformPieces` | Transform | V2 |
| `Restore` | Transform | V2 |
| `ApplyPointwiseFunction` | Transform | V2 |
| `ApplyPointwiseFunctionToCenter` | Transform | V2 |
| `ApplyFunction` | Transform | V2 |
| `ApplyMethod` | Transform | V2 |
| `ApplyMatrix` | Transform | V2 |
| `ApplyComplexFunction` | Transform | V2 |
| `MoveToTarget` | Transform/Movement | V2 |
| `MoveToTargetPosition` | Movement | V2 |
| `ComplexHomotopy` | Homotopy | V2 |
| `SmoothedVectorizedHomotopy` | Homotopy | V2 |
| `PhaseFlow` | Homotopy | V2 |
| `TracedPath` | Changing | V2 |
| `AnimatedBoundary` | Changing | V2 |
| `ChangeSpeed` | Speed | V2 |
| `MaintainPositionRelativeTo` | Utility | V2 |
| `ShowPassingFlashWithThinningStrokeWidth` | Indication | V2 |
| `TransformAnimations` | Transform | V2 |
