from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


Contour = list[list[float]]


def _signed_area_2d(pts: Contour) -> float:
    """Shoelace signed area using anchor points (every 3rd point in 3n+1 format).

    pre: len(pts) > 0
    pre: (len(pts) - 1) % 3 == 0
    post: isinstance(__return__, float)
    """
    anchors = pts[::3]
    n = len(anchors)
    return (
        sum(
            (anchors[(i + 1) % n][0] - anchors[i][0])
            * (anchors[(i + 1) % n][1] + anchors[i][1])
            for i in range(n)
        )
        / 2
    )


def _contour_winding(pts: Contour) -> str:
    """Return 'CW' or 'CCW' for a 3n+1 contour.

    pre: len(pts) > 0
    pre: (len(pts) - 1) % 3 == 0
    post: __return__ in ('CW', 'CCW')
    """
    return "CW" if _signed_area_2d(pts) > 0 else "CCW"


def _validate_contour(pts: Contour, name: str) -> Contour:
    """
    pre: isinstance(pts, list)
    post: (len(__return__) - 1) % 3 == 0
    post: all(len(p) == 3 for p in __return__)
    """
    if (len(pts) - 1) % 3 != 0:
        raise ValueError(f"{name} must have 3n+1 points, got {len(pts)}")
    for p in pts:
        if len(p) != 3:
            raise ValueError(
                f"each point in {name} must be [x, y, z], got length {len(p)}"
            )
    return pts


class VMobjectState(BaseModel):
    """A vectorized mobject with outer contours and optional holes.

    SVG winding convention is enforced by the renderer:
    - contours are CCW (outer filled regions)
    - holes are CW (cutouts, e.g. interior of 'O' or Difference)

    inv: all(_contour_winding(c) == 'CCW' for c in self.contours)
    inv: all(_contour_winding(h) == 'CW'  for h in self.holes)
    """

    model_config = {"extra": "forbid"}

    kind: Literal["VMobject"] = "VMobject"
    contours: list[Contour] = []
    holes: list[Contour] = []
    fill_color: str | None = None
    fill_opacity: float | None = None
    stroke_color: str | None = None
    stroke_width: float | None = None
    stroke_opacity: float | None = None
    z_index: float | None = None
    text: str | None = None
    font_size: float | None = None

    @field_validator("contours")
    @classmethod
    def _validate_contours(cls, v: list[Contour]) -> list[Contour]:
        """
        post: all((len(c) - 1) % 3 == 0 for c in __return__)
        post: all(_contour_winding(c) == 'CCW' for c in __return__)
        """
        for i, contour in enumerate(v):
            _validate_contour(contour, f"contours[{i}]")
            if contour and _contour_winding(contour) != "CCW":
                raise ValueError(f"contours[{i}] must be CCW (outer); got CW")
        return v

    @field_validator("holes")
    @classmethod
    def _validate_holes(cls, v: list[Contour]) -> list[Contour]:
        """
        post: all((len(h) - 1) % 3 == 0 for h in __return__)
        post: all(_contour_winding(h) == 'CW' for h in __return__)
        """
        for i, hole in enumerate(v):
            _validate_contour(hole, f"holes[{i}]")
            if hole and _contour_winding(hole) != "CW":
                raise ValueError(f"holes[{i}] must be CW (inner cutout); got CCW")
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

    kind: Literal["ValueTracker"] = "ValueTracker"
    value: float


MobjectState = (
    VMobjectState | VGroupState | ImageMobjectState | MathTexState | ValueTrackerState
)
