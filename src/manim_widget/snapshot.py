from __future__ import annotations

from typing import TYPE_CHECKING

from manim import ValueTracker
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


def serialize_mobject(mob: Mobject) -> dict[str, object]:
    if isinstance(mob, ValueTracker):
        return {
            "kind": "ValueTracker",
            "value": float(mob.get_value()),
        }

    state: dict[str, object] = {
        "kind": type(mob).__name__,
        "opacity": _opacity_for(mob),
        "position": mob.get_center().tolist(),
    }

    if hasattr(mob, "get_points"):
        points = mob.get_points()
        if len(points) > 0:
            state["points"] = points.tolist()

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
