from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manim import Scene


@dataclass
class _DummyCamera:
    use_z_index: bool = False


@dataclass
class SectionRecord:
    name: str
    commands: list[dict] = field(default_factory=list)


class CaptureRenderer:
    def __init__(self, fps: int) -> None:
        self.fps = fps
        self.registry: dict[int, object] = {}
        self.sections: list[SectionRecord] = []
        self._current: SectionRecord | None = None
        self.camera = _DummyCamera()

    def open_section(self, name: str) -> None:
        self._current = SectionRecord(name=name, commands=[])
        self.sections.append(self._current)

    def init_scene(self, scene: Scene) -> None:
        pass

    def update_frame(
        self,
        scene: Scene,
        moving_mobjects: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        pass

    def scene_finished(self, scene: Scene) -> None:
        pass

    def play(self, scene: Scene, *args: object, **kwargs: object) -> None:
        pass
