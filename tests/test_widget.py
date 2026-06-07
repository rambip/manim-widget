from __future__ import annotations

import base64
import io
import json
import math
import os

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from jsonschema import validate
from PIL import Image

from manim_widget.models import SceneData
from manim import (
    GREEN,
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
from manim_widget.renderer import CaptureRenderer, _needs_camera_frame_loop
from tests.scene_strategies import (
    construct_script,
    run_generated_scene,
    UpdaterCmd,
)
from manim_widget.states import (
    VMobjectState,
    VGroupState,
    ValueTrackerState,
)


def assert_valid_scene(data: dict) -> None:
    SceneData.model_validate(data)


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


def load_schema() -> dict:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "spec.json")
    with open(schema_path) as f:
        return json.load(f)


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
def test_value_tracker_state_serializes_kind(state):
    d = state.model_dump(exclude_none=True)
    assert d["kind"] == "ValueTracker"
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
    assert_valid_scene(data)

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
    assert_valid_scene(data)

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
    assert_valid_scene(data)

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


def test_static_mathtex_transform_updates_points():
    from manim_widget.tex_patch import PatchedMathTex

    class TexTransformScene(ManimWidget):
        def construct(self):
            tex = PatchedMathTex("x^2")
            self.add(tex)
            self.play(tex.animate.scale(2).shift(RIGHT))

    scene = TexTransformScene(fps=10)
    data = scene.scene_data
    assert_valid_scene(data)

    section = data["sections"][0]

    initial_state = section["states"][0]
    assert initial_state["kind"] == "MathTexSource"
    initial_points = initial_state["points"]

    anim = next(a for a in section["construct"][1]["animations"] if a["kind"] != "Add")
    assert anim["kind"] == "MoveToTarget"

    final_state = section["states"][anim["state_ref"]]
    assert final_state["kind"] == "MathTexSource"
    final_points = final_state["points"]

    assert initial_points != final_points


def test_mathtex_boundary_points_and_scale_center():
    """Verify get_points_defining_boundary returns corners and scale uses center."""
    from manim_widget.tex_patch import PatchedMathTex

    tex = PatchedMathTex("x^2", font_size=96)  # scale = 2.0

    # Boundary points should be the 4 corners
    boundary = tex.get_points_defining_boundary()
    assert len(boundary) == 4

    # Scale factor 96/48 = 2.0, so corners at ±2 in x and y
    expected_corners = [
        (-2.0, 2.0, 0.0),  # top_left
        (2.0, 2.0, 0.0),  # top_right
        (2.0, -2.0, 0.0),  # bottom_right
        (-2.0, -2.0, 0.0),  # bottom_left
    ]
    for pt, exp in zip(boundary, expected_corners):
        assert np.allclose(pt, exp)

    # Center should be at origin
    center = tex.get_center()
    assert np.allclose(center, [0.0, 0.0, 0.0])

    # After scaling about center, center should remain at origin
    tex.scale(0.5)
    assert np.allclose(tex.get_center(), [0.0, 0.0, 0.0])

    # Points should be halved
    new_boundary = tex.get_points_defining_boundary()
    for pt, exp in zip(new_boundary, expected_corners):
        assert np.allclose(pt, [e * 0.5 for e in exp])


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


def test_patch_tex_mathtex_add_serializes_as_mathtexsource():
    from manim_widget import patch_tex
    import manim

    original_math_tex = manim.MathTex
    original_tex = manim.Tex

    patch_tex()
    try:
        from manim import MathTex, WHITE

        class MathTexScene(ManimWidget):
            def construct(self):
                tex = MathTex(r"{0}", fill_color=WHITE)
                self.add(tex.scale(1))

        scene = MathTexScene(fps=10)
        data = scene.scene_data
        assert_valid_scene(data)

        section = data["sections"][0]
        register_cmd = section["construct"][0]
        state = section["states"][register_cmd["state_ref"]]

        assert state["kind"] == "MathTexSource"
        assert state["latex"] == r"{0}"
        assert "points" in state
        assert len(state["points"]) == 4
    finally:
        manim.MathTex = original_math_tex
        manim.Tex = original_tex


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
    """Test that FOV is correctly computed from Manim camera parameters."""

    class SimpleScene(ManimWidget):
        def construct(self):
            s = Square()
            self.play(Create(s))

    widget = SimpleScene(fps=10)
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
    assert_valid_scene(data)

    camera = data["sections"][0]["camera"]
    assert abs(camera["theta"] - 0.2) < 1e-12


