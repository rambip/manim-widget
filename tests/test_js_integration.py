from __future__ import annotations

import json
import os

import numpy as np
import pytest
from jsonschema import validate

from manim import (
    BLUE,
    GREEN,
    Group,
    LEFT,
    ORIGIN,
    RED,
    RIGHT,
    UP,
    AnimationGroup,
    Circle,
    Create,
    Difference,
    Ellipse,
    Exclusion,
    Intersection,
    ImageMobject,
    MarkupText,
    Square,
    Text,
    Triangle,
    VGroup,
    VMobject,
    FadeIn,
)
from manim_widget.widget import ManimWidget


def _load_schema() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "spec.json")
    with open(path) as f:
        return json.load(f)


_SCHEMA = _load_schema()


def assert_valid_schema(data: dict) -> None:
    validate(data, _SCHEMA)


def _create_logo_group() -> VGroup:
    """Create the standard logo group: circle, square, triangle."""
    logo_green = "#87c2a5"
    logo_black = "#343434"
    logo_red = "#e07a5f"
    circle = Circle(color=logo_green, fill_opacity=1).shift(LEFT)
    square = Square(color=logo_black, fill_opacity=1).shift(UP)
    triangle = Triangle(color=logo_red, fill_opacity=1).shift(RIGHT)
    return VGroup(triangle, square, circle)


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

    def test_simple_scene(self, runner, simple_scene_data):
        r = runner.check_data_validated(simple_scene_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 1
        assert sections[0]["name"] == "initial"
        assert len(sections[0]["ids"]) == 1

    def test_fadein_image(self, runner, fadein_image_data):
        section = fadein_image_data["sections"][0]
        states = fadein_image_data["states"]
        # DAG: content entry (kind+source) and addon entry (from+points)
        image_idx = next(
            i for i, s in enumerate(states) if s.get("kind") == "ImageMobject"
        )
        addon_idx = next(i for i, s in enumerate(states) if "from" in s)
        assert states[image_idx]["kind"] == "ImageMobject"
        assert "from" in states[addon_idx]

        register_cmd = section["construct"][0]
        animate_cmd = section["construct"][1]
        assert register_cmd["cmd"] == "register"
        # register points to the addon state (which has positional data)
        assert states[register_cmd["state_ref"]].get("from") == image_idx

        assert animate_cmd["cmd"] == "animate"
        assert animate_cmd["animations"][0]["kind"] == "FadeIn"
        assert animate_cmd["animations"][0]["id"] == register_cmd["id"]

        r = runner.check_data_validated(fadein_image_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_animate_shift_left(self, runner, animate_shift_left_data):
        section = animate_shift_left_data["sections"][0]
        animate_cmds = [cmd for cmd in section["construct"] if cmd["cmd"] == "animate"]
        assert len(animate_cmds) == 2
        # First play is introducer (Create), so second non-introducer play should
        # not need injected Add.
        assert not any(a["kind"] == "Add" for a in animate_cmds[1]["animations"])

        r = runner.check_data_validated(animate_shift_left_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_multi_section_scene(self, runner, multi_section_data):
        r = runner.check_data_validated(multi_section_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 2
        assert sections[0]["name"] == "initial"
        assert sections[1]["name"] == "second"
        assert len(sections[0]["ids"]) == 1
        assert len(sections[1]["ids"]) == 2

    def test_create_vgroup(self, runner, vgroup_create_data):
        r = runner.check_data_validated(vgroup_create_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        assert len(r.section_ids) == 1

    def test_vgroup_reordered(self, runner, vgroup_reordered_data):
        r = runner.check_data_validated(vgroup_reordered_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        assert len(r.section_ids) == 1

    def test_vgroup_scale_section(self, runner, vgroup_scale_section_data):
        r = runner.check_data_validated(vgroup_scale_section_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 2
        assert sections[0]["name"] == "initial"
        assert sections[1]["name"] == "scale"

    def test_vgroup_shift(self, runner, vgroup_shift_data):
        r = runner.check_data_validated(vgroup_shift_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        assert len(r.section_ids) == 1

    def test_boolean_operations(self, runner, boolean_operations_data):
        r = runner.check_data_validated(boolean_operations_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 1

    def test_multi_subpath(self, runner, multi_subpath_data):
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

        r = runner.check_data_validated(multi_subpath_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 1
        assert len(sections[0]["ids"]) == 1

    def test_invalid_contours_raises_error(self, runner):
        # contour with 9 points is invalid: must be 3n+1 (e.g. 4, 7, 10...)
        invalid_scene_data = {
            "version": 2,
            "fps": 10,
            "states": [
                {
                    "kind": "Circle",
                    "contours": [
                        [
                            [0, 0, 0],
                            [1, 1, 1],
                            [2, 0, 0],
                            [3, 1, 1],
                            [4, 0, 0],
                            [5, 1, 1],
                            [6, 0, 0],
                            [7, 1, 1],
                            [8, 0, 0],
                        ]
                    ],
                }
            ],
            "sections": [
                {
                    "name": "intro",
                    "snapshot": {},
                    "construct": [{"cmd": "register", "id": "circle1", "state_ref": 0}],
                }
            ],
        }

        r = runner.check_data(invalid_scene_data)
        assert not r.ok, "Expected CLI to fail for invalid contour point count"
        assert any("3n+1" in str(e) for e in r.errors), (
            f"Expected 3n+1 error, got: {r.errors}"
        )

    def test_boolean_operation(self, runner, bool_operations_data):
        r = runner.check_data_validated(bool_operations_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 1
        assert len(sections[0]["ids"]) >= 3

    @pytest.fixture
    def stroke_color_scene_data(self) -> str:
        class StrokeColorScene(ManimWidget):
            def construct(self):
                c = Circle(stroke_color=BLUE, fill_opacity=0.0)
                self.add(c)

        scene = StrokeColorScene()
        return scene.scene_data

    def test_cli_outputs_end_state_with_stroke(self, runner, stroke_color_scene_data):
        r = runner.check_data_validated(stroke_color_scene_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"

        sections = r.section_end_states
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

    def test_group_two_objects(self, runner, group_two_objects_data):
        r = runner.check_data_validated(group_two_objects_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        data = group_two_objects_data
        states = data["states"]
        construct = data["sections"][0]["construct"]

        mob_states = [s for s in states if s.get("kind") != "Camera"]
        assert len(mob_states) == 3, (
            f"Expected 3 states (2 children + Group), got {len(mob_states)}"
        )

        register_cmd = next(
            (c for c in construct if c["cmd"] == "register" and "child_ids" in c), None
        )
        assert register_cmd is not None, (
            "Expected a group register command with child_ids"
        )
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

    def test_swap_animation(self, runner, swap_animation_data):
        r = runner.check_data_validated(swap_animation_data, _SCHEMA)
        assert r.ok, f"CLI failed: {r.errors}"
        sections = r.section_ids
        assert len(sections) == 1
        # After swap, both original objects should be in the scene
        assert len(sections[0]["ids"]) == 2


def test_swap_with_world_coordinate_points(runner):
    """
    Test that Swap works correctly with world-coordinate points.

    Python manim's shift() modifies points directly, but manim-web's Swap
    now auto-centers points before the animation, so it works correctly.
    """
    # Two circles at different x positions
    # Circle 0: center at x=-1, Circle 1: center at x=+1
    scene_data = {
        "version": 2,
        "fps": 10,
        "states": [
            {
                "kind": "VMobject",
                "stroke_color": "#FC6255",
                "stroke_width": 4,
                "stroke_opacity": 1.0,
                "fill_opacity": 0.0,
                "z_index": 0,
                "contours": [
                    [
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
                    ]
                ],
            },
            {
                "kind": "VMobject",
                "stroke_color": "#58C4DD",
                "stroke_width": 4,
                "stroke_opacity": 1.0,
                "fill_opacity": 0.0,
                "z_index": 0,
                "contours": [
                    [
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
                    ]
                ],
            },
        ],
        "sections": [
            {
                "name": "test",
                "snapshot": {},
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

    r = runner.check_data_validated(scene_data, _SCHEMA)
    assert r.ok, f"CLI failed: {r.errors}"

    # After swap, circle 0 should be at x=+1, circle 1 at x=-1
    states = r.section_end_states[0]["end_state"]["states"]
    snapshot = r.section_end_states[0]["end_state"]["snapshot"]

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


def test_js_create_without_explicit_add_has_no_injected_add(runner):
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

    r = runner.check_data_validated(data, _SCHEMA)
    assert r.ok, f"CLI failed: {r.errors}"


def test_animation_group_plays_without_error(runner):
    """AnimationGroup serializes start/end timestamps and plays back cleanly."""

    class AnimGroupScene(ManimWidget):
        def construct(self):
            c = Circle()
            s = Square()
            self.play(Create(c))
            self.play(
                AnimationGroup(
                    c.animate.shift(LEFT), s.animate.shift(RIGHT), lag_ratio=0.5
                )
            )

    scene = AnimGroupScene()
    r = runner.check_data_validated(scene.scene_data, _SCHEMA)
    assert r.ok, f"CLI failed:\n{r.errors}\n{r.section_ids}"

    assert r.error_count == 0


def _minimal_scene_data(states: list, *, state_ref: int = 0) -> dict:
    """Build a minimal valid scene_data with a single register command."""
    return {
        "version": 1,
        "fps": 10,
        "states": states,
        "sections": [
            {
                "name": "default",
                "snapshot": {"0": state_ref},
                "construct": [{"cmd": "register", "id": "0", "state_ref": state_ref}],
            }
        ],
    }


def test_derived_state_in_order_no_warning(runner):
    """Valid image placement split: content at index 0, Derived at index 1 — no warning."""
    states = [
        {"kind": "ImageMobject", "source": "data:image/png;base64,abc"},
        {
            "kind": "Derived",
            "from": 0,
            "points": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
        },
    ]
    data = _minimal_scene_data(states, state_ref=1)
    r = runner.check_data(data)
    assert r.ok, f"CLI failed: {r.errors}"
    derived_warnings = [
        w for w in r.warnings if w.get("kind") == "derived_out_of_order"
    ]
    assert derived_warnings == [], f"Unexpected warnings: {derived_warnings}"


def test_derived_state_out_of_order_warns(runner):
    """Derived entry whose 'from' points forward must trigger a warning."""
    states = [
        {
            "kind": "Derived",
            "from": 1,
            "points": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
        },
        {"kind": "ImageMobject", "source": "data:image/png;base64,abc"},
    ]
    data = _minimal_scene_data(states, state_ref=0)
    r = runner.check_data(data)
    derived_warnings = [
        w for w in r.warnings if w.get("kind") == "derived_out_of_order"
    ]
    assert len(derived_warnings) == 1
    assert derived_warnings[0]["index"] == 0
    assert derived_warnings[0]["from"] == 1


def test_image_mobject_produces_no_derived_warning(runner):
    """A real ImageMobject scene must not trigger any Derived ordering warning."""
    import numpy as np

    pixels = np.zeros((4, 4, 4), dtype=np.uint8)

    class ImageScene(ManimWidget):
        def construct(self):
            img = ImageMobject(pixels)
            self.add(img)

    r = runner.check_data(ImageScene().scene_data)
    assert r.ok, f"CLI failed: {r.errors}"
    derived_warnings = [
        w for w in r.warnings if w.get("kind") == "derived_out_of_order"
    ]
    assert derived_warnings == [], f"Unexpected warnings: {derived_warnings}"
