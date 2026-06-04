from __future__ import annotations

import base64
import io
import json
import math
import os

import numpy as np
import pytest
from PIL import Image

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from jsonschema import validate
from manim import (
    GREEN,
    Scene,
    Circle,
    Create,
    Dot,
    LEFT,
    RIGHT,
    Square,
    ValueTracker,
    ImageMobject,
)

from manim_widget.widget import ManimWidget
from manim_widget.renderer import CaptureRenderer
from manim_widget.states import (
    VMobjectState,
    VGroupState,
    ValueTrackerState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _fresh_renderer() -> CaptureRenderer:
    """Return a renderer with one open section, ready for direct unit testing."""
    r = CaptureRenderer(fps=10)
    r.open_section("test")
    return r


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

coord = st.floats(-20.0, 20.0, allow_nan=False, allow_infinity=False)
point3 = st.lists(coord, min_size=3, max_size=3)
hex_color = st.from_regex(r"#[0-9A-F]{6}", fullmatch=True)
opacity = st.floats(0.0, 1.0, allow_nan=False)
z_idx = st.floats(-10.0, 10.0, allow_nan=False, allow_infinity=False)


@st.composite
def bezier_points_3n1(draw, min_segments: int = 0, max_segments: int = 4):
    """Generate a valid 3n+1 points list (n bezier segments)."""
    n = draw(st.integers(min_value=min_segments, max_value=max_segments))
    if n == 0:
        return []
    pts = draw(st.lists(point3, min_size=3 * n + 1, max_size=3 * n + 1))
    return pts


@st.composite
def vmobject_state(draw):
    points = draw(st.one_of(st.none(), bezier_points_3n1()))
    return VMobjectState(
        points=points,
        fill_color=draw(st.one_of(st.none(), hex_color)),
        fill_opacity=draw(st.one_of(st.none(), opacity)),
        stroke_color=draw(st.one_of(st.none(), hex_color)),
        stroke_width=draw(st.one_of(st.none(), st.floats(0.0, 20.0, allow_nan=False))),
        stroke_opacity=draw(st.one_of(st.none(), opacity)),
        z_index=draw(st.one_of(st.none(), z_idx)),
    )


@st.composite
def value_tracker_state(draw):
    return ValueTrackerState(
        value=draw(st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False))
    )


# ---------------------------------------------------------------------------
# Property tests: VMobjectState / Pydantic validation
# ---------------------------------------------------------------------------


@given(bezier_points_3n1(min_segments=1))
def test_vmobject_state_accepts_valid_3n1_points(pts):
    state = VMobjectState(points=pts)
    assert (len(state.points) - 1) % 3 == 0


@given(st.integers(min_value=1, max_value=6).map(lambda n: n * 3))
def test_vmobject_state_rejects_non_3n1_points(bad_len):
    """A points list of length 3n (not 3n+1) must be rejected."""
    from pydantic import ValidationError

    pts = [[0.0, 0.0, 0.0]] * bad_len
    with pytest.raises(ValidationError):
        VMobjectState(points=pts)


@given(vmobject_state())
def test_vmobject_state_round_trips_via_model_dump(state):
    d = state.model_dump(exclude_none=True)
    assert d.get("kind") == "VMobject"
    if "points" in d:
        assert (len(d["points"]) - 1) % 3 == 0
        assert all(len(p) == 3 for p in d["points"])


@given(value_tracker_state())
def test_value_tracker_state_has_no_kind(state):
    d = state.model_dump(exclude_none=True)
    assert "kind" not in d
    assert "value" in d


# ---------------------------------------------------------------------------
# Property tests: _intern_state (deduplication, bounds, idempotency)
# ---------------------------------------------------------------------------


@given(vmobject_state())
def test_intern_state_returns_valid_ref(state):
    r = _fresh_renderer()
    ref = r._intern_state(state)
    assert 0 <= ref < len(r._current.states)


@given(vmobject_state())
def test_intern_state_is_idempotent(state):
    r = _fresh_renderer()
    ref1 = r._intern_state(state)
    ref2 = r._intern_state(state)
    assert ref1 == ref2
    assert len(r._current.states) == 1


