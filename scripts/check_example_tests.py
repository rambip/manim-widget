#!/usr/bin/env python3
"""Check that every marimo example in examples/ has at least one test function."""

import ast
import sys
from pathlib import Path

EXAMPLES = sorted(Path("examples").glob("*.py"))


def is_marimo(path: Path) -> bool:
    return "import marimo" in path.read_text()


def has_test(path: Path) -> bool:
    tree = ast.parse(path.read_text())
    return any(
        isinstance(node, ast.FunctionDef) and node.name.startswith("test")
        for node in ast.walk(tree)
    )


missing = [p for p in EXAMPLES if is_marimo(p) and not has_test(p)]
total = sum(1 for p in EXAMPLES if is_marimo(p))

DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"

if missing:
    names = [str(p) for p in missing]
    print(f"ERROR: {len(missing)}/{total} examples missing a test function: {names}\n")
    print("Here is what the minimal test for a scene looks like:\n")
    code = (
        "@app.function(hide_code=True)\n"
        "def test_foo_scene(runner):\n"
        "    runner.check_validated(FooScene).assert_ok()"
    )
    print(DIM + code + RESET)
    print(
        f"\nSee {BOLD}./tests/js_runner.py{RESET} for how to write more complex tests."
    )
    sys.exit(1)

print(f"OK: all {total} examples have tests.")
