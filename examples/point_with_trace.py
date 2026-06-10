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


@app.function(hide_code=True)
def test(runner):
    scene = PointWithTrace(fps=5)
    r = runner.check_data(scene.scene_data)
    r.assert_ok()
    section = scene.scene_data["sections"][0]
    frame_ids = {
        mob_id
        for cmd in section["construct"]
        if cmd["cmd"] == "updater"
        for frame in cmd["frames"]
        for mob_id in frame
    }
    scene_ids = set(r.scene_ids(0))
    assert frame_ids <= scene_ids, (
        f"updater frame IDs not in scene: {frame_ids - scene_ids}"
    )


@app.cell
def _():
    PointWithTrace()
