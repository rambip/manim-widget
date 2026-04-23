import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    from manim import (
        Create,
        MathTex,
        RIGHT,
    )
    import marimo as mo
    from manim_widget import ManimWidget, patch_tex
    patch_tex()


@app.cell
def _(ManimWidget):
    class TexExample(ManimWidget):
        def construct(self):
            tex = MathTex("x=1", stroke_opacity=1, fill_opacity=1)
            self.play(Create(tex))
            self.play(tex.animate.shift(RIGHT))

    return (TexExample,)


@app.cell
def _(TexExample):
    TexExample()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()