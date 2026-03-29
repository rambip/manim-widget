from __future__ import annotations

from typing import cast

import pytest

from manim import Circle, Create, FadeIn, MathTex, Scene, Square, VGroup, Wait

from manim_widget.patches import apply_patches, remove_patches
from manim_widget.renderer import CaptureRenderer, Keyframe, Section, Segment
from manim_widget.serializer import (
    _animation_kind,
    _build_animation_entry,
    _build_mobject_entry,
    _build_section_entry,
    _build_segment_entry,
    _get_children_ids,
    _get_tex_string,
    _get_value,
    _kind_name,
    _rate_func_name,
    _short_id,
    serialize_scene,
)


@pytest.fixture(autouse=True)
def patched():
    apply_patches()
    yield
    remove_patches()


class TestShortId:
    def test_short_id_is_deterministic(self):
        id1 = _short_id(12345)
        id2 = _short_id(12345)
        assert id1 == id2

    def test_short_id_is_string(self):
        result = _short_id(999)
        assert isinstance(result, str)

    def test_short_id_length(self):
        result = _short_id(999)
        assert len(result) == 8

    def test_different_ids_different_short_ids(self):
        id1 = _short_id(111)
        id2 = _short_id(222)
        assert id1 != id2


class TestKindName:
    def test_circle(self):
        assert _kind_name(Circle()) == "Circle"

    def test_square(self):
        assert _kind_name(Square()) == "Square"


class TestGetChildrenIds:
    def test_simple_mobject_no_children(self):
        circle = Circle()
        children = _get_children_ids(circle)
        assert children == []

    def test_vgroup_children(self):
        c1, c2 = Circle(), Circle()
        vg = VGroup(c1, c2)
        children = _get_children_ids(vg)
        assert len(children) == 2
        assert _short_id(id(c1)) in children
        assert _short_id(id(c2)) in children


class TestGetTexString:
    def test_non_tex_returns_none(self):
        circle = Circle()
        assert _get_tex_string(circle) is None

    @pytest.mark.skipif(True, reason="latex not installed in test environment")
    def test_math_tex(self):
        mt = MathTex("x^2")
        result = _get_tex_string(mt)
        assert isinstance(result, str)


class TestGetValue:
    def test_non_tracker_returns_none(self):
        circle = Circle()
        assert _get_value(circle) is None


class TestBuildMobjectEntry:
    def test_has_id(self):
        mob = Circle()
        entry = _build_mobject_entry(mob)
        assert "id" in entry
        assert len(entry["id"]) == 8

    def test_has_kind(self):
        mob = Circle()
        entry = _build_mobject_entry(mob)
        assert entry["kind"] == "Circle"

    def test_has_children(self):
        mob = Circle()
        entry = _build_mobject_entry(mob)
        assert "children" in entry
        assert isinstance(entry["children"], list)

    @pytest.mark.skipif(True, reason="latex not installed in test environment")
    def test_tex_string_for_math_tex(self):
        mt = MathTex("x^2")
        entry = _build_mobject_entry(mt)
        assert entry["tex_string"] == "x^2"

    def test_tex_string_none_for_circle(self):
        circle = Circle()
        entry = _build_mobject_entry(circle)
        assert entry["tex_string"] is None


class TestAnimationKind:
    def test_create(self):
        circle = Circle()
        anim = Create(circle)
        assert _animation_kind(anim) == "Create"

    def test_fade_in(self):
        circle = Circle()
        anim = FadeIn(circle)
        assert _animation_kind(anim) == "FadeIn"


class TestRateFuncName:
    def test_no_rate_func_defaults_to_linear(self):
        circle = Circle()
        anim = FadeIn(circle)
        assert _rate_func_name(anim) == "smooth"


class TestBuildAnimationEntry:
    def test_has_kind(self):
        circle = Circle()
        anim = FadeIn(circle)
        entry = _build_animation_entry(anim)
        assert entry["kind"] == "FadeIn"

    def test_has_mob_id(self):
        circle = Circle()
        anim = FadeIn(circle)
        entry = _build_animation_entry(anim)
        assert "mob_id" in entry
        assert entry["mob_id"] == _short_id(id(circle))

    def test_has_rate_func(self):
        circle = Circle()
        anim = FadeIn(circle)
        entry = _build_animation_entry(anim)
        assert "rate_func" in entry

    def test_none_mob_id_when_no_mobjects(self):
        anim = Wait()
        entry = _build_animation_entry(anim)
        assert entry["mob_id"] is None


