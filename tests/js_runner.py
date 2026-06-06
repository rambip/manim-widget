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
        section_ids: Per-section mobject ID lists (populated with output_ids=True).
        section_end_states: Per-section serialized end states (populated with output_end_state=True).
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


def check_data(
    scene_data: str | dict[str, Any],
    output_ids: bool = False,
    output_end_state: bool = False,
) -> JSResult:
    """Validate pre-serialized scene data through the JS headless runner.

    Args:
        scene_data: Scene dict (or pre-serialized JSON string).
        output_ids: Include per-section mobject IDs in the result.
        output_end_state: Include per-section serialized end states in the result.

    Returns:
        JSResult with errors, warnings, and optional diagnostics.
    """
    _check_env()
    scene_json = json.dumps(scene_data) if isinstance(scene_data, dict) else scene_data
    args = [
        "bun",
        "run",
        "--preload",
        str(_PRELOAD),
        "--conditions",
        "source",
        str(_CLI),
    ]
    if output_ids:
        args.append("--output-ids")
    if output_end_state:
        args.append("--output-end-state")

    proc = subprocess.run(
        args, input=scene_json, capture_output=True, text=True, cwd=str(_JS_ROOT)
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"CLI produced non-JSON output (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
        ) from exc
    return JSResult._from_json(data)


def check(scene_cls: type, fps: int = 10, **kwargs: Any) -> JSResult:
    """Instantiate scene_cls and validate it through the JS headless runner.

    Args:
        scene_cls: A ManimWidget subclass.
        fps: Frames per second for serialization.
        **kwargs: Forwarded to check_data (output_ids, output_end_state).

    Returns:
        JSResult with errors, warnings, and optional diagnostics.
    """
    scene = scene_cls(fps=fps)
    return check_data(scene.scene_data, **kwargs)


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
    parser.add_argument("--output-ids", action="store_true")
    parser.add_argument("--output-end-state", action="store_true")

    args = parser.parse_args()

    if args.json:
        scene_json = sys.stdin.read()
        result = check_data(
            scene_json,
            output_ids=args.output_ids,
            output_end_state=args.output_end_state,
        )
    else:
        if not args.class_name:
            parser.error("class_name is required when providing an example file")
        spec = importlib.util.spec_from_file_location("_example", args.example)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        scene_cls = getattr(mod, args.class_name)
        result = check(
            scene_cls,
            output_ids=args.output_ids,
            output_end_state=args.output_end_state,
        )

    _pretty_print(result)
    sys.exit(0 if result.ok else 1)
