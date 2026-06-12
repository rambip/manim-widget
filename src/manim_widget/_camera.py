from __future__ import annotations

import numpy as np
from manim import Scene
from manim.camera.moving_camera import MovingCamera
from manim.camera.three_d_camera import ThreeDCamera


def _needs_camera_loop(scene: Scene, animations: list) -> bool:
    """Return True when camera is being animated and needs per-frame capture."""
    cam = getattr(scene, "camera", None)
    if cam is None:
        return False

    cam_objects: set = {cam}

    if isinstance(cam, ThreeDCamera):
        for tracker in (
            cam.phi_tracker,
            cam.theta_tracker,
            cam.focal_distance_tracker,
            cam.gamma_tracker,
            cam.zoom_tracker,
        ):
            cam_objects.add(tracker)

    if isinstance(cam, MovingCamera):
        cam_objects.add(cam.frame)
        if cam.frame.updaters:
            return True

    return any(getattr(a, "mobject", None) in cam_objects for a in animations)


def _serialize_camera(
    cam, frame_width: float, frame_height: float
) -> tuple[list[list[float]], float]:
    """Return (4-corner points [UL,UR,DR,DL], focal_distance) for any camera."""
    if isinstance(cam, MovingCamera):
        # get_vertices() returns [UR, UL, DL, DR]; reorder to [UL, UR, DR, DL]
        verts = cam.frame.get_vertices()
        return [
            verts[1].tolist(),
            verts[0].tolist(),
            verts[3].tolist(),
            verts[2].tolist(),
        ], 0.0

    if isinstance(cam, ThreeDCamera):
        rot = cam.generate_rotation_matrix()
        right = rot[0, :]
        up = rot[1, :]
        center = np.array(cam.frame_center, dtype=float)
        zoom = float(cam.get_zoom())
        hw = (frame_width / zoom) / 2
        hh = (frame_height / zoom) / 2
        return [
            (center - hw * right + hh * up).tolist(),
            (center + hw * right + hh * up).tolist(),
            (center + hw * right - hh * up).tolist(),
            (center - hw * right - hh * up).tolist(),
        ], float(cam.get_focal_distance())

    hw = frame_width / 2
    hh = frame_height / 2
    return [[-hw, hh, 0], [hw, hh, 0], [hw, -hh, 0], [-hw, -hh, 0]], 0.0
