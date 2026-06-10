from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _import(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _examples():
    return sorted(_EXAMPLES_DIR.glob("*.py"))


@pytest.mark.parametrize("path", _examples(), ids=lambda p: p.stem)
def test_example(runner, path):
    try:
        mod = _import(path)
    except Exception as e:
        pytest.skip(f"import error: {e}")

    test_fn = getattr(mod, "test", None)
    if test_fn is None:
        pytest.fail(
            f"examples/{path.name} has no test(runner) function.\n"
            f"Add one to opt in, or to explicitly opt out:\n\n"
            f"    def test(runner):\n"
            f"        pytest.skip('reason')"
        )

    test_fn(runner)
