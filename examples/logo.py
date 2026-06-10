import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim_widget import ManimWidget, patch_tex

    patch_tex()
    from manim import (
        Circle,
        Triangle,
        Square,
        VGroup,
        LEFT,
        UP,
        ORIGIN,
        RIGHT,
        MathTex,
        WHITE,
    )


@app.class_definition
class ManimCELogo(ManimWidget):
    def construct(self):
        self.camera.background_color = "#ece6e2"
        logo_green = "#87c2a5"
        logo_blue = "#525893"
        logo_red = "#e07a5f"
        # FIXME: black logo
        # logo_black = "#343434"
        ds_m = MathTex(r"\mathbb{M}", fill_color=WHITE).scale(7)
        ds_m.shift(2.25 * LEFT + 1.5 * UP)
        circle = Circle(color=logo_green, fill_opacity=1).shift(LEFT)
        square = Square(color=logo_blue, fill_opacity=1).shift(UP)
        triangle = Triangle(color=logo_red, fill_opacity=1).shift(RIGHT)
        logo = VGroup(triangle, square, circle, ds_m)  # order matters
        logo.move_to(ORIGIN)
        self.add(logo)


@app.cell
def _():
    ManimCELogo()
    return


@app.cell
def _():
    return


def test(runner):
    import pytest

    pytest.skip("requires LaTeX")


if __name__ == "__main__":
    app.run()
