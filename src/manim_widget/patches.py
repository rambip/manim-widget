from __future__ import annotations

from functools import reduce
from operator import add as op_add
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from manim import Mobject, Scene, VMobject
from manim.utils.space_ops import rotation_matrix

if TYPE_CHECKING:
    from numpy.typing import NDArray


IDENTITY_4x4 = np.eye(4, dtype=np.float64)


def _build_translation_matrix(vector: NDArray[np.float64]) -> NDArray[np.float64]:
    m = IDENTITY_4x4.copy()
    m[:3, 3] = vector
    return m


def _build_rotation_matrix(
    angle: float, axis: NDArray[np.float64]
) -> NDArray[np.float64]:
    rot = rotation_matrix(angle, axis)
    m = IDENTITY_4x4.copy()
    m[:3, :3] = rot
    return m


def _build_scale_matrix(
    factor: float, about_point: NDArray[np.float64] | None
) -> NDArray[np.float64]:
    m = IDENTITY_4x4.copy()
    if about_point is not None:
        T = _build_translation_matrix(-about_point)
        T_inv = _build_translation_matrix(about_point)
        S = IDENTITY_4x4.copy()
        S[:3, :3] *= factor
        return T_inv @ S @ T
    m[:3, :3] *= factor
    return m


def _init_matrix_tracking(self: Mobject, *args: object, **kwargs: object) -> None:
    obj = cast(Any, self)
    obj._orig_init(*args, **kwargs)
    obj._local_matrix = IDENTITY_4x4.copy()
    obj._dirty_geometry = False


def _new_shift(self: VMobject, *vectors: np.ndarray) -> Mobject:
    total_vector = reduce(op_add, vectors)
    m = _build_translation_matrix(total_vector)
    obj = cast(Any, self)
    if hasattr(obj, "_local_matrix"):
        obj._local_matrix = m @ obj._local_matrix
    return obj._orig_shift(*vectors)


def _new_rotate(
    self: VMobject,
    angle: float,
    axis: np.ndarray | None = None,
    *,
    about_point: np.ndarray | None = None,
    about_edge: np.ndarray | None = None,
) -> Mobject:
    from manim import OUT

    if axis is None:
        axis = OUT
    if about_point is None:
        if about_edge is None:
            about_edge = np.array([0.0, 0.0, 0.0])
        about_point = self.get_critical_point(about_edge)
    m = _build_rotation_matrix(angle, axis)
    T = _build_translation_matrix(-about_point)
    T_inv = _build_translation_matrix(about_point)
    obj = cast(Any, self)
    if hasattr(obj, "_local_matrix"):
        obj._local_matrix = T_inv @ m @ T @ obj._local_matrix
    return obj._orig_rotate(angle, axis, about_point=about_point, about_edge=about_edge)


def _new_scale(
    self: VMobject,
    scale_factor: float,
    *,
    about_point: np.ndarray | None = None,
    about_edge: np.ndarray | None = None,
) -> Mobject:
    if about_point is None:
        if about_edge is None:
            about_edge = np.array([0.0, 0.0, 0.0])
        about_point = self.get_critical_point(about_edge)
    m = _build_scale_matrix(scale_factor, about_point)
    obj = cast(Any, self)
    if hasattr(obj, "_local_matrix"):
        obj._local_matrix = m @ obj._local_matrix
    return obj._orig_scale(scale_factor, about_point=about_point, about_edge=about_edge)


def _dirty(self: Mobject) -> None:
    cast(Any, self)._dirty_geometry = True


def _new_apply_points_function_about_point(
    self: VMobject,
    func,
    about_point: np.ndarray | None = None,
    about_edge: np.ndarray | None = None,
) -> None:
    _dirty(self)
    cast(Any, self)._orig_apply_points_function_about_point(
        func, about_point, about_edge
    )


def _new_become(self: Mobject, other: Mobject) -> Mobject:
    _dirty(self)
    return cast(Any, self)._orig_become(other)


def _new_apply_function(self: Mobject, func) -> Mobject:
    _dirty(self)
    return cast(Any, self)._orig_apply_function(func)


def _new_put_start_and_end_on(self: Mobject, *args, **kwargs) -> Mobject:
    _dirty(self)
    return cast(Any, self)._orig_put_start_and_end_on(*args, **kwargs)


def _init_scene_tracking(self: Scene) -> None:
    obj = cast(Any, self)
    obj.active_mob_ids = set()
    obj._orig_init_scene()


_orig_scene_add = Scene.add


def _new_scene_add(self: Scene, *mobjects: Mobject) -> Scene:
    obj = cast(Any, self)
    for mob in mobjects:
        obj.active_mob_ids.add(id(mob))
        for child in mob.get_family():
            obj.active_mob_ids.add(id(child))
    return _orig_scene_add(self, *mobjects)


