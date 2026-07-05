from __future__ import annotations

import base64
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

from manim import GrowArrow, Text, VGroup, ValueTracker
from manim.mobject.mobject import Mobject
from manim.mobject.types.image_mobject import AbstractImageMobject
from manim.mobject.types.point_cloud_mobject import PMobject
from manim.mobject.types.vectorized_mobject import VMobject

from ._state_keys import _ImgKey, _MathTexKey, _PMobjectKey, _VMobKey, _GroupKey, _VTKey
from ._subpaths import _SubpathChild, _classify_subpaths, _subpath_to_3n1
from .models import RegisterCommand, RemoveCommand
from .registry import StateRegistry
from .snapshot import IdCounter
from .states import (
    DerivedState,
    ImageMobjectState,
    MathTexState,
    MobjectState,
    PMobjectState,
    VMobjectState,
    GroupState,
    ValueTrackerState,
    _signed_area_2d,
)
from .tex_patch import PatchedMathTex


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


class MobSerializer:
    """Translates Manim mobjects into wire-format state dicts and manages the state bank."""

    def __init__(self, id_counter: IdCounter) -> None:
        self._id_counter = id_counter
        self._state_registry: StateRegistry[
            Mobject, PixelContent, tuple, MobjectState
        ] = StateRegistry(
            extract_content=self._extract_content,
            extract_state=self._extract_state,
            make_from_content=self._make_from_content,
            make_from_state=self._make_from_state,
        )
        self.state_refs: dict[int, list[int]] = {}
        # Persistent add_fixed_in_frame_mobjects/add_fixed_orientation_mobjects
        # status, keyed by id(mob). Survives across sections so a direct section
        # jump can restore it from the snapshot's state_ref alone.
        self._fixed_status: dict[int, str] = {}

    def short_id(self, mob: object) -> str:
        return self._id_counter.short_id(mob)

    def set_fixed(self, mob: Mobject, mode: str | None) -> None:
        if mode is None:
            self._fixed_status.pop(id(mob), None)
        else:
            self._fixed_status[id(mob)] = mode

    def state_ref_for_register(self, mob: Mobject) -> int:
        """Like ``state_ref_for``, but wraps the result with the mob's current
        fixed status if any.

        The wrap is a synthetic, non-deduped copy (via ``insert_raw``) so that
        two identical-looking mobjects that differ only in fixed status never
        collide in the dedup bank, and so the flag never needs to participate
        in the content-hash keys used by ``extract_state``.
        """
        ref = self.state_ref_for(mob)
        mode = self._fixed_status.get(id(mob))
        if mode is None:
            return ref
        state = self._state_registry.get_by_id(ref).model_copy(update={"fixed": mode})
        return self._state_registry.insert_raw(state)

    # ------------------------------------------------------------------
    # Registry extract / make callbacks
    # ------------------------------------------------------------------

    def _extract_content(self, mob: Mobject) -> PixelContent | None:
        if isinstance(mob, AbstractImageMobject):
            return PixelContent.from_array(mob.get_pixel_array())
        return None

    def _extract_state(self, mob: Mobject) -> tuple | None:
        if isinstance(mob, ValueTracker):
            return _VTKey(float(mob.get_value()))

        if isinstance(mob, PatchedMathTex):
            raw = np.asarray(mob.points).tolist()
            color_hex = self._color_to_hex(mob.color) if mob.color is not None else None
            return _MathTexKey(mob.tex_string, tuple(tuple(p) for p in raw), color_hex)

        if isinstance(mob, AbstractImageMobject):
            content = self._extract_content(mob)
            content_ref = self._state_registry.get_content_ref(content)
            if content_ref is None:
                return (
                    None  # content not yet registered; insert() registers content first
                )
            raw = np.asarray(mob.points).tolist()
            return (
                _ImgKey(content_ref, tuple(tuple(p) for p in raw))
                if len(raw) == 4
                else None
            )

        if isinstance(mob, PMobject) and not mob.submobjects:
            return self._point_key(mob)

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
            return _GroupKey(tuple(child_refs))

        if isinstance(mob, VMobject) and not mob.submobjects:
            subpaths = mob.get_subpaths()
            contours, holes = _classify_subpaths(subpaths)
            fill_color = mob.get_fill_color()
            stroke_color = mob.get_stroke_color()
            return _VMobKey(
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

    def _point_key(self, mob: PMobject) -> _PMobjectKey:
        """Build a state key for a point-cloud PMobject (Point, PointCloudDot, ...).

        Reads the full ``points``/``rgbas`` arrays directly off the leaf mobject;
        a single Point is just a one-element cloud.
        """
        pts = np.asarray(mob.points)
        rgbas = np.asarray(mob.rgbas)
        points = tuple(tuple(float(c) for c in p) for p in pts)
        colors: tuple | None = None
        opacities: tuple | None = None
        if len(rgbas):
            colors = tuple(
                "#{:02x}{:02x}{:02x}".format(
                    round(float(r) * 255), round(float(g) * 255), round(float(b) * 255)
                )
                for r, g, b, _ in rgbas
            )
            opacities = tuple(float(a) for *_, a in rgbas)
        stroke_width = mob.get_stroke_width()
        return _PMobjectKey(
            points, colors, opacities, float(stroke_width) if stroke_width else None
        )

    def _make_from_content(self, content: PixelContent) -> ImageMobjectState:
        return ImageMobjectState(
            source=self._image_source_from_pixel_array(content.to_array())
        )

    def _make_from_state(self, state: tuple) -> MobjectState:
        if isinstance(state, _VTKey):
            return ValueTrackerState(value=state.value)
        if isinstance(state, _MathTexKey):
            return MathTexState(
                latex=state.latex,
                points=[[float(p[0]), float(p[1]), float(p[2])] for p in state.pts],
                color=state.color,
            )
        if isinstance(state, _ImgKey):
            return DerivedState(
                from_=state.content_ref,
                points=[list(p) for p in state.corners],
            )
        if isinstance(state, _PMobjectKey):
            return PMobjectState(
                points=[list(p) for p in state.points],
                colors=list(state.colors) if state.colors is not None else None,
                opacities=(
                    list(state.opacities) if state.opacities is not None else None
                ),
                stroke_width=state.stroke_width,
            )
        if isinstance(state, _GroupKey):
            return GroupState(children=list(state.child_refs))
        if isinstance(state, _VMobKey):
            return VMobjectState(
                contours=[[list(p) for p in c] for c in state.contours],
                holes=[[list(p) for p in h] for h in state.holes],
                fill_color=state.fill_color,
                stroke_color=state.stroke_color,
                fill_opacity=state.fill_opacity,
                stroke_width=state.stroke_width,
                stroke_opacity=state.stroke_opacity,
                z_index=state.z_index,
            )
        msg = f"Unknown state type: {type(state)!r}"
        raise ValueError(msg)

    # ------------------------------------------------------------------
    # State-ref helpers
    # ------------------------------------------------------------------

    def _ensure_image_refs(self, mob: AbstractImageMobject) -> tuple[int, int | None]:
        """Ensure image content and current-position derived state are registered.

        Content (pixel data) is registered once.  The derived state
        ``{from: content_ref, points: corners}`` is keyed by ``(content_ref, corners)``
        so each unique position gets its own entry and identical positions are reused.

        post: __return__[0] is not None
        post: 0 <= __return__[0] < len(self._state_registry)
        """
        reg = self._state_registry
        if reg.get(mob) is None:
            reg.insert(mob)
        else:
            state = self._extract_state(mob)
            if state is not None:
                reg.ensure_addon(state)
        return reg.get(mob), reg.get_addon(mob)

    def _js_children(self, mob: Mobject) -> list:
        """Single source of truth for what children a mob exposes to the JS player.

        Returns an empty list for leaf mobs (no JS children).
        For groups / mobs with children: actual submobjects.
        For VMobjects that carry both own subpaths AND submobjects (e.g. Arrow):
            _SubpathChild entries first (one per non-empty subpath), then actual submobjects.

        All consumers — register commands, remove commands, GroupState serialisation —
        must derive their child list exclusively from this method.
        """
        submobs = getattr(mob, "submobjects", None) or []
        if not submobs:
            return list(submobs)

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

    def _subpath_child_state_ref(self, child: _SubpathChild) -> int:
        """Allocate a state_ref for a synthetic subpath child."""
        style = self._vmob_style(child.parent)
        points_3n1 = _subpath_to_3n1(child.subpath)
        if not points_3n1:
            return self._state_registry.insert_raw(VMobjectState(contours=[], holes=[]))
        if _signed_area_2d(points_3n1) > 0:
            points_3n1 = points_3n1[::-1]
        subpath_state = VMobjectState(contours=[points_3n1], **style)
        return self._state_registry.insert_raw(subpath_state)

    def state_ref_for(self, mob: Mobject) -> int:
        """Return the global state-bank index for mob's current state.

        For images returns the derived-state ref ``{from: content_ref, points: corners}``.
        Recurses into children first so VGroup extract_state can look them up.
        Multi-subpath VMobjects are serialized via insert_raw (no dedup).

        post: 0 <= __return__ < len(self._state_registry)
        """
        if isinstance(mob, AbstractImageMobject):
            _, addon_ref = self._ensure_image_refs(mob)
            if addon_ref is not None:
                self.state_refs.setdefault(id(mob), []).append(addon_ref)
                return addon_ref
            ref = self._state_registry.get(mob)
            self.state_refs.setdefault(id(mob), []).append(ref)
            return ref

        if hasattr(mob, "submobjects") and mob.submobjects:
            for child in mob.submobjects:
                self.state_ref_for(child)

        ref = self._state_registry.get(mob)
        if ref is not None:
            self.state_refs.setdefault(id(mob), []).append(ref)
            return ref
        state = self._extract_state(mob)
        if state is not None:
            main_ref, _ = self._state_registry.insert(mob)
            self.state_refs.setdefault(id(mob), []).append(main_ref)
            return main_ref

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
                    vgroup_state = GroupState(children=child_refs)
                    ref = self._state_registry.insert_raw(vgroup_state)
                    self.state_refs.setdefault(id(mob), []).append(ref)
                    return ref
            if not mob.submobjects:
                style = self._vmob_style(mob)
                ref = self._state_registry.insert_raw(
                    VMobjectState(contours=[], holes=[], **style)
                )
                self.state_refs.setdefault(id(mob), []).append(ref)
                return ref

        # VMobject with submobjects but no own subpaths (e.g. MarkupText, SVGMobject)
        # whose children may have been registered via insert_raw and are invisible to
        # _state_registry.get().  Build GroupState from identity-keyed state_refs.
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
                vgroup_state = GroupState(children=child_refs)
                ref = self._state_registry.insert_raw(vgroup_state)
                self.state_refs.setdefault(id(mob), []).append(ref)
                return ref

        msg = f"Cannot compute state_ref for {mob!r}"
        raise ValueError(msg)

    def _vmob_style(self, mob: VMobject) -> dict[str, object]:
        """Extract fill/stroke style dict from a VMobject (not VGroup).

        post: implies(isinstance(mob, VGroup), not __return__)
        """
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
        return self._state_registry.insert_raw(state)

    def serialize_mobject(self, mob: Mobject, *, for_snapshot: bool) -> MobjectState:
        """Serialize a single mobject to a typed state object.

        post: implies(not isinstance(mob, ValueTracker), hasattr(__return__, "kind"))
        post: implies(isinstance(__return__, GroupState),
                      forall(__return__.children, lambda r: isinstance(r, int)))
        """
        if isinstance(mob, ValueTracker):
            return ValueTrackerState(value=float(mob.get_value()))

        if isinstance(mob, PatchedMathTex):
            raw = np.asarray(mob.points).tolist()
            pts = [[float(p[0]), float(p[1]), float(p[2])] for p in raw]
            return MathTexState(
                latex=mob.tex_string,
                points=pts,
                color=self._color_to_hex(mob.color) if mob.color is not None else None,
            )

        if isinstance(mob, AbstractImageMobject):
            raw = np.asarray(mob.points).tolist()
            if self._state_registry.get(mob) is None:
                self._state_registry.insert(mob)
            content_ref = self._state_registry.get(mob)
            source = self._state_registry.get_by_id(content_ref).source
            return ImageMobjectState(
                source=source,
                points=raw if len(raw) == 4 else None,
                z_index=getattr(mob, "z_index", None),
            )

        if isinstance(mob, PMobject) and not mob.submobjects:
            k = self._point_key(mob)
            return PMobjectState(
                points=[list(p) for p in k.points],
                colors=list(k.colors) if k.colors is not None else None,
                opacities=list(k.opacities) if k.opacities is not None else None,
            )

        style = self._vmob_style(mob) if isinstance(mob, VMobject) else {}
        js_children = self._js_children(mob)

        if isinstance(mob, VMobject):
            subpaths = mob.get_subpaths()
            if js_children:
                child_refs: list[int] = []
                for jsc in js_children:
                    if isinstance(jsc, _SubpathChild):
                        child_refs.append(self._subpath_child_state_ref(jsc))
                    else:
                        child_refs.append(self.state_ref_for(jsc))
                return GroupState(children=child_refs)
            if subpaths:
                contours, holes = _classify_subpaths(subpaths)
                style["contours"] = contours
                style["holes"] = holes

        if js_children:
            return GroupState(
                children=[self.state_ref_for(child) for child in mob.submobjects]
            )

        text_extras: dict[str, object] = {}
        if isinstance(mob, Text):
            text_extras["text"] = mob.text
            text_extras["font_size"] = mob.font_size

        return VMobjectState(**style, **text_extras)

    # ------------------------------------------------------------------
    # Register / remove command builders
    # ------------------------------------------------------------------

    def _mob_register_commands(self, mob: Mobject) -> list[RegisterCommand]:
        """Return register command(s) for mob and all its JS children.

        post: len(__return__) >= 1
        post: all(d.cmd == "register" for d in __return__)
        post: __return__[-1].id == self.short_id(mob)
        """
        js_children = self._js_children(mob)
        if not js_children:
            return [
                RegisterCommand(
                    id=self.short_id(mob),
                    state_ref=self.state_ref_for_register(mob),
                )
            ]

        cmds: list[RegisterCommand] = []
        child_ids: list[str] = []
        for child in js_children:
            if isinstance(child, _SubpathChild):
                state_ref = self._subpath_child_state_ref(child)
                cmds.append(RegisterCommand(id=child.mob_id, state_ref=state_ref))
                child_ids.append(child.mob_id)
            else:
                cmds.extend(self._mob_register_commands(child))
                child_ids.append(self.short_id(child))
        cmds.append(
            RegisterCommand(
                id=self.short_id(mob),
                state_ref=self.state_ref_for_register(mob),
                child_ids=child_ids,
            )
        )
        return cmds

    def _mob_remove_commands(self, mob: Mobject) -> list[RemoveCommand]:
        """Return remove command(s) for mob and all its JS children (deepest first).

        post: len(__return__) >= 1
        post: all(d.cmd == "remove" for d in __return__)
        post: __return__[-1].id == self.short_id(mob)
        """
        js_children = self._js_children(mob)
        cmds: list[RemoveCommand] = []
        for child in js_children:
            if isinstance(child, _SubpathChild):
                cmds.append(RemoveCommand(id=child.mob_id))
            else:
                cmds.extend(self._mob_remove_commands(child))
        cmds.append(RemoveCommand(id=self.short_id(mob)))
        return cmds

    def _grow_arrow_register_commands(
        self, mob: Mobject, anim: GrowArrow
    ) -> list[RegisterCommand]:
        """Register commands for GrowArrow: children get collapsed starting states,
        parent gets a virtual collapsed GroupState. The paired Transform descriptor
        then animates from this collapsed state to the final state."""
        starting = anim.create_starting_mobject()
        actual_children = self._js_children(mob)
        starting_children = self._js_children(starting)

        child_cmds: list[RegisterCommand] = []
        child_ids: list[str] = []
        collapsed_child_refs: list[int] = []

        for actual, start in zip(actual_children, starting_children):
            if isinstance(actual, _SubpathChild):
                collapsed_sc = _SubpathChild(
                    parent=actual.parent,
                    parent_id=actual.parent_id,
                    subpath_idx=actual.subpath_idx,
                    subpath=start.subpath,
                )
                ref = self._subpath_child_state_ref(collapsed_sc)
                child_cmds.append(RegisterCommand(id=actual.mob_id, state_ref=ref))
                child_ids.append(actual.mob_id)
            else:
                idx = mob.submobjects.index(actual)
                start_submob = starting.submobjects[idx]
                ref = self.state_ref_for(start_submob)
                mob_id = self.short_id(actual)
                child_cmds.append(RegisterCommand(id=mob_id, state_ref=ref))
                child_ids.append(mob_id)
            collapsed_child_refs.append(ref)

        collapsed_vgroup_ref = self._state_registry.insert_raw(
            GroupState(children=collapsed_child_refs)
        )
        return [
            *child_cmds,
            RegisterCommand(
                id=self.short_id(mob),
                state_ref=collapsed_vgroup_ref,
                child_ids=child_ids,
            ),
        ]

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

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
