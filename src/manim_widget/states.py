from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class VMobjectState(BaseModel):
    """A single-path or no-path vectorized mobject."""

    model_config = {"extra": "forbid"}

    kind: Literal["VMobject"] = "VMobject"
    points: list[list[float]] | None = None
    fill_color: str | None = None
    fill_opacity: float | None = None
    stroke_color: str | None = None
    stroke_width: float | None = None
    stroke_opacity: float | None = None
    z_index: float | None = None
    # Text-specific extras (set when mob is a Text instance)
    text: str | None = None
    font_size: float | None = None

    @field_validator("points")
    @classmethod
    def _validate_points(cls, v: list[list[float]] | None) -> list[list[float]] | None:
        """
        pre: v is None or isinstance(v, list)
        post: implies(__return__ is not None and len(__return__) > 0,
                      (len(__return__) - 1) % 3 == 0)
        post: implies(__return__ is not None,
                      forall(__return__, lambda p: len(p) == 3))
        """
        if v is not None and len(v) == 0:
            return None  # empty list is semantically no-points
        if v is not None:
            if (len(v) - 1) % 3 != 0:
                raise ValueError(f"VMobject points must be 3n+1, got {len(v)}")
            for p in v:
                if len(p) != 3:
                    raise ValueError(
                        f"each point must be [x, y, z], got length {len(p)}"
                    )
        return v


class VGroupState(BaseModel):
    """Container of child state-refs; carries no geometry of its own."""

    model_config = {"extra": "forbid"}

    kind: Literal["VGroup"] = "VGroup"
    children: list[int]


class ImageMobjectState(BaseModel):
    model_config = {"extra": "forbid"}

    kind: Literal["ImageMobject"] = "ImageMobject"
    source: str  # data URL
    points: list[list[float]] | None = None
    z_index: float | None = None


class MathTexState(BaseModel):
    model_config = {"extra": "forbid"}

    kind: Literal["MathTexSource"] = "MathTexSource"
    latex: str
    points: list[list[float]]  # 4 corner points
    color: str | None = None


class ValueTrackerState(BaseModel):
    model_config = {"extra": "forbid"}

    value: float


MobjectState = (
    VMobjectState | VGroupState | ImageMobjectState | MathTexState | ValueTrackerState
)
