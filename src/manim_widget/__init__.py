from __future__ import annotations

import hashlib
import json
import traitlets
from pathlib import Path
from typing import cast
from anywidget import AnyWidget
from manim import Scene, SceneFileWriter
from manim.typing import PixelArray

from . import patches
from .renderer import CaptureRenderer
from .serializer import serialize_scene


def _short_id(mob_id: int) -> str:
    return hashlib.md5(str(mob_id).encode()).hexdigest()[:8]


_JS_BUNDLE = (Path(__file__).parent / "static" / "index.js").read_text()


class CustomRenderer:
    def __init__(self, file_writer_class=SceneFileWriter, skip_animations=False):
        self.time = 0
        self._file_writer_class = file_writer_class
        self._skip_animations = skip_animations

    def init_scene(self, scene: Scene) -> None:
        pass

    def play(self, scene: Scene, *animations, **kwargs) -> None:
        print(animations)

    def update_frame(self, scene: Scene, moving_mobjects=None) -> None:
        pass

    def get_frame(self) -> PixelArray:
        pass  # type: ignore[return-value]

    def scene_finished(self, scene: Scene) -> None:
        pass


class ManimWidget(AnyWidget, Scene):
    scene_data = traitlets.Unicode("").tag(sync=True)

    def __init__(self, fps: int = 10, **kwargs):
        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)
        self._snapshots: dict[str, dict] = {}
        self._pending_snapshot: dict | None = None
        self._construct_fn: callable | None = None

        AnyWidget.__init__(self)
        Scene.__init__(self, renderer=self._renderer, **kwargs)

    def set_construct_fn(self, fn: callable) -> None:
        self._construct_fn = fn

    def _on_next_section(self, name: str) -> None:
        if self._pending_snapshot is not None:
            self._snapshots[self._pending_snapshot["name"]] = self._pending_snapshot[
                "snapshot"
            ]
        self._pending_snapshot = {
            "name": name,
            "snapshot": self._capture_snapshot(),
        }

    def _capture_snapshot(self) -> dict[str, dict]:
        snapshot = {}
        renderer = cast(CaptureRenderer, self.renderer)
        for mob_id in renderer.registry:
            for mob in self.mobjects:
                for m in mob.get_family():
                    if id(m) == mob_id:
                        snapshot[_short_id(mob_id)] = {
                            "position": list(m.get_center()),
                            "opacity": m.get_fill_opacity()
                            if hasattr(m, "get_fill_opacity")
                            else 1.0,
                            "color": str(m.get_color())
                            if hasattr(m, "get_color")
                            else "#ffffff",
                        }
        return snapshot

    def construct(self) -> None:
        if self._construct_fn is None:
            return

        patches.apply_patches()
        try:
            self.renderer.init_scene(self)
            self._pending_snapshot = None
            self._snapshots = {}
            self._on_next_section("initial")

            self._construct_fn(self)

            if self._pending_snapshot is not None:
                self._snapshots[self._pending_snapshot["name"]] = (
                    self._pending_snapshot["snapshot"]
                )
                self._pending_snapshot = None

            all_mobjects = list(cast(CaptureRenderer, self.renderer).registry)
            data = serialize_scene(
                fps=self._fps,
                mobjects=all_mobjects,
                sections=cast(CaptureRenderer, self.renderer).sections,
                snapshots=self._snapshots,
            )
            self.scene_data = json.dumps(data)
        finally:
            patches.remove_patches()

    _esm = _JS_BUNDLE