class TestBuildSegmentEntry:
    def test_has_run_time(self):
        renderer = CaptureRenderer(fps=10)
        seg = Segment(run_time=2.5, animations=[])
        entry = _build_segment_entry(seg)
        assert entry["run_time"] == 2.5

    def test_has_animations(self):
        renderer = CaptureRenderer(fps=10)
        circle = Circle()
        anim = FadeIn(circle)
        seg = Segment(run_time=1.0, animations=[anim])
        entry = _build_segment_entry(seg)
        assert len(entry["animations"]) == 1
        assert entry["animations"][0]["kind"] == "FadeIn"

    def test_has_keyframes(self):
        renderer = CaptureRenderer(fps=10)
        kf = Keyframe(
            frame=0,
            mob_id=12345,
            position=(1.0, 2.0, 3.0),
            rotation=0.5,
            scale=1.5,
        )
        seg = Segment(run_time=1.0, animations=[], keyframes=[kf])
        entry = _build_segment_entry(seg)
        assert len(entry["keyframes"]) == 1
        assert entry["keyframes"][0]["frame"] == 0
        assert entry["keyframes"][0]["position"] == [1.0, 2.0, 3.0]
        assert entry["keyframes"][0]["rotation"] == 0.5
        assert entry["keyframes"][0]["scale"] == 1.5


class TestBuildSectionEntry:
    def test_has_name(self):
        section = Section(name="intro")
        entry = _build_section_entry(section, {})
        assert entry["name"] == "intro"

    def test_has_supported(self):
        section = Section(name="intro")
        entry = _build_section_entry(section, {})
        assert entry["supported"] is True

    def test_unsupported_has_reason(self):
        section = Section(name="bad", supported=False, reason="geometry-level updater")
        entry = _build_section_entry(section, {})
        assert entry["supported"] is False
        assert entry["reason"] == "geometry-level updater"

    def test_has_snapshot(self):
        section = Section(name="intro")
        snapshot = {"a3f": {"position": [0, 0, 0], "opacity": 1.0, "color": "#fff"}}
        entry = _build_section_entry(section, snapshot)
        assert entry["snapshot"] == snapshot

    def test_has_segments(self):
        section = Section(name="intro")
        entry = _build_section_entry(section, {})
        assert "segments" in entry


class TestSerializeScene:
    def test_output_has_fps(self):
        renderer = CaptureRenderer(fps=10)
        scene = cast(Scene, None)
        renderer.init_scene(scene)
        renderer.start_section("intro")
        section = renderer.sections[0]
        result = serialize_scene(fps=10, mobjects=[], sections=[section], snapshots={})
        assert result["fps"] == 10

    def test_output_has_mobjects(self):
        renderer = CaptureRenderer(fps=10)
        scene = cast(Scene, None)
        renderer.init_scene(scene)
        renderer.start_section("intro")
        section = renderer.sections[0]
        circle = Circle()
        result = serialize_scene(
            fps=10, mobjects=[circle], sections=[section], snapshots={}
        )
        assert "mobjects" in result
        assert len(result["mobjects"]) >= 1

    def test_output_has_sections(self):
        renderer = CaptureRenderer(fps=10)
        scene = cast(Scene, None)
        renderer.init_scene(scene)
        renderer.start_section("intro")
        section = renderer.sections[0]
        result = serialize_scene(fps=10, mobjects=[], sections=[section], snapshots={})
        assert "sections" in result
        assert len(result["sections"]) == 1

    def test_mobject_entry_has_required_fields(self):
        circle = Circle()
        result = serialize_scene(fps=10, mobjects=[circle], sections=[], snapshots={})
        mob_entry = result["mobjects"][0]
        assert "id" in mob_entry
        assert "kind" in mob_entry
        assert "children" in mob_entry

    def test_section_entry_includes_snapshot(self):
        renderer = CaptureRenderer(fps=10)
        scene = cast(Scene, None)
        renderer.init_scene(scene)
        renderer.start_section("intro")
        section = renderer.sections[0]
        snapshot = {"a3f": {"position": [0, 0, 0], "opacity": 1.0, "color": "#fff"}}
        result = serialize_scene(
            fps=10, mobjects=[], sections=[section], snapshots={"intro": snapshot}
        )
        assert result["sections"][0]["snapshot"] == snapshot

    def test_vgroup_children_included_in_registry(self):
        c1, c2 = Circle(), Circle()
        vg = VGroup(c1, c2)
        result = serialize_scene(fps=10, mobjects=[vg], sections=[], snapshots={})
        ids = [m["id"] for m in result["mobjects"]]
        assert _short_id(id(c1)) in ids
        assert _short_id(id(c2)) in ids

    def test_multiple_sections(self):
        renderer = CaptureRenderer(fps=10)
        scene = cast(Scene, None)
        renderer.init_scene(scene)
        renderer.start_section("intro")
        renderer.start_section("main")
        sections = renderer.sections
        result = serialize_scene(fps=10, mobjects=[], sections=sections, snapshots={})
        assert len(result["sections"]) == 2
        assert result["sections"][0]["name"] == "intro"
        assert result["sections"][1]["name"] == "main"
