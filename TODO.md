# manim-widget Roadmap 

This roadmap tracked V1 implementation and now tracks pre-V2 hardening.

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

# 2) V2 

- Unsupported sections by data-size budget threshold
- `FadeTransformPieces`
- `Restore` support
- `DataCommand` compression
- async/background `construct()`
- Text serialization: `text` and `font_size` fields (blocked by multi-subpath SVG mobjects like Text)
