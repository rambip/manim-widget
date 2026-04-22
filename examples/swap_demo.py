import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


@app.cell
def _():
    import marimo as mo
    from manim_widget import ManimWidget

    return (ManimWidget,)


@app.cell
def _(ManimWidget):
    import manim as mn
    from manim import (
        Circle,
        Swap,
        Create,
        LEFT,
        RIGHT,
        UP,
        DOWN,
        RED,
        GREEN,
        BLUE,
    )

    class SwapDemo(ManimWidget):
        def construct(self):
            # Create three circles at different positions with different colors
            c1 = Circle(color=RED, fill_opacity=0.8).shift(LEFT * 3)
            c2 = Circle(color=GREEN, fill_opacity=0.8)
            c3 = Circle(color=BLUE, fill_opacity=0.8).shift(RIGHT * 3)

            # Show them
            self.play(Create(c1), Create(c2), Create(c3))

            # Swap 1 and 2
            self.play(Swap(c1, c2))

            # Swap 2 and 3
            self.play(Swap(c2, c3))

            # Swap 1 and 3
            self.play(Swap(c1, c3))

    return (SwapDemo,)


@app.cell
def _(SwapDemo):
    SwapDemo()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
