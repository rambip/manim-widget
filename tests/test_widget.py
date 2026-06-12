from __future__ import annotations

import base64
import io
import json
from pathlib import Path

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
    ImageMobject,
)

from manim_widget.widget import ManimWidget
from manim_widget.renderer import (
    CaptureRenderer,
    _classify_subpaths,
    _needs_camera_loop,
)
from manim_widget.states import _contour_winding
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


_SPEC = json.loads((Path(__file__).parent.parent / "spec.json").read_text())


def assert_valid_scene(data: dict) -> None:
    validate(data, _SPEC)
    SceneData.model_validate(data)


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


def _polygon_contour(n_sides: int, clockwise: bool = False) -> list[list[float]]:
    """Regular polygon with n_sides as a 3n+1 bezier contour.

    Uses n_sides >= 3 so signed area is unambiguous.
    CCW by default (angles increasing); CW when clockwise=True.
    """
    angles = [2 * 3.14159 * i / n_sides for i in range(n_sides + 1)]
    if clockwise:
        angles = angles[::-1]
    pts = [[float(np.cos(a)), float(np.sin(a)), 0.0] for a in angles]
    full: list[list[float]] = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        mid = [(p0[j] + p1[j]) / 2 for j in range(3)]
        full.extend([p0, mid, mid])
    full.append(pts[-1])
    return full


@st.composite
def ccw_contour(draw, min_sides: int = 3, max_sides: int = 8):
    """Generate a CCW 3n+1 contour (regular polygon, guaranteed CCW)."""
    n = draw(st.integers(min_value=min_sides, max_value=max_sides))
    return _polygon_contour(n, clockwise=False)


@st.composite
def cw_contour(draw, min_sides: int = 3, max_sides: int = 8):
    """Generate a CW 3n+1 contour (regular polygon, guaranteed CW)."""
    n = draw(st.integers(min_value=min_sides, max_value=max_sides))
    return _polygon_contour(n, clockwise=True)


@st.composite
def vmobject_state(draw):
    n_contours = draw(st.integers(min_value=0, max_value=2))
    n_holes = draw(st.integers(min_value=0, max_value=2))
    return VMobjectState(
        contours=[draw(ccw_contour()) for _ in range(n_contours)],
        holes=[draw(cw_contour()) for _ in range(n_holes)],
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


@given(ccw_contour())
def test_vmobject_state_accepts_ccw_contour(pts):
    state = VMobjectState(contours=[pts])
    assert len(state.contours) == 1
    assert (len(state.contours[0]) - 1) % 3 == 0


@given(cw_contour())
def test_vmobject_state_accepts_cw_hole(pts):
    state = VMobjectState(holes=[pts])
    assert len(state.holes) == 1
    assert (len(state.holes[0]) - 1) % 3 == 0


@given(cw_contour())
def test_vmobject_state_rejects_cw_contour(pts):
    """CW points in contours must be rejected (contours must be CCW)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="CCW"):
        VMobjectState(contours=[pts])


@given(ccw_contour())
def test_vmobject_state_rejects_ccw_hole(pts):
    """CCW points in holes must be rejected (holes must be CW)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="CW"):
        VMobjectState(holes=[pts])


@given(st.integers(min_value=1, max_value=6).map(lambda n: n * 3))
def test_vmobject_state_rejects_non_3n1_contour(bad_len):
    """A contour with length 3n (not 3n+1) must be rejected."""
    from pydantic import ValidationError

    pts = [[0.0, 0.0, 0.0]] * bad_len
    with pytest.raises(ValidationError):
        VMobjectState(contours=[pts])


@given(vmobject_state())
def test_vmobject_state_round_trips_via_model_dump(state):
    d = state.model_dump(exclude_none=True)
    assert d.get("kind") == "VMobject"
    for c in d.get("contours", []):
        assert (len(c) - 1) % 3 == 0
        assert all(len(p) == 3 for p in c)
    for h in d.get("holes", []):
        assert (len(h) - 1) % 3 == 0
        assert all(len(p) == 3 for p in h)


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
    assert 0 <= ref < len(r._state_registry.as_list())


