from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manim import Scene

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


def build_snapshot(scene: Scene) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for mob in scene.mobjects:
        for m in mob.get_family():
            mob_id = short_id(m)
            result[mob_id] = {"id": mob_id}
    return result


def reset_id_counter() -> None:
    global _counter, _id_map
    _counter = 0
    _id_map = {}
