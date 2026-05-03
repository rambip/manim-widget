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

    def _resolve_camera_angle(
        self,
        *,
        key: str,
        getter_name: str,
        attr_name: str,
        default: float,
    ) -> float:
        cam = self.camera
        getter = getattr(cam, getter_name, None)
        method_val = float(getter()) if callable(getter) else default

        raw_attr = getattr(cam, attr_name, method_val)
        attr_val = float(raw_attr) if isinstance(raw_attr, int | float) else method_val

        if abs(attr_val - method_val) <= 1e-12:
            return method_val

        # If method/tracker and raw attr disagree, prefer whichever changed more
        # from the previous serialized state. This captures direct assignments like
        # `self.camera.theta = 0.2` while still preserving animated tracker values.
        if self._last_camera_state is not None and key in self._last_camera_state:
            prev = float(self._last_camera_state[key])
            if abs(attr_val - prev) > abs(method_val - prev) + 1e-12:
                return attr_val
            return method_val

        # First capture fallback: if method value sits at canonical default while
        # attr deviates, treat attr as an explicit override.
        if abs(method_val - default) <= 1e-12 and abs(attr_val - default) > 1e-12:
            return attr_val

        return method_val

    def _resolve_camera_scalar(
        self,
        *,
        key: str,
        canonical: float,
        attr_name: str,
    ) -> float:
        raw_attr = getattr(self.camera, attr_name, canonical)
        attr_val = float(raw_attr) if isinstance(raw_attr, int | float) else canonical

        if abs(attr_val - canonical) <= 1e-12:
            return canonical

        if self._last_camera_state is not None and key in self._last_camera_state:
            prev = float(self._last_camera_state[key])
            if abs(attr_val - prev) > abs(canonical - prev) + 1e-12:
                return attr_val
            return canonical

        return attr_val

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