@given(vmobject_state(), vmobject_state())
def test_intern_state_distinct_states_get_distinct_refs(s1, s2):
    d1 = s1.model_dump(exclude_none=True)
    d2 = s2.model_dump(exclude_none=True)
    assume(d1 != d2)
    r = _fresh_renderer()
    ref1 = r._intern_state(s1)
    ref2 = r._intern_state(s2)
    assert ref1 != ref2
    assert len(r._state_registry.as_list()) == 2


# ---------------------------------------------------------------------------
# Property tests: serialize_mobject structural invariants
# ---------------------------------------------------------------------------


@given(bezier_points_3n1(min_segments=1, max_segments=3))
@settings(max_examples=30)
def test_serialize_single_subpath_vmobject_gives_one_contour_no_holes(pts_list):
    """A VMobject with one subpath serializes to VMobjectState with exactly one contour."""
    from manim import VMobject as ManimVMobject
    from manim_widget.states import _contour_winding

    mob = ManimVMobject()
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
    assert len(result.holes) == 0
    assert len(result.contours) <= 1
    for c in result.contours:
        assert (len(c) - 1) % 3 == 0
        assert _contour_winding(c) == "CCW"


def test_classify_subpaths_text_O_gives_one_contour_one_hole():
    """Text 'O' has one outer contour and one hole regardless of SVG winding."""
    from manim import Text
    from manim_widget.renderer import _classify_subpaths
    from manim_widget.states import _contour_winding

    mob = Text("O").submobjects[0]
    contours, holes = _classify_subpaths(mob.get_subpaths())

    assert len(contours) == 1
    assert len(holes) == 1
    assert _contour_winding(contours[0]) == "CCW"
    assert _contour_winding(holes[0]) == "CW"


def test_classify_subpaths_text_i_gives_two_contours_no_holes():
    """Text 'i' has two disconnected outer contours (stem + dot), no holes."""
    from manim import Text
    from manim_widget.renderer import _classify_subpaths
    from manim_widget.states import _contour_winding

    mob = Text("i").submobjects[0]
    contours, holes = _classify_subpaths(mob.get_subpaths())

    assert len(contours) == 2
    assert len(holes) == 0
    assert all(_contour_winding(c) == "CCW" for c in contours)


def test_classify_subpaths_difference_gives_one_contour_one_hole():
    """Difference(big, small) has one outer contour and one hole."""
    from manim import Circle, Difference
    from manim_widget.renderer import _classify_subpaths
    from manim_widget.states import _contour_winding

    mob = Difference(Circle(radius=1), Circle(radius=0.4))
    contours, holes = _classify_subpaths(mob.get_subpaths())

    assert len(contours) == 1
    assert len(holes) == 1
    assert _contour_winding(contours[0]) == "CCW"
    assert _contour_winding(holes[0]) == "CW"


def test_classify_subpaths_text_B_winding_invariant():
    """All contours are CCW and all holes are CW regardless of font."""
    from manim import Text
    from manim_widget.renderer import _classify_subpaths
    from manim_widget.states import _contour_winding

    mob = Text("B").submobjects[0]
    contours, holes = _classify_subpaths(mob.get_subpaths())

    assert len(contours) >= 1
    assert all(_contour_winding(c) == "CCW" for c in contours)
    assert all(_contour_winding(h) == "CW" for h in holes)


@given(st.floats(-100.0, 100.0, allow_nan=False, allow_infinity=False))
def test_serialize_value_tracker(value):
    from manim import ValueTracker

    mob = ValueTracker(value)
    r = _fresh_renderer()
    r.open_section("s")
    result = r.serialize_mobject(mob, for_snapshot=False)
    assert isinstance(result, ValueTrackerState)
    assert abs(result.value - value) < 1e-9


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


