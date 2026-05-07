import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    from manim import (
        Arrow,
        Dot,
        ORIGIN,
    )
    from manim_widget import patch_tex
    patch_tex()


@app.cell
def _(ManimWidget):
    class VectorArrow(ManimWidget):
        def construct(self):
            dot = Dot(ORIGIN)
            arrow = Arrow(ORIGIN, [2, 2, 0], buff=0)
            self.add(dot, arrow)

    return (VectorArrow,)


@app.cell
def _(VectorArrow):
    VectorArrow()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()