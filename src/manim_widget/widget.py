from __future__ import annotations

from pathlib import Path
from typing import Any

import anywidget
import traitlets
from manim import Mobject, ThreeDScene

from ._camera import _serialize_camera
from .models import (
    AnimateCommand,
    RegisterCommand,
    RemoveCommand,
    SceneData,
    SectionData,
    check_scene_data,
)
from .renderer import CaptureRenderer, SectionRecord
from .states import CameraState


_ESM = Path(__file__).parent / "static" / "index.js"
_CSS = Path(__file__).parent / "static" / "style.css"


def _camera_bg_hex(camera: Any) -> str:
    bg = camera.background_color
    if hasattr(bg, "to_hex"):
        return bg.to_hex()
    return str(bg)


_JS_BUNDLE = _ESM.read_text(encoding="utf-8")
_CSS_BUNDLE = _CSS.read_text(encoding="utf-8")


def _scene_data_to_json(scene_data: SceneData, widget: anywidget.AnyWidget) -> dict:
    return scene_data.model_dump(by_alias=True, exclude_none=True)


def _scene_data_from_json(data: dict, widget: anywidget.AnyWidget) -> SceneData:
    return SceneData.model_validate(data)


def serialize_scene(
    fps: int,
    sections: list[SectionRecord],
    states: list[object],
    frame_width: float = 14.222222222222221,
    frame_height: float = 8.0,
    background_color: str = "#000000",
) -> SceneData:
    sections = _without_implicit_empty_initial_section(sections)
    section_data = [
        SectionData(
            name=s.name,
            snapshot={entry.id: entry.state_ref for entry in s.setup},
            construct=s.commands,
        )
        for s in sections
    ]

    kwargs = dict(
        version=2,
        fps=fps,
        frame_width=frame_width,
        frame_height=frame_height,
        background_color=background_color,
        states=states,
        sections=section_data,
    )

    try:
        scene = SceneData(**kwargs)
    except Exception as exc:
        from .models import _emit_warning

        _emit_warning(exc)
        scene = SceneData.model_construct(**kwargs)

    check_scene_data(scene)
    return scene


def _without_implicit_empty_initial_section(
    sections: list[SectionRecord],
) -> list[SectionRecord]:
    if len(sections) < 2:
        return sections
    first = sections[0]
    if first.name != "initial" or first.commands:
        return sections
    if any(entry.id != "#camera" for entry in first.setup):
        return sections
    return sections[1:]


