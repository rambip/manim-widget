from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from manim import (
    Create,
    FadeIn,
    FadeOut,
    ReplacementTransform,
    Text,
    Transform,
    ValueTracker,
    VGroup,
    Write,
)
from manim.animation.animation import Animation
from manim.mobject.types.vectorized_mobject import VMobject
from manim.mobject.mobject import Mobject

if TYPE_CHECKING:
    from manim import Scene

from .snapshot import short_id


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
        # For VGroups, ensure children are serialized first
        if isinstance(mob, VGroup):
            for child in mob.submobjects:
                self.state_ref_for(child)
        return self._intern_state(self.serialize_mobject(mob, for_snapshot=False))

    def serialize_mobject(
        self, mob: Mobject, *, for_snapshot: bool
    ) -> dict[str, object]:
        if isinstance(mob, ValueTracker):
            return {
                "kind": "ValueTracker",
                "value": float(mob.get_value()),
            }

        state: dict[str, object] = {
            "kind": type(mob).__name__,
            "opacity": self._opacity_for(mob),
        }

        if isinstance(mob, Text):
            state["text"] = mob.text
            state["font_size"] = mob.font_size

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

        if isinstance(mob, VGroup) or (isinstance(mob, VMobject) and mob.submobjects):
            # Always use VGroup with children as mob_ids (consistent with spec)
            state["kind"] = "VGroup"
            state["children"] = [short_id(child) for child in mob.submobjects]

        return state

    def _serialize_multi_subpath(
        self, mob: Mobject, subpaths: list, *, for_snapshot: bool
    ) -> dict[str, object]:
        child_states: list[dict[str, object]] = []
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
                "kind": type(mob).__name__,
                "points": points_3n1,
                "opacity": self._opacity_for(mob),
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
            child_states.append(child_state)

        # Always use VGroup with children as mob_ids (consistent with spec)
        return {
            "kind": "VGroup",
            "opacity": self._opacity_for(mob),
            "children": child_states,
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
            if isinstance(mob, Mobject) and not isinstance(
                mob, VMobject | ValueTracker
            ):
                continue
            if not self.is_active(mob):
                self.register_mobject(mob)
                pre_commands.append(
                    {
                        "cmd": "add",
                        "id": short_id(mob),
                        "state_ref": self.state_ref_for(mob),
                    }
                )

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

        if hasattr(anim, "mobject"):
            descriptor["id"] = short_id(anim.mobject)

        target_mobject = getattr(anim, "target_mobject", None)

        if hasattr(anim, "rate_func"):
            rate_func_name = getattr(anim.rate_func, "__name__", "smooth")
            if "smooth" in rate_func_name.lower():
                descriptor["rate_func"] = "smooth"
            else:
                descriptor["rate_func"] = rate_func_name

        methods = getattr(anim, "methods", None)
        is_method_animation = False
        if methods:
            # For chained method animations, use Transform with target_mobject
            if len(methods) > 1:
                if target_mobject is None:
                    msg = "Chained method animation missing target_mobject"
                    raise RuntimeError(msg)
                descriptor["type"] = "transform"
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

            # Single method animation - decode method parameters
            for mwa in methods:
                method_name = mwa.method.__name__
                method_args = mwa.args
                is_method_animation = True
                if method_name == "shift":
                    anim_name = "Shift"
                    params["vector"] = list(method_args[0])
                elif method_name == "rotate":
                    anim_name = "Rotate"
                    params["angle"] = method_args[0]
                    if len(method_args) > 1:
                        params["axis"] = list(method_args[1])
                elif method_name == "scale":
                    anim_name = "ScaleInPlace"
                    params["scale_factor"] = method_args[0]
                elif method_name in (
                    "scale_to_fit_width",
                    "scale_to_fit_height",
                    "set_width",
                    "set_height",
                ):
                    anim_name = "ScaleInPlace"
                    mob = anim.mobject
                    if mob is not None:
                        if method_name in ("scale_to_fit_width", "set_width"):
                            target = method_args[0]
                            current = mob.get_width()
                        else:
                            target = method_args[0]
                            current = mob.get_height()
                        if current > 0:
                            params["scale_factor"] = target / current
                elif method_name in (
                    "move_to",
                    "next_to",
                    "to_corner",
                    "to_edge",
                    "align_to",
                ):
                    anim_name = "Shift"
                    if target_mobject is not None and anim.mobject is not None:
                        shift_vec = (
                            target_mobject.get_center() - anim.mobject.get_center()
                        )
                        params["vector"] = list(shift_vec)

        if is_method_animation:
            descriptor["type"] = "simple"
            descriptor["kind"] = anim_name
            descriptor["params"] = params
            return descriptor

        if anim_name in ("Transform", "ReplacementTransform"):
            if target_mobject is None:
                msg = "Transform animation missing target_mobject"
                raise RuntimeError(msg)
            descriptor["type"] = "transform"
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

        descriptor["type"] = "simple"
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
                "cmd": "data",
                "duration": run_time,
                "frames": frames,
            }
        )

    def _opacity_for(self, mob: Mobject) -> float:
        if isinstance(mob, VMobject):
            return float(mob.get_fill_opacity())
        if hasattr(mob, "opacity"):
            return float(getattr(mob, "opacity"))
        return 1.0

    def _color_to_hex(self, color: object) -> str:
        if hasattr(color, "to_hex"):
            return color.to_hex()
        return str(color)
