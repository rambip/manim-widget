from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from manim import (
    CyclicReplace,
    FadeOut,
    GrowArrow,
    ReplacementTransform,
    Rotate,
    ScaleInPlace,
    Scene,
    Swap,
    Text,
    ValueTracker,
    VGroup,
)
from manim.animation.animation import Animation
from manim.animation.composition import AnimationGroup
from manim.mobject.mobject import Mobject
from manim.mobject.types.image_mobject import AbstractImageMobject
from manim.mobject.types.vectorized_mobject import VMobject

from .anim_compat import force_end_state
from .registry import StateRegistry
from .snapshot import IdCounter
from .states import (
    _signed_area_2d,
    ImageMobjectState,
    MathTexState,
    MobjectState,
    VMobjectState,
    VGroupState,
    ValueTrackerState,
)
from .tex_patch import PatchedMathTex


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


def _needs_camera_frame_loop(scene: Scene, animations: list) -> bool:
    """Return True when the per-frame camera-capture loop must run.

    The loop is the only reason _play_animate_path ticks through time at all
    (mobject updaters are handled by _play_data_path). It is safe to skip when:

    - The camera has no updaters of its own.
    - No animation in the batch directly targets the camera object.

    This is 2D/3D-agnostic: a 3D scene whose camera is static during a given
    play() call gains the same speedup as a 2D scene.

    NOTE: camera animations (self.play(self.camera.animate.set_phi(...))) are
    not yet a first-class supported feature — they would need a dedicated
    command type in the wire format. The check below handles the case where
    they appear anyway so the frame loop still runs rather than silently
    dropping camera movement.
    """
    camera = getattr(scene, "camera", None)
    if camera is None:
        return False
    if getattr(camera, "updaters", []):
        return True
    if any(getattr(a, "mobject", None) is camera for a in animations):
        return True
    return False


def _compute_camera_state(cam) -> dict[str, float]:
    """Extract camera state including computed FOV from Manim camera."""
    distance = float(getattr(cam, "default_distance", 5))
    frame_height = float(getattr(cam, "frame_height", 8))
    fov_deg = 2 * math.degrees(math.atan(frame_height / (2 * distance)))
    return {
        "phi": float(cam.get_phi()),
        "theta": float(cam.get_theta()),
        "distance": distance,
        "fov": fov_deg,
    }


@dataclass
class SectionRecord:
    name: str
    commands: list[dict] = field(default_factory=list)
    # setup: list of {cmd:"register", id:..., state_ref:...} emitted for snapshot mobs
    setup: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class PixelContent:
    """Immutable, hashable container for a numpy pixel array."""

    data: bytes
    shape: tuple[int, ...]
    dtype: str

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "PixelContent":
        return cls(data=arr.tobytes(), shape=tuple(arr.shape), dtype=str(arr.dtype))

    def to_array(self) -> np.ndarray:
        return np.frombuffer(self.data, dtype=self.dtype).reshape(self.shape)


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


