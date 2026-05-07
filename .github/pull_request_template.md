## Summary

<!-- What does this PR do and why? -->

## Checklist

- [ ] Ruff passes: `uvx ruff check . && uvx ruff format --check .`
- [ ] Python tests pass: `uv run pytest -q tests/test_widget.py`
- [ ] JS integration tests pass: `uv run pytest -q tests/test_js_integration.py`
- [ ] If JS source changed: bundle rebuilt (`cd js && bun run build`)
- [ ] If the emitted `scene_data` JSON changed shape: `spec.json` reflects the new shape and was updated before the code

## scene_data / spec changes

<!-- Delete this section if the emitted JSON is unchanged. Otherwise describe new or modified fields. -->

## Testing notes

<!-- Anything reviewers should know about how to verify this. -->
