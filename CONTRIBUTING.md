# Contributing to manim-widget

Thanks for your interest in this project! 🎉 Contributions of all kinds are welcome — new animations, bug fixes, refactors, docs, or just opening an issue with a good repro.

---

## Dev setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/) and [Bun](https://bun.sh/). You do **not** need LaTeX installed — the Python side captures scene intent as JSON; actual rendering happens in the browser via `manim-web`.

```sh
git clone --recurse-submodules https://github.com/YOUR_ORG/manim-widget
cd manim-widget

uv sync          # Python deps (editable install included)

cd js
bun install      # JS deps
bun run build    # rebuild static bundle
cd ..
```

> Cloned without `--recurse-submodules`? Run `git submodule update --init --recursive`.

---

## Running tests

```sh
# Fast — run before every commit
uv run pytest -q tests/test_widget.py

# Slow (~1 min) — run before opening a PR
uv run pytest -q tests/test_js_integration.py

# Manual JS smoke test (use --conditions source to keep readable class names)
cd js && bun run cli --conditions source < ../spec.json
```

---

## Code style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```sh
uv run ruff check .          # lint
uv run ruff format .         # format in place
uv run ruff format --check . # check only (what CI does)
```

If you want do run them automatically on commit, do:
```
uv run pre-commit install
```

---

## The one rule about scene_data

The JSON emitted in `widget.scene_data` is the contract between Python and JavaScript. Whenever you change what that JSON looks like — new fields, renamed keys, new command types — **update `spec.json` to reflect the new shape before writing any code or tests**. That keeps the intended shape visible in its own commit, separate from the implementation.

If you're not changing the emitted JSON at all, ignore this entirely.

---

## Opening a PR

Use the PR template. The short version: ruff green, both test suites passing, bundle rebuilt if you touched JS, `spec.json` updated if the emitted JSON changed.

If your change is large, consider opening an issue first to align on the design before writing code.