@given(vmobject_state(), vmobject_state())
def test_intern_state_distinct_states_get_distinct_refs(s1, s2):
    d1 = s1.model_dump(exclude_none=True)
    d2 = s2.model_dump(exclude_none=True)
    assume(d1 != d2)
    r = _fresh_renderer()
    ref1 = r._intern_state(s1)
    ref2 = r._intern_state(s2)
    assert ref1 != ref2
    assert len(r._current.states) == 2


@given(st.lists(vmobject_state(), min_size=1, max_size=8))
def test_intern_state_bank_length_never_exceeds_unique_count(states):
    r = _fresh_renderer()
    for s in states:
        r._intern_state(s)
    unique = len(
        {json.dumps(s.model_dump(exclude_none=True), sort_keys=True) for s in states}
    )
    assert len(r._current.states) == unique


# ---------------------------------------------------------------------------
# Property tests: serialize_mobject structural invariants
# ---------------------------------------------------------------------------


@given(bezier_points_3n1(min_segments=1, max_segments=3))
@settings(max_examples=30)
def test_serialize_single_subpath_vmobject_preserves_point_format(pts_list):
    """A VMobject with exactly one subpath must serialize to VMobjectState with 3n+1 points."""
    from manim import VMobject as ManimVMobject

    mob = ManimVMobject()
    # Build a single Bezier subpath: set_points expects raw (4k) format
    n_segs = (len(pts_list) - 1) // 3
    raw_pts = []
    for i in range(n_segs):
        seg_pts = pts_list[i * 3 : i * 3 + 4]
        raw_pts.extend(seg_pts)
    assume(len(raw_pts) >= 4)
    mob.set_points(np.array(raw_pts, dtype=float))

    r = _fresh_renderer()
    r.open_section("s")
    result = r.serialize_mobject(mob, for_snapshot=False)

    assert isinstance(result, VMobjectState)
    if result.points:
        assert (len(result.points) - 1) % 3 == 0
        assert all(len(p) == 3 for p in result.points)


@given(st.floats(-100.0, 100.0, allow_nan=False, allow_infinity=False))
def test_serialize_value_tracker(value):
    from manim import ValueTracker

    mob = ValueTracker(value)
    r = _fresh_renderer()
    r.open_section("s")
    result = r.serialize_mobject(mob, for_snapshot=False)
    assert isinstance(result, ValueTrackerState)
    assert abs(result.value - value) < 1e-9


# ---------------------------------------------------------------------------
# Deterministic regression tests (exact payload assertions)
# ---------------------------------------------------------------------------


def test_v2_updater_command_uses_state_refs_and_dedup_is_deterministic():
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
                "camera": {
                    "phi": 0.0,
                    "theta": -1.5707963267948966,
                    "distance": 5.0,
                    "fov": 77.31961650818019,
                },
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
                    {"cmd": "register", "id": "0", "state_ref": 0},
                    {"cmd": "register", "id": "1", "state_ref": 1},
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
                "camera": {
                    "phi": 0.0,
                    "theta": -1.5707963267948966,
                    "distance": 5.0,
                    "fov": 77.31961650818019,
                },
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
                    {"cmd": "register", "id": "0", "state_ref": 0},
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

    anim = next(a for a in anim_cmd["animations"] if a["kind"] != "Add")
    assert anim["id"] == "0"
    assert "state_ref" in anim
    assert anim["kind"] == "MoveToTarget"

    target_state = section["states"][anim["state_ref"]]
    assert target_state["kind"] == "VMobject"


def test_v2_multiple_sections_with_move_to_target():
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
    for section in data["sections"]:
        anim = next(
            a for a in section["construct"][-1]["animations"] if a["kind"] != "Add"
        )
        assert "state_ref" in anim
        assert anim["kind"] == "MoveToTarget"


def test_add_injected_for_explicit_add_before_non_introducer_animation():
    class ShiftScene(ManimWidget):
        def construct(self):
            c = Circle()
            self.add(c)
            self.play(c.animate.shift((1, 0, 0)))

    scene = ShiftScene()
    section = scene.scene_data["sections"][0]
    anim_cmd = section["construct"][1]

    assert anim_cmd["cmd"] == "animate"
    assert any(a["kind"] == "Add" and a["id"] == "0" for a in anim_cmd["animations"])
    assert any(
        a["kind"] == "MoveToTarget" and a["id"] == "0" for a in anim_cmd["animations"]
    )


