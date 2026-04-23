import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    from manim import (
        Create,
        Circle,
        FadeIn,
        Rotate,
        RED,
        GREEN,
        BLUE,
        ORIGIN,
        LEFT,
        RIGHT,
        UP,
        OUT,
        IN,

    )

    import marimo as mo
    from manim_widget import ManimWidget


@app.cell
def _(ManimWidget):
    class Rotate3D(ManimWidget):
        def construct(self):
            # Circle in xy plane (default)
            c1 = Circle(radius=1.5, color=RED, fill_opacity=0.8)
            # Circle in xz plane (rotate to y-axis)
            c2 = Circle(radius=1.5, color=GREEN, fill_opacity=0.5)
            c2.rotate(mn.PI / 2, axis=RIGHT)
            # Circle in yz plane (rotate to z-axis)
            c3 = Circle(radius=1.5, color=BLUE, fill_opacity=0.5)
            c3.rotate(mn.PI / 2, axis=UP)


            # Fade in
            self.play(Create(c2), Create(c1), Create(c3))

            # Rotate around different axes
            self.play(Rotate(c1, mn.PI, axis=UP, run_time=2))   # z-axis rotation
            self.play(Rotate(c2, mn.PI, axis=RIGHT, run_time=2))    # y-axis rotation  
            self.play(Rotate(c3, mn.PI, axis=OUT, run_time=2)) # x-axis rotation

            # Move camera to see from 3D angle
            self.move_camera(phi=1.0, theta=0.8, run_time=2)

    return (Rotate3D,)

@app.cell
def _(Rotate3D):
    Rotate3D()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
