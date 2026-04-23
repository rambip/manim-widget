import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    from manim import (
        Dot,
        LEFT,
        RIGHT,
        Rotating,
        UP,
        VMobject,
    )
    import marimo as mo
    from manim_widget import ManimWidget, patch_tex
    patch_tex()


@app.cell
def _(ManimWidget):
    class PointWithTrace(ManimWidget):
        def construct(self):
            path = VMobject()
            dot = Dot()
            path.set_points_as_corners([dot.get_center(), dot.get_center()])
            def update_path(path):
                previous_path = path.copy()
                previous_path.add_points_as_corners([dot.get_center()])
                path.become(previous_path)
            path.add_updater(update_path)
            self.add(path, dot)
            self.play(Rotating(dot, angle=mn.PI, about_point=RIGHT, run_time=2))
            self.wait()
            self.play(dot.animate.shift(UP))
            self.play(dot.animate.shift(LEFT))
            self.wait()

    return (PointWithTrace,)


@app.cell
def _(PointWithTrace):
    PointWithTrace()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()