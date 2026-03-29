from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest

from manim import Circle, Scene, Square, VGroup, VMobject

from manim_widget.patches import (
    _build_rotation_matrix,
    _build_scale_matrix,
    _build_translation_matrix,
    apply_patches,
    remove_patches,
)


@pytest.fixture(autouse=True)
def patched():
    apply_patches()
    yield
    remove_patches()


@pytest.fixture
def vmob():
    return VMobject()


class TestMatrixTrapperInit:
    def test_local_matrix_exists(self, vmob):
        assert hasattr(vmob, "_local_matrix")
        assert vmob._local_matrix.shape == (4, 4)
        np.testing.assert_array_almost_equal(vmob._local_matrix, np.eye(4))

    def test_dirty_geometry_false_by_default(self, vmob):
        assert hasattr(vmob, "_dirty_geometry")
        assert vmob._dirty_geometry is False


class TestBuildMatrices:
    def test_translation_matrix(self):
        vector = np.array([1.0, 2.0, 3.0])
        m = _build_translation_matrix(vector)
        assert m.shape == (4, 4)
        np.testing.assert_array_almost_equal(m[3, :], [0, 0, 0, 1])
        np.testing.assert_array_almost_equal(m[:3, 3], vector)

    def test_rotation_matrix(self):
        angle = np.pi / 2
        axis = np.array([0.0, 0.0, 1.0])
        m = _build_rotation_matrix(angle, axis)
        assert m.shape == (4, 4)
        np.testing.assert_array_almost_equal(m[3, :], [0, 0, 0, 1])
        np.testing.assert_array_almost_equal(m[:, 3], [0, 0, 0, 1])

    def test_scale_matrix_about_origin(self):
        factor = 2.0
        m = _build_scale_matrix(factor, None)
        assert m.shape == (4, 4)
        np.testing.assert_array_almost_equal(m[3, :], [0, 0, 0, 1])
        np.testing.assert_array_almost_equal(m[:3, :3], factor * np.eye(3))

    def test_scale_matrix_about_point(self):
        factor = 2.0
        about = np.array([1.0, 0.0, 0.0])
        m = _build_scale_matrix(factor, about)
        assert m.shape == (4, 4)


class TestShiftPatch:
    def test_shift_accumulates(self, vmob):
        vmob.shift(np.array([1.0, 0.0, 0.0]))
        np.testing.assert_array_equal(vmob._local_matrix[:3, 3], [1.0, 0.0, 0.0])

    def test_shift_chained(self, vmob):
        vmob.shift(np.array([1.0, 0.0, 0.0]))
        vmob.shift(np.array([0.0, 2.0, 0.0]))
        np.testing.assert_array_equal(vmob._local_matrix[:3, 3], [1.0, 2.0, 0.0])


class TestRotatePatch:
    def test_rotate_accumulates(self, vmob):
        angle = np.pi / 2
        vmob.rotate(angle)
        assert not np.allclose(vmob._local_matrix, np.eye(4))

    def test_rotate_about_point(self, vmob):
        angle = np.pi
        center = np.array([1.0, 0.0, 0.0])
        vmob.rotate(angle, about_point=center)
        assert not np.allclose(vmob._local_matrix, np.eye(4))


class TestScalePatch:
    def test_scale_accumulates(self, vmob):
        vmob.scale(2.0)
        assert not np.allclose(vmob._local_matrix[:3, :3], np.eye(3))


class TestGeometrySentinel:
    def test_apply_points_sets_dirty(self, vmob):
        assert vmob._dirty_geometry is False
        vmob.apply_function(lambda pts: pts)
        assert vmob._dirty_geometry is True

    def test_become_sets_dirty(self, vmob):
        other = Square()
        assert vmob._dirty_geometry is False
        vmob.become(other)
        assert vmob._dirty_geometry is True

    def test_put_start_and_end_on_sets_dirty(self, vmob):
        assert vmob._dirty_geometry is False
        vmob.set_points(np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0]]))
        vmob.put_start_and_end_on(np.array([0.0, 0.0, 0.0]), np.array([2.0, 0.0, 0.0]))
        assert vmob._dirty_geometry is True


class TestScenePresenceTracking:
    def test_scene_has_active_mob_ids(self):
        class TestScene(Scene):
            def construct(self):
                pass

        scene = TestScene()
        tracked_scene = cast(Any, scene)
        assert hasattr(tracked_scene, "active_mob_ids")
        assert tracked_scene.active_mob_ids == set()

    def test_add_populates_active_mob_ids(self):
        class TestScene(Scene):
            def construct(self):
                pass

        scene = TestScene()
        circle = Circle()
        scene.add(circle)
        assert id(circle) in cast(Any, scene).active_mob_ids

    def test_remove_clears_active_mob_ids(self):
        class TestScene(Scene):
            def construct(self):
                pass

        scene = TestScene()
        circle = Circle()
        scene.add(circle)
        scene.remove(circle)
        assert id(circle) not in cast(Any, scene).active_mob_ids

    def test_add_vgroup_tracks_children(self):
        class TestScene(Scene):
            def construct(self):
                pass

        scene = TestScene()
        c1, c2 = Circle(), Circle()
        vg = VGroup(c1, c2)
        scene.add(vg)
        tracked = cast(Any, scene).active_mob_ids
        assert id(vg) in tracked
        assert id(c1) in tracked
        assert id(c2) in tracked

    def test_remove_vgroup_clears_children(self):
        class TestScene(Scene):
            def construct(self):
                pass

        scene = TestScene()
        c1, c2 = Circle(), Circle()
        vg = VGroup(c1, c2)
        scene.add(vg)
        scene.remove(vg)
        tracked = cast(Any, scene).active_mob_ids
        assert id(vg) not in tracked
        assert id(c1) not in tracked
        assert id(c2) not in tracked
