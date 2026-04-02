from __future__ import annotations

from typing import TYPE_CHECKING

from manim import Text, ValueTracker, VGroup
from manim.mobject.types.vectorized_mobject import VMobject

if TYPE_CHECKING:
    from manim import Mobject, Scene

_id_map: dict[int, str] = {}
_counter = 0

_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base62_encode(n: int) -> str:
    if n == 0:
        return _CHARS[0]
    result = []
    while n > 0:
        n, rem = divmod(n, 62)
        result.append(_CHARS[rem])
    return "".join(reversed(result))


def short_id(mob: object) -> str:
    key = id(mob)
    if key not in _id_map:
        global _counter
        _id_map[key] = base62_encode(_counter)
        _counter += 1
    return _id_map[key]


def _opacity_for(mob: Mobject) -> float:
    if isinstance(mob, VMobject):
        return float(mob.get_fill_opacity())
    if hasattr(mob, "opacity"):
        return float(getattr(mob, "opacity"))
    return 1.0


def _color_to_hex(color: object) -> str:
    if hasattr(color, "to_hex"):
        return color.to_hex()
    return str(color)


def serialize_mobject(mob: Mobject) -> dict[str, object]:
    if isinstance(mob, ValueTracker):
        return {
            "kind": "ValueTracker",
            "value": float(mob.get_value()),
        }

    state: dict[str, object] = {
        "kind": type(mob).__name__,
        "opacity": _opacity_for(mob),
    }

    if isinstance(mob, Text):
        state["text"] = mob.text
        state["font_size"] = mob.font_size

    if isinstance(mob, VMobject) and not isinstance(mob, VGroup):
        fill_color = mob.get_fill_color()
        if fill_color:
            state["fill_color"] = _color_to_hex(fill_color)
        fill_opacity = mob.get_fill_opacity()
        if fill_opacity is not None:
            state["fill_opacity"] = fill_opacity
        stroke_color = mob.get_stroke_color()
        if stroke_color:
            state["stroke_color"] = _color_to_hex(stroke_color)
        stroke_width = mob.get_stroke_width()
        if stroke_width:
            state["stroke_width"] = stroke_width
        stroke_opacity = mob.get_stroke_opacity()
        if stroke_opacity is not None:
            state["stroke_opacity"] = stroke_opacity
        z_index = mob.get_z_index()
        if z_index is not None:
            state["z_index"] = z_index

    if hasattr(mob, "get_points"):
        subpaths = mob.get_subpaths()
        if len(subpaths) > 1:
            msg = f"Mobject {type(mob).__name__} has multiple subpaths ({len(subpaths)}); not supported"
            raise ValueError(msg)
        if subpaths:
            raw_points = subpaths[0]
            if len(raw_points) > 0:
                points_3n1: list[list[float]] = []
                for i in range(0, len(raw_points), 4):
                    chunk = raw_points[i : i + 4]
                    if i == 0:
                        points_3n1.extend(chunk.tolist())
                    else:
                        points_3n1.extend(chunk[1:].tolist())
                state["points"] = points_3n1

    if hasattr(mob, "get_family"):
        family = mob.get_family()
        if len(family) > 1:
            state["children"] = [short_id(child) for child in family[1:]]

    return state


def build_snapshot(scene: Scene) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for mob in scene.mobjects:
        for m in mob.get_family():
            mob_id = short_id(m)
            if mob_id not in result:
                result[mob_id] = serialize_mobject(m)
    return result


def reset_id_counter() -> None:
    global _counter, _id_map
    _counter = 0
    _id_map = {}
