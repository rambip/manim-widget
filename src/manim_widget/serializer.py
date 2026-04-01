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
        "version": 1,
        "fps": fps,
        "sections": [
            {
                "name": s.name,
                "snapshot": snapshots.get(s.name),
                "construct": s.commands,
            }
            for s in sections
        ],
    }
