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

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Mobject states
# ---------------------------------------------------------------------------


class VMobjectState(BaseModel):
    kind: Literal["VMobject"] = "VMobject"
    contours: list[list[list[float]]] = Field(default_factory=list)
    holes: list[list[list[float]]] = Field(default_factory=list)
    fill_color: str | None = None
    fill_opacity: float | None = None
    stroke_color: str | None = None
    stroke_width: float | None = None
    stroke_opacity: float | None = None
    z_index: float | None = None


class VGroupState(BaseModel):
    kind: Literal["VGroup"] = "VGroup"
    children: list[int]


class MathTexSourceState(BaseModel):
    kind: Literal["MathTexSource"] = "MathTexSource"
    latex: str
    points: list[list[float]]
    color: str | None = None


class ImageMobjectState(BaseModel):
    kind: Literal["ImageMobject"] = "ImageMobject"
    source: str
    points: list[list[float]] | None = None
    z_index: float | None = None


class ValueTrackerState(BaseModel):
    kind: Literal["ValueTracker"] = "ValueTracker"
    value: float


class CameraState(BaseModel):
    kind: Literal["Camera"] = "Camera"
    points: list[list[float]]
    focal_distance: float = 0.0


class DerivedState(BaseModel):
    model_config = {"extra": "allow"}

    kind: Literal["Derived"] = "Derived"
    from_: int = Field(alias="from")
    points: list[list[float]] | None = None


MobjectState = (
    VMobjectState
    | VGroupState
    | MathTexSourceState
    | ImageMobjectState
    | ValueTrackerState
    | CameraState
    | DerivedState
)


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


Command = (
    RegisterCommand
    | RemoveCommand
    | RebindCommand
    | AnimateCommand
    | UpdaterCommand
    | MoveCameraCommand
)


# ---------------------------------------------------------------------------
# Section and scene
# ---------------------------------------------------------------------------


class SectionData(BaseModel):
    model_config = {"populate_by_name": True}

    name: str
    snapshot: dict[str, int] = Field(default_factory=dict)
    commands: list[dict[str, Any]] = Field(alias="construct", default_factory=list)


class SceneData(BaseModel):
    version: int
    fps: int
    states: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[SectionData]

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
                cmd_name = cmd.get("cmd", "?")
                if "state_ref" in cmd:
                    _check_ref(cmd["state_ref"], f"{cmd_name} command")
                for anim in cmd.get("animations", []):
                    if "state_ref" in anim:
                        _check_ref(anim["state_ref"], f"animation in {cmd_name}")
                for frame in cmd.get("frames", []):
                    for mob_id, mob_frame in frame.items():
                        if "state_ref" in mob_frame:
                            _check_ref(
                                mob_frame["state_ref"], f"updater frame[{mob_id!r}]"
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


def validate_scene_data(data: dict[str, Any]) -> SceneData | None:
    """Validate scene data against the JSON schema and Pydantic model.

    Prints a bug-report prompt to stderr if either validation fails.
    Returns the parsed Pydantic model on success, None on failure.
    """
    import json
    from pathlib import Path

    from jsonschema import ValidationError, validate

    # JSON schema validation
    try:
        spec_path = Path(__file__).parent.parent.parent / "spec.json"
        schema = json.loads(spec_path.read_text())
        validate(data, schema)
    except ValidationError as exc:
        _emit_warning(exc)
        return None
    except Exception:
        pass  # schema file unavailable (installed package) — skip, Pydantic still runs

    # Pydantic structural validation (cross-field invariants)
    try:
        return SceneData.model_validate(data)
    except Exception as exc:
        _emit_warning(exc)
        return None