class CaptureRenderer:
    def __init__(self, fps: int) -> None:
        self.fps = fps
        self.time = 0.0
        self.num_plays = 0
        self.skip_animations = False
        self.static_image = None
        self._scene: Scene | None = None  # Set via init_scene
        self._camera = None  # Will be set to scene's existing camera in init_scene
        self.registry: dict[int, Mobject] = {}
        self._active_ids: set[int] = set()
        self.sections: list[SectionRecord] = []
        self._current: SectionRecord | None = None
        # Global content-addressed state bank shared across all sections.
        self._state_registry: StateRegistry[Mobject, PixelContent, tuple, dict] = (
            StateRegistry(
                extract_content=self._extract_content,
                extract_state=self._extract_state,
                make_from_content=self._make_from_content,
                make_from_state=self._make_from_state,
            )
        )
        # Staging bucket for pre-play add() calls in current section.
        # Keyed by short_id; repeated add() of same object overwrites prior state.
        self._staged_adds: dict[str, Mobject] = {}
        # Ignore internal scene.add() calls during animation setup to avoid
        # duplicate staged register commands from introducer internals.
        self._suppress_stage_adds: bool = False
        # Runtime bookkeeping: whether a mobject has ever been introduced via
        # an animation introducer (Create/FadeIn/Write/GrowFromCenter/Add...).
        # Keyed by python object identity.
        self._introduced_by_animation: dict[int, bool] = {}
        self._id_counter = IdCounter()
        # id(mob) → list of state_refs assigned; updated by state_ref_for.
        self.state_refs: dict[int, list[int]] = {}

    def short_id(self, mob: object) -> str:
        return self._id_counter.short_id(mob)

    @property
    def camera(self):
        """Return our cached camera reference."""
        return self._camera

    @camera.setter
    def camera(self, value):
        """Allow setting the camera directly."""
        self._camera = value

    def init_scene(self, scene: Scene) -> None:
        self._scene = scene
        self.time = 0.0
        self.num_plays = 0

        # Create camera if not already set on renderer
        # This ensures scene.camera is available after init_scene
        if self._camera is None:
            from manim.camera.three_d_camera import ThreeDCamera

            camera_class = getattr(scene, "camera_class", None) or ThreeDCamera
            self._camera = camera_class()

    def open_section(self, name: str) -> None:
        self._current = SectionRecord(name=name, commands=[])
        self.sections.append(self._current)
        self._staged_adds = {}

    # ------------------------------------------------------------------
    # Registry extract / make functions (injected at construction)
    # ------------------------------------------------------------------

    def _extract_content(self, mob: Mobject) -> PixelContent | None:
        if isinstance(mob, AbstractImageMobject):
            return PixelContent.from_array(mob.get_pixel_array())
        return None

    def _extract_state(self, mob: Mobject) -> tuple | None:
        if isinstance(mob, ValueTracker):
            return ("vt", float(mob.get_value()))

        if isinstance(mob, PatchedMathTex):
            raw = (
                mob.points.tolist()
                if hasattr(mob.points, "tolist")
                else list(mob.points)
            )
            color_hex = self._color_to_hex(mob.color) if mob.color is not None else None
            return ("mathtex", mob.tex_string, tuple(tuple(p) for p in raw), color_hex)

        if isinstance(mob, AbstractImageMobject):
            content = self._extract_content(mob)
            content_ref = self._state_registry.get_content_ref(content)
            if content_ref is None:
                return (
                    None  # content not yet registered; insert() registers content first
                )
            raw = (
                mob.points.tolist()
                if hasattr(mob.points, "tolist")
                else list(mob.points)
            )
            return (
                ("img", content_ref, tuple(tuple(p) for p in raw))
                if len(raw) == 4
                else None
            )

        if hasattr(mob, "submobjects") and mob.submobjects:
            # If the mob also has its own subpaths (e.g. Arrow shaft), fall through
            # to _serialize_vgroup so both shaft and tip children are captured.
            if isinstance(mob, VMobject) and mob.get_subpaths():
                return None
            child_refs = []
            for child in mob.submobjects:
                ref = self._state_registry.get(child)
                if ref is None:
                    return None  # children not yet registered
                child_refs.append(ref)
            return ("vgroup", tuple(child_refs))

        if isinstance(mob, VMobject) and not mob.submobjects:
            subpaths = mob.get_subpaths()
            contours, holes = _classify_subpaths(subpaths)
            fill_color = mob.get_fill_color()
            stroke_color = mob.get_stroke_color()
            return (
                "vmob",
                tuple(tuple(tuple(p) for p in c) for c in contours),
                tuple(tuple(tuple(p) for p in h) for h in holes),
                self._color_to_hex(fill_color) if fill_color else None,
                self._color_to_hex(stroke_color) if stroke_color else None,
                mob.get_fill_opacity(),
                mob.get_stroke_width(),
                mob.get_stroke_opacity(),
                getattr(mob, "z_index", None),
            )

        return None

    def _make_from_content(self, content: PixelContent) -> dict:
        return {
            "kind": "ImageMobject",
            "source": self._image_source_from_pixel_array(content.to_array()),
        }

    def _make_from_state(self, state: tuple) -> dict:
        kind = state[0]
        if kind == "vt":
            return ValueTrackerState(value=state[1]).model_dump(exclude_none=True)
        if kind == "mathtex":
            _, latex, pts, color = state
            return MathTexState(
                latex=latex,
                points=[[float(p[0]), float(p[1]), float(p[2])] for p in pts],
                color=color,
            ).model_dump(exclude_none=True)
        if kind == "img":
            _, content_ref, corners = state
            return {
                "kind": "Derived",
                "from": content_ref,
                "points": [list(p) for p in corners],
            }
        if kind == "vgroup":
            _, child_refs = state
            return VGroupState(children=list(child_refs)).model_dump(exclude_none=True)
        if kind == "vmob":
            (
                _,
                contours,
                holes,
                fill_color,
                stroke_color,
                fill_opacity,
                stroke_width,
                stroke_opacity,
                z_index,
            ) = state
            return VMobjectState(
                contours=[[list(p) for p in c] for c in contours],
                holes=[[list(p) for p in h] for h in holes],
                fill_color=fill_color,
                stroke_color=stroke_color,
                fill_opacity=fill_opacity,
                stroke_width=stroke_width,
                stroke_opacity=stroke_opacity,
                z_index=z_index,
            ).model_dump(exclude_none=True)
        msg = f"Unknown state kind: {kind!r}"
        raise ValueError(msg)

    # ------------------------------------------------------------------
    # State-ref helpers
    # ------------------------------------------------------------------

    def _ensure_image_refs(self, mob: AbstractImageMobject) -> tuple[int, int | None]:
        """Ensure image content and current-position derived state are registered.

        Content (pixel data) is registered once.  The derived state
        ``{from: content_ref, points: corners}`` is keyed by ``(content_ref, corners)``
        so each unique position gets its own entry and identical positions are reused.
        """
        reg = self._state_registry
        if reg.get(mob) is None:
            # First time this content is seen: insert() registers content then derived state.
            reg.insert(mob)
        else:
            # Content already registered; ensure derived state for THIS position.
            state = self._extract_state(
                mob
            )  # ("img", content_ref, corners) — content_ref in bank ✓
            if state is not None:
                reg.ensure_addon(state)
        return reg.get(mob), reg.get_addon(mob)

    def _js_children(self, mob: Mobject) -> list:
        """Single source of truth for what children a mob exposes to the JS player.

        Returns an empty list for leaf mobs (no JS children).
        For groups / mobs with children: actual submobjects.
        For VMobjects that carry both own subpaths AND submobjects (e.g. Arrow):
            _SubpathChild entries first (one per non-empty subpath), then actual submobjects.

        All consumers — register commands, remove commands, VGroupState serialisation —
        must derive their child list exclusively from this method.
        """
        submobs = getattr(mob, "submobjects", None) or []
        if not submobs:
            return list(submobs)  # pure leaf or pure VGroup with no children

        # VMobject with own Bezier points AND actual children → mixed node.
        if isinstance(mob, VMobject) and not isinstance(mob, VGroup):
            own_subpaths = [sp for sp in mob.get_subpaths() if len(sp) > 0]
            if own_subpaths:
                parent_id = self.short_id(mob)
                result: list = [
                    _SubpathChild(
                        parent=mob, parent_id=parent_id, subpath_idx=i, subpath=sp
                    )
                    for i, sp in enumerate(own_subpaths)
                ]
                result.extend(submobs)
                return result

        return list(submobs)

    def _grow_arrow_register_commands(
        self, mob: Mobject, anim: GrowArrow
    ) -> list[dict]:
        """Register commands for GrowArrow: children get collapsed starting states,
        parent gets a virtual collapsed VGroupState. The paired Transform descriptor
        then animates from this collapsed state to the final state."""
        starting = anim.create_starting_mobject()
        actual_children = self._js_children(mob)
        starting_children = self._js_children(starting)

        child_cmds: list[dict] = []
        child_ids: list[str] = []
        collapsed_child_refs: list[int] = []

        for actual, start in zip(actual_children, starting_children):
            if isinstance(actual, _SubpathChild):
                # Reuse actual mob's parent/id but swap in the collapsed subpath.
                collapsed_sc = _SubpathChild(
                    parent=actual.parent,
                    parent_id=actual.parent_id,
                    subpath_idx=actual.subpath_idx,
                    subpath=start.subpath,
                )
                ref = self._subpath_child_state_ref(collapsed_sc)
                child_cmds.append(
                    {"cmd": "register", "id": actual.mob_id, "state_ref": ref}
                )
                child_ids.append(actual.mob_id)
            else:
                # VMobject submob: find corresponding submob in starting mob by index.
                idx = mob.submobjects.index(actual)
                start_submob = starting.submobjects[idx]
                ref = self.state_ref_for(start_submob)
                mob_id = self.short_id(actual)
                child_cmds.append({"cmd": "register", "id": mob_id, "state_ref": ref})
                child_ids.append(mob_id)
            collapsed_child_refs.append(ref)

        collapsed_vgroup_ref = self._state_registry.insert_raw(
            VGroupState(children=collapsed_child_refs).model_dump(exclude_none=True)
        )
        return [
            *child_cmds,
            {
                "cmd": "register",
                "id": self.short_id(mob),
                "state_ref": collapsed_vgroup_ref,
                "child_ids": child_ids,
            },
        ]

    def _mob_register_commands(self, mob: Mobject) -> list[dict]:
        """Return register command(s) for mob and all its JS children."""
        js_children = self._js_children(mob)
        if not js_children:
            return [
                {
                    "cmd": "register",
                    "id": self.short_id(mob),
                    "state_ref": self.state_ref_for(mob),
                }
            ]

        cmds: list[dict] = []
        child_ids: list[str] = []
        for child in js_children:
            if isinstance(child, _SubpathChild):
                state_ref = self._subpath_child_state_ref(child)
                cmds.append(
                    {"cmd": "register", "id": child.mob_id, "state_ref": state_ref}
                )
                child_ids.append(child.mob_id)
            else:
                cmds.extend(self._mob_register_commands(child))
                child_ids.append(self.short_id(child))
        cmds.append(
            {
                "cmd": "register",
                "id": self.short_id(mob),
                "state_ref": self.state_ref_for(mob),
                "child_ids": child_ids,
            }
        )
        return cmds

    def _mob_remove_commands(self, mob: Mobject) -> list[dict]:
        """Return remove command(s) for mob and all its JS children (deepest first)."""
        js_children = self._js_children(mob)
        cmds: list[dict] = []
        for child in js_children:
            if isinstance(child, _SubpathChild):
                cmds.append({"cmd": "remove", "id": child.mob_id})
            else:
                cmds.extend(self._mob_remove_commands(child))
        cmds.append({"cmd": "remove", "id": self.short_id(mob)})
        return cmds

    def _subpath_child_state_ref(self, child: _SubpathChild) -> int:
        """Allocate a state_ref for a synthetic subpath child."""
        style = self._vmob_style(child.parent)
        points_3n1 = _subpath_to_3n1(child.subpath)
        if not points_3n1:
            return self._state_registry.insert_raw(
                {"kind": "VMobject", "contours": [], "holes": []}
            )
        if _signed_area_2d(points_3n1) > 0:
            points_3n1 = points_3n1[::-1]
        subpath_state = VMobjectState(contours=[points_3n1], **style)
        return self._state_registry.insert_raw(
            subpath_state.model_dump(exclude_none=True)
        )

    def state_ref_for(self, mob: Mobject) -> int:
        """Return the global state-bank index for mob's current state.

        For images returns the derived-state ref ``{from: content_ref, points: corners}``.
        Recurses into children first so VGroup extract_state can look them up.
        Multi-subpath VMobjects are serialized via insert_raw (no dedup).

        post: 0 <= __return__ < len(self._state_registry)
        """
        if isinstance(mob, AbstractImageMobject):
            _, addon_ref = self._ensure_image_refs(mob)
            # addon_ref is the derived state {from, points}; fall back to content_ref if None
            if addon_ref is not None:
                self.state_refs.setdefault(id(mob), []).append(addon_ref)
                return addon_ref
            ref = self._state_registry.get(mob)
            self.state_refs.setdefault(id(mob), []).append(ref)
            return ref

        # Recurse into children first so VGroup extract_state can look them up.
        if hasattr(mob, "submobjects") and mob.submobjects:
            for child in mob.submobjects:
                self.state_ref_for(child)

        # Try typed state bank (handles simple VMobjects and VGroups with Mobject children).
        ref = self._state_registry.get(mob)
        if ref is not None:
            self.state_refs.setdefault(id(mob), []).append(ref)
            return ref
        state = self._extract_state(mob)
        if state is not None:
            main_ref, _ = self._state_registry.insert(mob)
            self.state_refs.setdefault(id(mob), []).append(main_ref)
            return main_ref

        # Mixed (own subpaths + submobjects) VMobject (e.g. Arrow).
        if isinstance(mob, VMobject):
            subpaths = mob.get_subpaths()
            if subpaths:
                js_ch = self._js_children(mob)
                if js_ch:
                    child_refs: list[int] = []
                    for jsc in js_ch:
                        if isinstance(jsc, _SubpathChild):
                            child_refs.append(self._subpath_child_state_ref(jsc))
                        else:
                            child_refs.append(self.state_ref_for(jsc))
                    vgroup_state = VGroupState(children=child_refs)
                    ref = self._state_registry.insert_raw(
                        vgroup_state.model_dump(exclude_none=True)
                    )
                    self.state_refs.setdefault(id(mob), []).append(ref)
                    return ref
            # Empty VMobject with no submobjects: treat as invisible.
            if not mob.submobjects:
                style = self._vmob_style(mob)
                ref = self._state_registry.insert_raw(
                    {"kind": "VMobject", "contours": [], "holes": [], **style}
                )
                self.state_refs.setdefault(id(mob), []).append(ref)
                return ref

        # VMobject with submobjects but no own subpaths (e.g. MarkupText, SVGMobject)
        # whose children may have been registered via insert_raw and are invisible to
        # _state_registry.get().  Build VGroupState from identity-keyed state_refs.
        if hasattr(mob, "submobjects") and mob.submobjects:
            child_refs = []
            for child in mob.submobjects:
                refs = self.state_refs.get(id(child))
                if refs is None:
                    self.state_ref_for(child)
                    refs = self.state_refs.get(id(child))
                if refs:
                    child_refs.append(refs[-1])
            if child_refs:
                vgroup_state = VGroupState(children=child_refs)
                ref = self._state_registry.insert_raw(
                    vgroup_state.model_dump(exclude_none=True)
                )
                self.state_refs.setdefault(id(mob), []).append(ref)
                return ref

        msg = f"Cannot compute state_ref for {mob!r}"
        raise ValueError(msg)

    def _vmob_style(self, mob: VMobject) -> dict[str, object]:
        """Extract fill/stroke style dict from a VMobject (not VGroup)."""
        if isinstance(mob, VGroup):
            return {}
        style: dict[str, object] = {}
        fill_color = mob.get_fill_color()
        if fill_color:
            style["fill_color"] = self._color_to_hex(fill_color)
        fill_opacity = mob.get_fill_opacity()
        if fill_opacity is not None:
            style["fill_opacity"] = fill_opacity
        stroke_color = mob.get_stroke_color()
        if stroke_color:
            style["stroke_color"] = self._color_to_hex(stroke_color)
        stroke_width = mob.get_stroke_width()
        if stroke_width:
            style["stroke_width"] = stroke_width
        stroke_opacity = mob.get_stroke_opacity()
        if stroke_opacity is not None:
            style["stroke_opacity"] = stroke_opacity
        z_index = getattr(mob, "z_index", None)
        if z_index is not None:
            style["z_index"] = z_index
        return style

    def _intern_state(self, state: MobjectState) -> int:
        """Insert a typed state into the global state bank and return its ref."""
        return self._state_registry.insert_raw(state.model_dump(exclude_none=True))

    def serialize_mobject(self, mob: Mobject, *, for_snapshot: bool) -> MobjectState:
        """Serialize a single mobject to a typed state object.

        post: implies(not isinstance(mob, ValueTracker), hasattr(__return__, "kind"))
        post: implies(isinstance(__return__, VGroupState),
                      forall(__return__.children, lambda r: isinstance(r, int)))
        """
        if isinstance(mob, ValueTracker):
            return ValueTrackerState(value=float(mob.get_value()))

        if isinstance(mob, PatchedMathTex):
            raw = (
                mob.points.tolist()
                if hasattr(mob.points, "tolist")
                else list(mob.points)
            )
            pts = [[float(p[0]), float(p[1]), float(p[2])] for p in raw]
            return MathTexState(
                latex=mob.tex_string,
                points=pts,
                color=self._color_to_hex(mob.color) if mob.color is not None else None,
            )

        if isinstance(mob, AbstractImageMobject):
            raw = (
                mob.points.tolist()
                if hasattr(mob.points, "tolist")
                else list(mob.points)
            )
            # Ensure pixel data is registered; retrieve cached source data-URI.
            if self._state_registry.get(mob) is None:
                self._state_registry.insert(mob)
            content_ref = self._state_registry.get(mob)
            source = self._state_registry.get_by_id(content_ref)["source"]
            return ImageMobjectState(
                source=source,
                points=raw if len(raw) == 4 else None,
                z_index=getattr(mob, "z_index", None),
            )

        # Collect VMobject styling shared by single-path and vgroup paths.
        style: dict[str, object] = {}
        if isinstance(mob, VMobject) and not isinstance(mob, VGroup):
            fill_color = mob.get_fill_color()
            if fill_color:
                style["fill_color"] = self._color_to_hex(fill_color)
            fill_opacity = mob.get_fill_opacity()
            if fill_opacity is not None:
                style["fill_opacity"] = fill_opacity
            stroke_color = mob.get_stroke_color()
            if stroke_color:
                style["stroke_color"] = self._color_to_hex(stroke_color)
            stroke_width = mob.get_stroke_width()
            if stroke_width:
                style["stroke_width"] = stroke_width
            stroke_opacity = mob.get_stroke_opacity()
            if stroke_opacity is not None:
                style["stroke_opacity"] = stroke_opacity
            z_index = getattr(mob, "z_index", None)
            if z_index is not None:
                style["z_index"] = z_index

        js_children = self._js_children(mob)

        if isinstance(mob, VMobject):
            subpaths = mob.get_subpaths()
            if js_children:
                # Mixed (own subpaths + submobs): emit VGroupState whose children
                # match exactly what _js_children returned.
                child_refs: list[int] = []
                for jsc in js_children:
                    if isinstance(jsc, _SubpathChild):
                        child_refs.append(self._subpath_child_state_ref(jsc))
                    else:
                        child_refs.append(self.state_ref_for(jsc))
                return VGroupState(children=child_refs)
            if subpaths:
                contours, holes = _classify_subpaths(subpaths)
                style["contours"] = contours
                style["holes"] = holes

        if js_children:
            return VGroupState(
                children=[self.state_ref_for(child) for child in mob.submobjects]
            )

        text_extras: dict[str, object] = {}
        if isinstance(mob, Text):
            text_extras["text"] = mob.text
            text_extras["font_size"] = mob.font_size

        return VMobjectState(**style, **text_extras)

    def update_frame(
        self,
        scene: Scene,
        moving_mobjects: list[object] | None = None,
        **kwargs: object,
    ) -> None:
        pass

    def scene_finished(self, scene: Scene) -> None:
        pass

    def register_mobject(self, mob: Mobject) -> None:
        for member in mob.get_family():
            member_id = id(member)
            self.registry[member_id] = member
            self._active_ids.add(member_id)
            self._introduced_by_animation.setdefault(member_id, False)

    def unregister_mobject(self, mob: Mobject) -> None:
        for member in mob.get_family():
            member_id = id(member)
            self._active_ids.discard(member_id)
            self._introduced_by_animation.pop(member_id, None)

    def is_active(self, mob: Mobject) -> bool:
        return id(mob) in self._active_ids

    def flush_staged_adds(self) -> None:
        """Emit staged pre-play register commands into the current section.

        Staging is section-local and deduplicated by mobject id (last add wins).
        """
        current = self._current
        if current is None or not self._staged_adds:
            return
        for mob in self._staged_adds.values():
            current.commands.extend(self._mob_register_commands(mob))
        self._staged_adds = {}

    def emit_final_add_animations(self, scene: Scene) -> None:
        """Emit a terminal animate command with Add descriptors if needed.

        This covers sections that only call ``self.add(...)`` and never call
        ``play(...)``. In that case we still need an animate batch so the JS
        player can apply the semantic Add operation.
        """
        current = self._current
        if current is None:
            return

        def _is_supported(mob: Mobject) -> bool:
            if isinstance(mob, VMobject | ValueTracker | AbstractImageMobject):
                return True
            return bool(hasattr(mob, "submobjects") and mob.submobjects)

        # Only emit a terminal Add batch for sections with no playback commands.
        # If section already has animate/updater entries, Add injection should
        # happen during play-path handling instead.
        if any(cmd.get("cmd") in {"animate", "updater"} for cmd in current.commands):
            return

        add_animations: list[dict[str, str]] = []
        for mob in scene.mobjects:
            if not _is_supported(mob):
                continue
            if not self.is_active(mob):
                continue
            if self._introduced_by_animation.get(id(mob), False):
                continue
            add_animations.append({"kind": "Add", "id": self.short_id(mob)})
            self._introduced_by_animation[id(mob)] = True

        if add_animations:
            current.commands.append(
                {
                    "cmd": "animate",
                    "duration": 0,
                    "animations": add_animations,
                }
            )

    def stage_add(self, mob: Mobject) -> None:
        """Stage an add command until play()/section-finalization flushes it."""
        self._staged_adds[self.short_id(mob)] = mob

    def play(self, scene: Scene, *args: Any, **kwargs: Any) -> None:
        self.flush_staged_adds()

        animations = scene.compile_animations(*args, **kwargs)
        if not animations:
            return

        run_time = scene.get_run_time(animations)
        suspend = kwargs.get("suspend_mobject_updating", False)
        has_updaters = (
            any(len(m.updaters) > 0 for m in scene.get_mobject_family_members())
            and not suspend
        )

        if has_updaters:
            self._play_data_path(scene, animations, run_time)
        else:
            self._play_animate_path(scene, animations, run_time)

        self.time += run_time
        self.num_plays += 1

    def _play_animate_path(
        self, scene: Scene, animations: list[Animation], run_time: float
    ) -> None:
        """Emit register + animate + post commands for a non-updater play() call.

        post: self._current.commands[-1]["cmd"] == "animate"
        post: implies(isinstance(anim, GrowArrow) for anim in animations,
                      forall([d for d in self._current.commands[-1]["animations"]
                               if "state_ref" in d],
                             lambda d: isinstance(d["state_ref"], int)))
        """
        current = self._current
        if current is None:
            return

        pre_commands: list[dict] = []
        animate_descriptors: list[dict] = []
        post_commands: list[dict] = []

        def _is_supported(mob: Mobject) -> bool:
            if isinstance(mob, VMobject | ValueTracker | AbstractImageMobject):
                return True
            return bool(hasattr(mob, "submobjects") and mob.submobjects)

        # Inject Add animations for currently present scene roots that were
        # not introduced by an animation yet.
        for mob in scene.mobjects:
            if not _is_supported(mob):
                continue
            if not self.is_active(mob):
                self.register_mobject(mob)
                pre_commands.extend(self._mob_register_commands(mob))
            if not self._introduced_by_animation.get(id(mob), False):
                animate_descriptors.append({"kind": "Add", "id": self.short_id(mob)})
                self._introduced_by_animation[id(mob)] = True

        def _process_leaf_anim(anim: Animation, desc: dict) -> None:
            """Register mobject and emit post-commands for a single leaf animation."""
            mob = anim.mobject
            if isinstance(anim, Swap | CyclicReplace):
                return
            if isinstance(mob, Mobject) and not _is_supported(mob):
                return

            if not self.is_active(mob):
                self.register_mobject(mob)
                if isinstance(anim, GrowArrow):
                    pre_commands.extend(self._grow_arrow_register_commands(mob, anim))
                else:
                    pre_commands.extend(self._mob_register_commands(mob))

            if anim.is_introducer():
                self._introduced_by_animation[id(mob)] = True

            if isinstance(anim, ReplacementTransform):
                target = anim.target_mobject
                if not self.is_active(target):
                    self.register_mobject(target)
                post_commands.append(
                    {
                        "cmd": "rebind",
                        "source_id": self.short_id(anim.mobject),
                        "target_id": self.short_id(target),
                    }
                )
            elif isinstance(anim, FadeOut):
                post_commands.extend(self._mob_remove_commands(anim.mobject))

        for anim in animations:
            if isinstance(anim, AnimationGroup):
                # Flatten sub-animations with explicit start/end timestamps so the
                # JS player can use playWithTimestamps for correct lag_ratio timing.
                scale = (
                    anim.run_time / anim.max_end_time if anim.max_end_time > 0 else 1.0
                )
                for row in anim.anims_with_timings:
                    sub: Animation = row["anim"]
                    desc = self._descriptor_from_animation(sub)
                    desc["start"] = round(float(row["start"]) * scale, 6)
                    desc["end"] = round(float(row["end"]) * scale, 6)
                    animate_descriptors.append(desc)
                    _process_leaf_anim(sub, desc)
            else:
                desc = self._descriptor_from_animation(anim)
                animate_descriptors.append(desc)
                _process_leaf_anim(anim, desc)

        if pre_commands:
            current.commands.extend(pre_commands)

        current.commands.append(
            {
                "cmd": "animate",
                "duration": run_time,
                "animations": animate_descriptors,
            }
        )

        if post_commands:
            current.commands.extend(post_commands)

        self._suppress_stage_adds = True
        try:
            for anim in animations:
                anim._setup_scene(scene)
        finally:
            self._suppress_stage_adds = False

        n_frames = math.ceil(run_time * self.fps)
        camera_frames: list[dict[str, float]] = []
        needs_frame_loop = _needs_camera_frame_loop(scene, animations)

        initial_cam_state: dict[str, float] | None = None
        if needs_frame_loop:
            initial_cam_state = _compute_camera_state(scene.camera)
        last_cam_state = initial_cam_state

        # Run the animation lifecycle so mobjects reach their end state.
        # Some transforms (e.g. between ImageMobjects of different pixel
        # dimensions) cannot interpolate Python-side; Manim raises in begin().
        # If that happens we warn, apply end states directly, and skip the
        # frame loop — it would fail too. Visual interpolation is the JS
        # player's job; Python only needs correct final geometry.
        # NOTE: mixing interpolable and non-interpolable animations in one
        # play() call is not supported — the whole batch is skipped on failure.
        begin_failed = False
        try:
            for anim in animations:
                anim.begin()
        except Exception as exc:
            import warnings

            warnings.warn(
                f"Animation batch could not begin Python-side ({exc}). "
                "Applying end states directly; this scene would not play back "
                "in plain Manim. See manim_widget.anim_compat for details.",
                stacklevel=3,
            )
            begin_failed = True
            for anim in animations:
                if hasattr(anim, "target_mobject"):
                    force_end_state(anim)

        if not begin_failed:
            if needs_frame_loop:
                scene.animations = animations
                scene.last_t = 0.0

                for i in range(n_frames):
                    t = (i + 1) / self.fps
                    if t > run_time:
                        t = run_time
                    scene.update_to_time(t)

                    cam_state = _compute_camera_state(scene.camera)
                    if cam_state != initial_cam_state and cam_state != last_cam_state:
                        camera_frames.append(cam_state)
                        last_cam_state = cam_state

                scene.animations = None

            for anim in animations:
                anim.finish()

        for anim in animations:
            if isinstance(anim, (FadeOut, ReplacementTransform)):
                self.unregister_mobject(anim.mobject)
        for anim in animations:
            anim.clean_up_from_scene(scene)
        scene.update_mobjects(0)

        # Add camera updates to animate command if any
        if camera_frames:
            current.commands[-1]["camera_updates"] = camera_frames

    def _descriptor_from_animation(self, anim: Animation) -> dict[str, Any]:
        """Translate a single manim Animation into a wire-format descriptor dict.

        post: "kind" in __return__
        post: implies("state_ref" in __return__, isinstance(__return__["state_ref"], int))
        post: implies(isinstance(anim, GrowArrow), __return__["kind"] == "Transform")
        post: implies(isinstance(anim, GrowArrow), "state_ref" in __return__)
        post: implies(isinstance(anim, (Swap, CyclicReplace)), "ids" in __return__)
        post: implies(isinstance(anim, (Swap, CyclicReplace)), "id" not in __return__)
        """
        anim_name = type(anim).__name__
        params: dict[str, Any] = {}
        descriptor: dict[str, Any] = {}

        if hasattr(anim, "mobject") and anim_name != "Wait":
            descriptor["id"] = self.short_id(anim.mobject)

        target_mobject = getattr(anim, "target_mobject", None)

        if hasattr(anim, "rate_func"):
            rate_func_name = getattr(anim.rate_func, "__name__", "smooth")
            if "smooth" in rate_func_name.lower():
                descriptor["rate_func"] = "smooth"
            else:
                descriptor["rate_func"] = rate_func_name

        methods = getattr(anim, "methods", None)
        if methods:
            if target_mobject is None:
                msg = "Method animation missing target_mobject"
                raise RuntimeError(msg)
            descriptor["kind"] = "MoveToTarget"
            descriptor["state_ref"] = self.state_ref_for(target_mobject)
            return descriptor

        if isinstance(anim, GrowArrow):
            # GrowArrow is replayed as a Transform from the collapsed arrow (its
            # starting mobject, registered as the initial state) to the full
            # arrow. This keeps the JS player free of arrow-specific growth and
            # reconstruction logic.
            descriptor["kind"] = "Transform"
            descriptor["state_ref"] = self.state_ref_for(anim.mobject)
            return descriptor

        if anim_name in ("Transform", "ReplacementTransform"):
            if target_mobject is None:
                msg = "Transform animation missing target_mobject"
                raise RuntimeError(msg)
            descriptor["kind"] = "Transform"
            descriptor["state_ref"] = self.state_ref_for(target_mobject)
            transform_params: dict[str, Any] = {}
            path_arc = getattr(anim, "path_arc", None)
            if path_arc is not None:
                transform_params["path_arc"] = float(path_arc)
            path_arc_axis = getattr(anim, "path_arc_axis", None)
            if path_arc_axis is not None:
                transform_params["path_arc_axis"] = list(path_arc_axis)
            if transform_params:
                descriptor["params"] = transform_params
            return descriptor

        if isinstance(anim, Swap):
            group = getattr(anim, "group", None)
            if group is None or not hasattr(group, "submobjects"):
                msg = "Swap animation missing group or submobjects"
                raise RuntimeError(msg)
            submobjects = group.submobjects
            if len(submobjects) < 2:
                msg = "Swap animation requires at least 2 mobjects"
                raise RuntimeError(msg)
            descriptor = {
                "kind": "Swap",
                "ids": [self.short_id(m) for m in submobjects[:2]],
            }
            swap_params: dict[str, Any] = {}
            path_arc = getattr(anim, "path_arc", None)
            if path_arc is not None:
                swap_params["path_arc"] = float(path_arc)
            if swap_params:
                descriptor["params"] = swap_params
            if hasattr(anim, "rate_func"):
                rate_func_name = getattr(anim.rate_func, "__name__", "smooth")
                if "smooth" in rate_func_name.lower():
                    descriptor["rate_func"] = "smooth"
                else:
                    descriptor["rate_func"] = rate_func_name
            return descriptor

        if isinstance(anim, CyclicReplace) and not isinstance(anim, Swap):
            group = getattr(anim, "group", None)
            if group is None or not hasattr(group, "submobjects"):
                msg = "CyclicReplace animation missing group or submobjects"
                raise RuntimeError(msg)
            submobjects = group.submobjects
            if len(submobjects) < 2:
                msg = "CyclicReplace animation requires at least 2 mobjects"
                raise RuntimeError(msg)
            descriptor = {
                "kind": "CyclicReplace",
                "ids": [self.short_id(m) for m in submobjects],
            }
            cyclic_params: dict[str, Any] = {}
            path_arc = getattr(anim, "path_arc", None)
            if path_arc is not None:
                cyclic_params["path_arc"] = float(path_arc)
            if cyclic_params:
                descriptor["params"] = cyclic_params
            if hasattr(anim, "rate_func"):
                rate_func_name = getattr(anim.rate_func, "__name__", "smooth")
                if "smooth" in rate_func_name.lower():
                    descriptor["rate_func"] = "smooth"
                else:
                    descriptor["rate_func"] = rate_func_name
            return descriptor

        if isinstance(anim, Rotate):
            params["angle"] = float(getattr(anim, "angle", 0.0))
            axis = getattr(anim, "axis", None)
            if axis is not None:
                params["axis"] = list(axis)
            about_point = getattr(anim, "about_point", None)
            if about_point is not None:
                params["about_point"] = list(about_point)
        elif isinstance(anim, ScaleInPlace):
            params["scale_factor"] = float(getattr(anim, "scale_factor", 1.0))
        else:
            path = getattr(anim, "path", None)
            if path is not None:
                params["path_id"] = self.short_id(path)
            about_point = getattr(anim, "about_point", None)
            if about_point is not None:
                params["about_point"] = list(about_point)
        descriptor["kind"] = anim_name
        if params:
            descriptor["params"] = params
        return descriptor

    def _play_data_path(
        self, scene: Scene, animations: list[Animation], run_time: float
    ) -> None:
        current = self._current
        if current is None:
            return

        tracked: list[Mobject] = []
        seen: set[int] = set()
        for m in scene.get_mobject_family_members():
            for member in m.get_family():
                member_id = id(member)
                if member_id in seen:
                    continue
                seen.add(member_id)
                tracked.append(member)
        for anim in animations:
            if hasattr(anim, "mobject"):
                member = anim.mobject
                member_id = id(member)
                if member_id not in seen:
                    seen.add(member_id)
                    tracked.append(member)

        self.flush_staged_adds()

        scene.animations = animations
        scene.last_t = 0.0
        self._suppress_stage_adds = True
        try:
            for anim in animations:
                anim._setup_scene(scene)
        finally:
            self._suppress_stage_adds = False
        for anim in animations:
            anim.begin()

        # Register any mob that is about to appear in frames but has not yet
        # been registered (e.g. polygon added to scene by Create inside this call).
        registered_ids = {
            cmd["id"] for cmd in current.commands if cmd.get("cmd") == "register"
        }
        for mob in tracked:
            mob_id = self.short_id(mob)
            if mob_id not in registered_ids:
                current.commands.extend(self._mob_register_commands(mob))
                registered_ids.add(mob_id)

        n_frames = math.ceil(run_time * self.fps)
        frames: list[dict[str, Any]] = []
        camera_frames: list[dict[str, float]] = []
        is_3d = hasattr(scene, "camera") and hasattr(scene.camera, "get_phi")

        # Capture initial camera state
        initial_cam_state: dict[str, float] | None = None
        if is_3d:
            initial_cam_state = _compute_camera_state(scene.camera)
        last_cam_state = initial_cam_state

        for i in range(n_frames):
            t = (i + 1) / self.fps
            if t > run_time:
                t = run_time
            scene.update_to_time(t)
            frame: dict[str, Any] = {}
            for mob in tracked:
                mob_id = self.short_id(mob)
                frame[mob_id] = {"state_ref": self.state_ref_for(mob)}
            frames.append(frame)

            # Capture camera state for 3D scenes (only if changed from initial)
            if is_3d:
                cam_state = _compute_camera_state(scene.camera)
                if cam_state != initial_cam_state and cam_state != last_cam_state:
                    camera_frames.append(cam_state)
                    last_cam_state = cam_state

        for anim in animations:
            anim.finish()
        for anim in animations:
            anim.clean_up_from_scene(scene)
        scene.update_mobjects(0)

        cmd: dict[str, Any] = {
            "cmd": "updater",
            "duration": run_time,
            "frames": frames,
        }
        if camera_frames:
            cmd["camera_updates"] = camera_frames
        current.commands.append(cmd)

    def _image_source_from_pixel_array(self, pixel_array: object) -> str:
        arr = np.asarray(pixel_array)
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)

        mode: str
        if arr.ndim == 2:
            mode = "L"
        elif arr.ndim == 3:
            channels = arr.shape[2]
            if channels == 1:
                arr = arr[:, :, 0]
                mode = "L"
            elif channels == 3:
                mode = "RGB"
            elif channels == 4:
                mode = "RGBA"
            else:
                msg = f"Unsupported ImageMobject channel count: {channels}"
                raise ValueError(msg)
        else:
            msg = f"Unsupported ImageMobject array shape: {arr.shape}"
            raise ValueError(msg)

        image = Image.fromarray(arr, mode=mode)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def _color_to_hex(self, color: object) -> str:
        if hasattr(color, "to_hex"):
            return color.to_hex()
        return str(color)
