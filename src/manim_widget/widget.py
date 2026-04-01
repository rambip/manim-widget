from __future__ import annotations

import json
from typing import Any

import traitlets
import anywidget
from manim import Mobject
from manim import Scene

from .renderer import CaptureRenderer
from .serializer import serialize_scene
from .snapshot import build_snapshot, serialize_mobject, short_id


class ManimWidget(anywidget.AnyWidget, Scene):
    scene_data = traitlets.Unicode("").tag(sync=True)

    def __init__(self, fps: int = 10, **kwargs: Any) -> None:
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)
        self._snapshots: dict[str, dict[str, Any]] = {}

        anywidget.AnyWidget.__init__(self)
        Scene.__init__(self, renderer=self._renderer, **kwargs)

        self._renderer.init_scene(self)
        self._renderer.open_section("initial")
        self.construct()
        if self._renderer._current is not None:
            self._snapshots[self._renderer._current.name] = build_snapshot(self)

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
        current = self._renderer._current
        if current is not None:
            self._snapshots[current.name] = self._snapshot_from_registry()
        self._renderer.open_section(name)

    def _snapshot_from_registry(self) -> dict[str, dict[str, Any]]:
        snapshot: dict[str, dict[str, Any]] = {}
        for mob in self._renderer.registry.values():
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
                            "state": serialize_mobject(mob),
                        }
                    )
        Scene.add(self, *mobjects)  # type: ignore[arg-type]

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
        Scene.remove(self, *mobjects)  # type: ignore[arg-type]