_orig_scene_remove = Scene.remove


def _new_scene_remove(self: Scene, *mobjects: Mobject) -> Scene:
    obj = cast(Any, self)
    for mob in mobjects:
        obj.active_mob_ids.discard(id(mob))
        for child in mob.get_family():
            obj.active_mob_ids.discard(id(child))
    return _orig_scene_remove(self, *mobjects)


_orig_scene_next_section = Scene.next_section


def _new_scene_next_section(
    self: Scene,
    name: str = "unnamed",
    section_type=None,
    skip_animations: bool = False,
) -> None:
    obj = cast(Any, self)
    if hasattr(obj, "_on_next_section"):
        obj._on_next_section(name)
    return _orig_scene_next_section(self, name, section_type, skip_animations)


def apply_patches() -> None:
    _orig_init = VMobject.__init__
    cast(Any, VMobject)._orig_init = _orig_init
    VMobject.__init__ = _init_matrix_tracking  # type: ignore[method-assign]

    cast(Any, VMobject)._orig_shift = VMobject.shift
    VMobject.shift = _new_shift  # type: ignore[method-assign]

    cast(Any, VMobject)._orig_rotate = VMobject.rotate
    VMobject.rotate = _new_rotate  # type: ignore[method-assign]

    cast(Any, VMobject)._orig_scale = VMobject.scale
    VMobject.scale = _new_scale  # type: ignore[method-assign]

    cast(
        Any, VMobject
    )._orig_apply_points_function_about_point = (
        VMobject.apply_points_function_about_point
    )
    VMobject.apply_points_function_about_point = _new_apply_points_function_about_point  # type: ignore[method-assign]

    cast(Any, VMobject)._orig_become = VMobject.become
    VMobject.become = _new_become  # type: ignore[method-assign]

    cast(Any, VMobject)._orig_apply_function = VMobject.apply_function
    VMobject.apply_function = _new_apply_function  # type: ignore[method-assign]

    cast(Any, VMobject)._orig_put_start_and_end_on = VMobject.put_start_and_end_on
    VMobject.put_start_and_end_on = _new_put_start_and_end_on  # type: ignore[method-assign]

    cast(Any, Scene)._orig_init_scene = Scene.__init__
    Scene.__init__ = _init_scene_tracking  # type: ignore[method-assign]

    cast(Any, Scene)._orig_add = Scene.add
    Scene.add = _new_scene_add  # type: ignore[method-assign]

    cast(Any, Scene)._orig_remove = Scene.remove
    Scene.remove = _new_scene_remove  # type: ignore[method-assign]

    cast(Any, Scene)._orig_next_section = Scene.next_section
    Scene.next_section = _new_scene_next_section  # type: ignore[method-assign]


def remove_patches() -> None:
    if hasattr(VMobject, "_orig_init"):
        VMobject.__init__ = cast(Any, VMobject)._orig_init  # type: ignore[method-assign]
    if hasattr(VMobject, "_orig_shift"):
        VMobject.shift = cast(Any, VMobject)._orig_shift  # type: ignore[method-assign]
    if hasattr(VMobject, "_orig_rotate"):
        VMobject.rotate = cast(Any, VMobject)._orig_rotate  # type: ignore[method-assign]
    if hasattr(VMobject, "_orig_scale"):
        VMobject.scale = cast(Any, VMobject)._orig_scale  # type: ignore[method-assign]
    if hasattr(VMobject, "_orig_apply_points_function_about_point"):
        VMobject.apply_points_function_about_point = cast(
            Any, VMobject
        )._orig_apply_points_function_about_point  # type: ignore[method-assign]
    if hasattr(VMobject, "_orig_become"):
        VMobject.become = cast(Any, VMobject)._orig_become  # type: ignore[method-assign]
    if hasattr(VMobject, "_orig_apply_function"):
        VMobject.apply_function = cast(Any, VMobject)._orig_apply_function  # type: ignore[method-assign]
    if hasattr(VMobject, "_orig_put_start_and_end_on"):
        VMobject.put_start_and_end_on = cast(Any, VMobject)._orig_put_start_and_end_on  # type: ignore[method-assign]

    if hasattr(Scene, "_orig_init_scene"):
        Scene.__init__ = cast(Any, Scene)._orig_init_scene  # type: ignore[method-assign]
    if hasattr(Scene, "_orig_add"):
        Scene.add = cast(Any, Scene)._orig_add  # type: ignore[method-assign]
    if hasattr(Scene, "_orig_remove"):
        Scene.remove = cast(Any, Scene)._orig_remove  # type: ignore[method-assign]
    if hasattr(Scene, "_orig_next_section"):
        Scene.next_section = cast(Any, Scene)._orig_next_section  # type: ignore[method-assign]
