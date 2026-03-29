from __future__ import annotations

from typing import cast

import numpy as np
import pytest

from manim import Circle, Create, FadeIn, Scene, Square, VGroup, Wait

from manim_widget.patches import apply_patches, remove_patches
from manim_widget.renderer import CaptureRenderer, Keyframe, Section, Segment


@pytest.fixture(autouse=True)
def patched():
    apply_patches()
    yield
    remove_patches()


@pytest.fixture
def renderer():
    return CaptureRenderer(fps=10)


@pytest.fixture
def scene():
    class TestScene(Scene):
        def construct(self):
            pass

    return TestScene()


class TestCaptureRendererInit:
    def test_fps_default(self):
        r = CaptureRenderer()
        assert r.fps == 10

    def test_fps_custom(self):
        r = CaptureRenderer(fps=30)
        assert r.fps == 30

    def test_time_starts_at_zero(self, renderer):
        assert renderer.time == 0.0

    def test_sections_empty(self, renderer):
        assert renderer.sections == []

    def test_registry_empty(self, renderer):
        assert renderer.registry == set()


class TestInitScene:
    def test_resets_time(self, renderer, scene):
        renderer.time = 5.0
        renderer.init_scene(scene)
        assert renderer.time == 0.0

    def test_resets_sections(self, renderer, scene):
        renderer._sections = [Section("fake")]
        renderer.init_scene(scene)
        assert renderer.sections == []

    def test_resets_current_section(self, renderer, scene):
        renderer._current_section = Section("fake")
        renderer.init_scene(scene)
        assert renderer._current_section is None

    def test_resets_registry(self, renderer, scene):
        renderer._registry.add(Circle())
        renderer.init_scene(scene)
        assert renderer.registry == set()


class TestStartSection:
    def test_creates_section(self, renderer, scene):
        renderer.init_scene(scene)
        renderer.start_section("intro")
        assert len(renderer.sections) == 1
        assert renderer.sections[0].name == "intro"

    def test_sets_current_section(self, renderer, scene):
        renderer.init_scene(scene)
        renderer.start_section("intro")
        assert renderer._current_section is not None
        assert renderer._current_section.name == "intro"

    def test_multiple_sections(self, renderer, scene):
        renderer.init_scene(scene)
        renderer.start_section("intro")
        renderer.start_section("main")
        assert len(renderer.sections) == 2
        assert renderer.sections[0].name == "intro"
        assert renderer.sections[1].name == "main"


class TestPlay:
    def test_wait_creates_no_segment(self, renderer, scene):
        renderer.init_scene(scene)
        scene.add(Circle())
        renderer.play(scene, Wait(run_time=0.5))
        assert len(renderer.sections[0].segments) == 0

    def test_play_creates_segment(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle))
        assert len(renderer.sections) == 1
        assert len(renderer.sections[0].segments) == 1
        assert renderer.sections[0].segments[0].run_time == 1.0

    def test_play_uses_custom_run_time(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle), run_time=2.5)
        assert renderer.sections[0].segments[0].run_time == 2.5

    def test_play_adds_mobjects_to_registry(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle))
        assert circle in renderer.registry

    def test_vgroup_added_to_registry(self, renderer, scene):
        renderer.init_scene(scene)
        c1, c2 = Circle(), Circle()
        vg = VGroup(c1, c2)
        scene.add(vg)
        renderer.play(scene, FadeIn(vg))
        assert vg in renderer.registry

    def test_play_without_section_creates_default(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle))
        assert renderer.sections[0].name == "default"

    def test_play_updates_time(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle), run_time=2.0)
        assert renderer.time == 2.0

    def test_play_chained(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle), run_time=1.0)
        renderer.play(scene, FadeIn(circle), run_time=2.0)
        assert len(renderer.sections[0].segments) == 2
        assert renderer.time == 3.0


class TestPlayKeyframes:
    def test_updater_mobject_generates_keyframe(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)

        def updater(m, dt):
            pass

        circle.add_updater(updater)
        renderer.play(scene, FadeIn(circle))
        seg = renderer.sections[0].segments[0]
        assert len(seg.keyframes) > 0

    def test_keyframe_has_position(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)

        def updater(m, dt):
            m.shift(np.array([0.1, 0.0, 0.0]))

        circle.add_updater(updater)
        renderer.play(scene, FadeIn(circle))
        kf = renderer.sections[0].segments[0].keyframes[0]
        assert isinstance(kf.position, tuple)
        assert len(kf.position) == 3


class TestUnsupportedUpdaters:
    def test_geometry_updater_marks_section_unsupported(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)

        def dirty_updater(m, dt):
            m.apply_function(lambda pts: pts)

        circle.add_updater(dirty_updater)
        renderer.play(scene, FadeIn(circle))
        assert renderer.sections[0].supported is False
        assert "geometry-level updater" in renderer.sections[0].reason

    def test_normal_updater_keeps_section_supported(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)

        def clean_updater(m, dt):
            m.shift(np.array([0.1, 0.0, 0.0]))

        circle.add_updater(clean_updater)
        renderer.play(scene, Wait(run_time=0.5))
        assert renderer.sections[0].supported is True


class TestSection:
    def test_section_defaults_supported(self, renderer, scene):
        renderer.init_scene(scene)
        renderer.start_section("intro")
        assert renderer.sections[0].supported is True
        assert renderer.sections[0].reason is None

    def test_section_segments_initially_empty(self, renderer, scene):
        renderer.init_scene(scene)
        renderer.start_section("intro")
        assert renderer.sections[0].segments == []


class TestRegistry:
    def test_registry_contains_mobjects(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle))
        assert len(renderer.registry) == 1
        mob = next(iter(renderer.registry))
        assert isinstance(mob, Circle)

    def test_registry_stores_unique_mobjects(self, renderer, scene):
        renderer.init_scene(scene)
        circle = Circle()
        scene.add(circle)
        renderer.play(scene, FadeIn(circle))
        renderer.play(scene, FadeIn(circle))
        assert len(renderer.registry) == 1