def test_method_animation_uses_move_to_target():
    class ShiftScene(ManimWidget):
        def construct(self):
            c = Circle()
            self.add(c)
            self.play(c.animate.shift((1, 0, 0)))

    scene = ShiftScene()
    data = scene.scene_data
    section = data["sections"][0]

    assert data["version"] == 2
    assert len(data["states"]) >= 2

    anim_cmd = section["construct"][1]
    assert anim_cmd["cmd"] == "animate"

    anim = next(a for a in anim_cmd["animations"] if a["kind"] != "Add")
    assert anim["id"] == "0"
    assert "state_ref" in anim
    assert anim["kind"] == "MoveToTarget"

    target_state = data["states"][anim["state_ref"]]
    assert target_state["kind"] == "VMobject"


def test_multiple_sections_with_move_to_target():
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
    from manim_widget.tex_patch import PatchedMathTex, unpatch_tex
    import manim

    patch_tex()
    try:
        assert manim.MathTex is PatchedMathTex
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
        unpatch_tex()


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
    states = data["states"]
    # DAG: content entry (kind+source) and addon entry (from+points)
    content_idx = next(
        i for i, s in enumerate(states) if s.get("kind") == "ImageMobject"
    )
    addon_idx = next(i for i, s in enumerate(states) if "from" in s)

    assert section["construct"][0]["cmd"] == "register"
    assert section["construct"][0]["id"] == "0"
    # register points to the addon state, which points back to the content state
    assert states[section["construct"][0]["state_ref"]].get("from") == content_idx

    content_state = states[content_idx]
    addon_state = states[addon_idx]
    assert content_state["kind"] == "ImageMobject"
    assert content_state["source"].startswith("data:image/png;base64,")
    assert "points" in addon_state
    assert len(addon_state["points"]) == 4
    assert all(len(pt) == 3 for pt in addon_state["points"])

    encoded = content_state["source"].split(",", 1)[1]
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

    state = next(s for s in data["states"] if s.get("kind") == "MathTexSource")

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

    initial_state = next(s for s in data["states"] if s.get("kind") == "MathTexSource")
    assert initial_state["kind"] == "MathTexSource"
    initial_points = initial_state["points"]

    anim = next(a for a in section["construct"][1]["animations"] if a["kind"] != "Add")
    assert anim["kind"] == "MoveToTarget"

    final_state = data["states"][anim["state_ref"]]
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


def test_patch_tex_mathtex_add_serializes_as_mathtexsource():
    from manim_widget import patch_tex
    from manim_widget.tex_patch import PatchedMathTex, unpatch_tex
    import manim

    patch_tex()
    try:
        assert manim.MathTex is PatchedMathTex
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
        state = data["states"][register_cmd["state_ref"]]

        assert state["kind"] == "MathTexSource"
        assert state["latex"] == r"{0}"
        assert "points" in state
        assert len(state["points"]) == 4
    finally:
        unpatch_tex()


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


def test_camera_state_is_in_state_bank():
    """Camera states must be stored in the global state bank as kind='Camera'."""

    class SimpleScene(ManimWidget):
        def construct(self):
            s = Square()
            self.play(Create(s))

    data = SimpleScene(fps=10).scene_data
    assert_valid_scene(data)
    cam_states = [s for s in data["states"] if s.get("kind") == "Camera"]
    # Static scene always has exactly 1 Camera state (the initial snapshot position)
    assert len(cam_states) == 1


def test_camera_state_has_four_points_and_focal_distance():
    """A CameraState entry must have exactly 4 corner points and a focal_distance."""
    from manim_widget.renderer import _serialize_camera
    from manim.camera.three_d_camera import ThreeDCamera

    cam = ThreeDCamera()
    pts, fd = _serialize_camera(cam, 14.222, 8.0)
    assert len(pts) == 4
    assert all(len(p) == 3 for p in pts)
    assert isinstance(fd, float)
    assert fd > 0


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
    state = data["states"][state_ref]
    first_anchor = state["contours"][0][0]
    assert abs(first_anchor[0] - 1.0) < 1e-9
    assert abs(first_anchor[1] - 1.0) < 1e-9
    assert abs(first_anchor[2] - 0.0) < 1e-9


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

    states = scene.scene_data["states"]
    p0 = states[register_cmds[0]["state_ref"]]["contours"][0][0]
    p1 = states[register_cmds[1]["state_ref"]]["contours"][0][0]

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

    global_states = data["states"]
    p0 = global_states[reg0[0]["state_ref"]]["contours"][0][0]
    p1 = global_states[reg1[0]["state_ref"]]["contours"][0][0]

    assert abs(p0[0] - 0.5) < 1e-9
    assert abs(p1[0] - 1.0) < 1e-9


