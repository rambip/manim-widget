import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    import numpy as np
    from manim import (
        Axes,
        Circle,
        Dot,
        MoveAlongPath,
        Restore,
        Square,
        BLUE,
        ORANGE,
        PI,
        linear,
    )
    from manim.camera.moving_camera import MovingCamera
    from manim_widget import ManimWidget, SharedCamera


@app.class_definition
class FollowingGraphCamera(ManimWidget):
    camera_class = MovingCamera

    def construct(self):
        self.camera.frame.save_state()

        ax = Axes(x_range=[-1, 10], y_range=[-1, 10])
        graph = ax.plot(lambda x: np.sin(x), color=BLUE, x_range=[0, 3 * PI])
        moving_dot = Dot(ax.i2gp(graph.t_min, graph), color=ORANGE)

        self.add(
            ax,
            graph,
            Dot(ax.i2gp(graph.t_min, graph)),
            Dot(ax.i2gp(graph.t_max, graph)),
            moving_dot,
        )

        self.play(self.camera.frame.animate.scale(0.5).move_to(moving_dot))

        def update_curve(mob):
            mob.move_to(moving_dot.get_center())

        self.camera.frame.add_updater(update_curve)
        self.play(MoveAlongPath(moving_dot, graph, rate_func=linear))
        self.camera.frame.remove_updater(update_curve)

        self.play(Restore(self.camera.frame))


@app.cell
def _():
    widget = FollowingGraphCamera(fps=15)
    widget
    return


@app.class_definition
class SquareScene(ManimWidget):
    def construct(self):
        self.add(Square(color=BLUE, fill_opacity=0.5))


@app.class_definition
class CircleScene(ManimWidget):
    def construct(self):
        self.add(Circle(color=ORANGE, fill_opacity=0.5))


@app.cell
def _():
    cam = SharedCamera()
    mo.hstack(
        [
            SquareScene(is_3d=True, shared_camera=cam),
            CircleScene(is_3d=True, shared_camera=cam),
        ]
    )
    return


@app.function(hide_code=True)
def test_plays_without_error(runner):
    runner.check(FollowingGraphCamera).assert_ok()


@app.function(hide_code=True)
def test_many_camera_states_in_state_bank(runner):
    """Updater animation must produce per-frame camera states, not just start/end."""
    data = FollowingGraphCamera(fps=15).scene_data
    cam_states = [s for s in data["states"] if s.get("kind") == "Camera"]
    assert len(cam_states) > 10, (
        f"Expected >10 Camera states (one per unique frame position), got {len(cam_states)}"
    )


@app.function(hide_code=True)
def test_updater_frames_all_have_camera(runner):
    """Every frame in the updater command must carry a '#camera' state_ref."""
    data = FollowingGraphCamera(fps=15).scene_data
    section = data["sections"][0]
    updater_cmds = [c for c in section["construct"] if c["cmd"] == "updater"]
    assert len(updater_cmds) == 1, "Expected exactly one updater command"
    for i, frame in enumerate(updater_cmds[0]["frames"]):
        assert "#camera" in frame, f"Frame {i} is missing '#camera' key"


@app.function(hide_code=True)
def test_camera_refs_vary_across_frames(runner):
    """Camera state_refs must vary across updater frames — camera was tracking the path."""
    data = FollowingGraphCamera(fps=15).scene_data
    section = data["sections"][0]
    updater = next(c for c in section["construct"] if c["cmd"] == "updater")
    refs = [frame["#camera"]["state_ref"] for frame in updater["frames"]]
    unique = len(set(refs))
    assert unique > 5, (
        f"Expected >5 distinct camera state_refs across frames (camera zigzags), got {unique}"
    )


@app.function(hide_code=True)
def test_camera_restored_to_initial_position(runner):
    """After Restore, JS camera must be back near the initial scene center."""
    r = runner.check(FollowingGraphCamera)
    r.assert_ok()
    cam_center = r.section_end_states[0]["end_state"].get("camera_center")
    assert cam_center is not None, "camera_center not reported in end state"
    assert abs(cam_center[0]) < 1.0, (
        f"Camera x should be near 0 after Restore, got {cam_center[0]}"
    )
    assert abs(cam_center[1]) < 1.0, (
        f"Camera y should be near 0 after Restore, got {cam_center[1]}"
    )


@app.function(hide_code=True)
def test_shared_camera_scenes_play(runner):
    runner.check(SquareScene).assert_ok()
    runner.check(CircleScene).assert_ok()


if __name__ == "__main__":
    app.run()
