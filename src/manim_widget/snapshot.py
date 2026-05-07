from __future__ import annotations

_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base62_encode(n: int) -> str:
    if n == 0:
        return _CHARS[0]
    result = []
    while n > 0:
        n, rem = divmod(n, 62)
        result.append(_CHARS[rem])
    return "".join(reversed(result))


class IdCounter:
    """Instance-based counter for generating stable short IDs for mobjects."""

    def __init__(self) -> None:
        self._id_map: dict[int, str] = {}
        self._counter: int = 0

    def short_id(self, mob: object) -> str:
        key = id(mob)
        if key not in self._id_map:
            self._id_map[key] = base62_encode(self._counter)
            self._counter += 1
        return self._id_map[key]
