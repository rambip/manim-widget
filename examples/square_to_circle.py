import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    import manim as mn
    from manim import Circle, Square, Transform
    from manim_widget import ManimWidget, patch_tex

    patch_tex()


@app.class_definition
class SquareToCircle(ManimWidget):
    def construct(self):
        b = Square(color=mn.BLUE)
        a = Circle(color=mn.RED)

        # self.play(mn.Create(a))
        self.play(Transform(a, b), run_time=2)


@app.cell
def _():
    SquareToCircle()
    return


if __name__ == "__main__":
    app.run()
