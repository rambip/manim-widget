# Manim Widget

<img width="645" height="544" alt="image" src="https://github.com/user-attachments/assets/e8094a2c-864b-45f1-9d0d-cd724f859e18" />


Interactive Manim for Jupyter/marimo notebooks. The power of [Manim](https://www.manim.community/), without the hassle.

## Installation

```bash
# in your project
uv add manim-widget
```

And you're good to go ! You do not even need to install LaTeX.

> If you get errors during installation, go read the [manim install guide](https://docs.manim.community/en/stable/installation/uv.html)

Want to try it online ?

Thank's to [marimo](https://marimo.io/), that's a no brainer:
[![Open in molab](https://molab.marimo.io/molab-shield.svg)](https://molab.marimo.io/notebooks/nb_v69Q632SKXkCxbZLF4Vpid)

## How it works

Manim widget uses the amazing [Manim Web](https://github.com/maloyan/manim-web) project to render your scenes.

Code in this repository mainly does the serialization form python to js, using a precise [json specification](https://github.com/rambip/manim-widget/blob/main/spec.json). And it turns out it's harder than one could think !

If you want to dig deeper, I strongly recommend to use the deepwiki documentation [here](https://deepwiki.com/rambip/manim-widget)



## Headless testing

`tests/js_runner.py` lets you validate a scene through the JS renderer without a browser — useful for quick sanity-checks and CI.

```bash
# run a scene class from an example file
uv run python tests/js_runner.py examples/arrow.py ArrowDance

# pipe in pre-serialized JSON
uv run python -c "from mymodule import MyScene; import json; print(json.dumps(MyScene().scene_data))" \
  | uv run python tests/js_runner.py --json
```

Exit code is 0 on success, 1 on any JS playback error. Errors and warnings are printed to stdout.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md)

## AI

This project used AI extensively. I still spent hours on papers for the design decisions, and reviewed most of the architecture, contracts and tests (except for JS 😬)
