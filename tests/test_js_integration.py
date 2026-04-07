from __future__ import annotations

import json
import subprocess
import tempfile
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
    Ellipse,
    Exclusion,
    FadeIn,
    Intersection,
    MarkupText,
    Square,
    Text,
    Triangle,
    VGroup,
    VMobject,
)

from manim_widget.widget import ManimWidget

CLI_PATH = Path(__file__).parent.parent / "js" / "src" / "cli.js"


def run_cli(scene_data: str | dict) -> tuple[int, str, str]:
    if isinstance(scene_data, dict):
        scene_json = json.dumps(scene_data)
    else:
        scene_json = scene_data

    result = subprocess.run(
        ["bun", "run", str(CLI_PATH)],
        input=scene_json,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


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
    def boolean_operations_data(self) -> str:
        class BooleanOperations(ManimWidget):
            def construct(self):
                ellipse1 = Ellipse(
                    width=2, height=3, fill_opacity=0.5, color=BLUE
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
    def bool_operations_data(self) -> str:
        class BooleanOperations(ManimWidget):
            def construct(self):
                ellipse1 = Ellipse(
                    width=4.0,
                    height=5.0,
                    fill_opacity=0.5,
                    color=mn.BLUE,
                    stroke_width=10,
                ).move_to(LEFT)
                ellipse2 = ellipse1.copy().set_color(color=mn.RED).move_to(RIGHT)
                bool_ops_text = MarkupText("<u>Boolean Operation</u>").next_to(
                    ellipse1, UP * 3
                )
                ellipse_group = VGroup(bool_ops_text, ellipse1, ellipse2).move_to(
                    LEFT * 3
                )
                self.play(FadeIn(ellipse_group))

                # i = Intersection(ellipse1, ellipse2, color=mn.GREEN, fill_opacity=0.5)
                # self.play(i.animate.scale(0.25).move_to(RIGHT * 5 + UP * 2.5))
                # intersection_text = Text("Intersection", font_size=23).next_to(i, UP)
                # self.play(FadeIn(intersection_text))
                #
                # u = Union(ellipse1, ellipse2, color=mn.ORANGE, fill_opacity=0.5)
                # union_text = Text("Union", font_size=23)
                # self.play(u.animate.scale(0.3).next_to(i, DOWN, buff=union_text.height * 3))
                # union_text.next_to(u, UP)
                # self.play(FadeIn(union_text))
                #
                e = Exclusion(ellipse1, ellipse2, color=mn.YELLOW, fill_opacity=0.5)
                exclusion_text = Text("Exclusion", font_size=23)
                self.play(e.animate.scale(0.3).move_to(LEFT * 3))
                exclusion_text.next_to(e, UP)
                self.play(FadeIn(exclusion_text))
                ##
                d = Difference(ellipse1, ellipse2, color=mn.PINK, fill_opacity=0.5)
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
        returncode, stdout, stderr = run_cli(simple_scene_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"

    def test_animate_shift_left(self, animate_shift_left_data):
        returncode, stdout, stderr = run_cli(animate_shift_left_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"

    def test_multi_section_scene(self, multi_section_data):
        returncode, stdout, stderr = run_cli(multi_section_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"

    def test_create_vgroup(self, vgroup_create_data):
        returncode, stdout, stderr = run_cli(vgroup_create_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"

    def test_boolean_operations(self, boolean_operations_data):
        returncode, stdout, stderr = run_cli(boolean_operations_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"

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

        returncode, stdout, stderr = run_cli(multi_subpath_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"

    def test_arrow_with_tip(self, arrow_with_tip_data):
        returncode, stdout, stderr = run_cli(arrow_with_tip_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"
        assert "Errors: 0" in stdout, f"Expected no errors. stdout:\n{stdout}"

    def test_invalid_points_raises_error(self):
        invalid_scene_data = {
            "version": 2,
            "fps": 10,
            "sections": [
                {
                    "name": "intro",
                    "snapshot": {},
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
                            "opacity": 1,
                        }
                    ],
                    "construct": [{"cmd": "add", "id": "circle1", "state_ref": 0}],
                }
            ],
        }

        returncode, stdout, stderr = run_cli(invalid_scene_data)
        assert returncode != 0, "Expected CLI to fail for invalid points"
        assert "3n+1" in stderr or "3n+1" in stdout, (
            f"Expected '3n+1' in output. stderr:\n{stderr}\nstdout:\n{stdout}"
        )

    def test_boolean_operation(self, bool_operations_data):
        returncode, stdout, stderr = run_cli(bool_operations_data)
        assert returncode == 0, f"CLI failed with stderr:\n{stderr}\nstdout:\n{stdout}"
