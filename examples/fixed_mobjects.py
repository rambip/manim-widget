import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    from manim_widget import ManimWidget
    from manim import (
        BLUE,
        DOWN,
        GRAY,
        GREEN,
        RED,
        UP,
        WHITE,
        Create,
        Dot3D,
        Text,
        ThreeDAxes,
    )


@app.class_definition
class FixedMobjectsDemo(ManimWidget):
    """The 8 vertices of a cube, combining both 'fixed' mechanisms.

    - Title and equation are pinned to the screen with
      add_fixed_in_frame_mobjects: they stay put in the viewport no matter
      how the camera moves.
    - Each vertex's label is pinned with add_fixed_orientation_mobjects: it
      stays anchored to its 3D point, but always faces the camera.
    """

    def construct(self):
        self.set_camera_orientation(phi=1.0, theta=1.1, zoom=2)

        axes = ThreeDAxes(axis_config={"color": GRAY})
        title = Text("Vertices of a cube", color=WHITE).to_edge(UP)
        equation = Text("x, y, z ∈ {-1, 1}", color=WHITE).to_edge(DOWN)

        self.play(Create(axes))
        self.add_fixed_in_frame_mobjects(title, equation)
        self.play(Create(title), Create(equation))

        vertices = [(sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        colors = [RED, GREEN, BLUE, WHITE] * 2
        for i, (position, color) in enumerate(zip(vertices, colors)):
            dot = Dot3D(point=position, color=color)
            label = Text(str(i), color=color).scale(0.6).next_to(dot, UP, buff=0.1)
            self.add_fixed_orientation_mobjects(label)
            self.play(Create(dot), Create(label), run_time=0.4)


@app.cell(hide_code=True)
def _():
    mo.md("""
    Drag inside the scene to orbit the camera.
    """)
    return


@app.cell
def _():
    FixedMobjectsDemo(is_3d=True)
    return


@app.function(hide_code=True)
def test_fixed_mobjects_demo(runner):
    result = runner.check(FixedMobjectsDemo, is_3d=True)
    result.assert_ok()
    camera = result.section_end_states[0]["camera"]
    assert camera["kind"] == "3d"
    assert abs(camera["phi"] - 1.0) < 1e-6
    assert abs(camera["theta"] - 1.1) < 1e-6


if __name__ == "__main__":
    app.run()
