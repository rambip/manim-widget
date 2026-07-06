import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    from manim import BLUE, Circle, Create, NumberPlane, Square, Triangle, YELLOW
    from manim_widget import ManimWidget

    PULSE_COLORS = [BLUE, YELLOW] * 5


@app.class_definition
class PlayerOptionsDemo(ManimWidget):
    """Three sections, so there's something to select/deselect/replay."""

    def construct(self):
        self.play(Create(Circle(color=BLUE)))
        self.next_section("square")
        self.play(Create(Square(color=YELLOW)))
        self.next_section("triangle")
        self.play(Create(Triangle(color=BLUE)))


@app.cell(hide_code=True)
def _():
    mo.md("""
    ### Default
    """)
    return


@app.cell
def _():
    PlayerOptionsDemo()
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ### Add `play` button
    """)
    return


@app.cell
def _():
    PlayerOptionsDemo(autoplay=False)
    return


@app.cell(hide_code=True)
def _():
    mo.md("""
    ### Hide controls
    """)
    return


@app.cell
def _():
    PlayerOptionsDemo(show_controls=False)
    return


@app.class_definition
class TenSections(ManimWidget):
    """10 sections, to see how the section picker behaves with many entries.

    Each section pulses the same circle (grow then shrink back) so playback
    is visible rather than an instant static change; 1s per section.
    """

    def construct(self):
        circle = Circle(color=PULSE_COLORS[0])
        for i in range(10):
            self.next_section(f"pulse {i + 1}")
            if i == 0:
                self.add(circle)
            else:
                circle.set_color(PULSE_COLORS[i])
            self.play(circle.animate.scale(1.5), run_time=0.5)
            self.play(circle.animate.scale(1 / 1.5), run_time=0.5)


@app.cell(hide_code=True)
def _():
    mo.md("""
    ### 10 sections

    You can click on the different sections, the player will follow.
    """)
    return


@app.cell
def _():
    TenSections()
    return


@app.class_definition
class FrameSizeDemo(ManimWidget):
    """A grid sized to the camera frame, so changing frame_width/frame_height
    is visible as a different aspect ratio. The canvas pixel width stays fixed —
    only its derived pixel height changes to match the new aspect ratio.
    """

    def construct(self):
        grid = NumberPlane(
            x_range=[-self.camera.frame_width / 2, self.camera.frame_width / 2, 1],
            y_range=[-self.camera.frame_height / 2, self.camera.frame_height / 2, 1],
            x_length=self.camera.frame_width * 0.9,
            y_length=self.camera.frame_height * 0.9,
        )
        self.play(Create(grid))


@app.cell(hide_code=True)
def _():
    mo.md("""
    ### Sizes and aspect ratios
    """)
    return


@app.cell
def _():
    # Default 16:9 frame, wider canvas (pixel height derives to ~506px).
    FrameSizeDemo(canvas_width=900)
    return


@app.cell
def _():
    # Square frame, explicit pixel height (pixel width derives to match).
    mo.ui.anywidget(
        FrameSizeDemo(
            frame_width=8, frame_height=8, canvas_height=500, show_controls=False
        )
    ).center()
    return


@app.cell
def _():
    # Portrait frame, narrower canvas (pixel height derives to ~500px).
    FrameSizeDemo(frame_width=7, frame_height=9, canvas_width=300)
    return


@app.function(hide_code=True)
def test_player_options_demo(runner):
    runner.check(PlayerOptionsDemo).assert_ok()

    default_widget = PlayerOptionsDemo()
    assert default_widget.autoplay is True
    assert default_widget.show_controls is True

    paused_widget = PlayerOptionsDemo(autoplay=False)
    assert paused_widget.autoplay is False

    bare_widget = PlayerOptionsDemo(show_controls=False)
    assert bare_widget.show_controls is False

    ten_sections = runner.check(TenSections)
    ten_sections.assert_ok()
    assert ten_sections.section_count == 10

    wide_widget = FrameSizeDemo(canvas_width=900)
    runner.check(FrameSizeDemo).assert_ok()
    assert wide_widget.canvas_width == 900
    assert wide_widget.canvas_height is None

    square_widget = FrameSizeDemo(frame_width=8, frame_height=8, canvas_height=500)
    assert square_widget.data.frame_width == 8
    assert square_widget.data.frame_height == 8
    assert square_widget.canvas_height == 500

    portrait_widget = FrameSizeDemo(frame_width=6, frame_height=10, canvas_width=300)
    assert portrait_widget.data.frame_width == 6
    assert portrait_widget.data.frame_height == 10
    assert portrait_widget.canvas_width == 300

    import pytest

    with pytest.raises(ValueError):
        FrameSizeDemo(canvas_width=300, canvas_height=300)


if __name__ == "__main__":
    app.run()
