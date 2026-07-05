"""Pydantic models for the manim-widget wire format.

These models are the canonical definition of scene_data shape.
They validate structural invariants that JSON Schema cannot express:
- state_ref indices are in-bounds
- animation start < end <= animate command duration
- all cross-field constraints

When validation fails, ManimWidget emits a UserWarning asking the user
to file a bug report.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, model_validator

from .states import (
    CameraState,
    DerivedState,
    GroupState,
    ImageMobjectState,
    MathTexState,
    MobjectState,
    PMobjectState,
    ValueTrackerState,
    VMobjectState,
)

# Re-export state types so external code importing from .models still works.
__all__ = [
    "CameraState",
    "DerivedState",
    "GroupState",
    "ImageMobjectState",
    "MathTexState",
    "MathTexSourceState",
    "MobjectState",
    "PMobjectState",
    "ValueTrackerState",
    "VMobjectState",
    "AnimationDescriptor",
    "RegisterCommand",
    "RemoveCommand",
    "RebindCommand",
    "UpdaterFrame",
    "UpdaterCommand",
    "AnimateCommand",
    "MoveCameraCommand",
    "Command",
    "SectionData",
    "SceneData",
    "check_scene_data",
]

# Alias for the old name used in spec alignment tests.
MathTexSourceState = MathTexState


# ---------------------------------------------------------------------------
# Animation descriptors
# ---------------------------------------------------------------------------


class AnimationDescriptor(BaseModel):
    model_config = {"extra": "allow"}

    kind: str
    id: str | None = None
    ids: list[str] | None = None
    state_ref: int | None = None
    rate_func: str | None = None
    rate_func_params: dict[str, float] | None = None
    params: dict[str, Any] | None = None
    start: float | None = None
    end: float | None = None

    @model_validator(mode="after")
    def check_timestamps(self) -> AnimationDescriptor:
        if self.start is not None and self.end is not None:
            if self.start >= self.end:
                raise ValueError(f"start={self.start} >= end={self.end}")
        return self


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


class RegisterCommand(BaseModel):
    cmd: Literal["register"] = "register"
    id: str
    state_ref: int
    child_ids: list[str] | None = None


class RemoveCommand(BaseModel):
    cmd: Literal["remove"] = "remove"
    id: str


class RebindCommand(BaseModel):
    cmd: Literal["rebind"] = "rebind"
    source_id: str
    target_id: str


class UpdaterFrame(BaseModel):
    model_config = {"extra": "allow"}
    state_ref: int


class UpdaterCommand(BaseModel):
    cmd: Literal["updater"] = "updater"
    duration: float
    frames: list[dict[str, UpdaterFrame]]


class AnimateCommand(BaseModel):
    cmd: Literal["animate"] = "animate"
    duration: float
    animations: list[AnimationDescriptor]

    @model_validator(mode="after")
    def check_animation_bounds(self) -> AnimateCommand:
        for desc in self.animations:
            if desc.end is not None and desc.end > self.duration + 1e-9:
                raise ValueError(
                    f"end={desc.end} exceeds animate command duration={self.duration}"
                )
        return self


class MoveCameraCommand(BaseModel):
    cmd: Literal["move_camera"] = "move_camera"
    state_ref: int


Command = Annotated[
    Union[
        RegisterCommand,
        RemoveCommand,
        RebindCommand,
        AnimateCommand,
        UpdaterCommand,
        MoveCameraCommand,
    ],
    Field(discriminator="cmd"),
]


# ---------------------------------------------------------------------------
# Section and scene
# ---------------------------------------------------------------------------


class SectionData(BaseModel):
    model_config = {"populate_by_name": True}

    name: str
    snapshot: dict[str, int] = Field(default_factory=dict)
    commands: list[Command] = Field(alias="construct", default_factory=list)

    def animate_commands(self) -> list[AnimateCommand]:
        return [c for c in self.commands if isinstance(c, AnimateCommand)]

    def register_commands(self) -> list[RegisterCommand]:
        return [c for c in self.commands if isinstance(c, RegisterCommand)]

    def updater_commands(self) -> list[UpdaterCommand]:
        return [c for c in self.commands if isinstance(c, UpdaterCommand)]


class SceneData(BaseModel):
    version: int
    fps: int
    frame_width: float = 14.222222222222221
    frame_height: float = 8.0
    background_color: str = "#000000"
    states: list[MobjectState] = Field(default_factory=list)
    sections: list[SectionData]

    def camera_states(self) -> list[CameraState]:
        return [s for s in self.states if isinstance(s, CameraState)]

    @model_validator(mode="after")
    def check_state_refs_in_bounds(self) -> SceneData:
        n = len(self.states)

        def _check_ref(ref: int, ctx: str) -> None:
            if not (0 <= ref < n):
                raise ValueError(
                    f"state_ref={ref} out of bounds (global states has {n} entries) in {ctx}"
                )

        for section in self.sections:
            for mob_id, ref in section.snapshot.items():
                _check_ref(ref, f"snapshot[{mob_id!r}]")

            for cmd in section.commands:
                if isinstance(cmd, (RegisterCommand, MoveCameraCommand)):
                    _check_ref(cmd.state_ref, f"{cmd.cmd} command")
                elif isinstance(cmd, AnimateCommand):
                    for anim in cmd.animations:
                        if anim.state_ref is not None:
                            _check_ref(anim.state_ref, f"animation in {cmd.cmd}")
                elif isinstance(cmd, UpdaterCommand):
                    for frame in cmd.frames:
                        for mob_id, mob_frame in frame.items():
                            _check_ref(
                                mob_frame.state_ref, f"updater frame[{mob_id!r}]"
                            )

        return self


_BUG_REPORT_URL = "https://github.com/rambip/manim-widget/issues"

_WARNING_TEMPLATE = """\
Warning: this scene created an invalid specification.
This is a bug with manim-widget, please open a ticket at {url}
with the exact code and the json data (.scene)
Validation Error:
{error}"""


def _emit_warning(error: Exception) -> None:
    import sys

    msg = _WARNING_TEMPLATE.format(url=_BUG_REPORT_URL, error=error)
    print(msg, file=sys.stderr)


def check_scene_data(scene: SceneData) -> None:
    """Warn (but do not block) if scene violates the spec or cross-field invariants.

    Two independent checks:
    - Spec: JSON schema (catches malformed state/command payloads).
    - Invariants: pydantic model_validators (state_ref bounds, anim timestamps).

    Both warn via stderr with a bug-report URL; the scene is always usable.
    """
    import json
    from pathlib import Path

    from jsonschema import ValidationError, validate

    raw = scene.model_dump(by_alias=True, exclude_none=True)

    # Spec check
    try:
        spec_path = Path(__file__).parent.parent.parent / "spec.json"
        schema = json.loads(spec_path.read_text())
        validate(raw, schema)
    except ValidationError as exc:
        _emit_warning(exc)
    except Exception:
        pass  # spec file unavailable in installed package — skip

    # Invariants check
    try:
        SceneData.model_validate(raw)
    except Exception as exc:
        _emit_warning(exc)