def test_camera_distance_and_fov_attr_assignment_is_serialized():
    class ZYImageCNN(ManimWidget):
        def construct(self):
            self.camera.distance = 7.5
            self.camera.fov = 52.0

    scene = ZYImageCNN(fps=10)
    data = scene.scene_data
    assert_valid_scene(data)

    camera = data["sections"][0]["camera"]
    assert abs(camera["distance"] - 7.5) < 1e-12
    assert abs(camera["fov"] - 52.0) < 1e-12


def test_same_square_scaled_and_readded_serializes_only_scaled_state():
    class ScaledSquareScene(ManimWidget):
        def construct(self):
            s = Square(side_length=1.0)
            self.add(s)
            s.scale(2.0)
            self.add(s)

    scene = ScaledSquareScene(fps=10)
    data = scene.scene_data
    section = data["sections"][0]

    register_cmds = [cmd for cmd in section["construct"] if cmd["cmd"] == "register"]
    assert len(register_cmds) == 1

    state_ref = register_cmds[0]["state_ref"]
    points = section["states"][state_ref]["points"]
    assert abs(points[0][0] - 1.0) < 1e-9
    assert abs(points[0][1] - 1.0) < 1e-9
    assert abs(points[0][2] - 0.0) < 1e-9


def test_register_play_mutate_register_back_emits_two_registers_with_two_states():
    class AddPlayMutateAddBack(ManimWidget):
        def construct(self):
            s = Square(side_length=1.0)
            self.add(s)
            self.play()  # flush staged adds
            s.scale(2.0)
            self.add(s)

    scene = AddPlayMutateAddBack(fps=10)
    section = scene.scene_data["sections"][0]

    register_cmds = [cmd for cmd in section["construct"] if cmd["cmd"] == "register"]
    assert len(register_cmds) == 2

    p0 = section["states"][register_cmds[0]["state_ref"]]["points"][0]
    p1 = section["states"][register_cmds[1]["state_ref"]]["points"][0]

    assert abs(p0[0] - 0.5) < 1e-9
    assert abs(p1[0] - 1.0) < 1e-9


def test_register_new_section_register_back_emits_two_registers_with_two_states():
    class AddSectionAddBack(ManimWidget):
        def construct(self):
            s = Square(side_length=1.0)
            self.add(s)
            self.next_section("second")
            s.scale(2.0)
            self.add(s)

    scene = AddSectionAddBack(fps=10)
    data = scene.scene_data

    s0 = data["sections"][0]
    s1 = data["sections"][1]

    reg0 = [cmd for cmd in s0["construct"] if cmd["cmd"] == "register"]
    reg1 = [cmd for cmd in s1["construct"] if cmd["cmd"] == "register"]
    assert len(reg0) == 1
    assert len(reg1) == 1

    p0 = s0["states"][reg0[0]["state_ref"]]["points"][0]
    p1 = s1["states"][reg1[0]["state_ref"]]["points"][0]

    assert abs(p0[0] - 0.5) < 1e-9
    assert abs(p1[0] - 1.0) < 1e-9


def test_camera_set_before_next_section_appears_in_first_and_second_sections():
    """Test that camera parameters set before next_section() appear in both outgoing and new section entry."""

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


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Integration tests: frame-loop routing
# ---------------------------------------------------------------------------


