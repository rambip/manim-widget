from __future__ import annotations

import json
import os

from jsonschema import validate
from manim import Circle, Dot, ReplacementTransform, Square, ValueTracker

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

    section = data["sections"][0]
    assert data["version"] == 2
    assert section["name"] == "initial"
    assert section["snapshot"] == {}

    construct = section["construct"]
    assert construct[0]["cmd"] == "add"
    assert construct[1]["cmd"] == "add"
    assert construct[2]["cmd"] == "data"

    data_cmd = construct[2]
    assert data_cmd["duration"] == 0.5
    assert len(data_cmd["frames"]) == 5

    states = section["states"]
    assert isinstance(states, list)
    assert len(states) >= 3

    for frame in data_cmd["frames"]:
        assert set(frame.keys()) == {"0", "1"}
        assert set(frame["0"].keys()) == {"state_ref"}
        assert set(frame["1"].keys()) == {"state_ref"}
        assert 0 <= frame["0"]["state_ref"] < len(states)
        assert 0 <= frame["1"]["state_ref"] < len(states)

    dot_ref_seq = [frame["1"]["state_ref"] for frame in data_cmd["frames"]]
    assert dot_ref_seq == sorted(dot_ref_seq)


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
    validate(instance=data, schema=schema)


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
