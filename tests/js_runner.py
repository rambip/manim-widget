"""Headless JS validation of manim-widget scenes.

Requires a manim-widget source checkout (js/ directory) and bun on PATH.

API usage::

    from js_runner import check, check_data
    result = check(MyScene)
    result.assert_ok()
    print(result.errors)

CLI usage::

    # from a scene class
    python tests/js_runner.py examples/arrow.py ArrowDance

    # from a marimo notebook class
    python tests/js_runner.py examples/polygon_on_axes.py PolygonOnAxes

    # from pre-serialized JSON
    python tests/js_runner.py --json < scene.json
    uv run python -c "..." | python tests/js_runner.py --json
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_JS_ROOT = Path(__file__).parent.parent / "js"
_CLI = _JS_ROOT / "src" / "test_cli.js"
_PRELOAD = _JS_ROOT / "src" / "preload-typia.ts"


def _check_env() -> None:
    if not _JS_ROOT.exists():
        raise RuntimeError(
            "js/ source directory not found — js_runner requires a manim-widget source checkout.\n"
            "See https://github.com/rambip/manim-widget"
        )
    if shutil.which("bun") is None:
        raise RuntimeError("bun not found on PATH — install from https://bun.sh")


@dataclass
class JSResult:
    """Structured result from a JS headless playback run.

    Attributes:
        ok: True if playback completed with no errors.
        section_count: Number of sections in the scene.
        errors: List of error dicts, each with keys: section, name, error, stack.
        warnings: List of warning dicts, each with keys: section, name, reason.
        section_ids: Per-section mobject ID lists (registry ids + scene ids).
        section_end_states: Per-section serialized end states.
    """

    ok: bool
    section_count: int
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    section_ids: list[dict[str, Any]] = field(default_factory=list)
    section_end_states: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def _from_json(cls, data: dict[str, Any]) -> JSResult:
        return cls(
            ok=data.get("ok", False),
            section_count=data.get("sectionCount", 0),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            section_ids=data.get("sectionIds", []),
            section_end_states=data.get("sectionEndStates", []),
        )

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def assert_ok(self) -> None:
        """Raise AssertionError with error details if playback failed."""
        if not self.ok:
            msgs = "\n".join(e.get("error", str(e)) for e in self.errors)
            raise AssertionError(f"JS playback failed:\n{msgs}")

    def scene_ids(self, section: int = 0) -> list[str]:
        """IDs of mobjects present in the scene (not just registry) at section end."""
        if section >= len(self.section_ids):
            return []
        return self.section_ids[section].get("scene_ids", [])


def check_data(scene_data: str | dict[str, Any]) -> JSResult:
    """Validate pre-serialized scene data through the JS headless runner.

    Args:
        scene_data: Scene dict (or pre-serialized JSON string).

    Returns:
        JSResult with errors, warnings, section_ids, and section_end_states.
    """
    import tempfile
    import os

    _check_env()
    scene_json = json.dumps(scene_data) if isinstance(scene_data, dict) else scene_data

    # Write input to a temp file to avoid pipe buffer limits on large scenes.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write(scene_json)
        input_path = f.name

    out_path = input_path + ".out"
    try:
        args = [
            "bun",
            "run",
            "--preload",
            str(_PRELOAD),
            "--conditions",
            "source",
            str(_CLI),
            input_path,
        ]
        with open(out_path, "w") as outf:
            proc = subprocess.run(
                args, stdout=outf, stderr=subprocess.PIPE, text=True, cwd=str(_JS_ROOT)
            )
        with open(out_path) as f:
            raw = f.read()
    finally:
        os.unlink(input_path)
        if os.path.exists(out_path):
            os.unlink(out_path)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"CLI produced non-JSON output (exit {proc.returncode}):\n{raw[:500]}\n{proc.stderr}"
        ) from exc
    return JSResult._from_json(data)


def check(scene_cls: type, fps: int = 10) -> JSResult:
    """Instantiate scene_cls and validate it through the JS headless runner.

    Args:
        scene_cls: A ManimWidget subclass.
        fps: Frames per second for serialization.

    Returns:
        JSResult with errors, warnings, section_ids, and section_end_states.
    """
    scene = scene_cls(fps=fps)
    return check_data(scene.scene_data)


def _pretty_print(result: JSResult) -> None:
    status = "OK" if result.ok else "FAILED"
    print(f"[{status}] {result.section_count} section(s)")
    for w in result.warnings:
        print(
            f"  warning  section={w.get('section')} ({w.get('name')}): {w.get('reason')}"
        )
    for e in result.errors:
        print(
            f"  error    section={e.get('section')} ({e.get('name')}): {e.get('error')}"
        )
        if e.get("stack"):
            for line in e["stack"].splitlines()[1:]:
                print(f"           {line}")


if __name__ == "__main__":
    import argparse
    import importlib.util

    parser = argparse.ArgumentParser(
        description="Run a manim-widget scene through the JS headless CLI."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("example", nargs="?", help="Path to example .py file")
    group.add_argument(
        "--json", action="store_true", help="Read pre-serialized JSON from stdin"
    )
    parser.add_argument(
        "class_name", nargs="?", help="Scene class name (required with example)"
    )

    args = parser.parse_args()

    if args.json:
        scene_json = sys.stdin.read()
        result = check_data(scene_json)
    else:
        if not args.class_name:
            parser.error("class_name is required when providing an example file")
        spec = importlib.util.spec_from_file_location("_example", args.example)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        scene_cls = getattr(mod, args.class_name)
        result = check(scene_cls)

    _pretty_print(result)
    sys.exit(0 if result.ok else 1)