def test_manim_camera_has_no_updaters_attribute():
    """Manim's ThreeDCamera has no 'updaters' attribute, so the camera-updater
    branch of _needs_camera_frame_loop is currently unreachable for real scenes.
    If a future Manim version adds camera updaters this test will fail and we'll
    need to revisit the predicate."""
    from manim.camera.three_d_camera import ThreeDCamera

    cam = ThreeDCamera()
    assert not hasattr(cam, "updaters"), (
        "ThreeDCamera now has 'updaters' — revisit _needs_camera_frame_loop"
    )


def test_needs_camera_frame_loop_false_for_real_scene_with_real_animation():
    """_needs_camera_frame_loop must return False for a typical non-camera play()
    so the optimised (no frame-loop) path is actually taken."""

    class SimpleScene(ManimWidget):
        _captured: bool = False

        def construct(self):
            c = Circle()
            anims = self.compile_animations(Create(c))
            SimpleScene._captured = _needs_camera_frame_loop(self, anims)
            self.play(Create(c))

    SimpleScene()
    assert not SimpleScene._captured


# ---------------------------------------------------------------------------
# Property tests: generated scenes
# ---------------------------------------------------------------------------


@given(construct_script(min_mobs=1, max_mobs=4, min_plays=2, max_plays=5))
@settings(max_examples=30, deadline=None)
def test_generated_scene_produces_valid_schema(args):
    """Any randomly generated (non-updater) scene must pass JSON schema validation."""
    mob_specs, commands = args
    schema = load_schema()
    data = run_generated_scene(mob_specs, commands, fps=5)
    validate(data, schema)


@given(construct_script(min_mobs=1, max_mobs=4, min_plays=2, max_plays=5))
@settings(max_examples=30, deadline=None)
def test_generated_scene_no_camera_updates_in_animate_commands(args):
    """Non-updater scenes must never emit camera_updates in animate commands
    (frame loop skipped)."""
    mob_specs, commands = args
    data = run_generated_scene(mob_specs, commands, fps=5)
    for section in data["sections"]:
        for cmd in section["construct"]:
            if cmd["cmd"] == "animate":
                assert "camera_updates" not in cmd


@given(
    construct_script(
        min_mobs=1, max_mobs=3, min_plays=1, max_plays=4, allow_updaters=True
    )
)
@settings(max_examples=20, deadline=None)
def test_generated_scene_updater_commands_have_correct_frame_count(args):
    """Every 'updater' command must have exactly ceil(fps * run_time) frames."""
    import math as _math

    mob_specs, commands = args
    fps = 5
    data = run_generated_scene(mob_specs, commands, fps=fps)

    updater_run_times = [
        cmd.run_time for cmd in commands if isinstance(cmd, UpdaterCmd)
    ]
    updater_wire_cmds = [
        c
        for section in data["sections"]
        for c in section["construct"]
        if c["cmd"] == "updater"
    ]

    assert len(updater_wire_cmds) == len(updater_run_times)
    for wire_cmd, rt in zip(updater_wire_cmds, updater_run_times):
        assert len(wire_cmd["frames"]) == _math.ceil(fps * rt)


@given(construct_script(min_mobs=1, max_mobs=3, min_plays=2, max_plays=5))
@settings(max_examples=20, deadline=None)
def test_generated_scene_all_state_refs_in_bounds(args):
    """Every state_ref anywhere in the output must be a valid index into
    the section's states list."""
    mob_specs, commands = args
    data = run_generated_scene(mob_specs, commands, fps=5)

    for section in data["sections"]:
        n_states = len(section["states"])
        for ref in section.get("snapshot", {}).values():
            assert 0 <= ref < n_states
        for cmd in section["construct"]:
            if "state_ref" in cmd:
                assert 0 <= cmd["state_ref"] < n_states
            for anim in cmd.get("animations", []):
                if "state_ref" in anim:
                    assert 0 <= anim["state_ref"] < n_states
            for frame in cmd.get("frames", []):
                for mob_frame in frame.values():
                    assert 0 <= mob_frame["state_ref"] < n_states