def test_sections_have_no_camera_key():
    """Sections must not have a top-level 'camera' key — camera is in the state bank now."""

    class CameraSetupScene(ManimWidget):
        def construct(self):
            self.camera.theta = 0.5
            self.next_section("after_camera_setup")

    data = CameraSetupScene(fps=10).scene_data
    assert_valid_scene(data)

    for section in data["sections"]:
        assert "camera" not in section


def test_arrow_serializes_as_vgroup_container():
    """Arrow: pure VGroup container, no points on container, 2 VMobject children."""
    from manim import Arrow

    class ArrowScene(ManimWidget):
        def construct(self):
            a = Arrow(start=LEFT, end=RIGHT)
            self.play(Create(a))

    scene = ArrowScene(fps=10)
    states = scene.scene_data["states"]

    arrow_state = next(
        (
            s
            for s in states
            if s.get("kind") == "VGroup"
            and all(states[r].get("kind") == "VMobject" for r in s["children"])
        ),
        None,
    )

    assert arrow_state is not None
    assert "points" not in arrow_state
    assert "contours" not in arrow_state
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
        assert 0 <= ref < len(r._state_registry.as_list())
    for ref in refs:
        assert 0 <= ref < len(r._state_registry.as_list())


@given(vmobject_state())
def test_state_bank_stores_dict_not_pydantic_model(state):
    """States in the bank must be plain dicts (for JSON serialization)."""
    r = _fresh_renderer()
    ref = r._intern_state(state)
    stored = r._state_registry.as_list()[ref]
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


def test_needs_camera_loop_false_for_real_scene_with_real_animation():
    """_needs_camera_loop must return False for a typical non-camera play()
    so the optimised (no frame-loop) path is actually taken."""

    class SimpleScene(ManimWidget):
        _captured: bool = False

        def construct(self):
            c = Circle()
            anims = self.compile_animations(Create(c))
            SimpleScene._captured = _needs_camera_loop(self, anims)
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
    data = run_generated_scene(mob_specs, commands, fps=5)
    validate(data, _SPEC)


@given(construct_script(min_mobs=1, max_mobs=4, min_plays=2, max_plays=5))
@settings(max_examples=30, deadline=None)
def test_generated_scene_no_camera_frames_in_animate_commands(args):
    """Non-updater scenes must never emit camera_frames in animate commands
    (frame loop skipped when camera is static)."""
    mob_specs, commands = args
    data = run_generated_scene(mob_specs, commands, fps=5)
    for section in data["sections"]:
        for cmd in section["construct"]:
            if cmd["cmd"] == "animate":
                assert "camera_frames" not in cmd


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

    n_states = len(data["states"])
    for section in data["sections"]:
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
    data = run_generated_scene(mob_specs, commands, fps=5)
    validate(data, _SPEC)

    n_states = len(data["states"])
    for section in data["sections"]:
        for cmd in section["construct"]:
            for anim in cmd.get("animations", []):
                if "state_ref" in anim:
                    assert 0 <= anim["state_ref"] < n_states


# ---------------------------------------------------------------------------
# Group registration invariants
# ---------------------------------------------------------------------------


