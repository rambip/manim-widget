from __future__ import annotations

import json
from typing import Any

import traitlets
import anywidget
from manim import Scene

from .renderer import CaptureRenderer
from .serializer import serialize_scene
from .snapshot import build_snapshot, short_id


class ManimWidget(anywidget.AnyWidget, Scene):
    scene_data = traitlets.Unicode("").tag(sync=True)

    def __init__(self, fps: int = 10, **kwargs: Any) -> None:
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._pending_snapshot: dict[str, Any] | None = None

        anywidget.AnyWidget.__init__(self)
        Scene.__init__(self, renderer=self._renderer, **kwargs)

        self._renderer.init_scene(self)
        self.next_section("initial")
        self.construct()

        if self._pending_snapshot is not None:
            self._snapshots[self._pending_snapshot["name"]] = self._pending_snapshot[
                "snapshot"
            ]

        data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            snapshots=self._snapshots,
        )
        self.scene_data = json.dumps(data)

    def next_section(self, name: str = "unnamed", **kwargs: Any) -> None:
        if self._pending_snapshot is not None:
            self._snapshots[self._pending_snapshot["name"]] = self._pending_snapshot[
                "snapshot"
            ]
        self._pending_snapshot = {"name": name, "snapshot": build_snapshot(self)}
        self._renderer.open_section(name)

    def add(self, *mobjects: Any) -> None:  # type: ignore[override]
        current = self._renderer._current
        if current is not None:
            for mob in mobjects:
                current.commands.append(
                    {
                        "cmd": "add",
                        "id": short_id(mob),
                        "state": {},
                    }
                )
        Scene.add(self, *mobjects)  # type: ignore[arg-type]

    def remove(self, *mobjects: Any) -> None:  # type: ignore[override]
        current = self._renderer._current
        if current is not None:
            for mob in mobjects:
                current.commands.append(
                    {
                        "cmd": "remove",
                        "id": short_id(mob),
                    }
                )
        Scene.remove(self, *mobjects)  # type: ignore[arg-type]