@given(
    construct_script(
        min_mobs=2,
        max_mobs=4,
        min_plays=3,
        max_plays=6,
        allow_transform=True,
        allow_fadeout=True,
        allow_groups=True,
    )
)
@settings(max_examples=20, deadline=None)
def test_generated_scene_with_transforms_fadeouts_groups_is_valid(args):
    """Scenes mixing Create, Transform, Shift, FadeOut and VGroups must pass
    schema validation and have coherent state refs."""
    mob_specs, commands = args
    schema = load_schema()
    data = run_generated_scene(mob_specs, commands, fps=5)
    validate(data, schema)

    for section in data["sections"]:
        n_states = len(section["states"])
        for cmd in section["construct"]:
            for anim in cmd.get("animations", []):
                if "state_ref" in anim:
                    assert 0 <= anim["state_ref"] < n_states


# ---------------------------------------------------------------------------
# Group registration invariants
# ---------------------------------------------------------------------------


def _collect_register_invariants(section: dict) -> None:
    """Assert group registration invariants for a single section's construct list.

    1. For every register with child_ids, all those IDs appear in earlier registers.
    2. child_ids length == len(VGroupState.children) for the referenced state.
    3. Every animate descriptor ID appears in a prior register.
    4. No duplicate register IDs within a section.
    """
    states = section["states"]
    seen_register_ids: set[str] = set()
    duplicate_ids: list[str] = []

    for cmd in section["construct"]:
        if cmd["cmd"] == "register":
            rid = cmd["id"]
            if rid in seen_register_ids:
                duplicate_ids.append(rid)
            else:
                seen_register_ids.add(rid)

            child_ids = cmd.get("child_ids", [])
            for cid in child_ids:
                assert cid in seen_register_ids, (
                    f"child_id '{cid}' in register '{rid}' was not registered before its parent"
                )

            if child_ids:
                state = states[cmd["state_ref"]]
                assert state.get("kind") == "VGroup", (
                    f"register '{rid}' has child_ids but state kind is {state.get('kind')!r}"
                )
                assert len(child_ids) == len(state.get("children", [])), (
                    f"register '{rid}' child_ids length {len(child_ids)} != "
                    f"VGroupState.children length {len(state.get('children', []))}"
                )

        elif cmd["cmd"] == "animate":
            for anim in cmd.get("animations", []):
                if "id" in anim and anim.get("kind") != "Add":
                    assert anim["id"] in seen_register_ids, (
                        f"animate descriptor id '{anim['id']}' not in prior registers"
                    )

    assert not duplicate_ids, f"Duplicate register IDs within section: {duplicate_ids}"


@given(
    construct_script(
        min_mobs=1,
        max_mobs=4,
        min_plays=1,
        max_plays=5,
        allow_groups=True,
    )
)
@settings(max_examples=40, deadline=None)
def test_generated_scene_group_registration_invariants(args):
    """For every generated scene with groups, all group registration invariants hold."""
    mob_specs, commands = args
    data = run_generated_scene(mob_specs, commands, fps=5)
    for section in data["sections"]:
        _collect_register_invariants(section)


@given(
    construct_script(
        min_mobs=2,
        max_mobs=5,
        min_plays=2,
        max_plays=7,
        allow_transform=True,
        allow_fadeout=True,
        allow_groups=True,
    )
)
@settings(max_examples=20, deadline=None)
def test_generated_scene_child_ids_precede_parent_always(args):
    """child_ids ordering invariant holds even with transforms and fadeouts."""
    mob_specs, commands = args
    data = run_generated_scene(mob_specs, commands, fps=5)
    for section in data["sections"]:
        _collect_register_invariants(section)
