from __future__ import annotations

import json
import warnings

from manim import Circle, Create, FadeIn, Square

from manim_widget import ManimWidget
from manim_widget.patches import apply_patches, remove_patches


class TestCircleScene(ManimWidget):
    def construct(self):
        self.play(Create(Circle()))


class TestFadeInCircle(ManimWidget):
    def construct(self):
        circle = Circle()
        self.add(circle)
        self.play(FadeIn(circle))


class TestFadeInCircleCustomRunTime(ManimWidget):
    def construct(self):
        circle = Circle()
        self.add(circle)
        self.play(FadeIn(circle), run_time=2.0)


class TestUnsupportedGeometryUpdater(ManimWidget):
    def construct(self):
        circle = Circle()
        self.add(circle)

        def dirty_updater(m, dt):
            m.apply_function(lambda pts: pts)

        circle.add_updater(dirty_updater)
        self.play(FadeIn(circle))


class TestCleanUpdater(ManimWidget):
    def construct(self):
        circle = Circle()
        self.add(circle)

        def clean_updater(m, dt):
            m.shift([0.1, 0.0, 0.0])

        circle.add_updater(clean_updater)
        self.play(FadeIn(circle))


class TestMultipleSections(ManimWidget):
    def construct(self):
        c1 = Circle()
        self.add(c1)
        self.play(FadeIn(c1))
        self.next_section("second")
        c2 = Square()
        self.add(c2)
        self.play(FadeIn(c2))


class TestWaitOnly(ManimWidget):
    def construct(self):
        circle = Circle()
        self.add(circle)
        self.wait(0.5)


class TestCreateCircleAndSquare(ManimWidget):
    def construct(self):
        circle = Circle()
        square = Square()
        self.play(Create(circle))
        self.next_section("Square")
        self.play(Create(square))


def test_widget_produces_json():
    widget = TestCircleScene(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    assert "fps" in data
    assert "mobjects" in data
    assert "sections" in data


def test_circle_in_json():
    widget = TestCircleScene(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    kinds = [m["kind"] for m in data["mobjects"]]
    assert "Circle" in kinds


def test_create_animation_recorded():
    widget = TestCircleScene(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    animations = data["sections"][0]["segments"][0]["animations"]
    assert animations[0]["kind"] == "Create"


def test_fadein_animation_recorded():
    widget = TestFadeInCircle(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    animations = data["sections"][0]["segments"][0]["animations"]
    assert len(animations) == 1
    assert animations[0]["kind"] == "FadeIn"
    assert animations[0]["rate_func"] == "smooth"


def test_fadein_custom_run_time():
    widget = TestFadeInCircleCustomRunTime(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    assert data["sections"][0]["segments"][0]["run_time"] == 2.0


def test_section_supported_by_default():
    widget = TestFadeInCircle(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    assert data["sections"][0]["supported"] is True


def test_unsupported_section_triggers_warning():
    widget = TestUnsupportedGeometryUpdater(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    section = data["sections"][0]
    if not section["supported"]:
        warnings.warn(
            f"Section '{section['name']}' uses unsupported features: {section['reason']}"
        )
    assert section["supported"] is False
    assert "geometry-level updater" in section["reason"]


def test_clean_updater_section_stays_supported():
    widget = TestCleanUpdater(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    assert data["sections"][0]["supported"] is True


def test_multiple_sections():
    widget = TestMultipleSections(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    assert len(data["sections"]) == 2
    assert data["sections"][0]["name"] == "initial"
    assert data["sections"][1]["name"] == "second"


def test_wait_creates_no_animation_segment():
    widget = TestWaitOnly(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    segments = data["sections"][0]["segments"]
    animation_segments = [s for s in segments if s["animations"]]
    assert len(animation_segments) == 0


def test_create_circle_and_square():
    widget = TestCreateCircleAndSquare(fps=10)
    widget.construct()
    data = json.loads(widget.scene_data)
    assert len(data["sections"]) == 2
    assert data["sections"][0]["name"] == "initial"
    assert data["sections"][1]["name"] == "Square"
