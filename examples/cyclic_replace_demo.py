import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


@app.cell
def _():
    import marimo as mo
    from manim_widget import ManimWidget

    return ManimWidget,


@app.cell
def _(ManimWidget):
    import manim as mn
    from manim import (
        Circle,
        CyclicReplace,
        Create,
        LEFT,
        RIGHT,
        UP,
        RED,
        GREEN,
        BLUE,
    )

    class CyclicReplaceDemo(ManimWidget):
        def construct(self):
            # Create three circles at different positions with different colors
            c1 = Circle(color=RED, fill_opacity=0.8).shift(LEFT * 2)
            c2 = Circle(color=GREEN, fill_opacity=0.8)
            c3 = Circle(color=BLUE, fill_opacity=0.8).shift(RIGHT * 2)

            # Show them
            self.play(Create(c1), Create(c2), Create(c3))

            # CyclicReplace: each circle moves to the next position
            # c1 -> c2 position, c2 -> c3 position, c3 -> c1 position
            self.play(CyclicReplace(c1, c2, c3))

            # Do it again to see the cycle continue
            self.play(CyclicReplace(c1, c2, c3))

    return CyclicReplaceDemo,


@app.cell
def _(CyclicReplaceDemo):
    CyclicReplaceDemo()
    return


if __name__ == "__main__":
    app.run()
