from __future__ import annotations

import hashlib
from typing import Any

from manim import Mobject, VMobject

from .renderer import Section, Segment, Keyframe


def _short_id(mob_id: int) -> str:
    return hashlib.md5(str(mob_id).encode()).hexdigest()[:8]


def _kind_name(mob: Mobject) -> str:
    return type(mob).__name__


def _get_children_ids(mob: Mobject) -> list[str]:
    children = []
    for child in mob.get_family():
        if child is not mob:
            children.append(_short_id(id(child)))
    return children


def _get_tex_string(mob: Any) -> str | None:
    if hasattr(mob, "get_tex_string"):
        try:
            return mob.get_tex_string()
        except Exception:
            return None
    return None


def _get_value(mob: Any) -> float | None:
    if hasattr(mob, "get_value"):
        try:
            return float(mob.get_value())
        except Exception:
            return None
    return None


def _build_mobject_entry(mob: Mobject) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": _short_id(id(mob)),
        "kind": _kind_name(mob),
        "children": _get_children_ids(mob),
        "tex_string": None,
        "value": None,
    }
    if hasattr(mob, "get_tex_string"):
        entry["tex_string"] = _get_tex_string(mob)
    if hasattr(mob, "get_value"):
        entry["value"] = _get_value(mob)
    return entry


def _animation_kind(anim: Any) -> str:
    return type(anim).__name__


def _rate_func_name(anim: Any) -> str:
    rf = getattr(anim, "rate_func", None)
    if rf is None:
        return "linear"
    name = getattr(rf, "__name__", str(rf))
    return name


def _build_animation_entry(anim: Any) -> dict[str, Any]:
    try:
        mobjects = anim.get_all_mobjects()
    except AttributeError:
        mobjects = [anim.mobject]
    mob = mobjects[0] if mobjects else None
    return {
        "kind": _animation_kind(anim),
        "mob_id": _short_id(id(mob)) if mob else None,
        "rate_func": _rate_func_name(anim),
    }


def _build_segment_entry(segment: Segment) -> dict[str, Any]:
    return {
        "run_time": segment.run_time,
        "animations": [_build_animation_entry(a) for a in segment.animations],
        "keyframes": [
            {
                "frame": kf.frame,
                "mob_id": _short_id(kf.mob_id),
                "position": list(kf.position),
                "rotation": kf.rotation,
                "scale": kf.scale,
            }
            for kf in segment.keyframes
        ],
    }


def _build_section_entry(section: Section, snapshot: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": section.name,
        "supported": section.supported,
        "snapshot": snapshot,
        "segments": [_build_segment_entry(s) for s in section.segments],
    }
    if not section.supported and section.reason:
        entry["reason"] = section.reason
    return entry


def serialize_scene(
    fps: int,
    mobjects: list[Mobject],
    sections: list[Section],
    snapshots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    registry: dict[str, dict[str, Any]] = {}
    for mob in mobjects:
        mob_id = id(mob)
        short_id = _short_id(mob_id)
        if short_id not in registry:
            registry[short_id] = _build_mobject_entry(mob)
        for child in mob.get_family():
            child_id = id(child)
            child_short = _short_id(child_id)
            if child_short not in registry:
                registry[child_short] = _build_mobject_entry(child)

    return {
        "fps": fps,
        "mobjects": list(registry.values()),
        "sections": [
            _build_section_entry(s, snapshots.get(s.name, {})) for s in sections
        ],
    }
