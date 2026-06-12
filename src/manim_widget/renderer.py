from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from manim import (
    CyclicReplace,
    FadeOut,
    GrowArrow,
    ReplacementTransform,
    Rotate,
    ScaleInPlace,
    Scene,
    Swap,
)
from manim.animation.animation import Animation
from manim.animation.composition import AnimationGroup
from manim.mobject.mobject import Mobject
from manim.mobject.types.vectorized_mobject import VMobject

from ._camera import _needs_camera_loop, _serialize_camera
from ._serializer import MobSerializer
from .anim_compat import force_end_state
from .snapshot import IdCounter
from .states import MobjectState


def _is_mob_supported(mob: Mobject) -> bool:
    """Return True for mob types the JS player can render."""
    from manim import ValueTracker
    from manim.mobject.types.image_mobject import AbstractImageMobject

    if isinstance(mob, VMobject | ValueTracker | AbstractImageMobject):
        return True
    return bool(hasattr(mob, "submobjects") and mob.submobjects)


def _rate_func_name(anim: object) -> str:
    name = getattr(getattr(anim, "rate_func", None), "__name__", "smooth")
    return "smooth" if "smooth" in name.lower() else name


@dataclass
class SectionRecord:
    name: str
    commands: list[dict] = field(default_factory=list)
    # setup: list of {cmd:"register", id:..., state_ref:...} emitted for snapshot mobs
    setup: list[dict] = field(default_factory=list)


