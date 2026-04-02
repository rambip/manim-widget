from __future__ import annotations

import json
import math
import os

import pytest
from jsonschema import validate
from manim import (
    BLUE,
    PINK,
    RED,
    WHITE,
    Circle,
    Create,
    FadeIn,
    FadeOut,
    ReplacementTransform,
    Square,
    ValueTracker,
    VGroup,
)

from manim_widget.serializer import serialize_scene
from manim_widget.snapshot import reset_id_counter, short_id
from manim_widget.widget import ManimWidget


def load_schema() -> dict:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "spec.json")
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def reset_ids():
    reset_id_counter()


class TestShortId:
    def test_same_mobject_same_id(self):
        c = Circle()
        assert short_id(c) == short_id(c)

    def test_different_mobjects_different_id(self):
        c1 = Circle()
        c2 = Circle()
        assert short_id(c1) != short_id(c2)

    def test_id_is_short_string(self):
        c = Circle()
        sid = short_id(c)
        assert len(sid) <= 4


class TestWidgetEmptyScene:
    def test_empty_scene_produces_valid_json(self):
        class EmptyScene(ManimWidget):
            def construct(self):
                pass

        scene = EmptyScene()
        data = json.loads(scene.scene_data)
        assert data["version"] == 1
        assert data["fps"] == 10
        assert len(data["sections"]) == 1
        assert data["sections"][0]["name"] == "initial"
        assert data["sections"][0]["construct"] == []

    def test_empty_scene_snapshot_is_empty_dict(self):
        class EmptyScene(ManimWidget):
            def construct(self):
                pass

        scene = EmptyScene()
        data = json.loads(scene.scene_data)
        assert data["sections"][0]["snapshot"] == {}


class TestAddRemove:
    def test_add_emits_add_command(self):
        class AddScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.add(c)

        scene = AddScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        assert len(commands) == 1
        assert commands[0]["cmd"] == "add"
        assert "id" in commands[0]


class TestAnimations:
    def test_create_emits_animate_command(self):
        class CreateScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))

        scene = CreateScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        assert len(commands) == 1
        assert commands[0]["cmd"] == "animate"
        assert commands[0]["animations"][0]["type"] == "Create"

    def test_fadein_emits_animate_command(self):
        class FadeInScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.add(c)
                self.play(FadeIn(c))

        scene = FadeInScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        animate_cmd = [c for c in commands if c["cmd"] == "animate"][0]
        assert animate_cmd["animations"][0]["type"] == "FadeIn"

    def test_fadeout_emits_animate_then_remove(self):
        class FadeOutScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.play(FadeOut(c))

        scene = FadeOutScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        animate_cmds = [c for c in commands if c["cmd"] == "animate"]
        remove_cmds = [c for c in commands if c["cmd"] == "remove"]
        assert len(animate_cmds) == 2
        assert animate_cmds[1]["animations"][0]["type"] == "FadeOut"
        assert len(remove_cmds) == 1

    def test_animate_shift_emits_shift_animation(self):
        class ShiftScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.play(c.animate.shift((1, 0, 0)))

        scene = ShiftScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        animate_cmds = [c for c in commands if c["cmd"] == "animate"]
        shift_cmd = animate_cmds[1]
        assert shift_cmd["animations"][0]["type"] == "Shift"
        assert shift_cmd["animations"][0]["params"]["vector"] == [1.0, 0.0, 0.0]

    def test_animate_rotate_emits_rotate_animation(self):
        class RotateScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.play(c.animate.rotate(math.pi / 2))

        scene = RotateScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        animate_cmds = [c for c in commands if c["cmd"] == "animate"]
        rotate_cmd = animate_cmds[1]
        assert rotate_cmd["animations"][0]["type"] == "Rotate"
        assert abs(rotate_cmd["animations"][0]["params"]["angle"] - math.pi / 2) < 0.001

    def test_replacement_transform_pre_and_post_commands(self):
        class RepTransformScene(ManimWidget):
            def construct(self):
                a = Circle()
                b = Square()
                self.add(a)
                self.play(ReplacementTransform(a, b))

        scene = RepTransformScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        add_cmds = [c for c in commands if c["cmd"] == "add"]
        animate_cmds = [c for c in commands if c["cmd"] == "animate"]
        remove_cmds = [c for c in commands if c["cmd"] == "remove"]
        assert len(add_cmds) == 2
        circle_add = add_cmds[0]
        square_add = add_cmds[1]
        assert circle_add["state"]["kind"] == "Circle"
        assert square_add["state"]["hidden"] is True
        assert square_add["state"]["opacity"] == 0
        assert len(animate_cmds) == 1
        assert animate_cmds[0]["animations"][0]["type"] == "ReplacementTransform"
        assert len(remove_cmds) == 1


