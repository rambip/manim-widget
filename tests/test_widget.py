from __future__ import annotations

import base64
import io
import json
import os

import numpy as np
from PIL import Image

from jsonschema import validate
from manim import (
    GREEN,
    Scene,
    Circle,
    Create,
    Dot,
    LEFT,
    ReplacementTransform,
    RIGHT,
    Square,
    VGroup,
    ValueTracker,
    ImageMobject,
)

from manim_widget.snapshot import reset_id_counter
from manim_widget.widget import ManimWidget


def load_schema() -> dict:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "spec.json")
    with open(schema_path) as f:
        return json.load(f)


def assert_close(actual: object, expected: object, tol: float = 1e-9) -> None:
    if isinstance(expected, float):
        assert isinstance(actual, int | float)
        assert abs(float(actual) - expected) <= tol
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for a, e in zip(actual, expected, strict=True):
            assert_close(a, e, tol=tol)
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert set(actual.keys()) == set(expected.keys())
        for key in expected:
            assert_close(actual[key], expected[key], tol=tol)
        return
    assert actual == expected


def strip_points(obj: dict) -> dict:
    result = {}
    for key, value in obj.items():
        if key == "points":
            continue
        if isinstance(value, dict):
            result[key] = strip_points(value)
        elif isinstance(value, list):
            result[key] = [strip_points(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result


def test_v2_updater_command_uses_state_refs_and_dedup_is_deterministic():
    reset_id_counter()

    class DataScene(ManimWidget):
        def construct(self):
            vt = ValueTracker(0)
            dot = Dot()
            dot.add_updater(lambda m: m.move_to((vt.get_value(), 0, 0)))
            self.add(vt, dot)
            self.play(vt.animate.set_value(3), run_time=0.5)

    scene = DataScene(fps=10)
    data = scene.scene_data

    expected = {
        "version": 2,
        "fps": 10,
        "sections": [
            {
                "name": "initial",
                "snapshot": {},
                "camera": {"phi": 0.0, "theta": -1.5707963267948966, "distance": 5.0, "fov": 77.31961650818019},
                "states": [
                    {"value": 0.0},
                    {
                        "kind": "VMobject",
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"value": 0.12385697935738824},
                    {
                        "kind": "VMobject",
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"value": 0.7974197341465827},
                    {
                        "kind": "VMobject",
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"value": 2.2025802658534173},
                    {
                        "kind": "VMobject",
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"value": 2.8761430206426124},
                    {
                        "kind": "VMobject",
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"value": 3.0},
                    {
                        "kind": "VMobject",
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                ],
                "construct": [
                    {"cmd": "add", "id": "0", "state_ref": 0},
                    {"cmd": "add", "id": "1", "state_ref": 1},
                    {
                        "cmd": "updater",
                        "duration": 0.5,
                        "frames": [
                            {"0": {"state_ref": 2}, "1": {"state_ref": 3}},
                            {"0": {"state_ref": 4}, "1": {"state_ref": 5}},
                            {"0": {"state_ref": 6}, "1": {"state_ref": 7}},
                            {"0": {"state_ref": 8}, "1": {"state_ref": 9}},
                            {"0": {"state_ref": 10}, "1": {"state_ref": 11}},
                        ],
                    },
                ],
            }
        ],
    }

    assert_close(strip_points(data), strip_points(expected))


def test_v2_create_then_next_section_snapshot_only_second_section():
    reset_id_counter()

    class Move(ManimWidget):
        def construct(self):
            circle = Circle(1, color=GREEN, fill_opacity=1, stroke_opacity=1)
            self.play(Create(circle))
            self.next_section("a")

    scene = Move()
    data = scene.scene_data

    expected = {
        "version": 2,
        "fps": 10,
        "sections": [
            {
                "name": "initial",
                "snapshot": {},
                "camera": {"phi": 0.0, "theta": -1.5707963267948966, "distance": 5.0, "fov": 77.31961650818019},
                "states": [
                    {
                        "kind": "VMobject",
                        "fill_color": "#83C167",
                        "fill_opacity": 1.0,
                        "stroke_color": "#83C167",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                ],
                "construct": [
                    {"cmd": "add", "id": "0", "state_ref": 0, "hidden": True},
                    {
                        "cmd": "animate",
                        "duration": 1.0,
                        "animations": [
                            {
                                "id": "0",
                                "rate_func": "smooth",
                                "kind": "Create",
                            }
                        ],
                    },
                ],
            },
            {
                "name": "a",
                "snapshot": {"0": 0},
                "states": [
                    {
                        "kind": "VMobject",
                        "fill_color": "#83C167",
                        "fill_opacity": 1.0,
                        "stroke_color": "#83C167",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                ],
                "construct": [],
            },
        ],
    }

    assert_close(strip_points(data), strip_points(expected))


def test_wait_with_vmobject():
    class SceneWithWait(ManimWidget):
        def construct(self):
            dot = Dot()
            self.add(dot)
            self.play(Create(dot))
            self.wait()

    widget = SceneWithWait()
    data = widget.scene_data
    schema = load_schema()
    validate(data, schema)

    assert data["version"] == 2
    assert len(data["sections"]) == 1
    assert len(data["sections"][0]["construct"]) == 3


def test_v2_method_animation_uses_move_to_target():
    reset_id_counter()

    class ShiftScene(ManimWidget):
        def construct(self):
            c = Circle()
            self.add(c)
            self.play(c.animate.shift((1, 0, 0)))

    scene = ShiftScene()
    data = scene.scene_data
    section = data["sections"][0]

    assert data["version"] == 2
    assert len(section["states"]) >= 2

    anim_cmd = section["construct"][1]
    assert anim_cmd["cmd"] == "animate"

    anim = anim_cmd["animations"][0]
    assert anim["id"] == "0"
    assert "state_ref" in anim
    assert anim["kind"] == "MoveToTarget"

    state_ref = anim["state_ref"]
    target_state = section["states"][state_ref]
    assert target_state["kind"] == "VMobject"


def test_v2_chained_method_animation_uses_move_to_target():
    reset_id_counter()

    class ChainedScene(ManimWidget):
        def construct(self):
            s = Square(side_length=1.0)
            self.add(s)
            self.play(s.animate.scale(2.0).shift((1, 0, 0)))

    scene = ChainedScene()
    data = scene.scene_data
    section = data["sections"][0]

    assert data["version"] == 2
    assert len(section["states"]) >= 2

    anim_cmd = section["construct"][1]
    assert anim_cmd["cmd"] == "animate"

    anim = anim_cmd["animations"][0]
    assert anim["id"] == "0"
    assert "state_ref" in anim
    assert anim["kind"] == "MoveToTarget"

    state_ref = anim["state_ref"]
    target_state = section["states"][state_ref]
    assert target_state["kind"] == "VMobject"


def test_v2_multiple_sections_with_move_to_target():
    reset_id_counter()

    class MultiSectionMoveToTarget(ManimWidget):
        def construct(self):
            c = Circle()
            self.add(c)
            self.play(c.animate.shift((1, 0, 0)))
            self.next_section("second")
            s = Square()
            self.add(s)
            self.play(s.animate.scale(2))
            self.next_section("third")
            t = Dot()
            self.add(t)
            self.play(t.animate.shift((0, 1, 0)))

    scene = MultiSectionMoveToTarget()
    data = scene.scene_data

    assert data["version"] == 2
    assert len(data["sections"]) == 3

    section1 = data["sections"][0]
    assert section1["name"] == "initial"
    assert len(section1["states"]) >= 2
    anim1 = section1["construct"][1]["animations"][0]
    assert "state_ref" in anim1
    assert anim1["kind"] == "MoveToTarget"

    section2 = data["sections"][1]
    assert section2["name"] == "second"
    assert len(section2["states"]) >= 2
    anim2 = section2["construct"][1]["animations"][0]
    assert "state_ref" in anim2
    assert anim2["kind"] == "MoveToTarget"

    section3 = data["sections"][2]
    assert section3["name"] == "third"
    assert len(section3["states"]) >= 2
    anim3 = section3["construct"][1]["animations"][0]
    assert "state_ref" in anim3
    assert anim3["kind"] == "MoveToTarget"


def test_image_mobject_serializes_source_and_pixels():
    reset_id_counter()

    pixels = np.array(
        [
            [[255, 0, 0, 255], [0, 255, 0, 255], [0, 0, 255, 255]],
            [[10, 20, 30, 255], [40, 50, 60, 200], [70, 80, 90, 128]],
        ],
        dtype=np.uint8,
    )

    class ImageScene(ManimWidget):
        def construct(self):
            img = ImageMobject(pixels)
            img.height = 2
            self.add(img)

    scene = ImageScene(fps=10)
    data = scene.scene_data
    schema = load_schema()
    validate(data, schema)

    section = data["sections"][0]
    assert section["construct"][0] == {"cmd": "add", "id": "0", "state_ref": 0}

    state = section["states"][0]
    assert state["kind"] == "ImageMobject"
    assert state["source"].startswith("data:image/png;base64,")
    assert "points" in state
    assert len(state["points"]) == 4
    assert all(len(pt) == 3 for pt in state["points"])

    encoded = state["source"].split(",", 1)[1]
    decoded = np.array(Image.open(io.BytesIO(base64.b64decode(encoded))))
    assert decoded.shape == pixels.shape
    assert np.array_equal(decoded, pixels)


def test_static_mathtex_serialization():
    reset_id_counter()
    from manim_widget.tex_patch import PatchedMathTex

    class TexScene(ManimWidget):
        def construct(self):
            tex = PatchedMathTex("x^2", font_size=72, color=GREEN)
            self.add(tex)

    scene = TexScene(fps=10)
    data = scene.scene_data
    schema = load_schema()
    validate(data, schema)

    section = data["sections"][0]
    state = section["states"][0]

    assert state["kind"] == "MathTexSource"
    assert state["latex"] == "x^2"
    assert state["font_size"] == 72
    assert state["color"] == "#83C167"
    assert "points" in state
    assert len(state["points"]) == 4
    for pt in state["points"]:
        assert len(pt) == 3


def test_static_mathtex_transform_updates_points():
    reset_id_counter()
    from manim_widget.tex_patch import PatchedMathTex

    class TexTransformScene(ManimWidget):
        def construct(self):
            tex = PatchedMathTex("x^2")
            self.add(tex)
            self.play(tex.animate.scale(2).shift(RIGHT))

    scene = TexTransformScene(fps=10)
    data = scene.scene_data
    schema = load_schema()
    validate(data, schema)

    section = data["sections"][0]

    initial_state = section["states"][0]
    assert initial_state["kind"] == "MathTexSource"
    initial_points = initial_state["points"]

    anim = section["construct"][1]["animations"][0]
    assert anim["kind"] == "MoveToTarget"

    final_state = section["states"][anim["state_ref"]]
    assert final_state["kind"] == "MathTexSource"
    final_points = final_state["points"]

    assert initial_points != final_points


def test_patch_tex_replaces_manim_classes():
    from manim_widget import patch_tex
    import manim

    original_math_tex = manim.MathTex
    original_tex = manim.Tex

    patch_tex()

    assert manim.MathTex is not original_math_tex
    assert manim.Tex is not original_tex

    tex = manim.Tex("test")
    assert tex.tex_string == "test"

    manim.MathTex = original_math_tex
    manim.Tex = original_tex


def test_swap_animation_emits_group_animation():
    reset_id_counter()

    class SwapScene(ManimWidget):
        def construct(self):
            from manim import Swap

            s1 = Square().shift(LEFT)
            s2 = Circle().shift(RIGHT)
            self.add(s1, s2)
            self.play(Swap(s1, s2))

    scene = SwapScene()
    data = scene.scene_data
    section = data["sections"][0]

    assert data["version"] == 2

    # Find the animate command (should be after add commands)
    animate_cmd = None
    for cmd in section["construct"]:
        if cmd["cmd"] == "animate":
            animate_cmd = cmd
            break
    assert animate_cmd is not None

    anim = animate_cmd["animations"][0]
    assert anim["kind"] == "Swap"
    assert "ids" in anim
    assert anim["ids"] == ["0", "1"]

    # path_arc should be present (default is PI/2)
    if "params" in anim:
        assert "path_arc" in anim["params"]


def test_cyclic_replace_animation_emits_group_animation():
    reset_id_counter()

    class CyclicReplaceScene(ManimWidget):
        def construct(self):
            from manim import CyclicReplace, Triangle, UP

            s1 = Square().shift(LEFT)
            s2 = Circle().shift(RIGHT)
            s3 = Triangle().shift(UP)
            self.add(s1, s2, s3)
            self.play(CyclicReplace(s1, s2, s3))

    scene = CyclicReplaceScene()
    data = scene.scene_data
    section = data["sections"][0]

    assert data["version"] == 2

    # Find the animate command
    animate_cmd = None
    for cmd in section["construct"]:
        if cmd["cmd"] == "animate":
            animate_cmd = cmd
            break
    assert animate_cmd is not None

    anim = animate_cmd["animations"][0]
    assert anim["kind"] == "CyclicReplace"
    assert "ids" in anim
    assert len(anim["ids"]) == 3


def test_camera_fov_calculation():
    """Test that FOV is correctly computed from Manim camera parameters."""
    import math

    class SimpleScene(Scene):
        def construct(self):
            s = Square()
            self.play(Create(s))

    widget = ManimWidget(SimpleScene)
    data = widget.scene_data

    # Check camera state includes fov
    camera = data["sections"][0]["camera"]
    assert "fov" in camera

    # Verify FOV calculation: fov = 2 * atan(frame_height / (2 * distance))
    # With defaults: frame_height=8, distance=5
    expected_fov = 2 * math.degrees(math.atan(8 / (2 * 5)))
    assert abs(camera["fov"] - expected_fov) < 0.001
    assert abs(camera["fov"] - 77.32) < 0.01  # Approximate check
