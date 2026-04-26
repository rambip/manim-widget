import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    from manim import Circle, Square, Triangle, VGroup, LEFT, UP, RIGHT, ORIGIN
    import marimo as mo
    from manim_widget import ManimWidget, patch_tex
    patch_tex()


@app.cell
def _(ManimWidget):
    class NoAnimation(ManimWidget):
        def construct(self):
            self.camera.background_color = "#ece6e2"
            logo_green = "#87c2a5"
            logo_blue = "#525893"
            logo_red = "#e07a5f"
            circle = Circle(color=logo_green, fill_opacity=1).shift(LEFT)
            square = Square(color=logo_blue, fill_opacity=1).shift(UP)
            triangle = Triangle(color=logo_red, fill_opacity=1).shift(RIGHT)
            logo = VGroup(triangle, square, circle)
            logo.move_to(ORIGIN)
            self.add(logo)
            # NO ANIMATIONS

    return (NoAnimation,)


@app.cell
def _(NoAnimation):
    NoAnimation()
    return


if __name__ == "__main__":
    app.run()