class ManimWidget(anywidget.AnyWidget, ThreeDScene):
    """Interactive Manim scene viewer widget.

    The control bar background reads the CSS custom property
    ``--mw-controls-bg``, falling back to a Radix Colors slate-8 gray
    (``#b9bbc6``) if unset. Set ``--mw-controls-bg`` on any ancestor element
    in the host page to restyle it.

    ``canvas_width``/``canvas_height`` set the on-screen canvas pixel size
    (independent of ``frame_width``/``frame_height``, which are Manim
    world-unit camera framing). Only one may be set at a time — the pixel
    aspect ratio always matches ``frame_width``/``frame_height``, so the
    other dimension is derived automatically; passing both raises
    ``ValueError``.
    """

    _esm = _JS_BUNDLE
    _css = _CSS_BUNDLE
    data = traitlets.Instance(SceneData).tag(
        sync=True,
        to_json=_scene_data_to_json,
        from_json=_scene_data_from_json,
    )

    def _data_default(self) -> SceneData:
        return SceneData.model_construct(
            version=2,
            fps=10,
            frame_width=14.222222222222221,
            frame_height=8.0,
            states=[],
            sections=[],
        )

    playback_error = traitlets.Unicode("").tag(sync=True)
    is_3d = traitlets.Bool(False).tag(sync=True)
    orbit_controls_up = traitlets.Enum(["x", "y", "z"], default_value="z").tag(
        sync=True
    )
    shared_camera_id = traitlets.Unicode("").tag(sync=True)
    autoplay = traitlets.Bool(True).tag(sync=True)
    show_controls = traitlets.Bool(True).tag(sync=True)
    canvas_width = traitlets.Int(allow_none=True, default_value=None).tag(sync=True)
    canvas_height = traitlets.Int(allow_none=True, default_value=None).tag(sync=True)

    def __init__(
        self,
        fps: int = 10,
        is_3d: bool = False,
        frame_width: float = 14.222222222222221,
        frame_height: float = 8.0,
        background_color: str | None = None,
        orbit_controls_up: str = "z",
        shared_camera: Any = None,
        autoplay: bool = True,
        show_controls: bool = True,
        canvas_width: int | None = None,
        canvas_height: int | None = None,
        **kwargs: Any,
    ) -> None:
        if canvas_width is not None and canvas_height is not None:
            raise ValueError(
                "canvas_width and canvas_height cannot both be set — the canvas "
                "pixel aspect ratio always matches frame_width/frame_height. Set "
                "only one (the other is derived), or adjust frame_width/"
                "frame_height instead."
            )

        self._fps = fps
        self._renderer = CaptureRenderer(fps=fps)

        from manim.camera.three_d_camera import ThreeDCamera as _ThreeDCamera

        _camera_class = getattr(type(self), "camera_class", _ThreeDCamera)

        anywidget.AnyWidget.__init__(self)
        ThreeDScene.__init__(
            self,
            renderer=self._renderer,
            camera_class=_camera_class,
            **kwargs,
        )
        self.is_3d = is_3d
        self.orbit_controls_up = orbit_controls_up
        self.autoplay = autoplay
        self.show_controls = show_controls
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        if shared_camera is not None:
            self.shared_camera_id = shared_camera.camera_id

        self.camera.frame_width = frame_width
        self.camera.frame_height = frame_height
        if background_color is not None:
            from manim.utils.color import ManimColor

            self.camera.background_color = ManimColor(background_color)

        self._renderer.init_scene(self)
        self._renderer.open_section("initial")
        self._flush_setup_to_section()

        _pre_fw = float(self.camera.frame_width)
        _pre_fh = float(self.camera.frame_height)
        _pre_bg: str = _camera_bg_hex(self.camera)

        self.construct()

        self._patch_initial_camera_snapshot()
        self._renderer.flush_staged_adds()
        self._renderer.emit_final_add_animations(self)

        self.data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            states=self._renderer._state_registry.as_list(),
            frame_width=float(self.camera.frame_width),
            frame_height=float(self.camera.frame_height),
            background_color=_camera_bg_hex(self.camera),
        )

        if not is_3d:
            self._warn_if_camera_animated()
        self._warn_if_display_props_changed(_pre_fw, _pre_fh, _pre_bg)

    def _warn_if_camera_animated(self) -> None:
        import warnings

        for section in self.data.sections:
            for cmd in section.animate_commands():
                if any(a.id == "#camera" for a in cmd.animations):
                    warnings.warn(
                        "Camera was animated in a 2D scene. "
                        "Pass is_3d=True when creating the widget to enable 3D camera support.",
                        stacklevel=4,
                    )
                    return
            for cmd in section.updater_commands():
                if any("#camera" in frame for frame in cmd.frames):
                    warnings.warn(
                        "Camera was animated in a 2D scene. "
                        "Pass is_3d=True when creating the widget to enable 3D camera support.",
                        stacklevel=4,
                    )
                    return

    def _warn_if_display_props_changed(
        self, pre_fw: float, pre_fh: float, pre_bg: str
    ) -> None:
        import warnings

        cam = self.camera
        if float(cam.frame_width) != pre_fw or float(cam.frame_height) != pre_fh:
            warnings.warn(
                "frame_width or frame_height was changed during construct(). "
                "Only the initial value is serialized; changes during the scene are ignored.",
                stacklevel=4,
            )
        if _camera_bg_hex(cam) != pre_bg:
            warnings.warn(
                "background_color was changed during construct(). "
                "Only the initial value is serialized; changes during the scene are ignored.",
                stacklevel=4,
            )

    def _patch_initial_camera_snapshot(self) -> None:
        """Re-serialize the camera into the first section's snapshot after construct() has run.

        _flush_setup_to_section() is called before construct(), so any camera
        mutations made at the start of construct() (set_phi, set_theta, etc.)
        are not captured in the initial snapshot.  This method fixes that by
        overwriting the #camera entry with the camera's state as it is now.
        """
        sections = self._renderer.sections
        if not sections:
            return
        initial_setup = sections[0].setup
        cam_entry = next((e for e in initial_setup if e.id == "#camera"), None)
        if cam_entry is None:
            return
        cam = self.camera
        fw = float(getattr(cam, "frame_width", 14.222))
        fh = float(getattr(cam, "frame_height", 8.0))
        cam_pts, cam_focal = _serialize_camera(cam, fw, fh)
        self._renderer._state_registry.overwrite(
            cam_entry.state_ref,
            CameraState(points=cam_pts, focal_distance=cam_focal),
        )

    def _mob_is_animated(self, mob: Mobject) -> bool:
        """Return True if mob was the source or target of any animation during construction."""
        refs = self._renderer.state_refs.get(id(mob), [])
        if len(refs) > 1:
            return True
        mob_id = self._renderer.short_id(mob)
        for section in self._renderer.sections:
            for cmd in section.commands:
                if not isinstance(cmd, AnimateCommand):
                    continue
                for anim in cmd.animations:
                    if anim.id == mob_id and anim.state_ref is not None:
                        return True
        return False

    def sync(self, *mobs: Mobject) -> None:
        """Re-serialize mutated mobjects and push updated data.

        Assumes no add/remove/play calls happened since construction.
        Emits a warning and skips any mob that was animated during construction,
        since overwriting its state_refs would corrupt the recorded animation.
        """
        import warnings

        reg = self._renderer._state_registry
        for mob in mobs:
            refs = self._renderer.state_refs.get(id(mob))
            if not refs:
                warnings.warn(f"mob {mob!r} not found in state registry", stacklevel=2)
                continue
            if self._mob_is_animated(mob):
                warnings.warn(
                    f"mob {mob!r} was animated during construction; sync() ignored",
                    stacklevel=2,
                )
                continue
            state = self._renderer.serialize_mobject(mob, for_snapshot=False)
            for ref in refs:
                reg.overwrite(ref, state)
        self.data = serialize_scene(
            fps=self._fps,
            sections=self._renderer.sections,
            states=list(reg.as_list()),
            frame_width=float(self.camera.frame_width),
            frame_height=float(self.camera.frame_height),
            background_color=_camera_bg_hex(self.camera),
        )

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

        self._renderer.open_section(name)
        self._flush_setup_to_section()

    def _flush_setup_to_section(self) -> None:
        """Populate the current section's setup with register commands for all active mobs.

        For ImageMobjects two register commands are emitted: one carrying only the
        pixel data (kind + source, no points) and one carrying only the position
        (points). This way the expensive PNG blob is stored once in the global
        states bank and position updates in later sections only add a cheap
        points-only entry — never re-encode the image.

        Only root mobjects are included; group children are referenced via their
        parent's GroupState children array.
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
            state_ref = renderer.state_ref_for_register(mob)
            current.setup.append(RegisterCommand(id=mob_sid, state_ref=state_ref))

        cam = self.camera
        fw = float(getattr(cam, "frame_width", 14.222))
        fh = float(getattr(cam, "frame_height", 8.0))
        cam_pts, cam_focal = _serialize_camera(cam, fw, fh)
        cam_ref = renderer._state_registry.insert_raw(
            CameraState(points=cam_pts, focal_distance=cam_focal)
        )
        current.setup.append(RegisterCommand(id="#camera", state_ref=cam_ref))

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
                        RemoveCommand(id=self._renderer.short_id(mob))
                    )
        ThreeDScene.remove(self, *mobjects)

    def add_fixed_in_frame_mobjects(self, *mobjects: Mobject) -> None:  # type: ignore[override]
        for mob in mobjects:
            self._renderer.set_fixed(mob, "frame")
        self.add(*mobjects)

    def add_fixed_orientation_mobjects(self, *mobjects: Mobject, **kwargs: Any) -> None:  # type: ignore[override]
        for mob in mobjects:
            self._renderer.set_fixed(mob, "orientation")
        self.add(*mobjects)

    def remove_fixed_in_frame_mobjects(self, *mobjects: Mobject) -> None:  # type: ignore[override]
        for mob in mobjects:
            self._renderer.set_fixed(mob, None)
        # Re-stage: `add()` always restages regardless of prior registration,
        # and `register` is idempotent on the JS side, so this just flushes
        # an updated (unfixed) state for an id that's already live.
        self.add(*mobjects)

    def remove_fixed_orientation_mobjects(self, *mobjects: Mobject) -> None:  # type: ignore[override]
        for mob in mobjects:
            self._renderer.set_fixed(mob, None)
        self.add(*mobjects)
