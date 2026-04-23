import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    from manim import (
        Brace,
        Dot,
        Line,
        PI,
    )
    import marimo as mo
    from manim_widget import ManimWidget, patch_tex
    patch_tex()


@app.cell
def _(ManimWidget):
    class BraceAnnotation(ManimWidget):
        def construct(self):
            dot = Dot([-2, -1, 0])
            dot2 = Dot([2, 1, 0])
            line = Line(dot.get_center(), dot2.get_center()).set_color(mn.ORANGE)
            b1 = Brace(line)
            b1text = b1.get_text("Horizontal distance")
            b2 = Brace(line, direction=line.copy().rotate(PI / 2).get_unit_vector())
            b2text = b2.get_tex("x-x_1")
            self.add(line, dot, dot2, b1, b2, b1text, b2text)

    return (BraceAnnotation,)


@app.cell
def _(BraceAnnotation):
    BraceAnnotation()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()