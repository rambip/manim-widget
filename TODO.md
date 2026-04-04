# manim-widget Roadmap 

# Reminders

- `spec.json` is the wire-format contract between Python and JS.
- If a field changes, update `spec.json` first, then Python/JS.
- The Renderer and Serializer must treat Python Mobjects as read-only during transitions. Never mutate the python attributes.

---

# Tasks (delete when done)

- [ ] Fix bugs and add integration tests
  - [ ] Bugs are handled via github
- [ ] Improve code quality:
  - [ ] Add documentation for python and JS function and classes
  - [ ] Dead code and Dead branches elimination
  - [ ] create nice README (always ask the user for content)
- [ ] Fix class-vs-factory handling for other animations (not only `Shift`)
- [ ] Open issues upstream to simplify our edge-cases. For example the mocking logic could be provided by manim-web

---

# V2 

Once all tasks are done, start working on V2

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
