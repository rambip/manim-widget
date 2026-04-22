from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from manim import (
    Create,
    CyclicReplace,
    FadeIn,
    FadeOut,
    GrowFromCenter,
    ReplacementTransform,
    Rotate,
    ScaleInPlace,
    Scene,
    Swap,
    Text,
    ValueTracker,
    VGroup,
    Write,
)
from manim.animation.animation import Animation
from manim.mobject.mobject import Mobject
from manim.mobject.types.vectorized_mobject import VMobject

from .snapshot import short_id
from .tex_patch import PatchedMathTex


@dataclass
class _DummyCamera:
    use_z_index: bool = False


@dataclass
class SectionRecord:
    name: str
    commands: list[dict] = field(default_factory=list)
    states: list[dict[str, object]] = field(default_factory=list)
    _state_ref_map: dict[str, int] = field(default_factory=dict)


class CaptureRenderer:
    def __init__(self, fps: int) -> None:
        self.fps = fps
        self.time = 0.0
        self.num_plays = 0
        self.skip_animations = False
        self.static_image = None
        self.camera = _DummyCamera(use_z_index=False)
        self.registry: dict[int, Mobject] = {}
        self._active_ids: set[int] = set()
        self.sections: list[SectionRecord] = []
        self._current: SectionRecord | None = None

    def init_scene(self, scene: Scene) -> None:
        self.time = 0.0
        self.num_plays = 0

    def open_section(self, name: str) -> None:
        self._current = SectionRecord(name=name, commands=[])
        self.sections.append(self._current)

    def state_ref_for(self, mob: Mobject) -> int:
        # For groups (VGroup, Group, etc.), ensure children are serialized first
        if hasattr(mob, "submobjects") and mob.submobjects:
            for child in mob.submobjects:
                self.state_ref_for(child)
        return self._intern_state(self.serialize_mobject(mob, for_snapshot=False))

    def serialize_mobject(
        self, mob: Mobject, *, for_snapshot: bool
    ) -> dict[str, object]:
        if isinstance(mob, ValueTracker):
            return {
                "value": float(mob.get_value()),
            }

        state: dict[str, object] = {}

        if isinstance(mob, Text):
            state["text"] = mob.text
            state["font_size"] = mob.font_size

        if isinstance(mob, PatchedMathTex):
            state["kind"] = "MathTexSource"
            state["latex"] = mob.tex_string
            state["points"] = (
                mob.points.tolist()
                if hasattr(mob.points, "tolist")
                else list(mob.points)
            )
            if mob.color is not None:
                state["color"] = self._color_to_hex(mob.color)
            state["font_size"] = mob.font_size
            stroke_opacity = mob.get_stroke_opacity()
            if stroke_opacity is not None:
                state["stroke_opacity"] = stroke_opacity
            return state

        if isinstance(mob, VMobject) and not isinstance(mob, VGroup):
            fill_color = mob.get_fill_color()
            if fill_color:
                state["fill_color"] = self._color_to_hex(fill_color)
            fill_opacity = mob.get_fill_opacity()
            if fill_opacity is not None:
                state["fill_opacity"] = fill_opacity
            stroke_color = mob.get_stroke_color()
            if stroke_color:
                state["stroke_color"] = self._color_to_hex(stroke_color)
            stroke_width = mob.get_stroke_width()
            if stroke_width:
                state["stroke_width"] = stroke_width
            stroke_opacity = mob.get_stroke_opacity()
            if stroke_opacity is not None:
                state["stroke_opacity"] = stroke_opacity
            z_index = mob.get_z_index()
            if z_index is not None:
                state["z_index"] = z_index

        if isinstance(mob, VMobject):
            subpaths = mob.get_subpaths()
            if len(subpaths) > 1:
                return self._serialize_multi_subpath(
                    mob, subpaths, for_snapshot=for_snapshot
                )
            if subpaths:
                raw_points = subpaths[0]
                if len(raw_points) > 0:
                    points_3n1: list[list[float]] = []
                    for i in range(0, len(raw_points), 4):
                        chunk = raw_points[i : i + 4]
                        if i == 0:
                            points_3n1.extend(chunk.tolist())
                        else:
                            points_3n1.extend(chunk[1:].tolist())
                    state["points"] = points_3n1

        if hasattr(mob, "submobjects") and mob.submobjects:
            state["kind"] = "VGroup"
            state["children"] = [self.state_ref_for(child) for child in mob.submobjects]
        else:
            state["kind"] = "VMobject"

        return state

    def _serialize_multi_subpath(
        self, mob: Mobject, subpaths: list, *, for_snapshot: bool
    ) -> dict[str, object]:
        child_refs: list[int] = []
        for subpath in subpaths:
            if len(subpath) == 0:
                continue
            points_3n1: list[list[float]] = []
            for i in range(0, len(subpath), 4):
                chunk = subpath[i : i + 4]
                if i == 0:
                    points_3n1.extend(chunk.tolist())
                else:
                    points_3n1.extend(chunk[1:].tolist())
            child_state: dict[str, object] = {
                "kind": "VMobject",
                "points": points_3n1,
            }
            if isinstance(mob, VMobject):
                fill_color = mob.get_fill_color()
                if fill_color:
                    child_state["fill_color"] = self._color_to_hex(fill_color)
                fill_opacity = mob.get_fill_opacity()
                if fill_opacity is not None:
                    child_state["fill_opacity"] = fill_opacity
                stroke_color = mob.get_stroke_color()
                if stroke_color:
                    child_state["stroke_color"] = self._color_to_hex(stroke_color)
                stroke_width = mob.get_stroke_width()
                if stroke_width:
                    child_state["stroke_width"] = stroke_width
                stroke_opacity = mob.get_stroke_opacity()
                if stroke_opacity is not None:
                    child_state["stroke_opacity"] = stroke_opacity
                z_index = mob.get_z_index()
                if z_index is not None:
                    child_state["z_index"] = z_index
            child_refs.append(self._intern_state(child_state))

        return {
            "kind": "VGroup",
            "children": child_refs,
        }

    def _intern_state(self, state: dict[str, object]) -> int:
        current = self._current
        if current is None:
            msg = "No active section"
            raise RuntimeError(msg)
        key = json.dumps(state, sort_keys=True, separators=(",", ":"))
        existing = current._state_ref_map.get(key)
        if existing is not None:
            return existing
        ref = len(current.states)
        current.states.append(state)
        current._state_ref_map[key] = ref
        return ref

    def update_frame(
        self,
        scene: Scene,
        moving_mobjects: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        pass

    def scene_finished(self, scene: Scene) -> None:
        pass

    def register_mobject(self, mob: Mobject) -> None:
        for member in mob.get_family():
            member_id = id(member)
            self.registry[member_id] = member
            self._active_ids.add(member_id)

    def unregister_mobject(self, mob: Mobject) -> None:
        for member in mob.get_family():
            self._active_ids.discard(id(member))

    def is_active(self, mob: Mobject) -> bool:
        return id(mob) in self._active_ids

    def play(self, scene: Scene, *args: Any, **kwargs: Any) -> None:
        animations = scene.compile_animations(*args, **kwargs)
        if not animations:
            return

        run_time = scene.get_run_time(animations)
        suspend = kwargs.get("suspend_mobject_updating", False)
        has_updaters = (
            any(len(m.updaters) > 0 for m in scene.get_mobject_family_members())
            and not suspend
        )

        if has_updaters:
            self._play_data_path(scene, animations, run_time)
        else:
            self._play_animate_path(scene, animations, run_time)

        self.time += run_time
        self.num_plays += 1

    def _play_animate_path(
        self, scene: Scene, animations: list[Animation], run_time: float
    ) -> None:
        current = self._current
        if current is None:
            return

        pre_commands: list[dict] = []
        animate_descriptors: list[dict] = []
        post_commands: list[dict] = []

        for anim in animations:
            desc = self._descriptor_from_animation(anim)
            animate_descriptors.append(desc)

            mob = anim.mobject
            # Skip registration for group animation internal Groups
            if isinstance(anim, Swap | CyclicReplace):
                continue
            if isinstance(mob, Mobject) and not isinstance(
                mob, VMobject | ValueTracker
            ):
                if not (hasattr(mob, "submobjects") and mob.submobjects):
                    continue
            
            # Intro animations (Create, FadeIn, etc.) need the mobject staged but hidden
            is_intro_animation = isinstance(anim, Create | FadeIn | Write | GrowFromCenter)
            
            if not self.is_active(mob):
                self.register_mobject(mob)
                add_cmd = {
                    "cmd": "add",
                    "id": short_id(mob),
                    "state_ref": self.state_ref_for(mob),
                }
                if is_intro_animation:
                    add_cmd["hidden"] = True
                pre_commands.append(add_cmd)

            if isinstance(anim, ReplacementTransform):
                target = anim.target_mobject
                if not self.is_active(target):
                    self.register_mobject(target)
                source = anim.mobject
                post_commands.append(
                    {
                        "cmd": "rebind",
                        "source_id": short_id(source),
                        "target_id": short_id(target),
                    }
                )

            elif isinstance(anim, FadeOut):
                post_commands.append({"cmd": "remove", "id": short_id(anim.mobject)})

        if pre_commands:
            current.commands.extend(pre_commands)

        current.commands.append(
            {
                "cmd": "animate",
                "duration": run_time,
                "animations": animate_descriptors,
            }
        )

        if post_commands:
            current.commands.extend(post_commands)

        for anim in animations:
            anim._setup_scene(scene)
        for anim in animations:
            anim.begin()
        for anim in animations:
            anim.finish()
        for anim in animations:
            if isinstance(anim, (FadeOut, ReplacementTransform)):
                self.unregister_mobject(anim.mobject)
        for anim in animations:
            anim.clean_up_from_scene(scene)
        scene.update_mobjects(0)

    def _descriptor_from_animation(self, anim: Animation) -> dict[str, Any]:
        anim_name = type(anim).__name__
        params: dict[str, Any] = {}
        descriptor: dict[str, Any] = {}

        if hasattr(anim, "mobject") and anim_name != "Wait":
            descriptor["id"] = short_id(anim.mobject)

        target_mobject = getattr(anim, "target_mobject", None)

        if hasattr(anim, "rate_func"):
            rate_func_name = getattr(anim.rate_func, "__name__", "smooth")
            if "smooth" in rate_func_name.lower():
                descriptor["rate_func"] = "smooth"
            else:
                descriptor["rate_func"] = rate_func_name

        methods = getattr(anim, "methods", None)
        if methods:
            if target_mobject is None:
                msg = "Method animation missing target_mobject"
                raise RuntimeError(msg)
            descriptor["kind"] = "MoveToTarget"
            descriptor["state_ref"] = self.state_ref_for(target_mobject)
            return descriptor

        if anim_name in ("Transform", "ReplacementTransform"):
            if target_mobject is None:
                msg = "Transform animation missing target_mobject"
                raise RuntimeError(msg)
            descriptor["kind"] = "Transform"
            descriptor["state_ref"] = self.state_ref_for(target_mobject)
            transform_params: dict[str, Any] = {}
            path_arc = getattr(anim, "path_arc", None)
            if path_arc is not None:
                transform_params["path_arc"] = float(path_arc)
            path_arc_axis = getattr(anim, "path_arc_axis", None)
            if path_arc_axis is not None:
                transform_params["path_arc_axis"] = list(path_arc_axis)
            if transform_params:
                descriptor["params"] = transform_params
            return descriptor

        if isinstance(anim, Swap):
            group = getattr(anim, "group", None)
            if group is None or not hasattr(group, "submobjects"):
                msg = "Swap animation missing group or submobjects"
                raise RuntimeError(msg)
            submobjects = group.submobjects
            if len(submobjects) < 2:
                msg = "Swap animation requires at least 2 mobjects"
                raise RuntimeError(msg)
            descriptor = {
                "kind": "Swap",
                "ids": [short_id(m) for m in submobjects[:2]],
            }
            swap_params: dict[str, Any] = {}
            path_arc = getattr(anim, "path_arc", None)
            if path_arc is not None:
                swap_params["path_arc"] = float(path_arc)
            if swap_params:
                descriptor["params"] = swap_params
            if hasattr(anim, "rate_func"):
                rate_func_name = getattr(anim.rate_func, "__name__", "smooth")
                if "smooth" in rate_func_name.lower():
                    descriptor["rate_func"] = "smooth"
                else:
                    descriptor["rate_func"] = rate_func_name
            return descriptor

        if isinstance(anim, CyclicReplace) and not isinstance(anim, Swap):
            group = getattr(anim, "group", None)
            if group is None or not hasattr(group, "submobjects"):
                msg = "CyclicReplace animation missing group or submobjects"
                raise RuntimeError(msg)
            submobjects = group.submobjects
            if len(submobjects) < 2:
                msg = "CyclicReplace animation requires at least 2 mobjects"
                raise RuntimeError(msg)
            descriptor = {
                "kind": "CyclicReplace",
                "ids": [short_id(m) for m in submobjects],
            }
            cyclic_params: dict[str, Any] = {}
            path_arc = getattr(anim, "path_arc", None)
            if path_arc is not None:
                cyclic_params["path_arc"] = float(path_arc)
            if cyclic_params:
                descriptor["params"] = cyclic_params
            if hasattr(anim, "rate_func"):
                rate_func_name = getattr(anim.rate_func, "__name__", "smooth")
                if "smooth" in rate_func_name.lower():
                    descriptor["rate_func"] = "smooth"
                else:
                    descriptor["rate_func"] = rate_func_name
            return descriptor

        if isinstance(anim, Rotate):
            params["angle"] = float(getattr(anim, "angle", 0.0))
            axis = getattr(anim, "axis", None)
            if axis is not None:
                params["axis"] = list(axis)
            about_point = getattr(anim, "about_point", None)
            if about_point is not None:
                params["about_point"] = list(about_point)
        elif isinstance(anim, ScaleInPlace):
            params["scale_factor"] = float(getattr(anim, "scale_factor", 1.0))
        else:
            path = getattr(anim, "path", None)
            if path is not None:
                params["path_id"] = short_id(path)
            about_point = getattr(anim, "about_point", None)
            if about_point is not None:
                params["about_point"] = list(about_point)
        descriptor["kind"] = anim_name
        if params:
            descriptor["params"] = params
        return descriptor

    def _play_data_path(
        self, scene: Scene, animations: list[Animation], run_time: float
    ) -> None:
        current = self._current
        if current is None:
            return

        tracked: list[Mobject] = []
        seen: set[int] = set()
        for m in scene.get_mobject_family_members():
            for member in m.get_family():
                member_id = id(member)
                if member_id in seen:
                    continue
                seen.add(member_id)
                tracked.append(member)
        for anim in animations:
            if hasattr(anim, "mobject"):
                member = anim.mobject
                member_id = id(member)
                if member_id not in seen:
                    seen.add(member_id)
                    tracked.append(member)

        scene.animations = animations
        scene.last_t = 0.0
        for anim in animations:
            anim._setup_scene(scene)
        for anim in animations:
            anim.begin()

        n_frames = math.ceil(run_time * self.fps)
        frames: list[dict[str, Any]] = []
        for i in range(n_frames):
            t = (i + 1) / self.fps
            if t > run_time:
                t = run_time
            scene.update_to_time(t)
            frame: dict[str, Any] = {}
            for mob in tracked:
                mob_id = short_id(mob)
                frame[mob_id] = {"state_ref": self.state_ref_for(mob)}
            frames.append(frame)

        for anim in animations:
            anim.finish()
        for anim in animations:
            anim.clean_up_from_scene(scene)
        scene.update_mobjects(0)

        current.commands.append(
            {
                "cmd": "updater",
                "duration": run_time,
                "frames": frames,
            }
        )

    def _color_to_hex(self, color: object) -> str:
        if hasattr(color, "to_hex"):
            return color.to_hex()
        return str(color)
