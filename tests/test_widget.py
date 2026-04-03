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


def test_v2_scene_with_add_shift_transform_rebind_and_sections_exact_json():
    reset_id_counter()

    class SceneV2(ManimWidget):
        def construct(self):
            c = Circle()
            self.add(c)
            self.play(c.animate.shift((1, 0, 0)))
            self.next_section("second")
            s = Square()
            self.play(ReplacementTransform(c, s))

    scene = SceneV2()
    data = json.loads(scene.scene_data)

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
                        "opacity": 0.0,
                        "fill_color": "#FC6255",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FC6255",
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
                                "kind": "Shift",
                                "params": {"vector": [1, 0, 0]},
                            }
                        ],
                    },
                ],
            },
            {
                "name": "second",
                "snapshot": {
                    "0": {
                        "kind": "Circle",
                        "opacity": 0.0,
                        "fill_color": "#FC6255",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FC6255",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                },
                "states": [
                    {
                        "kind": "Square",
                        "opacity": 0.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                ],
                "construct": [
                    {
                        "cmd": "animate",
                        "duration": 1.0,
                        "animations": [
                            {
                                "id": "0",
                                "rate_func": "smooth",
                                "type": "transform",
                                "kind": "Transform",
                                "state_ref": 0,
                                "params": {
                                    "path_arc": 0.0,
                                    "path_arc_axis": [0.0, 0.0, 1.0],
                                },
                            }
                        ],
                    },
                    {"cmd": "rebind", "source_id": "0", "target_id": "1"},
                ],
            },
        ],
    }

    assert_close(strip_points(data), strip_points(expected))


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
    data = json.loads(scene.scene_data)

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


def test_v2_scene_validates_against_schema():
    reset_id_counter()
    schema = load_schema()

    class SchemaScene(ManimWidget):
        def construct(self):
            c = Circle()
            self.add(c)
            self.play(c.animate.shift((1, 0, 0)))

    scene = SchemaScene()
    data = json.loads(scene.scene_data)
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
                        "opacity": 0.0,
                        "fill_color": "#FC6255",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FC6255",
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
                                "kind": "Shift",
                                "params": {"vector": [1, 0, 0]},
                            }
                        ],
                    },
                ],
            }
        ],
    }

    assert_close(strip_points(data), strip_points(expected))
    validate(instance=data, schema=schema)


def test_v2_create_then_next_section_snapshot_only_second_section():
    reset_id_counter()

    class Move(ManimWidget):
        def construct(self):
            circle = Circle(1, color=GREEN, fill_opacity=1, stroke_opacity=1)
            self.play(Create(circle))
            self.next_section("a")

    scene = Move()
    data = json.loads(scene.scene_data)

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
                "snapshot": {
                    "0": {
                        "kind": "Circle",
                        "opacity": 1.0,
                        "fill_color": "#83C167",
                        "fill_opacity": 1.0,
                        "stroke_color": "#83C167",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                },
                "states": [],
                "construct": [],
            },
        ],
    }

    assert_close(strip_points(data), strip_points(expected))


def test_v2_multiple_sections():
    reset_id_counter()

    class MultiSectionScene(ManimWidget):
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

    scene = MultiSectionScene()
    data = json.loads(scene.scene_data)

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
                        "opacity": 0.0,
                        "fill_color": "#FC6255",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FC6255",
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
                                "kind": "Shift",
                                "params": {"vector": [1, 0, 0]},
                            }
                        ],
                    },
                ],
            },
            {
                "name": "second",
                "snapshot": {
                    "0": {
                        "kind": "Circle",
                        "opacity": 0.0,
                        "fill_color": "#FC6255",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FC6255",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                },
                "states": [
                    {
                        "kind": "Square",
                        "opacity": 0.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                ],
                "construct": [
                    {"cmd": "add", "id": "1", "state_ref": 0},
                    {
                        "cmd": "animate",
                        "duration": 1.0,
                        "animations": [
                            {
                                "id": "1",
                                "rate_func": "smooth",
                                "type": "simple",
                                "kind": "ScaleInPlace",
                                "params": {"scale_factor": 2},
                            }
                        ],
                    },
                ],
            },
            {
                "name": "third",
                "snapshot": {
                    "0": {
                        "kind": "Circle",
                        "opacity": 0.0,
                        "fill_color": "#FC6255",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FC6255",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                    "1": {
                        "kind": "Square",
                        "opacity": 0.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 0.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_width": 4,
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    },
                },
                "states": [
                    {
                        "kind": "Dot",
                        "opacity": 1.0,
                        "fill_color": "#FFFFFF",
                        "fill_opacity": 1.0,
                        "stroke_color": "#FFFFFF",
                        "stroke_opacity": 1.0,
                        "z_index": 0,
                    }
                ],
                "construct": [
                    {"cmd": "add", "id": "2", "state_ref": 0},
                    {
                        "cmd": "animate",
                        "duration": 1.0,
                        "animations": [
                            {
                                "id": "2",
                                "rate_func": "smooth",
                                "type": "simple",
                                "kind": "Shift",
                                "params": {"vector": [0, 1, 0]},
                            }
                        ],
                    },
                ],
            },
        ],
    }

    assert_close(strip_points(data), strip_points(expected))


def test_v2_vgroup_children_are_state_refs():
    reset_id_counter()

    class GroupScene(ManimWidget):
        def construct(self):
            c = Circle()
            s = Square()
            g = VGroup(c, s)
            self.add(g)

    scene = GroupScene()
    data = json.loads(scene.scene_data)
    section = data["sections"][0]
    states = section["states"]

    assert section["construct"][0]["cmd"] == "add"
    group_state = states[section["construct"][0]["state_ref"]]
    assert group_state["kind"] == "VGroup"
    assert group_state["children"] == [0, 1]
    assert states[0]["kind"] == "Circle"
    assert states[1]["kind"] == "Square"