def test_add_not_reinjected_after_first_animation_batch():
    class TwoPlaysScene(ManimWidget):
        def construct(self):
            c = Circle()
            self.add(c)
            self.play(c.animate.shift((1, 0, 0)))
            self.play(c.animate.shift((1, 0, 0)))

    scene = TwoPlaysScene()
    section = scene.scene_data["sections"][0]
    animate_cmds = [cmd for cmd in section["construct"] if cmd["cmd"] == "animate"]

    assert len(animate_cmds) == 2
    assert any(a["kind"] == "Add" for a in animate_cmds[0]["animations"])
    assert not any(a["kind"] == "Add" for a in animate_cmds[1]["animations"])


def test_create_without_explicit_add_does_not_emit_add_animation():
    class CreateScene(ManimWidget):
        def construct(self):
            c = Circle()
            self.play(Create(c))

    scene = CreateScene()
    section = scene.scene_data["sections"][0]
    anim_cmd = next(cmd for cmd in section["construct"] if cmd["cmd"] == "animate")

    assert not any(a["kind"] == "Add" for a in anim_cmd["animations"])
    assert any(a["kind"] == "Create" and a["id"] == "0" for a in anim_cmd["animations"])


def test_mathtex_add_only_emits_add_animation():
    from manim_widget import patch_tex
    import manim

    original_math_tex = manim.MathTex
    original_tex = manim.Tex

    patch_tex()
    try:
        from manim import MathTex, WHITE

        class MathTexAddOnlyScene(ManimWidget):
            def construct(self):
                tex = MathTex(r"{0}", fill_color=WHITE)
                self.add(tex)

        scene = MathTexAddOnlyScene(fps=10)
        section = scene.scene_data["sections"][0]
        anim_cmd = next(cmd for cmd in section["construct"] if cmd["cmd"] == "animate")

        assert any(
            a["kind"] == "Add" and a["id"] == "0" for a in anim_cmd["animations"]
        )
    finally:
        manim.MathTex = original_math_tex
        manim.Tex = original_tex


def test_image_mobject_serializes_source_and_pixels():
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
    assert section["construct"][0] == {"cmd": "register", "id": "0", "state_ref": 0}

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
    assert state["color"] == "#83C167"
    assert "points" in state
    assert len(state["points"]) == 4
    for pt in state["points"]:
        assert len(pt) == 3

    assert state["points"][0] == pytest.approx([-1.5, 1.5, 0.0])
    assert state["points"][1] == pytest.approx([1.5, 1.5, 0.0])
    assert state["points"][2] == pytest.approx([1.5, -1.5, 0.0])
    assert state["points"][3] == pytest.approx([-1.5, -1.5, 0.0])


def test_swap_animation_emits_group_animation():
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

    animate_cmd = next(cmd for cmd in section["construct"] if cmd["cmd"] == "animate")
    anim = next(a for a in animate_cmd["animations"] if a["kind"] != "Add")
    assert anim["kind"] == "Swap"
    assert anim["ids"] == ["0", "1"]


def test_cyclic_replace_animation_emits_group_animation():
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

    animate_cmd = next(cmd for cmd in section["construct"] if cmd["cmd"] == "animate")
    anim = next(a for a in animate_cmd["animations"] if a["kind"] != "Add")
    assert anim["kind"] == "CyclicReplace"
    assert len(anim["ids"]) == 3


def test_camera_fov_calculation():
    class SimpleScene(Scene):
        def construct(self):
            s = Square()
            self.play(Create(s))

    widget = ManimWidget(SimpleScene)
    data = widget.scene_data

    camera = data["sections"][0]["camera"]
    assert "fov" in camera

    expected_fov = 2 * math.degrees(math.atan(8 / (2 * 5)))
    assert abs(camera["fov"] - expected_fov) < 0.001


