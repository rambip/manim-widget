import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    from manim import (
        Circle,
        Dot,
        GrowFromCenter,
        Line,
        MoveAlongPath,
        RIGHT,
        Rotating,
        Transform,
    )
    import marimo as mo
    from manim_widget import ManimWidget, patch_tex
    patch_tex()


@app.cell
def _(ManimWidget):
    class PointMovingOnShapes(ManimWidget):
        def construct(self):
            circle = Circle(radius=1, color=mn.BLUE)
            dot = Dot()
            dot2 = dot.copy().shift(RIGHT)
            self.add(dot)

            line = Line([3, 0, 0], [5, 0, 0])
            self.add(line)

            self.play(GrowFromCenter(circle))
            self.play(Transform(dot, dot2))
            self.play(MoveAlongPath(dot, circle), run_time=2, rate_func=mn.linear)
            self.play(Rotating(dot, about_point=[2, 0, 0]), run_time=1.5)
            self.wait()

    return (PointMovingOnShapes,)


@app.cell
def _(PointMovingOnShapes):
    PointMovingOnShapes()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()