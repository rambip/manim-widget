from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anywidget
import traitlets
from manim import Mobject, Scene

from .renderer import CaptureRenderer
from .serializer import serialize_scene
from .snapshot import serialize_mobject, short_id

_ESM = Path(__file__).parent / "static" / "index.js"
_JS_BUNDLE = _ESM.read_text()


class ManimWidget(anywidget.AnyWidget, Scene):
    _esm = _JS_BUNDLE
    scene_data = traitlets.Unicode("").tag(sync=True)

    def __init__(self, fps: int = 10, **kwargs: Any) -> None:
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)
        self._snapshots: dict[str, dict[str, Any]] = {}

        anywidget.AnyWidget.__init__(self)
        Scene.__init__(self, renderer=self._renderer, **kwargs)

        self._renderer.init_scene(self)
        self._renderer.open_section("initial")
        self._snapshots["initial"] = self._snapshot_from_registry()
        self.construct()

        data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            snapshots=self._snapshots,
        )
        self.scene_data = json.dumps(data)

    def next_section(
        self,
        name: str = "unnamed",
        section_type: str = "normal",
        skip_animations: bool = False,
    ) -> None:
        del section_type, skip_animations
        self._renderer.open_section(name)
        self._snapshots[name] = self._snapshot_from_registry()

    def _snapshot_from_registry(self) -> dict[str, dict[str, Any]]:
        snapshot: dict[str, dict[str, Any]] = {}
        for mob_id, mob in self._renderer.registry.items():
            if mob_id not in self._renderer._active_ids:
                continue
            mob_sid = short_id(mob)
            if mob_sid not in snapshot:
                snapshot[mob_sid] = serialize_mobject(mob)
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
        Scene.add(self, *mobjects)

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
        Scene.remove(self, *mobjects)
