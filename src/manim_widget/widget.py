from __future__ import annotations

from pathlib import Path
from typing import Any

import anywidget
import traitlets
from manim import Mobject, ThreeDScene

from .renderer import CaptureRenderer, SectionRecord, _serialize_camera


_ESM = Path(__file__).parent / "static" / "index.js"
_JS_BUNDLE = _ESM.read_text()


def serialize_scene(
    fps: int,
    sections: list[SectionRecord],
    states: list[object],
    frame_width: float = 14.222222222222221,
    frame_height: float = 8.0,
) -> dict[str, object]:
    return {
        "version": 2,
        "fps": fps,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "states": states,
        "sections": [
            {
                "name": s.name,
                "snapshot": {
                    entry["id"]: entry["state_ref"]
                    for entry in s.setup
                    if entry.get("cmd") == "register"
                },
                "construct": s.commands,
            }
            for s in sections
        ],
    }


class ManimWidget(anywidget.AnyWidget, ThreeDScene):
    _esm = _JS_BUNDLE
    scene_data = traitlets.Any({}).tag(sync=True)
    playback_error = traitlets.Unicode("").tag(sync=True)
    is_3d = traitlets.Bool(False).tag(sync=True)
    shared_camera_id = traitlets.Unicode("").tag(sync=True)

    def __init__(
        self,
        fps: int = 10,
        is_3d: bool = False,
        shared_camera: Any = None,
        **kwargs: Any,
    ) -> None:
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)

        from manim.camera.three_d_camera import ThreeDCamera as _ThreeDCamera

        _camera_class = getattr(type(self), "camera_class", _ThreeDCamera)

        anywidget.AnyWidget.__init__(self)
        ThreeDScene.__init__(
            self, renderer=self._renderer, camera_class=_camera_class, **kwargs
        )
        self.is_3d = is_3d
        if shared_camera is not None:
            self.shared_camera_id = shared_camera.camera_id

        self._renderer.init_scene(self)
        self._renderer.open_section("initial")
        self._flush_setup_to_section()

        self.construct()

        self._renderer.flush_staged_adds()
        self._renderer.emit_final_add_animations(self)

        data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            states=self._renderer._state_registry.as_list(),
            frame_width=float(self.camera.frame_width),
            frame_height=float(self.camera.frame_height),
        )
        self.scene_data = data

    def _mob_is_animated(self, mob: Mobject) -> bool:
        """Return True if mob was the source or target of any animation during construction."""
        refs = self._renderer.state_refs.get(id(mob), [])
        if len(refs) > 1:
            return True
        mob_id = self._renderer.short_id(mob)
        for section in self._renderer.sections:
            for cmd in section.commands:
                if cmd.get("cmd") != "animate":
                    continue
                for anim in cmd.get("animations", []):
                    if anim.get("id") == mob_id and "state_ref" in anim:
                        return True
        return False

    def sync(self, *mobs: Mobject) -> None:
        """Re-serialize mutated mobjects and push updated scene_data.

        Assumes no add/remove/play calls happened since construction.
        Emits a warning and skips any mob that was animated during construction,
        since overwriting its state_refs would corrupt the recorded animation.
        """
        import warnings

        reg = self._renderer._state_registry
        for mob in mobs:
            refs = self._renderer.state_refs.get(id(mob))
            if not refs:
                warnings.warn(f"mob {mob!r} not found in state registry", stacklevel=2)
                continue
            if self._mob_is_animated(mob):
                warnings.warn(
                    f"mob {mob!r} was animated during construction; sync() ignored",
                    stacklevel=2,
                )
                continue
            state = self._renderer.serialize_mobject(mob, for_snapshot=False)
            d = state.model_dump(exclude_none=True, exclude_defaults=False)
            if d.get("kind") == "VMobject":
                d.setdefault("contours", [])
            for ref in refs:
                reg._values[ref] = d
        data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            states=list(reg.as_list()),
            frame_width=float(self.camera.frame_width),
            frame_height=float(self.camera.frame_height),
        )
        self.scene_data = data

    def next_section(
        self,
        name: str = "unnamed",
        section_type: str = "normal",
        skip_animations: bool = False,
    ) -> None:
        del section_type, skip_animations
        # Finalize staged adds into the outgoing section before section switch.
        self._renderer.flush_staged_adds()
        # If outgoing section had only add() calls, emit terminal Add animate batch.
        self._renderer.emit_final_add_animations(self)

        self._renderer.open_section(name)
        self._flush_setup_to_section()

    def _flush_setup_to_section(self) -> None:
        """Populate the current section's setup with register commands for all active mobs.

        For ImageMobjects two register commands are emitted: one carrying only the
        pixel data (kind + source, no points) and one carrying only the position
        (points). This way the expensive PNG blob is stored once in the global
        states bank and position updates in later sections only add a cheap
        points-only entry — never re-encode the image.

        Only root mobjects are included; VGroup children are referenced via their
        parent's VGroupState children array.
        """
        renderer = self._renderer
        current = renderer._current
        if current is None:
            return

        child_ids: set[int] = set()
        for mob_id, mob in renderer.registry.items():
            if mob_id not in renderer._active_ids:
                continue
            if hasattr(mob, "submobjects") and mob.submobjects:
                for child in mob.submobjects:
                    child_ids.add(id(child))

        for mob_id, mob in renderer.registry.items():
            if mob_id not in renderer._active_ids:
                continue
            if mob_id in child_ids:
                continue
            mob_sid = renderer.short_id(mob)
            state_ref = renderer.state_ref_for(mob)
            current.setup.append(
                {"cmd": "register", "id": mob_sid, "state_ref": state_ref}
            )

        cam = self.camera
        fw = float(getattr(cam, "frame_width", 14.222))
        fh = float(getattr(cam, "frame_height", 8.0))
        cam_pts, cam_focal = _serialize_camera(cam, fw, fh)
        cam_ref = renderer._state_registry.insert_raw(
            {"kind": "Camera", "points": cam_pts, "focal_distance": cam_focal}
        )
        current.setup.append({"cmd": "register", "id": "#camera", "state_ref": cam_ref})

    def add(self, *mobjects: Mobject) -> None:  # type: ignore[override]
        current = self._renderer._current
        if current is not None:
            for mob in mobjects:
                mob_id = id(mob)
                if mob_id not in self._renderer.registry:
                    self._renderer.register_mobject(mob)
                # Stage pre-play adds; last add of same object wins.
                # Suppress staging for internal animation-setup scene.add() calls.
                if not self._renderer._suppress_stage_adds:
                    self._renderer.stage_add(mob)
        ThreeDScene.add(self, *mobjects)

    def remove(self, *mobjects: Mobject) -> None:  # type: ignore[override]
        current = self._renderer._current
        if current is not None:
            for mob in mobjects:
                if self._renderer.is_active(mob):
                    self._renderer.unregister_mobject(mob)
                    current.commands.append(
                        {
                            "cmd": "remove",
                            "id": self._renderer.short_id(mob),
                        }
                    )
        ThreeDScene.remove(self, *mobjects)
