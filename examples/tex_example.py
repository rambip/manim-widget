import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim_widget import ManimWidget, patch_tex
    patch_tex()
    from manim import (
        Create,
        MathTex,
        RIGHT,
    )



@app.class_definition
class TexExample(ManimWidget):
    def construct(self):
        tex = MathTex("x=1", stroke_opacity=1, fill_opacity=1)
        self.play(Create(tex))
        self.play(tex.animate.shift(RIGHT))


@app.cell
def _():
    TexExample()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