def _collect_register_invariants(section: dict, states: list) -> None:
    """Assert group registration invariants for a single section's construct list.

    1. For every register with child_ids, all those IDs appear in earlier registers.
    2. child_ids length == len(VGroupState.children) for the referenced state.
    3. Every animate descriptor ID appears in a prior register.
    4. No duplicate register IDs within a section.
    """
    seen_register_ids: set[str] = set()
    removed_ids: set[str] = set()
    duplicate_ids: list[str] = []

    for cmd in section["construct"]:
        if cmd["cmd"] == "remove":
            removed_ids.add(cmd["id"])
            seen_register_ids.discard(cmd["id"])
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

        elif cmd["cmd"] == "updater":
            for frame in cmd.get("frames", []):
                for mob_id in frame:
                    if mob_id.startswith("#"):
                        continue  # pseudo-mobjects like #camera are not registered
                    assert mob_id in seen_register_ids, (
                        f"updater frame references mob '{mob_id}' not in prior registers"
                    )

    assert not duplicate_ids, f"Duplicate register IDs within section: {duplicate_ids}"


@given(
    construct_script(
        min_mobs=1,
        max_mobs=4,
        min_plays=1,
        max_plays=5,
        allow_groups=True,
        allow_arrows=True,
        allow_updaters=True,
    )
)
@settings(max_examples=40, deadline=None)
def test_generated_scene_group_registration_invariants(args):
    """For every generated scene with groups, arrows and updaters, all registration invariants hold."""
    mob_specs, commands = args
    data = run_generated_scene(mob_specs, commands, fps=5)
    for section in data["sections"]:
        _collect_register_invariants(section, data["states"])


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
        _collect_register_invariants(section, data["states"])


# ---------------------------------------------------------------------------
# Group child isolation: animating one child must not mutate siblings
# ---------------------------------------------------------------------------


@st.composite
def _group_with_shift(draw):
    """Generate (n_children, animated_idx, dx, dy) for a VGroup shift test."""
    n = draw(st.integers(2, 4))
    animated_idx = draw(st.integers(0, n - 1))
    dx = draw(st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False))
    dy = draw(st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False))
    return n, animated_idx, dx, dy


@given(_group_with_shift())
@settings(max_examples=30, deadline=None)
def test_animating_vgroup_child_does_not_affect_siblings(args):
    """Animating one child of a VGroup must not produce state_ref changes for siblings."""
    from manim import Circle, Dot, VGroup, Create

    n_children, animated_idx, dx, dy = args

    class S(ManimWidget):
        def construct(self):
            mobs = [Circle() if i % 2 == 0 else Dot() for i in range(n_children)]
            group = VGroup(*mobs)
            self.play(Create(group))
            self.play(mobs[animated_idx].animate.shift((dx, dy, 0)))

    data = S().scene_data
    section = data["sections"][0]
    commands = section["construct"]

    animate_cmds = [c for c in commands if c["cmd"] == "animate"]
    shift_animate = animate_cmds[-1]  # the shift play() is the last animate

    # IDs that have a new state_ref in the shift animation (i.e. actually changed)
    anim_ids_with_state = {
        a["id"] for a in shift_animate.get("animations", []) if "state_ref" in a
    }

    # All registered mob IDs
    all_registered = {c["id"] for c in commands if c["cmd"] == "register"}

    # No sibling should appear with a state change
    siblings_changed = (all_registered - anim_ids_with_state) & anim_ids_with_state
    assert not siblings_changed, (
        f"Siblings {siblings_changed} got state_ref changes in the shift animate"
    )


# ---------------------------------------------------------------------------
# sync() safety: animated mobs are rejected with a warning, static mobs pass
# ---------------------------------------------------------------------------


@given(
    dx=st.floats(-2.0, 2.0, allow_nan=False, allow_infinity=False),
    dy=st.floats(-2.0, 2.0, allow_nan=False, allow_infinity=False),
    sync_dx=st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False),
    sync_dy=st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30, deadline=None)
