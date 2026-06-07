import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim import RIGHT, Dot, Rotating, VMobject
    from manim_widget import ManimWidget


@app.class_definition
class PointWithTrace(ManimWidget):
    def construct(self):
        path = VMobject()
        dot = Dot()
        path.set_points_as_corners([dot.get_center(), dot.get_center()])

        def update_path(p):
            prev = p.copy()
            prev.add_points_as_corners([dot.get_center()])
            p.become(prev)

        path.add_updater(update_path)
        self.add(path, dot)
        self.play(Rotating(dot, angle=3.14, about_point=RIGHT, run_time=2))


@app.cell
def _():
    PointWithTrace()
