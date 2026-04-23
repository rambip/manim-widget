import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    from manim import (
        Circle,
        Triangle,
        Square,
        VGroup,
        LEFT,
        UP,
        ORIGIN,
        RIGHT,
        Create,
        TAU,
    )
    import marimo as mo
    from manim_widget import ManimWidget, patch_tex
    patch_tex()


@app.cell
def _(ManimWidget):
    class ManimCELogo(ManimWidget):
        def construct(self):
            self.camera.background_color = "#ece6e2"
            logo_green = "#87c2a5"
            logo_blue = "#525893"
            logo_red = "#e07a5f"
            circle = Circle(color=logo_green, fill_opacity=1).shift(LEFT)
            square = Square(color=logo_blue, fill_opacity=1).shift(UP)
            triangle = Triangle(color=logo_red, fill_opacity=1).shift(RIGHT)
            logo = VGroup(triangle, square, circle)  # order matters
            logo.move_to(ORIGIN)
            self.play(Create(logo))
            self.play(logo.animate.shift(LEFT).scale(0.5))
            self.play(logo.animate.shift(RIGHT*3).scale(2))
            self.play(logo.animate.rotate(TAU/2))
            self.play(logo.animate.flip())

    return (ManimCELogo,)


@app.cell
def _(ManimCELogo):
    ManimCELogo()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()