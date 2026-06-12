from __future__ import annotations

from dataclasses import dataclass

from .states import _signed_area_2d


def _subpath_to_3n1(raw_points) -> list[list[float]]:
    pts: list[list[float]] = []
    for i in range(0, len(raw_points), 4):
        chunk = raw_points[i : i + 4]
        pts.extend(chunk.tolist() if i == 0 else chunk[1:].tolist())
    return pts


def _classify_subpaths(
    subpaths,
) -> tuple[list[list[list[float]]], list[list[list[float]]]]:
    """Classify raw manim subpaths into CCW contours and CW holes.

    Winding convention (SVG even-odd / non-zero fill):
    - The first non-degenerate subpath determines outer_sign.
    - Subpaths with the same sign as outer_sign are outer contours (CCW after flip).
    - Subpaths with the opposite sign are holes (CW after flip).
    - Zero-area (degenerate/collinear) subpaths cannot be holes; they are appended
      to contours as-is. _contour_winding returns 'CCW' for them (area ≤ 0).

    post: all(_contour_winding(c) == 'CCW' for c in __return__[0])
    post: all(_contour_winding(h) == 'CW'  for h in __return__[1])
    post: len(__return__[0]) + len(__return__[1]) <= len(subpaths)
    """
    contours: list[list[list[float]]] = []
    holes: list[list[list[float]]] = []
    outer_sign: float | None = None
    for sp in subpaths:
        if len(sp) == 0:
            continue
        pts = _subpath_to_3n1(sp)
        if not pts:
            continue
        area = _signed_area_2d(pts)
        if area == 0.0:
            contours.append(pts)  # degenerate/collinear: no winding, treat as contour
            continue
        if outer_sign is None:
            outer_sign = area
        is_outer = (area >= 0) == (outer_sign >= 0)
        if is_outer and area > 0:
            pts = pts[::-1]
        elif not is_outer and area < 0:
            pts = pts[::-1]
        if is_outer:
            contours.append(pts)
        else:
            holes.append(pts)
    return contours, holes


@dataclass
class _SubpathChild:
    """Synthetic JS child node for one subpath of a VMobject that also has submobjects.

    Arises when a VMobject carries both its own Bezier points (e.g. Arrow's shaft)
    and actual submobjects (e.g. Arrow's tip).  Gets a stable synthetic mob-id and
    a state_ref allocated on first use.
    """

    parent: object  # the owning VMobject (Mobject, not typed to avoid circular)
    parent_id: str  # short_id of the owning mob, pre-computed
    subpath_idx: int
    subpath: object  # numpy array

    @property
    def mob_id(self) -> str:
        return f"{self.parent_id}_sp{self.subpath_idx}"
