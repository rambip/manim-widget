from __future__ import annotations

from pathlib import Path
from typing import Any

import anywidget
import traitlets
from manim import Mobject, ThreeDScene

from .renderer import CaptureRenderer, SectionRecord

_ESM = Path(__file__).parent / "static" / "index.js"
_JS_BUNDLE = _ESM.read_text()


def serialize_scene(
    fps: int,
    sections: list[SectionRecord],
    cameras: dict[str, dict[str, float]],
    states: list[object],
) -> dict[str, object]:
    return {
        "version": 1,
        "fps": fps,
        "states": states,
        "sections": [
            {
                "name": s.name,
                "setup": s.setup,
                **({"camera": cameras[s.name]} if s.name in cameras else {}),
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

    def __init__(self, fps: int = 10, is_3d: bool = False, **kwargs: Any) -> None:
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)
        self._cameras: dict[str, dict[str, float]] = {}
        self._last_camera_state: dict[str, float] | None = None

        anywidget.AnyWidget.__init__(self)
        ThreeDScene.__init__(self, renderer=self._renderer, **kwargs)
        self.is_3d = is_3d

        # Initialize renderer - this makes scene.camera available
        self._renderer.init_scene(self)

        self._renderer.open_section("initial")
        self._flush_setup_to_section()

        # Capture initial camera state
        cam_state = self._get_camera_state()
        self._cameras["initial"] = cam_state
        self._last_camera_state = cam_state

        self.construct()

        # Flush any remaining staged adds for final section with no play().
        self._renderer.flush_staged_adds()
        # If section only had add() calls and no play(), still emit semantic Add.
        self._renderer.emit_final_add_animations(self)

        final_cam = self._get_camera_state()
        last_section = (
            self._renderer.sections[-1].name if self._renderer.sections else None
        )
        if last_section and self._camera_changed(final_cam):
            self._cameras[last_section] = final_cam

        data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            cameras=self._cameras,
            states=self._renderer._state_registry.as_list(),
        )
        self.scene_data = data

    def _resolve_camera_angle(
        self,
        *,
        key: str,
        getter_name: str,
        attr_name: str,
        default: float,
    ) -> float:
        del key, getter_name, default
        raw_attr = getattr(self.camera, attr_name, None)
        if isinstance(raw_attr, int | float):
            return float(raw_attr)
        return 0.0

    def _resolve_camera_scalar(
        self,
        *,
        key: str,
        canonical: float,
        attr_name: str,
    ) -> float:
        del key
        raw_attr = getattr(self.camera, attr_name, None)
        if isinstance(raw_attr, int | float):
            return float(raw_attr)
        return canonical

    def _get_camera_state(self) -> dict[str, float]:
        """Capture current 3D camera state including computed FOV."""
        import math

        cam = self.camera
        distance_default = float(getattr(cam, "default_distance", 5))
        distance = self._resolve_camera_scalar(
            key="distance",
            canonical=distance_default,
            attr_name="distance",
        )

        frame_height = float(getattr(cam, "frame_height", 8))
        fov_computed = 2 * math.degrees(math.atan(frame_height / (2 * distance)))
        fov = self._resolve_camera_scalar(
            key="fov",
            canonical=fov_computed,
            attr_name="fov",
        )

        return {
            "phi": self._resolve_camera_angle(
                key="phi",
                getter_name="get_phi",
                attr_name="phi",
                default=0.0,
            ),
            "theta": self._resolve_camera_angle(
                key="theta",
                getter_name="get_theta",
                attr_name="theta",
                default=-math.pi / 2,
            ),
            "distance": distance,
            "fov": fov,
        }

    def _camera_changed(self, state: dict[str, float]) -> bool:
        """Check if camera state differs from previous section."""
        if self._last_camera_state is None:
            return True
        return state != self._last_camera_state

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

        # Capture camera for outgoing section before section switch
        current_section = self._renderer.sections[-1].name
        cam_state = self._get_camera_state()
        changed = self._camera_changed(cam_state)
        if changed:
            self._cameras[current_section] = cam_state
            self._last_camera_state = cam_state

        self._renderer.open_section(name)
        self._flush_setup_to_section()
        if changed:
            self._cameras[name] = cam_state

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
