# Manim Widget







https://github.com/user-attachments/assets/507e4685-de60-40d6-a0bc-1a473028da80




Interactive Manim for Jupyter/marimo notebooks. The power of [Manim](https://www.manim.community/), but interactive, and without the hassle.

## Quickstart

<details>
  <summary>🤖 AI AGENT SKILL</summary>

There's a work in progress prompt/skill you can just paste to start vibing.
It's [here](https://raw.githubusercontent.com/rambip/manim-widget/refs/heads/main/SKILL.md)

Have fun, but please remember: LLMs are awful at scientific writing and story telling. For now, there's no shortcut to writing good explanations !
</details>

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


## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md)

## FAQ

### I want to use manim without being sudo, what do I do ?

On linux, you can build cairo and pango without root, you just need a C compiler.

Follow [this guide](https://gist.github.com/rambip/47a412b3f3fec8d4ab7a55f70ad2c47b)

## AI

This project used AI extensively. I still spent hours on papers for the design decisions, and reviewed most of the architecture, contracts and tests (except for JS 😬)
