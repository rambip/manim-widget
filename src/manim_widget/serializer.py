from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .renderer import SectionRecord


def serialize_scene(
    fps: int,
    sections: list[SectionRecord],
    snapshots: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "version": 2,
        "fps": fps,
        "sections": [
            {
                "name": s.name,
                "snapshot": snapshots.get(s.name, {}),
                "states": s.states,
                "construct": s.commands,
            }
            for s in sections
        ],
    }
