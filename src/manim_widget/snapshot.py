from __future__ import annotations

_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

_id_map: dict[int, str] = {}
_counter = 0


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


def reset_id_counter() -> None:
    global _counter, _id_map
    _counter = 0
    _id_map = {}
