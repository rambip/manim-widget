from __future__ import annotations

from pathlib import Path
from typing import Any

import anywidget
import traitlets
from manim import Mobject, ThreeDScene

from .renderer import CaptureRenderer, SectionRecord
from .snapshot import short_id

_ESM = Path(__file__).parent / "static" / "index.js"
_JS_BUNDLE = _ESM.read_text()


def serialize_scene(
    fps: int,
    sections: list[SectionRecord],
    snapshots: dict[str, dict[str, object]],
    cameras: dict[str, dict[str, float]],
) -> dict[str, object]:
    return {
        "version": 2,
        "fps": fps,
        "sections": [
            {
                "name": s.name,
                "snapshot": snapshots.get(s.name, {}),
                **({"camera": cameras[s.name]} if s.name in cameras else {}),
                "states": s.states,
                "construct": s.commands,
            }
            for s in sections
        ],
    }


class ManimWidget(anywidget.AnyWidget, ThreeDScene):
    _esm = _JS_BUNDLE
    scene_data = traitlets.Any({}).tag(sync=True)
    playback_error = traitlets.Unicode("").tag(sync=True)

    def __init__(self, fps: int = 10, **kwargs: Any) -> None:
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._cameras: dict[str, dict[str, float]] = {}
        self._last_camera_state: dict[str, float] | None = None

        anywidget.AnyWidget.__init__(self)
        ThreeDScene.__init__(self, renderer=self._renderer, **kwargs)

        # Initialize renderer - this makes scene.camera available
        self._renderer.init_scene(self)

        self._renderer.open_section("initial")
        self._snapshots["initial"] = self._snapshot_from_registry()
        
        # Capture initial camera state
        cam_state = self._get_camera_state()
        self._cameras["initial"] = cam_state
        self._last_camera_state = cam_state
        
        self.construct()
        
        # Capture final camera state if changed (for last section)
        final_cam = self._get_camera_state()
        last_section = self._renderer.sections[-1].name if self._renderer.sections else None
        if last_section and self._camera_changed(final_cam):
            self._cameras[last_section] = final_cam

        data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            snapshots=self._snapshots,
            cameras=self._cameras,
        )
        self.scene_data = data

    def _get_camera_state(self) -> dict[str, float]:
        """Capture current 3D camera state (phi, theta, distance)."""
        cam = self.camera
        return {
            "phi": float(getattr(cam, "get_phi", lambda: 0)()),
            "theta": float(getattr(cam, "get_theta", lambda: 0)()),
            "distance": float(getattr(cam, "default_distance", 5)),
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
        self._renderer.open_section(name)
        self._snapshots[name] = self._snapshot_from_registry()
        
        # Capture camera only if changed
        cam_state = self._get_camera_state()
        if self._camera_changed(cam_state):
            self._cameras[name] = cam_state
            self._last_camera_state = cam_state

    def _snapshot_from_registry(self) -> dict[str, int]:
        """Build snapshot as mob_id -> state_ref mapping.

        Only includes root mobjects. VGroup children are NOT included separately
        since they are referenced via the VGroupState's children array.
        """
        snapshot: dict[str, int] = {}

        child_ids: set[int] = set()
        for mob_id, mob in self._renderer.registry.items():
            if mob_id not in self._renderer._active_ids:
                continue
            from manim import VGroup

            if hasattr(mob, "submobjects") and mob.submobjects:
                for child in mob.submobjects:
                    child_ids.add(id(child))

        for mob_id, mob in self._renderer.registry.items():
            if mob_id not in self._renderer._active_ids:
                continue
            if mob_id in child_ids:
                continue
            mob_sid = short_id(mob)
            if mob_sid not in snapshot:
                snapshot[mob_sid] = self._renderer.state_ref_for(mob)
        return snapshot

    def add(self, *mobjects: Mobject) -> None:  # type: ignore[override]
        current = self._renderer._current
        if current is not None:
            for mob in mobjects:
                mob_id = id(mob)
                if mob_id not in self._renderer.registry:
                    self._renderer.register_mobject(mob)
                    current.commands.append(
                        {
                            "cmd": "add",
                            "id": short_id(mob),
                            "state_ref": self._renderer.state_ref_for(mob),
                        }
                    )
        ThreeDScene.add(self, *mobjects)

    def remove(self, *mobjects: Mobject) -> None:  # type: ignore[override]
        current = self._renderer._current
        if current is not None:
            for mob in mobjects:
                mob_id = id(mob)
                if self._renderer.is_active(mob):
                    self._renderer.unregister_mobject(mob)
                    current.commands.append(
                        {
                            "cmd": "remove",
                            "id": short_id(mob),
                        }
                    )
        ThreeDScene.remove(self, *mobjects)