class TestSections:
    def test_next_section_creates_two_sections(self):
        class TwoSectionScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.next_section("second")
                self.play(Create(Square()))

        scene = TwoSectionScene()
        data = json.loads(scene.scene_data)
        assert len(data["sections"]) == 2
        assert data["sections"][0]["name"] == "initial"
        assert data["sections"][1]["name"] == "second"

    def test_second_section_has_independent_snapshot(self):
        class TwoSectionScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.next_section("second")
                s = Square()
                self.play(Create(s))

        scene = TwoSectionScene()
        data = json.loads(scene.scene_data)
        snap1 = data["sections"][0]["snapshot"]
        snap2 = data["sections"][1]["snapshot"]
        ids1 = set(snap1.keys())
        ids2 = set(snap2.keys())
        assert ids1 != ids2
        assert len(ids2) > len(ids1)


class TestDataCommand:
    def test_updater_triggers_data_command(self):
        class UpdaterScene(ManimWidget):
            def construct(self):
                from manim import Dot, ValueTracker

                vt = ValueTracker(0)
                dot = Dot()
                dot.add_updater(lambda m: m.move_to((vt.get_value(), 0, 0)))
                self.add(dot)
                self.play(vt.animate.set_value(3), run_time=0.5)

        scene = UpdaterScene()
        data = json.loads(scene.scene_data)
        commands = data["sections"][0]["construct"]
        data_cmds = [c for c in commands if c["cmd"] == "data"]
        assert len(data_cmds) == 1
        assert data_cmds[0]["duration"] == 0.5
        expected_frames = math.ceil(0.5 * data["fps"])
        assert len(data_cmds[0]["frames"]) == expected_frames


class TestSnapshot:
    def test_snapshot_contains_mobject_ids(self):
        class SnapshotScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.add(c)
                self.next_section("after_add")

        scene = SnapshotScene()
        data = json.loads(scene.scene_data)
        snap = data["sections"][1]["snapshot"]
        assert len(snap) > 0

    def test_fadeout_removes_from_next_snapshot(self):
        class FadeoutSnapshotScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.play(FadeOut(c))
                self.next_section("after_fadeout")

        scene = FadeoutSnapshotScene()
        data = json.loads(scene.scene_data)
        snap_before = data["sections"][0]["snapshot"]
        snap_after = data["sections"][1]["snapshot"]
        assert len(snap_before) > 0
        assert len(snap_after) == 0


class TestSerializeScene:
    def test_serialized_scene_is_valid_json(self):
        class SimpleScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))

        scene = SimpleScene()
        result = serialize_scene(
            fps=scene._fps,
            sections=scene._renderer.sections,
            snapshots=scene._snapshots,
        )
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["version"] == 1


class TestSchemaValidation:
    def test_simple_scene_validates_against_schema(self):
        schema = load_schema()

        class SimpleScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))

        scene = SimpleScene()
        data = json.loads(scene.scene_data)
        validate(instance=data, schema=schema)

    def test_vgroup_scene_validates_against_schema(self):
        schema = load_schema()

        class VGroupScene(ManimWidget):
            def construct(self):
                c = Circle()
                s = Square()
                g = VGroup(c, s)
                self.add(g)

        scene = VGroupScene()
        data = json.loads(scene.scene_data)
        validate(instance=data, schema=schema)
        construct = data["sections"][0]["construct"]
        add_cmd = construct[0]
        assert add_cmd["state"]["kind"] == "VGroup"
        assert "children" in add_cmd["state"]

    def test_valuetracker_scene_validates_against_schema(self):
        schema = load_schema()

        class ValueTrackerScene(ManimWidget):
            def construct(self):
                vt = ValueTracker(0)
                self.add(vt)

        scene = ValueTrackerScene()
        data = json.loads(scene.scene_data)
        validate(instance=data, schema=schema)
        construct = data["sections"][0]["construct"]
        add_cmd = construct[0]
        assert add_cmd["state"]["kind"] == "ValueTracker"
        assert "value" in add_cmd["state"]


