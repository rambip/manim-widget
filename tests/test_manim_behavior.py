"""Tests probing raw manim behavior with a dummy capturing renderer.

Focus on:
- When mobjects are added to / removed from scene.mobjects
- When mobjects appear in get_family()
- Transform vs ReplacementTransform lifecycle differences
"""

from __future__ import annotations

import math
import pytest
from manim import (
    Circle,
    Square,
    Triangle,
    Create,
    FadeIn,
    FadeOut,
    Write,
    ReplacementTransform,
    Transform,
    Rotate,
)
from manim import Scene, VGroup
from manim.animation.animation import Animation
from manim.mobject.mobject import Mobject


class CapturingRenderer:
    """Minimal renderer that records all play() calls."""

    def __init__(self) -> None:
        self.time: float = 0.0
        self.num_plays: int = 0
        self.skip_animations: bool = False
        self.static_image = None
        self.camera = type("DummyCamera", (), {"use_z_index": False})()  # type: ignore[assignment]
        self.events: list[tuple] = []
        self._scene_inits: int = 0

    def init_scene(self, scene: Scene) -> None:
        self._scene_inits += 1
        if self._scene_inits > 1:
            return
        self.events.append(("init_scene",))

    def update_frame(
        self,
        scene: Scene,
        moving_mobjects: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        pass

    def scene_finished(self, scene: Scene) -> None:
        self.events.append(("scene_finished",))

    def play(self, scene: Scene, *args: object, **kwargs: object) -> None:
        animations: list[Animation] = scene.compile_animations(*args, **kwargs)
        if not animations:
            return

        run_time: float = scene.get_run_time(animations)
        anim_summaries: list[tuple] = []
        for anim in animations:
            summary: dict[str, object] = {
                "type": type(anim).__name__,
                "mobject": anim.mobject,
                "target": getattr(anim, "target_mobject", None),
                "run_time": run_time,
            }
            if hasattr(anim, "methods"):
                summary["methods"] = [
                    (mwa.method.__name__, mwa.args) for mwa in anim.methods
                ]
            anim_summaries.append(summary)

        self.events.append(("play", anim_summaries))

        for anim in animations:
            anim._setup_scene(scene)
        for anim in animations:
            anim.begin()
        for anim in animations:
            anim.finish()
        for anim in animations:
            anim.clean_up_from_scene(scene)
        scene.update_mobjects(0)

        self.time += run_time
        self.num_plays += 1


def make_scene() -> tuple[Scene, CapturingRenderer]:
    renderer = CapturingRenderer()
    scene = Scene(renderer=renderer)  # type: ignore[arg-type]
    return scene, renderer


def scene_get_all_mobjects_with_family(scene: Scene) -> list[Mobject]:
    """Get all mobjects including those nested in groups."""
    result: list[Mobject] = []
    for mob in scene.mobjects:
        result.extend(mob.get_family())
    return result


class TestMobjectInSceneAfterAdd:
    """Test when mobjects are in scene.mobjects after add()."""

    def test_add_circle_circle_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.add(c)
        assert c in scene.mobjects

    def test_add_square_square_in_mobjects(self):
        scene, renderer = make_scene()
        s = Square()
        scene.add(s)
        assert s in scene.mobjects

    def test_add_vgroup_vgroup_in_mobjects_not_children(self):
        scene, renderer = make_scene()
        c1 = Circle()
        c2 = Square()
        vg = VGroup(c1, c2)
        scene.add(vg)
        assert vg in scene.mobjects
        assert c1 not in scene.mobjects
        assert c2 not in scene.mobjects


class TestMobjectInSceneAfterCreate:
    """Test when mobjects are in scene.mobjects after Create()."""

    def test_create_circle_circle_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.add(c)
        scene.play(Create(c))
        assert c in scene.mobjects

    def test_create_without_add_circle_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.play(Create(c))
        assert c in scene.mobjects

    def test_create_vgroup_vgroup_in_mobjects_children_not(self):
        scene, renderer = make_scene()
        c1 = Circle()
        c2 = Square()
        vg = VGroup(c1, c2)
        scene.add(vg)
        scene.play(Create(vg))
        assert vg in scene.mobjects
        assert c1 not in scene.mobjects
        assert c2 not in scene.mobjects


class TestMobjectInSceneAfterFadeIn:
    """Test when mobjects are in scene.mobjects after FadeIn()."""

    def test_fadein_circle_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.play(FadeIn(c))
        assert c in scene.mobjects

    def test_fadein_then_fadeout_circle_out(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.play(FadeIn(c))
        assert c in scene.mobjects
        scene.play(FadeOut(c))
        assert c not in scene.mobjects


class TestMobjectInSceneAfterReplacementTransform:
    """Test scene.mobjects after ReplacementTransform."""

    def test_replacement_transform_source_removed(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(ReplacementTransform(a, b))
        assert a not in scene.mobjects

    def test_replacement_transform_target_added(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(ReplacementTransform(a, b))
        assert b in scene.mobjects


class TestMobjectInSceneAfterTransform:
    """Test scene.mobjects after plain Transform."""

    def test_transform_source_stays(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(Transform(a, b))
        assert a in scene.mobjects

    def test_transform_target_not_added(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(Transform(a, b))
        assert b not in scene.mobjects


class TestGetFamilyBehavior:
    """Test when mobjects appear in get_family()."""

    def test_vgroup_get_family_includes_children(self):
        c1 = Circle()
        c2 = Square()
        vg = VGroup(c1, c2)
        family = vg.get_family()
        assert c1 in family
        assert c2 in family

    def test_circle_get_family_is_self(self):
        c = Circle()
        family = c.get_family()
        assert c in family
        assert len(family) == 1

    def test_add_vgroup_get_family_includes_children(self):
        scene, renderer = make_scene()
        c1 = Circle()
        c2 = Square()
        vg = VGroup(c1, c2)
        scene.add(vg)
        family = scene_get_all_mobjects_with_family(scene)
        assert vg in scene.mobjects
        assert c1 in family
        assert c2 in family

    def test_after_create_vgroup_get_family_includes_children(self):
        scene, renderer = make_scene()
        c1 = Circle()
        c2 = Square()
        vg = VGroup(c1, c2)
        scene.add(vg)
        scene.play(Create(vg))
        family = scene_get_all_mobjects_with_family(scene)
        assert c1 in family
        assert c2 in family

    def test_after_replacement_transform_get_family(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(ReplacementTransform(a, b))
        assert b in scene.mobjects
        assert a not in scene.mobjects

    def test_after_transform_get_family(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(Transform(a, b))
        assert a in scene.mobjects
        assert b not in scene.mobjects


class TestFadeInFadeOutGetFamily:
    """Test get_family after FadeIn/FadeOut."""

    def test_after_fadein_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.play(FadeIn(c))
        assert c in scene.mobjects

    def test_after_fadeout_not_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.play(FadeIn(c))
        scene.play(FadeOut(c))
        assert c not in scene.mobjects


class TestAnimateWithGetFamily:
    """Test mobjects with .animate syntax."""

    def test_after_animate_shift_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.add(c)
        scene.play(Create(c))
        scene.play(c.animate.shift((2, 0, 0)))
        assert c in scene.mobjects

    def test_after_animate_rotate_in_mobjects(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.add(c)
        scene.play(Create(c))
        scene.play(c.animate.rotate(math.pi / 4))
        assert c in scene.mobjects

    def test_position_after_animate_shift(self):
        scene, renderer = make_scene()
        c = Circle()
        scene.add(c)
        scene.play(Create(c))
        scene.play(c.animate.shift((2, 0, 0)))
        assert abs(c.get_center()[0] - 2.0) < 0.01


class TestReplacementTransformThenAnimate:
    """Test animating after ReplacementTransform."""

    def test_animate_target_after_replacement(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(ReplacementTransform(a, b))
        scene.play(b.animate.shift((1, 0, 0)))
        assert abs(b.get_center()[0] - 1.0) < 0.01

    def test_animate_source_after_replacement(self):
        scene, renderer = make_scene()
        a = Circle()
        b = Square()
        scene.add(a)
        scene.play(ReplacementTransform(a, b))
        scene.play(a.animate.shift((1, 0, 0)))


class TestMultipleAnimationsGetFamily:
    """Test with multiple animations."""

    def test_two_circles_create_both_in_mobjects(self):
        scene, renderer = make_scene()
        c1 = Circle()
        c2 = Square()
        scene.add(c1, c2)
        scene.play(Create(c1), Create(c2))
        assert c1 in scene.mobjects
        assert c2 in scene.mobjects

    def test_add_then_create_multiple(self):
        scene, renderer = make_scene()
        c1 = Circle()
        c2 = Square()
        scene.add(c1, c2)
        scene.play(Create(c1), Create(c2))
        assert c1 in scene.mobjects
        assert c2 in scene.mobjects
