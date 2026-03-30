from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from manim import Animation, Mobject, Scene, SceneFileWriter

if TYPE_CHECKING:
    pass


@dataclass
class Keyframe:
    frame: int
    mob_id: int
    position: tuple[float, float, float]
    rotation: float
    scale: float


@dataclass
class Segment:
    run_time: float
    animations: list[Animation]
    keyframes: list[Keyframe] = field(default_factory=list)


@dataclass
class Section:
    name: str
    supported: bool = True
    reason: str | None = None
    segments: list[Segment] = field(default_factory=list)


class _DummyCamera:
    use_z_index = False


class _DummyFileWriter:
    def next_section(self, *args, **kwargs) -> None:
        return None


class CaptureRenderer:
    def __init__(
        self,
        fps: int = 10,
        file_writer_class=SceneFileWriter,
        skip_animations: bool = False,
    ):
        self.fps = fps
        self.time = 0.0
        self.skip_animations = skip_animations
        self._current_section: Section | None = None
        self._sections: list[Section] = []
        self._registry: set[Mobject] = set()
        self._updater_mob_ids: set[int] = set()
        self.camera = _DummyCamera()
        self.file_writer = _DummyFileWriter()

    def init_scene(self, scene: Scene) -> None:
        self._scene = scene
        self.time = 0.0
        self._current_section = None
        self._sections = []
        self._registry = set()
        self._updater_mob_ids = set()

    def start_section(self, name: str) -> None:
        section = Section(name=name)
        self._sections.append(section)
        self._current_section = section

    def play(self, scene: Scene, *animations: Animation, **kwargs) -> None:
        from manim import Wait

        if not animations:
            return

        if self._current_section is None:
            self.start_section("default")

        run_time = kwargs.get("run_time", 1.0)

        real_animations = [a for a in animations if not isinstance(a, Wait)]
        if not real_animations:
            return

        segment = Segment(run_time=run_time, animations=list(animations))

        for anim in real_animations:
            try:
                mobs = anim.get_all_mobjects()
            except AttributeError:
                mobs = [anim.mobject]
            for mob in mobs:
                self._registry.add(mob)
                if bool(mob.get_updaters()):
                    self._updater_mob_ids.add(id(mob))

        n_frames = int(run_time * self.fps)
        dt = 1.0 / self.fps

        unsupported_detected = False
        unsupported_reason = None

        for frame_idx in range(n_frames):
            scene.update_mobjects(dt=dt)
            moving_mobjects = scene.get_moving_mobjects(*animations)
            for mob in moving_mobjects:
                mob_id = id(mob)
                if mob_id in self._updater_mob_ids:
                    if getattr(mob, "_dirty_geometry", False):
                        unsupported_detected = True
                        unsupported_reason = (
                            f"geometry-level updater on mob_id {mob_id}"
                        )
                        break
                    kf = Keyframe(
                        frame=frame_idx,
                        mob_id=mob_id,
                        position=tuple(mob.get_center().tolist()),
                        rotation=getattr(mob, "_track_rotation", 0.0),
                        scale=getattr(mob, "_track_scale", 1.0),
                    )
                    segment.keyframes.append(kf)
            if unsupported_detected:
                break

        if unsupported_detected:
            assert self._current_section is not None
            self._current_section.supported = False
            self._current_section.reason = unsupported_reason

        assert self._current_section is not None
        self._current_section.segments.append(segment)
        self.time += run_time

    def update_frame(
        self, scene: Scene, moving_mobjects=None, dt: float | None = None
    ) -> None:
        if dt is None:
            dt = 1.0 / self.fps
        if moving_mobjects is None:
            moving_mobjects = scene.mobjects
        for mob in moving_mobjects:
            if mob.has_updaters:
                mob.update(dt)

    def get_frame(self):
        pass

    def scene_finished(self, scene: Scene) -> None:
        self.time = 0.0

    @property
    def sections(self) -> list[Section]:
        return self._sections

    @property
    def registry(self) -> set[Mobject]:
        return self._registry