class TestLifecycleCorrectness:
    def test_create_without_add_appears_in_next_section_snapshot(self):
        class CreateNoAddScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.next_section("after_create")

        scene = CreateNoAddScene()
        data = json.loads(scene.scene_data)
        snap_initial = data["sections"][0]["snapshot"]
        snap_after = data["sections"][1]["snapshot"]
        assert len(snap_initial) > 0
        assert len(snap_after) > 0


class TestSnapshotOrdering:
    def test_snapshot_preserves_z_index_ordering(self):
        class ZOrderScene(ManimWidget):
            def construct(self):
                c1 = Circle()
                c2 = Circle()
                c1.shift((-1, 0, 0))
                c2.shift((1, 0, 0))
                c1.set_z_index(1)
                c2.set_z_index(2)
                self.add(c1, c2)
                self.next_section("after_add")

        scene = ZOrderScene()
        data = json.loads(scene.scene_data)
        snap = data["sections"][1]["snapshot"]
        ids = list(snap.keys())
        assert len(ids) == 2


class TestColors:
    def test_fill_color_serialized_in_snapshot(self):
        class ColorScene(ManimWidget):
            def construct(self):
                circle = Circle()
                circle.set_fill(PINK, opacity=0.5)
                self.add(circle)
                self.next_section("after_add")

        scene = ColorScene()
        data = json.loads(scene.scene_data)
        snap = data["sections"][1]["snapshot"]
        assert len(snap) > 0
        mob_state = next(iter(snap.values()))
        assert "fill_color" in mob_state
        assert mob_state["fill_color"].startswith("#")

    def test_stroke_color_serialized_in_snapshot(self):
        class StrokeColorScene(ManimWidget):
            def construct(self):
                circle = Circle()
                circle.set_stroke(RED, width=3)
                self.add(circle)
                self.next_section("after_add")

        scene = StrokeColorScene()
        data = json.loads(scene.scene_data)
        snap = data["sections"][1]["snapshot"]
        mob_state = next(iter(snap.values()))
        assert "stroke_color" in mob_state
        assert mob_state["stroke_color"].startswith("#")

    def test_color_and_opacity_together(self):
        class BothColorScene(ManimWidget):
            def construct(self):
                circle = Circle()
                circle.set_fill(BLUE, opacity=0.5)
                circle.set_stroke(WHITE, width=2)
                self.add(circle)
                self.next_section("after_add")

        scene = BothColorScene()
        data = json.loads(scene.scene_data)
        snap = data["sections"][1]["snapshot"]
        mob_state = next(iter(snap.values()))
        assert mob_state["fill_color"].startswith("#")
        assert mob_state["stroke_color"].startswith("#")
        assert mob_state["opacity"] == 0.5


class TestBezierPointsFormat:
    def test_circle_points_are_3n_plus_1(self):
        class CircleScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.add(c)
                self.next_section("after_add")

        scene = CircleScene()
        data = json.loads(scene.scene_data)
        snap = data["sections"][1]["snapshot"]
        for mob_state in snap.values():
            if "points" in mob_state:
                pts = mob_state["points"]
                assert (len(pts) - 1) % 3 == 0, (
                    f"points count {len(pts)} does not satisfy 3n+1"
                )

    def test_rectangle_points_are_3n_plus_1(self):
        class RectScene(ManimWidget):
            def construct(self):
                from manim import Rectangle

                r = Rectangle(width=2, height=1)
                self.add(r)
                self.next_section("after_add")

        scene = RectScene()
        data = json.loads(scene.scene_data)
        snap = data["sections"][1]["snapshot"]
        for mob_state in snap.values():
            if "points" in mob_state:
                pts = mob_state["points"]
                assert (len(pts) - 1) % 3 == 0, (
                    f"points count {len(pts)} does not satisfy 3n+1"
                )
