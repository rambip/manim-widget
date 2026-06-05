from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from manim import (
    BLUE,
    GREEN,
    LEFT,
    ORIGIN,
    RED,
    RIGHT,
    UP,
    Arrow,
    Circle,
    Create,
    Difference,
    Dot,
    Ellipse,
    Exclusion,
    FadeIn,
    Group,
    GrowFromCenter,
    ImageMobject,
    Intersection,
    Line,
    MarkupText,
    MoveAlongPath,
    Rotating,
    Square,
    Text,
    Transform,
    Triangle,
    VGroup,
    VMobject,
    linear,
)

from manim_widget.widget import ManimWidget


def _create_logo_group() -> VGroup:
    """Create the standard logo group: circle, square, triangle."""
    logo_green = "#87c2a5"
    logo_black = "#343434"
    logo_red = "#e07a5f"
    circle = Circle(color=logo_green, fill_opacity=1).shift(LEFT)
    square = Square(color=logo_black, fill_opacity=1).shift(UP)
    triangle = Triangle(color=logo_red, fill_opacity=1).shift(RIGHT)
    return VGroup(triangle, square, circle)


CLI_PATH = Path(__file__).parent.parent / "js" / "src" / "test_cli.js"


def run_cli(
    scene_data: str | dict, output_ids: bool = False, output_end_state: bool = False
) -> tuple[int, dict]:
    """Run the test CLI and return (returncode, report_dict).

    The CLI always emits a single JSON report object on stdout.
    """
    scene_json = json.dumps(scene_data) if isinstance(scene_data, dict) else scene_data

    args = ["bun", "run", "--conditions", "source", str(CLI_PATH)]
    if output_ids:
        args.append("--ids")
    if output_end_state:
        args.append("--end-state")

    result = subprocess.run(
        args,
        input=scene_json,
        capture_output=True,
        text=True,
        # Run from the js/ dir so bun picks up bunfig.toml (typia transform).
        cwd=str(CLI_PATH.parent.parent),
    )
    # Strip any non-JSON preamble (e.g. bun/typia banners written to stdout).
    json_start = result.stdout.find("{")
    try:
        report = json.loads(result.stdout[json_start:]) if json_start >= 0 else {}
        assert "sections" in report
    except (json.JSONDecodeError, AssertionError):
        report = {
            "success": False,
            "errors": [
                {
                    "error": "unparseable_output",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            ],
            "sections": [],
        }
    return result.returncode, report


class TestCLIIntegration:
    @pytest.fixture
    def simple_scene_data(self) -> str:
        class SimpleScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))

        scene = SimpleScene()
        return scene.scene_data

    @pytest.fixture
    def fadein_image_data(self) -> str:
        class FadeInImageScene(ManimWidget):
            def construct(self):
                h, w = 24, 32
                data = np.zeros((h, w, 4), dtype=np.uint8)
                data[..., 0] = 255
                data[..., 3] = 255
                img = ImageMobject(data)
                img.height = 2.0
                self.play(FadeIn(img))

        scene = FadeInImageScene()
        return scene.scene_data

    @pytest.fixture
    def animate_shift_left_data(self) -> str:
        class AnimateShiftLeftScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.play(c.animate.shift(LEFT))

        scene = AnimateShiftLeftScene()
        return scene.scene_data

    @pytest.fixture
    def multi_section_data(self) -> str:
        class MultiSectionScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.next_section("second")
                s = Square()
                self.play(FadeIn(s))

        scene = MultiSectionScene()
        return scene.scene_data

    @pytest.fixture
    def vgroup_create_data(self) -> str:
        class VGroupScene(ManimWidget):
            def construct(self):
                logo_green = "#87c2a5"
                logo_blue = "#525893"
                logo_red = "#e07a5f"
                circle = Circle(color=logo_green, fill_opacity=1).shift(LEFT)
                square = Square(color=logo_blue, fill_opacity=1).shift((0, 1, 0))
                triangle = Triangle(color=logo_red, fill_opacity=1).shift((1, 0, 0))
                logo = VGroup(triangle, square, circle)
                logo.move_to(ORIGIN)
                self.play(Create(logo))

        scene = VGroupScene()
        return scene.scene_data

    @pytest.fixture
    def vgroup_reordered_data(self) -> str:
        class VGroupReordered(ManimWidget):
            def construct(self):
                self.camera.background_color = "#ece6e2"
                logo = _create_logo_group()
                logo.move_to(ORIGIN + LEFT)
                self.play(Create(logo))

        scene = VGroupReordered()
        return scene.scene_data

    @pytest.fixture
    def boolean_operations_data(self) -> str:
        class BooleanOperations(ManimWidget):
            def construct(self):
                ellipse1 = Ellipse(
                    width=4, height=3, fill_opacity=0.5, color=BLUE
                ).move_to(LEFT)
                ellipse2 = ellipse1.copy().set_color(RED).move_to(RIGHT)
                self.play(FadeIn(VGroup(ellipse1, ellipse2)))

                e = Intersection(ellipse1, ellipse2, color=GREEN, fill_opacity=0.5)
                self.play(e.animate.scale(0.5).move_to(UP * 2))

        scene = BooleanOperations()
        return scene.scene_data

    @pytest.fixture
    def multi_subpath_data(self) -> str:
        class MultiSubpathScene(ManimWidget):
            def construct(self):
                vmob = VMobject()
                vmob.set_stroke(color=GREEN, width=5)
                vmob.start_new_path(np.array([0, 0, 0]))
                vmob.add_line_to(np.array([1, 0, 0]))
                vmob.add_line_to(np.array([1, 1, 0]))
                vmob.start_new_path(np.array([2, 0, 0]))
                vmob.add_line_to(np.array([3, 0, 0]))
                vmob.add_line_to(np.array([3, 1, 0]))
                self.play(Create(vmob))

        scene = MultiSubpathScene()
        return scene.scene_data

    @pytest.fixture
    def arrow_with_tip_data(self) -> str:
        class VectorArrow(ManimWidget):
            def construct(self):
                arrow = Arrow(
                    ORIGIN, [1, 1, 0], buff=0, fill_opacity=1, stroke_opacity=1
                )
                self.add(arrow)

        scene = VectorArrow()
        return scene.scene_data

    @pytest.fixture
    def vgroup_scale_section_data(self) -> str:
        class VGroupScaleSection(ManimWidget):
            def construct(self):
                self.camera.background_color = "#ece6e2"
                logo = _create_logo_group()
                logo.move_to(ORIGIN + LEFT)
                self.play(Create(logo))
                self.next_section("scale")
                self.play(logo.animate.scale(2))

        scene = VGroupScaleSection()
        return scene.scene_data

    @pytest.fixture
    def vgroup_shift_data(self) -> str:
        class VGroupShiftScene(ManimWidget):
            def construct(self):
                group = VGroup(Circle(), Square().shift((1, 0, 0)))
                self.add(group)
                self.play(group.animate.shift((1, 0, 0)))

        scene = VGroupShiftScene()
        return scene.scene_data

    @pytest.fixture
    def bool_operations_data(self) -> str:
        class BooleanOperations(ManimWidget):
            def construct(self):
                ellipse1 = Ellipse(
                    width=4.0,
                    height=5.0,
                    fill_opacity=0.5,
                    color=BLUE,
                    stroke_width=10,
                ).move_to(LEFT)
                ellipse2 = ellipse1.copy().set_color(color=RED).move_to(RIGHT)
                bool_ops_text = MarkupText("<u>Boolean Operation</u>").next_to(
                    ellipse1, UP * 3
                )
                ellipse_group = VGroup(bool_ops_text, ellipse1, ellipse2).move_to(
                    LEFT * 3
                )
                self.play(FadeIn(ellipse_group))

                # i = Intersection(ellipse1, ellipse2, color=GREEN, fill_opacity=0.5)
                # self.play(i.animate.scale(0.25).move_to(RIGHT * 5 + UP * 2.5))
                # intersection_text = Text("Intersection", font_size=23).next_to(i, UP)
                # self.play(FadeIn(intersection_text))
                #
                # u = Union(ellipse1, ellipse2, color=ORANGE, fill_opacity=0.5)
                # union_text = Text("Union", font_size=23)
                # self.play(u.animate.scale(0.3).next_to(i, DOWN, buff=union_text.height * 3))
                # union_text.next_to(u, UP)
                # self.play(FadeIn(union_text))
                #
                e = Exclusion(ellipse1, ellipse2, color=GREEN, fill_opacity=0.5)
                exclusion_text = Text("Exclusion", font_size=23)
                self.play(e.animate.scale(0.3).move_to(LEFT * 3))
                exclusion_text.next_to(e, UP)
                self.play(FadeIn(exclusion_text))
                ##
                d = Difference(ellipse1, ellipse2, color=GREEN, fill_opacity=0.5)
                difference_text = Text("Difference", font_size=23)
                self.play(
                    d.animate.scale(0.3).next_to(
                        e, LEFT, buff=difference_text.height * 3.5
                    )
                )
                difference_text.next_to(d, UP)
                self.play(FadeIn(difference_text))

        scene = BooleanOperations()
        return scene.scene_data

    def test_simple_scene(self, simple_scene_data):
        returncode, report = run_cli(simple_scene_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert sections[0]["name"] == "initial"
        assert len(sections[0]["ids"]) == 1

    def test_fadein_image(self, fadein_image_data):
        data = fadein_image_data
        # Content state (kind+source) is global
        content_state = next(
            s for s in data["states"] if s.get("kind") == "ImageMobject"
        )
        assert content_state["kind"] == "ImageMobject"
        assert "source" in content_state

        section = data["sections"][0]
        register_cmd = next(c for c in section["construct"] if c["cmd"] == "register")
        animate_cmd = next(c for c in section["construct"] if c["cmd"] == "animate")

        # state_ref may be a derived state; check that chain resolves to ImageMobject
        def resolve(ref):
            s = data["states"][ref]
            return {**resolve(s["from"]), **s} if "from" in s else s

        assert resolve(register_cmd["state_ref"])["kind"] == "ImageMobject"

        assert animate_cmd["animations"][0]["kind"] == "FadeIn"
        assert animate_cmd["animations"][0]["id"] == register_cmd["id"]

        returncode, report = run_cli(fadein_image_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_animate_shift_left(self, animate_shift_left_data):
        section = animate_shift_left_data["sections"][0]
        animate_cmds = [cmd for cmd in section["construct"] if cmd["cmd"] == "animate"]
        assert len(animate_cmds) == 2
        # First play is introducer (Create), so second non-introducer play should
        # not need injected Add.
        assert not any(a["kind"] == "Add" for a in animate_cmds[1]["animations"])

        returncode, report = run_cli(animate_shift_left_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_multi_section_scene(self, multi_section_data):
        returncode, report = run_cli(multi_section_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 2
        assert sections[0]["name"] == "initial"
        assert sections[1]["name"] == "second"
        assert len(sections[0]["ids"]) == 1
        assert len(sections[1]["ids"]) == 2

    def test_create_vgroup(self, vgroup_create_data):
        returncode, report = run_cli(vgroup_create_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_vgroup_reordered(self, vgroup_reordered_data):
        returncode, report = run_cli(vgroup_reordered_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_vgroup_scale_section(self, vgroup_scale_section_data):
        returncode, report = run_cli(vgroup_scale_section_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 2
        assert sections[0]["name"] == "initial"
        assert sections[1]["name"] == "scale"
        assert len(sections[0]["ids"]) == 1
        assert len(sections[1]["ids"]) == 1

    def test_vgroup_shift(self, vgroup_shift_data):
        returncode, report = run_cli(vgroup_shift_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert sections[0]["name"] == "initial"
        assert len(sections[0]["ids"]) == 1

    def test_boolean_operations(self, boolean_operations_data):
        returncode, report = run_cli(boolean_operations_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 2

    def test_multi_subpath(self, multi_subpath_data):
        vmob = VMobject()
        vmob.start_new_path(np.array([0, 0, 0]))
        vmob.add_line_to(np.array([1, 0, 0]))
        vmob.add_line_to(np.array([1, 1, 0]))
        vmob.start_new_path(np.array([2, 0, 0]))
        vmob.add_line_to(np.array([3, 0, 0]))
        vmob.add_line_to(np.array([3, 1, 0]))
        subpaths = vmob.get_subpaths()
        assert len(subpaths) == 2, (
            f"VMobject should have 2 subpaths, got {len(subpaths)}"
        )

        returncode, report = run_cli(multi_subpath_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_arrow_with_tip(self, arrow_with_tip_data):
        returncode, report = run_cli(arrow_with_tip_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        assert report["success"], f"Expected no errors: {report['errors']}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) >= 1

    def test_invalid_points_raises_error(self):
        invalid_scene_data = {
            "version": 1,
            "fps": 10,
            "states": [
                {
                    "kind": "Circle",
                    "points": [
                        [0, 0, 0],
                        [1, 1, 1],
                        [2, 0, 0],
                        [3, 1, 1],
                        [4, 0, 0],
                        [5, 1, 1],
                        [6, 0, 0],
                        [7, 1, 1],
                        [8, 0, 0],
                    ],
                }
            ],
            "sections": [
                {
                    "name": "intro",
                    "setup": [],
                    "construct": [{"cmd": "register", "id": "circle1", "state_ref": 0}],
                }
            ],
        }

        returncode, report = run_cli(invalid_scene_data)
        assert returncode != 0, "Expected CLI to fail for invalid points"
        assert any("3n+1" in str(e) for e in report.get("errors", [])), (
            f"Expected 3n+1 error in report: {report}"
        )

    def test_boolean_operation(self, bool_operations_data):
        returncode, report = run_cli(bool_operations_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        assert len(sections[0]["ids"]) >= 3

    @pytest.fixture
    def point_moving_on_shapes_data(self) -> str:
        class PointMovingOnShapes(ManimWidget):
            def construct(self):
                circle = Circle(radius=1, color=BLUE)
                dot = Dot()
                dot2 = dot.copy().shift(RIGHT)
                self.add(dot)

                line = Line([3, 0, 0], [5, 0, 0])
                self.add(line)

                self.play(GrowFromCenter(circle))
                self.play(Transform(dot, dot2))
                self.play(MoveAlongPath(dot, circle), run_time=2, rate_func=linear)
                self.play(Rotating(dot, about_point=[2, 0, 0]), run_time=1.5)
                self.wait()

        scene = PointMovingOnShapes()
        return scene.scene_data

    def test_point_moving_on_shapes(self, point_moving_on_shapes_data):
        returncode, report = run_cli(point_moving_on_shapes_data, output_ids=True)
        sections = report["sections"]
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        assert len(sections) == 1
        assert sections[0]["name"] == "initial"

    @pytest.fixture
    def stroke_color_scene_data(self) -> str:
        class StrokeColorScene(ManimWidget):
            def construct(self):
                c = Circle(stroke_color=BLUE, fill_opacity=0.0)
                self.add(c)

        scene = StrokeColorScene()
        return scene.scene_data

    def test_cli_outputs_end_state_with_stroke(self, stroke_color_scene_data):
        returncode, report = run_cli(stroke_color_scene_data, output_end_state=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"

        sections = report["sections"]
        assert len(sections) == 1

        end_state = sections[0]["end_state"]
        snapshot = end_state["snapshot"]
        states = end_state["states"]

        assert len(snapshot) == 1
        circle_ref = next(iter(snapshot.values()))
        circle_state = states[circle_ref]

        assert circle_state["stroke_color"] == "#58C4DD"

    @pytest.fixture
    def group_two_objects_data(self) -> str:
        class GroupTwoObjectsScene(ManimWidget):
            def construct(self):
                c1 = Circle()
                c2 = Circle().shift(RIGHT)
                group = Group(c1, c2)
                self.play(FadeIn(group))

        scene = GroupTwoObjectsScene()
        return scene.scene_data

    def test_group_two_objects(self, group_two_objects_data):
        returncode, report = run_cli(group_two_objects_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        data = group_two_objects_data
        states = data["states"]
        construct = data["sections"][0]["construct"]

        assert len(states) == 3, (
            f"Expected 3 states (2 children + Group), got {len(states)}"
        )

        register_cmd = next((c for c in construct if c["cmd"] == "register"), None)
        assert register_cmd is not None, "Expected a register command"
        group_ref = register_cmd["state_ref"]

        group_state = states[group_ref]
        assert group_state["kind"] == "VGroup", (
            f"Expected VGroup, got {group_state['kind']}"
        )
        assert "children" in group_state, "Group should have children"
        assert len(group_state["children"]) == 2, (
            f"Expected 2 children, got {len(group_state.get('children', []))}"
        )

        child1_ref, child2_ref = group_state["children"]
        assert states[child1_ref]["kind"] == "VMobject"
        assert states[child2_ref]["kind"] == "VMobject"

    @pytest.fixture
    def swap_animation_data(self) -> str:
        from manim import Swap

        class SwapScene(ManimWidget):
            def construct(self):
                s1 = Square().shift(LEFT)
                s2 = Circle().shift(RIGHT)
                self.play(Create(s1), Create(s2))
                self.play(Swap(s1, s2))

        scene = SwapScene()
        return scene.scene_data

    def test_swap_animation(self, swap_animation_data):
        returncode, report = run_cli(swap_animation_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        # After swap, both original objects should be in the scene
        assert len(sections[0]["ids"]) == 2

    @pytest.fixture
    def cyclic_replace_animation_data(self) -> str:
        from manim import UP, CyclicReplace, Triangle

        class CyclicReplaceScene(ManimWidget):
            def construct(self):
                s1 = Square().shift(LEFT)
                s2 = Circle().shift(RIGHT)
                s3 = Triangle().shift(UP)
                self.play(Create(s1), Create(s2), Create(s3))
                self.play(CyclicReplace(s1, s2, s3))

        scene = CyclicReplaceScene()
        return scene.scene_data

    def test_cyclic_replace_animation(self, cyclic_replace_animation_data):
        returncode, report = run_cli(cyclic_replace_animation_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 1
        # After cyclic replace, all three objects should still be in the scene
        assert len(sections[0]["ids"]) == 3

    @pytest.fixture
    def multi_section_vgroup_arrow_data(self):
        from manim import GrowArrow, Rectangle

        class MultiSectionScene(ManimWidget):
            def construct(self):
                block = VGroup(Rectangle(), Rectangle().shift(RIGHT))
                a = Arrow(LEFT * 2, RIGHT * 2)
                self.play(Create(block), GrowArrow(a))
                self.next_section("s2")
                self.play(block.animate.shift(UP))

        return MultiSectionScene(fps=10).scene_data

    def test_vgroup_and_arrow_persist_in_section2(
        self, multi_section_vgroup_arrow_data
    ):
        """VGroup and Arrow registered in section 1 must still be present in section 2."""
        returncode, report = run_cli(multi_section_vgroup_arrow_data, output_ids=True)
        assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
        sections = report["sections"]
        assert len(sections) == 2, f"Expected 2 sections, got {len(sections)}"
        # Section 1: block + arrow registered during construct
        assert len(sections[0]["ids"]) == 2, (
            f"Section 1 should have 2 mobs, got {sections[0]['ids']}"
        )
        # Section 2: both mobs must survive the scene.clear() + setup re-registration
        assert len(sections[1]["ids"]) == 2, (
            f"Section 2 should still have 2 mobs after setup, got {sections[1]['ids']}"
        )
        # Same IDs in both sections
        assert set(sections[0]["ids"]) == set(sections[1]["ids"]), (
            f"Mob IDs changed between sections: {sections[0]['ids']} vs {sections[1]['ids']}"
        )


def test_swap_with_world_coordinate_points():
    """
    Test that Swap works correctly with world-coordinate points.

    Python manim's shift() modifies points directly, but manim-web's Swap
    now auto-centers points before the animation, so it works correctly.
    """
    # Two circles at different x positions
    # Circle 0: center at x=-1, Circle 1: center at x=+1
    scene_data = {
        "version": 1,
        "fps": 10,
        "states": [
            {
                "kind": "VMobject",
                "stroke_color": "#FC6255",
                "stroke_width": 4,
                "stroke_opacity": 1.0,
                "fill_opacity": 0.0,
                "z_index": 0,
                # Circle centered at x=-1 (radius 1)
                "points": [
                    [-2, 0, 0],
                    [-2, 0.26, 0],
                    [-1.89, 0.52, 0],
                    [-1.71, 0.71, 0],
                    [-1.52, 0.89, 0],
                    [-1.26, 1.0, 0],
                    [-1.0, 1.0, 0],
                    [-0.74, 1.0, 0],
                    [-0.48, 0.89, 0],
                    [-0.29, 0.71, 0],
                    [-0.11, 0.52, 0],
                    [0, 0.26, 0],
                    [0, 0, 0],
                    [0, -0.26, 0],
                    [-0.11, -0.52, 0],
                    [-0.29, -0.71, 0],
                    [-0.48, -0.89, 0],
                    [-0.74, -1.0, 0],
                    [-1.0, -1.0, 0],
                    [-1.26, -1.0, 0],
                    [-1.52, -0.89, 0],
                    [-1.71, -0.71, 0],
                    [-1.89, -0.52, 0],
                    [-2, -0.26, 0],
                    [-2, 0, 0],
                ],
            },
            {
                "kind": "VMobject",
                "stroke_color": "#58C4DD",
                "stroke_width": 4,
                "stroke_opacity": 1.0,
                "fill_opacity": 0.0,
                "z_index": 0,
                # Circle centered at x=+1 (radius 1)
                "points": [
                    [0, 0, 0],
                    [0, 0.26, 0],
                    [0.11, 0.52, 0],
                    [0.29, 0.71, 0],
                    [0.48, 0.89, 0],
                    [0.74, 1.0, 0],
                    [1.0, 1.0, 0],
                    [1.26, 1.0, 0],
                    [1.52, 0.89, 0],
                    [1.71, 0.71, 0],
                    [1.89, 0.52, 0],
                    [2, 0.26, 0],
                    [2, 0, 0],
                    [2, -0.26, 0],
                    [1.89, -0.52, 0],
                    [1.71, -0.71, 0],
                    [1.52, -0.89, 0],
                    [1.26, -1.0, 0],
                    [1.0, -1.0, 0],
                    [0.74, -1.0, 0],
                    [0.48, -0.89, 0],
                    [0.29, -0.71, 0],
                    [0.11, -0.52, 0],
                    [0, -0.26, 0],
                    [0, 0, 0],
                ],
            },
        ],
        "sections": [
            {
                "name": "test",
                "setup": [],
                "construct": [
                    {"cmd": "register", "id": "0", "state_ref": 0},
                    {"cmd": "register", "id": "1", "state_ref": 1},
                    {
                        "cmd": "animate",
                        "duration": 1.0,
                        "animations": [
                            {
                                "kind": "Swap",
                                "ids": ["0", "1"],
                                "params": {"path_arc": 1.57},
                                "rate_func": "smooth",
                            }
                        ],
                    },
                ],
            }
        ],
    }

    returncode, report = run_cli(scene_data, output_end_state=True)
    assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"

    # Extract JSON from output (after the === Section End State === marker)
    # JSON is pretty-printed, so find the opening brace
    end_state = report

    # After swap, circle 0 should be at x=+1, circle 1 at x=-1
    states = end_state["sections"][0]["end_state"]["states"]
    snapshot = end_state["sections"][0]["end_state"]["snapshot"]

    # Circle 0 (red) should now be at x=+1 (was at x=-1)
    state0 = states[snapshot["0"]]
    assert "position" in state0, "position should be in end state"
    assert state0["position"][0] > 0.5, (
        f"Circle 0 should be at positive x after swap, got {state0['position'][0]}"
    )

    # Circle 1 (blue) should now be at x=-1 (was at x=+1)
    state1 = states[snapshot["1"]]
    assert state1["position"][0] < -0.5, (
        f"Circle 1 should be at negative x after swap, got {state1['position'][0]}"
    )


def test_js_create_without_explicit_add_has_no_injected_add():
    class CreateOnlyScene(ManimWidget):
        def construct(self):
            c = Circle()
            self.play(Create(c))

    scene = CreateOnlyScene()
    data = scene.scene_data
    section = data["sections"][0]
    animate_cmd = next(cmd for cmd in section["construct"] if cmd["cmd"] == "animate")

    assert not any(a["kind"] == "Add" for a in animate_cmd["animations"])
    assert any(a["kind"] == "Create" for a in animate_cmd["animations"])

    returncode, report = run_cli(data, output_ids=True)
    assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"


def test_js_static_mathtex_creates_and_transforms():
    scene_data = {
        "version": 1,
        "fps": 10,
        "states": [
            {
                "kind": "StaticMathTex",
                "latex": "x^2",
                "points": [[-2, 1, 0], [2, 1, 0], [2, -1, 0], [-2, -1, 0]],
                "stroke_opacity": 1.0,
                "color": "#83C167",
            }
        ],
        "sections": [
            {
                "name": "test_tex",
                "setup": [],
                "construct": [{"cmd": "register", "id": "tex1", "state_ref": 0}],
            }
        ],
    }

    returncode, report = run_cli(scene_data, output_ids=True)
    assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
    assert report["success"], f"Unexpected errors: {report['errors']}"

    sections = report["sections"]
    assert len(sections) == 1
    assert "tex1" in sections[0]["ids"]


def test_js_static_mathtex_with_scaled_transform():
    scene_data = {
        "version": 1,
        "fps": 10,
        "states": [
            {
                "kind": "StaticMathTex",
                "latex": "\\frac{a}{b}",
                "points": [[-8, 4, 0], [8, 4, 0], [8, -4, 0], [-8, -4, 0]],
                "stroke_opacity": 1.0,
            }
        ],
        "sections": [
            {
                "name": "scaled_tex",
                "setup": [],
                "construct": [{"cmd": "register", "id": "frac", "state_ref": 0}],
            }
        ],
    }

    returncode, report = run_cli(scene_data, output_ids=True)
    assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"
    sections = report["sections"]
    assert len(sections) == 1


def test_arrow_vgroup_body_points_applied_in_end_state():
    """Regression: Arrow restores as a VGroup whose shaft child keeps its points."""
    from manim import ORIGIN, RIGHT, Arrow

    class ArrowScene(ManimWidget):
        def construct(self):
            self.add(Arrow(ORIGIN, RIGHT))

    scene = ArrowScene()
    returncode, report = run_cli(scene.scene_data, output_end_state=True)
    assert returncode == 0, f"CLI failed:\n{json.dumps(report, indent=2)}"

    end_state = report

    states = end_state["sections"][0]["end_state"]["states"]
    snapshot = end_state["sections"][0]["end_state"]["snapshot"]
    root_ref = next(iter(snapshot.values()))
    root_state = states[root_ref]

    assert root_state["kind"] == "VGroup"
    assert "children" in root_state and len(root_state["children"]) == 2

    body_ref = root_state["children"][0]
    body_state = states[body_ref]
    assert body_state["kind"] == "VMobject"
    assert len(body_state.get("points", [])) >= 4