def test_camera_theta_attr_assignment_is_serialized():
    class ZYImageCNN(ManimWidget):
        def construct(self):
            self.camera.theta = 0.2

    scene = ZYImageCNN(fps=10)
    data = scene.scene_data
    schema = load_schema()
    validate(data, schema)

    camera = data["sections"][0]["camera"]
    assert abs(camera["theta"] - 0.2) < 1e-12


def test_camera_distance_and_fov_attr_assignment_is_serialized():
    class ZYImageCNN(ManimWidget):
        def construct(self):
            self.camera.distance = 7.5
            self.camera.fov = 52.0

    scene = ZYImageCNN(fps=10)
    data = scene.scene_data
    schema = load_schema()
    validate(data, schema)

    camera = data["sections"][0]["camera"]
    assert abs(camera["distance"] - 7.5) < 1e-12
    assert abs(camera["fov"] - 52.0) < 1e-12


def test_camera_set_before_next_section_appears_in_both_sections():
    class CameraSetupScene(ManimWidget):
        def construct(self):
            self.camera.theta = 0.5
            self.camera.phi = 0.3
            self.camera.distance = 10.0
            self.next_section("after_camera_setup")

    scene = CameraSetupScene(fps=10)
    data = scene.scene_data

    for section in data["sections"]:
        cam = section["camera"]
        assert abs(cam["theta"] - 0.5) < 1e-9
        assert abs(cam["phi"] - 0.3) < 1e-9
        assert abs(cam["distance"] - 10.0) < 1e-9


# ---------------------------------------------------------------------------
# Property tests: Arrow / VGroup structural invariants (replace hand-crafted)
# ---------------------------------------------------------------------------


def test_arrow_serializes_as_vgroup_container():
    """Arrow: pure VGroup container, no points on container, 2 VMobject children."""
    from manim import Arrow

    class ArrowScene(ManimWidget):
        def construct(self):
            a = Arrow(start=LEFT, end=RIGHT)
            self.play(Create(a))

    scene = ArrowScene(fps=10)
    states = scene.scene_data["sections"][0]["states"]

    arrow_state = next(
        (
            s
            for s in states
            if s.get("kind") == "VGroup"
            and all(
                states[r].get("kind") == "VMobject" and states[r].get("points")
                for r in s["children"]
            )
        ),
        None,
    )

    assert arrow_state is not None
    assert "points" not in arrow_state
    assert len(arrow_state["children"]) == 2


@given(
    st.lists(vmobject_state(), min_size=2, max_size=6),
    st.integers(min_value=0, max_value=5),
)
def test_intern_state_ref_always_in_bounds_after_mixed_inserts(states, extra_repeats):
    """Repeating intern calls never push ref out of bounds."""
    r = _fresh_renderer()
    refs = [r._intern_state(s) for s in states]
    # Re-intern a subset to exercise deduplication path
    for s in states[:extra_repeats]:
        ref = r._intern_state(s)
        assert 0 <= ref < len(r._current.states)
    for ref in refs:
        assert 0 <= ref < len(r._current.states)


@given(bezier_points_3n1(min_segments=1, max_segments=3))
@settings(max_examples=25)
def test_state_bank_stores_dict_not_pydantic_model(pts):
    """States in the bank must be plain dicts (for JSON serialization)."""
    r = _fresh_renderer()
    state = VMobjectState(points=pts)
    ref = r._intern_state(state)
    stored = r._current.states[ref]
    assert isinstance(stored, dict)
    assert stored.get("kind") == "VMobject"


@given(vmobject_state())
def test_serialize_mobject_never_produces_arrow_kind(state):
    """No serialize path should ever emit kind='Arrow'."""
    d = state.model_dump(exclude_none=True)
    assert d.get("kind") != "Arrow"


@given(
    st.lists(vmobject_state(), min_size=1, max_size=4),
)
def test_vgroup_state_children_are_all_ints(child_states):
    r = _fresh_renderer()
    children = [r._intern_state(s) for s in child_states]
    vg = VGroupState(children=children)
    assert all(isinstance(c, int) for c in vg.children)
    d = vg.model_dump(exclude_none=True)
    assert "points" not in d
    assert d["kind"] == "VGroup"