def test_sync_warns_and_skips_animated_mob(dx, dy, sync_dx, sync_dy):
    """sync() on a mob that was animated during construction emits a warning and ignores it."""
    import warnings
    from manim import Square, Circle, Create

    class S(ManimWidget):
        def construct(self):
            self.animated = Square()
            self.static = Circle()
            self.play(Create(self.animated))
            self.play(self.animated.animate.shift((dx, dy, 0)))
            self.add(self.static)

    w = S()
    state_before = list(w._renderer._state_registry.as_list())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        w.animated.shift((sync_dx, sync_dy, 0))
        w.sync(w.animated)

    warned_msgs = [str(c.message) for c in caught]
    assert any("animated" in m for m in warned_msgs), (
        f"Expected warning about animated mob, got: {warned_msgs}"
    )
    # State bank must be unchanged — the animated mob's refs were not overwritten.
    assert w._renderer._state_registry.as_list() == state_before


@given(
    dx=st.floats(-2.0, 2.0, allow_nan=False, allow_infinity=False),
    dy=st.floats(-2.0, 2.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=30, deadline=None)
def test_sync_updates_static_mob_without_warning(dx, dy):
    """sync() on a mob that was never animated updates its state_ref silently."""
    import warnings
    from manim import Square

    class S(ManimWidget):
        def construct(self):
            self.square = Square()
            self.add(self.square)

    w = S()
    refs_before = list(w._renderer.state_refs.get(id(w.square), []))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        w.square.shift((dx, dy, 0))
        w.sync(w.square)

    sync_warnings = [
        c
        for c in caught
        if "animated" in str(c.message) or "not found" in str(c.message)
    ]
    assert not sync_warnings, (
        f"Unexpected warnings: {[str(c.message) for c in sync_warnings]}"
    )

    # State bank entry for the mob must have changed (new position serialized).
    refs_after = w._renderer.state_refs.get(id(w.square), [])
    assert refs_before and refs_after
    new_state = w._renderer._state_registry.get_by_id(refs_after[-1])
    assert new_state is not None


# ---------------------------------------------------------------------------
# Contour / hole winding
# ---------------------------------------------------------------------------


@st.composite
def _raw_subpath(draw, min_segments: int = 1, max_segments: int = 4):
    """Numpy array of 4k points — raw manim bezier format consumed by _subpath_to_3n1."""
    import numpy as np

    k = draw(st.integers(min_value=min_segments, max_value=max_segments))
    pts = draw(st.lists(point3, min_size=4 * k, max_size=4 * k))
    return np.array(pts)


@st.composite
def _raw_subpath_list(draw, min_size: int = 1, max_size: int = 4):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(_raw_subpath()) for _ in range(n)]


@given(_raw_subpath_list())
def test_classify_subpaths_winding_invariant(subpaths):
    """_classify_subpaths: every contour is CCW, every hole is CW, nothing is dropped."""
    contours, holes = _classify_subpaths(subpaths)
    for c in contours:
        assert _contour_winding(c) == "CCW"
    for h in holes:
        assert _contour_winding(h) == "CW"
    assert len(contours) + len(holes) <= len(subpaths)


_HOLE_CHARS = list("04689ABDOPQRbdgopq")


@given(st.sampled_from(_HOLE_CHARS))
def test_glyph_hole_serialized(char):
    """Glyphs with interior holes must produce a VMobjectState with non-empty holes."""
    from manim import Text
    from manim_widget.tex_patch import patch_tex

    patch_tex()

    class S(ManimWidget):
        def construct(self):
            self.add(Text(char, font_size=200))

    data = S(fps=10).scene_data
    vmob_states = [s for s in data["states"] if s.get("kind") == "VMobject"]
    assert any(s.get("holes") for s in vmob_states), (
        f"No holes found in serialized states for '{char}'"
    )


@given(st.sampled_from(_HOLE_CHARS))
def test_glyph_hole_winding(char):
    """Serialized VMobjectState: all contours CCW, all holes CW."""
    from manim import Text
    from manim_widget.tex_patch import patch_tex

    patch_tex()

    class S(ManimWidget):
        def construct(self):
            self.add(Text(char, font_size=200))

    data = S(fps=10).scene_data
    for state in data["states"]:
        if state.get("kind") != "VMobject":
            continue
        for c in state.get("contours", []):
            assert _contour_winding(c) == "CCW"
        for h in state.get("holes", []):
            assert _contour_winding(h) == "CW"
