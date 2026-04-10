from __future__ import annotations

import json
import os

from jsonschema import validate
from manim import (
    GREEN,
    Circle,
    Create,
    Dot,
    ReplacementTransform,
    Square,
    VGroup,
    ValueTracker,
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


def test_v2_data_command_uses_state_refs_and_dedup_is_deterministic():
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
                "states": [
                    {"kind": "ValueTracker", "value": 0.0},
                    {
                        "kind": "Dot",
                        "opacity": 1.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"kind": "ValueTracker", "value": 0.12385697935738824},
                    {
                        "kind": "Dot",
                        "opacity": 1.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"kind": "ValueTracker", "value": 0.7974197341465827},
                    {
                        "kind": "Dot",
                        "opacity": 1.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"kind": "ValueTracker", "value": 2.2025802658534173},
                    {
                        "kind": "Dot",
                        "opacity": 1.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"kind": "ValueTracker", "value": 2.8761430206426124},
                    {
                        "kind": "Dot",
                        "opacity": 1.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    {"kind": "ValueTracker", "value": 3.0},
                    {
                        "kind": "Dot",
                        "opacity": 1.0,
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
                        "cmd": "data",
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
                "states": [
                    {
                        "kind": "Circle",
                        "opacity": 1.0,
                        "fill_color": "#83C167",
                        "fill_opacity": 1.0,
                        "stroke_color": "#83C167",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                ],
                "construct": [
                    {"cmd": "add", "id": "0", "state_ref": 0},
                    {
                        "cmd": "animate",
                        "duration": 1.0,
                        "animations": [
                            {
                                "id": "0",
                                "rate_func": "smooth",
                                "type": "simple",
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
                        "kind": "Circle",
                        "opacity": 1.0,
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
    assert anim["type"] == "transform"
    assert anim["kind"] == "MoveToTarget"
    assert "state_ref" in anim

    state_ref = anim["state_ref"]
    target_state = section["states"][state_ref]
    assert target_state["kind"] == "Circle"


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
    assert anim["type"] == "transform"
    assert anim["kind"] == "MoveToTarget"
    assert "state_ref" in anim

    state_ref = anim["state_ref"]
    target_state = section["states"][state_ref]
    assert target_state["kind"] == "Square"


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
    assert anim1["type"] == "transform"
    assert anim1["kind"] == "MoveToTarget"
    assert "state_ref" in anim1

    section2 = data["sections"][1]
    assert section2["name"] == "second"
    assert len(section2["states"]) >= 2
    anim2 = section2["construct"][1]["animations"][0]
    assert anim2["type"] == "transform"
    assert anim2["kind"] == "MoveToTarget"
    assert "state_ref" in anim2

    section3 = data["sections"][2]
    assert section3["name"] == "third"
    assert len(section3["states"]) >= 2
    anim3 = section3["construct"][1]["animations"][0]
    assert anim3["type"] == "transform"
    assert anim3["kind"] == "MoveToTarget"
    assert "state_ref" in anim3
