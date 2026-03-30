from __future__ import annotations

import hashlib
import json
import traitlets
from pathlib import Path
from typing import cast
from anywidget import AnyWidget
from manim import VMobject, Scene, SceneFileWriter
from manim.scene.section import DefaultSectionType
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
        self.active_mob_ids: set[int] = set()

        AnyWidget.__init__(self)
        Scene.__init__(self, renderer=self._renderer, **kwargs)

        # We may want a cleaner lifecycle later, but this is good enough for now.
        patches.apply_patches()
        try:
            self.renderer.init_scene(self)
            self._pending_snapshot = None
            self._snapshots = {}
            self.next_section("initial")
            self.construct()

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

    def _capture_snapshot(self) -> dict[str, dict]:
        snapshot = {}
        renderer = cast(CaptureRenderer, self.renderer)
        for mob in renderer.registry:
            snapshot[_short_id(id(mob))] = {
                "position": list(mob.get_center()),
                "opacity": mob.get_fill_opacity() if isinstance(mob, VMobject) else 1.0,
                "color": str(mob.get_color())
                if isinstance(mob, VMobject)
                else "#ffffff",
            }
        return snapshot

    def next_section(
        self,
        name: str = "unnamed",
        section_type: str = DefaultSectionType.NORMAL,
        skip_animations: bool = False,
    ) -> None:
        if self._pending_snapshot is not None:
            self._snapshots[self._pending_snapshot["name"]] = self._pending_snapshot[
                "snapshot"
            ]
        self._pending_snapshot = {
            "name": name,
            "snapshot": self._capture_snapshot(),
        }
        cast(CaptureRenderer, self.renderer).start_section(name)
        super().next_section(name, section_type, skip_animations)

    _esm = _JS_BUNDLE