class CaptureRenderer:
    def __init__(self, fps: int) -> None:
        self.fps = fps
        self.time = 0.0
        self.num_plays = 0
        self.skip_animations = False
        self.static_image = None
        self._scene: Scene | None = None
        self._camera = None
        self.registry: dict[int, Mobject] = {}
        self._active_ids: set[int] = set()
        self.sections: list[SectionRecord] = []
        self._current: SectionRecord | None = None
        self._serializer = MobSerializer(IdCounter())
        # Staging bucket for pre-play add() calls in current section.
        self._staged_adds: dict[str, Mobject] = {}
        # Ignore internal scene.add() calls during animation setup.
        self._suppress_stage_adds: bool = False
        # Whether a mobject has ever been introduced via an animation introducer.
        self._introduced_by_animation: dict[int, bool] = {}

    # ------------------------------------------------------------------
    # Delegation to serializer (preserve external API surface)
    # ------------------------------------------------------------------

    @property
    def _state_registry(self):
        return self._serializer._state_registry

    @property
    def state_refs(self) -> dict[int, list[int]]:
        return self._serializer.state_refs

    def short_id(self, mob: object) -> str:
        return self._serializer.short_id(mob)

    def state_ref_for(self, mob: Mobject) -> int:
        return self._serializer.state_ref_for(mob)

    def serialize_mobject(self, mob: Mobject, *, for_snapshot: bool) -> MobjectState:
        return self._serializer.serialize_mobject(mob, for_snapshot=for_snapshot)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, value):
        self._camera = value

    def init_scene(self, scene: Scene) -> None:
        self._scene = scene
        self.time = 0.0
        self.num_plays = 0

        if self._camera is None:
            from manim.camera.three_d_camera import ThreeDCamera

            camera_class = getattr(scene, "camera_class", None) or ThreeDCamera
            self._camera = camera_class()

    def open_section(self, name: str) -> None:
        self._current = SectionRecord(name=name, commands=[])
        self.sections.append(self._current)
        self._staged_adds = {}

    def update_frame(
        self,
        scene: Scene,
        moving_mobjects: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        pass

    def scene_finished(self, scene: Scene) -> None:
        pass

    # ------------------------------------------------------------------
    # Mob registry
    # ------------------------------------------------------------------

    def register_mobject(self, mob: Mobject) -> None:
        for member in mob.get_family():
            member_id = id(member)
            self.registry[member_id] = member
            self._active_ids.add(member_id)
            self._introduced_by_animation.setdefault(member_id, False)

    def unregister_mobject(self, mob: Mobject) -> None:
        for member in mob.get_family():
            member_id = id(member)
            self._active_ids.discard(member_id)
            self._introduced_by_animation.pop(member_id, None)

    def is_active(self, mob: Mobject) -> bool:
        return id(mob) in self._active_ids

    # ------------------------------------------------------------------
    # Section staging
    # ------------------------------------------------------------------

    def flush_staged_adds(self) -> None:
        """Emit staged pre-play register commands into the current section."""
        current = self._current
        if current is None or not self._staged_adds:
            return
        for mob in self._staged_adds.values():
            current.commands.extend(self._serializer._mob_register_commands(mob))
        self._staged_adds = {}

    def emit_final_add_animations(self, scene: Scene) -> None:
        """Emit a terminal animate command with Add descriptors if needed.

        Covers sections that only call ``self.add(...)`` and never call ``play(...)``.
        """
        current = self._current
        if current is None:
            return

        if any(cmd.get("cmd") in {"animate", "updater"} for cmd in current.commands):
            return

        add_animations: list[dict[str, str]] = []
        for mob in scene.mobjects:
            if not _is_mob_supported(mob):
                continue
            if not self.is_active(mob):
                continue
            if self._introduced_by_animation.get(id(mob), False):
                continue
            add_animations.append({"kind": "Add", "id": self.short_id(mob)})
            self._introduced_by_animation[id(mob)] = True

        if add_animations:
            current.commands.append(
                {
                    "cmd": "animate",
                    "duration": 0,
                    "animations": add_animations,
                }
            )

    def stage_add(self, mob: Mobject) -> None:
        """Stage an add command until play()/section-finalization flushes it."""
        self._staged_adds[self.short_id(mob)] = mob

    # ------------------------------------------------------------------
    # Play / animation capture
    # ------------------------------------------------------------------

    def play(self, scene: Scene, *args: Any, **kwargs: Any) -> None:
        self.flush_staged_adds()

        animations = scene.compile_animations(*args, **kwargs)
        if not animations:
            return

        run_time = scene.get_run_time(animations)
        suspend = kwargs.get("suspend_mobject_updating", False)
        _cam_frame_for_updater_check = getattr(
            getattr(scene, "camera", None), "frame", None
        )
        cam_frame_has_updaters = bool(
            _cam_frame_for_updater_check is not None
            and getattr(_cam_frame_for_updater_check, "updaters", [])
        )
        has_updaters = (
            any(len(m.updaters) > 0 for m in scene.get_mobject_family_members())
            or cam_frame_has_updaters
        ) and not suspend

        if has_updaters:
            self._play_data_path(scene, animations, run_time)
        else:
            self._play_animate_path(scene, animations, run_time)

        self.time += run_time
        self.num_plays += 1

    def _process_leaf_anim(
        self,
        anim: Animation,
        pre_commands: list[dict],
        post_commands: list[dict],
    ) -> None:
        """Register mob and accumulate pre/post commands for one leaf animation."""
        mob = anim.mobject
        if isinstance(anim, Swap | CyclicReplace):
            return
        if isinstance(mob, Mobject) and not _is_mob_supported(mob):
            return

        if not self.is_active(mob):
            self.register_mobject(mob)
            if isinstance(anim, GrowArrow):
                pre_commands.extend(
                    self._serializer._grow_arrow_register_commands(mob, anim)
                )
            else:
                pre_commands.extend(self._serializer._mob_register_commands(mob))

        if anim.is_introducer():
            self._introduced_by_animation[id(mob)] = True

        if isinstance(anim, ReplacementTransform):
            target = anim.target_mobject
            if not self.is_active(target):
                self.register_mobject(target)
            post_commands.append(
                {
                    "cmd": "rebind",
                    "source_id": self.short_id(anim.mobject),
                    "target_id": self.short_id(target),
                }
            )
        elif isinstance(anim, FadeOut):
            post_commands.extend(self._serializer._mob_remove_commands(anim.mobject))

    def _play_animate_path(
        self, scene: Scene, animations: list[Animation], run_time: float
    ) -> None:
        """Emit register + animate + post commands for a non-updater play() call.

        post: self._current.commands[-1]["cmd"] == "animate"
        post: implies(isinstance(anim, GrowArrow) for anim in animations,
                      forall([d for d in self._current.commands[-1]["animations"]
                               if "state_ref" in d],
                             lambda d: isinstance(d["state_ref"], int)))
        """
        current = self._current
        if current is None:
            return

        pre_commands: list[dict] = []
        animate_descriptors: list[dict] = []
        post_commands: list[dict] = []

        for mob in scene.mobjects:
            if not _is_mob_supported(mob):
                continue
            if not self.is_active(mob):
                self.register_mobject(mob)
                pre_commands.extend(self._serializer._mob_register_commands(mob))
            if not self._introduced_by_animation.get(id(mob), False):
                animate_descriptors.append({"kind": "Add", "id": self.short_id(mob)})
                self._introduced_by_animation[id(mob)] = True

        for anim in animations:
            if isinstance(anim, AnimationGroup):
                animate_descriptors.extend(self._flatten_animation_group(anim))
                for row in anim.anims_with_timings:
                    self._process_leaf_anim(row["anim"], pre_commands, post_commands)
            else:
                animate_descriptors.append(self._descriptor_from_animation(anim))
                self._process_leaf_anim(anim, pre_commands, post_commands)

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

        self._suppress_stage_adds = True
        try:
            for anim in animations:
                anim._setup_scene(scene)
        finally:
            self._suppress_stage_adds = False

        n_frames = math.ceil(run_time * self.fps)
        needs_cam_anim = _needs_camera_loop(scene, animations)

        fw = float(getattr(scene.camera, "frame_width", 14.222))
        fh = float(getattr(scene.camera, "frame_height", 8.0))
        initial_cam_pts: list | None = None
        initial_cam_focal: float = 0.0
        if needs_cam_anim:
            initial_cam_pts, initial_cam_focal = _serialize_camera(scene.camera, fw, fh)

        begin_failed = False
        try:
            for anim in animations:
                anim.begin()
        except Exception as exc:
            import warnings

            warnings.warn(
                f"Animation batch could not begin Python-side ({exc}). "
                "Applying end states directly; this scene would not play back "
                "in plain Manim. See manim_widget.anim_compat for details.",
                stacklevel=3,
            )
            begin_failed = True
            for anim in animations:
                if hasattr(anim, "target_mobject"):
                    force_end_state(anim)

        if not begin_failed:
            if needs_cam_anim:
                scene.animations = animations
                scene.last_t = 0.0

                _cam_frame = getattr(getattr(scene, "camera", None), "frame", None)
                _frame_dt = 1.0 / self.fps
                for i in range(n_frames):
                    t = (i + 1) / self.fps
                    if t > run_time:
                        t = run_time
                    scene.update_to_time(t)
                    if _cam_frame is not None:
                        _cam_frame.update(_frame_dt)

                scene.animations = None

            for anim in animations:
                anim.finish()

        for anim in animations:
            if isinstance(anim, (FadeOut, ReplacementTransform)):
                self.unregister_mobject(anim.mobject)
        for anim in animations:
            anim.clean_up_from_scene(scene)
        scene.update_mobjects(0)

        if needs_cam_anim:
            final_cam_pts, final_cam_focal = _serialize_camera(scene.camera, fw, fh)
            if final_cam_pts != initial_cam_pts:
                final_cam_ref = self._state_registry.insert_raw(
                    {
                        "kind": "Camera",
                        "points": final_cam_pts,
                        "focal_distance": final_cam_focal,
                    }
                )
                animate_descriptors.append(
                    {
                        "kind": "MoveToTarget",
                        "id": "#camera",
                        "state_ref": final_cam_ref,
                    }
                )

    def _flatten_animation_group(self, group: AnimationGroup) -> list[dict]:
        """Expand an AnimationGroup into timestamped descriptors for the JS player.

        Timestamps are scaled so the last sub-animation ends at group.run_time,
        preserving lag_ratio spacing proportionally.
        """
        scale = group.run_time / group.max_end_time if group.max_end_time > 0 else 1.0
        result = []
        for row in group.anims_with_timings:
            desc = self._descriptor_from_animation(row["anim"])
            desc["start"] = round(float(row["start"]) * scale, 6)
            desc["end"] = round(float(row["end"]) * scale, 6)
            result.append(desc)
        return result

    def _descriptor_from_animation(self, anim: Animation) -> dict[str, Any]:
        """Translate a single manim Animation into a wire-format descriptor dict.

        post: "kind" in __return__
        post: implies("state_ref" in __return__, isinstance(__return__["state_ref"], int))
        post: implies(isinstance(anim, GrowArrow), __return__["kind"] == "Transform")
        post: implies(isinstance(anim, GrowArrow), "state_ref" in __return__)
        post: implies(isinstance(anim, (Swap, CyclicReplace)), "ids" in __return__)
        post: implies(isinstance(anim, (Swap, CyclicReplace)), "id" not in __return__)
        """
        anim_name = type(anim).__name__
        params: dict[str, Any] = {}
        descriptor: dict[str, Any] = {}

        if hasattr(anim, "mobject") and anim_name != "Wait":
            descriptor["id"] = self.short_id(anim.mobject)

        target_mobject = getattr(anim, "target_mobject", None)

        descriptor["rate_func"] = _rate_func_name(anim)

        methods = getattr(anim, "methods", None)
        if methods:
            if target_mobject is None:
                msg = "Method animation missing target_mobject"
                raise RuntimeError(msg)
            descriptor["kind"] = "MoveToTarget"
            descriptor["state_ref"] = self.state_ref_for(target_mobject)
            return descriptor

        if isinstance(anim, GrowArrow):
            descriptor["kind"] = "Transform"
            descriptor["state_ref"] = self.state_ref_for(anim.mobject)
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

        if isinstance(anim, Swap | CyclicReplace):
            kind = "Swap" if isinstance(anim, Swap) else "CyclicReplace"
            group = getattr(anim, "group", None)
            if group is None or not hasattr(group, "submobjects"):
                msg = f"{kind} animation missing group or submobjects"
                raise RuntimeError(msg)
            submobjects = group.submobjects
            if len(submobjects) < 2:
                msg = f"{kind} animation requires at least 2 mobjects"
                raise RuntimeError(msg)
            ids = [
                self.short_id(m)
                for m in (submobjects[:2] if kind == "Swap" else submobjects)
            ]
            descriptor = {"kind": kind, "ids": ids}
            path_arc = getattr(anim, "path_arc", None)
            if path_arc is not None:
                descriptor["params"] = {"path_arc": float(path_arc)}
            descriptor["rate_func"] = _rate_func_name(anim)
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
                params["path_id"] = self.short_id(path)
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

        self.flush_staged_adds()

        scene.animations = animations
        scene.last_t = 0.0
        self._suppress_stage_adds = True
        try:
            for anim in animations:
                anim._setup_scene(scene)
        finally:
            self._suppress_stage_adds = False
        for anim in animations:
            anim.begin()

        registered_ids = {
            cmd["id"] for cmd in current.commands if cmd.get("cmd") == "register"
        }
        for mob in tracked:
            mob_id = self.short_id(mob)
            if mob_id not in registered_ids:
                current.commands.extend(self._serializer._mob_register_commands(mob))
                registered_ids.add(mob_id)

        n_frames = math.ceil(run_time * self.fps)
        frames: list[dict[str, Any]] = []

        fw = float(getattr(scene.camera, "frame_width", 14.222))
        fh = float(getattr(scene.camera, "frame_height", 8.0))
        initial_cam_pts, initial_cam_focal = _serialize_camera(scene.camera, fw, fh)
        last_cam_pts = initial_cam_pts
        last_cam_ref = self._state_registry.insert_raw(
            {
                "kind": "Camera",
                "points": initial_cam_pts,
                "focal_distance": initial_cam_focal,
            }
        )
        _cam_frame = getattr(getattr(scene, "camera", None), "frame", None)
        _frame_dt = 1.0 / self.fps

        for i in range(n_frames):
            t = (i + 1) / self.fps
            if t > run_time:
                t = run_time
            scene.update_to_time(t)
            if _cam_frame is not None:
                _cam_frame.update(_frame_dt)
            frame: dict[str, Any] = {}
            for mob in tracked:
                mob_id = self.short_id(mob)
                frame[mob_id] = {"state_ref": self.state_ref_for(mob)}

            cam_pts, cam_focal = _serialize_camera(scene.camera, fw, fh)
            if cam_pts != last_cam_pts:
                last_cam_ref = self._state_registry.insert_raw(
                    {"kind": "Camera", "points": cam_pts, "focal_distance": cam_focal}
                )
                last_cam_pts = cam_pts
            frame["#camera"] = {"state_ref": last_cam_ref}

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
