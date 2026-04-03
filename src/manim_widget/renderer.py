from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from manim import Create, FadeIn, FadeOut, ReplacementTransform, Transform, Write
from manim.animation.animation import Animation
from manim.mobject.types.vectorized_mobject import VMobject
from manim.mobject.mobject import Mobject

if TYPE_CHECKING:
    from manim import Scene

from .snapshot import serialize_mobject, short_id


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
        return self._intern_state(serialize_mobject(mob))

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

            elif isinstance(anim, (Create, FadeIn, Write)):
                mob = anim.mobject
                if not self.is_active(mob):
                    self.register_mobject(mob)
                pre_commands.append(
                    {
                        "cmd": "add",
                        "id": short_id(mob),
                        "state_ref": self.state_ref_for(mob),
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
