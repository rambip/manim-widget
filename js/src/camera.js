export function _vec3norm(v) {
  const len = Math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2);
  return len > 0 ? [v[0] / len, v[1] / len, v[2] / len] : v;
}

export function _vec3cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

export function apply2DCameraState(scene, points) {
  const [UL, UR, DR, DL] = points;
  const camera = scene.camera;
  if (!camera) return;
  const center = [(UL[0] + DR[0]) / 2, (UL[1] + DR[1]) / 2, (UL[2] + DR[2]) / 2];
  const frameWidth = Math.sqrt(
    (UR[0] - UL[0]) ** 2 + (UR[1] - UL[1]) ** 2 + (UR[2] - UL[2]) ** 2,
  );
  const frameHeight = Math.sqrt(
    (UL[0] - DL[0]) ** 2 + (UL[1] - DL[1]) ** 2 + (UL[2] - DL[2]) ** 2,
  );
  if (frameWidth > 0) camera.frameWidth = frameWidth;
  if (frameHeight > 0) camera.frameHeight = frameHeight;
  camera.moveTo([center[0], center[1], camera.position.z]);
  scene.render();
}

export function apply3DCameraState(scene, points, fd) {
  const [UL, UR, DR, DL] = points;
  const center = [(UL[0] + DR[0]) / 2, (UL[1] + DR[1]) / 2, (UL[2] + DR[2]) / 2];
  const right = _vec3norm([UR[0] - UL[0], UR[1] - UL[1], UR[2] - UL[2]]);
  const up = _vec3norm([UL[0] - DL[0], UL[1] - DL[1], UL[2] - DL[2]]);
  const camDir = _vec3cross(right, up);
  const phi = Math.acos(Math.max(-1, Math.min(1, camDir[2])));
  const theta = Math.atan2(camDir[1], camDir[0]);
  if (typeof scene.setCameraOrientation === "function") {
    scene.setCameraOrientation(phi, theta, fd);
  }
  if (typeof scene.setLookAt === "function") {
    scene.setLookAt(center);
  }
  const rectWidth = Math.sqrt(
    (UR[0] - UL[0]) ** 2 + (UR[1] - UL[1]) ** 2 + (UR[2] - UL[2]) ** 2,
  );
  if (rectWidth > 0 && scene.camera3D) {
    const fovDeg = (2 * Math.atan(rectWidth / (2 * fd)) * 180) / Math.PI;
    scene.camera3D.setFov(fovDeg);
  }
}

/** Apply a CameraState object (kind:"Camera", points, focal_distance) to the scene. */
export function applyCameraState(scene, state) {
  if (!state) return;
  if (state.kind === "OrbitState") {
    if (typeof scene.setCameraOrientation === "function") {
      scene.setCameraOrientation(state.phi, state.theta, state.distance);
    }
    if (typeof scene.setLookAt === "function" && state.target) {
      scene.setLookAt(state.target);
    }
    return;
  }
  if (state.kind !== "Camera") return;
  const { points, focal_distance } = state;
  if (!Array.isArray(points) || points.length < 4) return;
  const fd = focal_distance || 0;
  if (fd === 0) {
    apply2DCameraState(scene, points);
  } else {
    apply3DCameraState(scene, points, fd);
  }
}

export function getRateFunc(name) {
  switch (name) {
    case "linear": return (t) => t;
    case "rush_into": return (t) => 2 * t * t;
    case "rush_from": return (t) => 1 - 2 * (1 - t) * (1 - t);
    default: return (t) => t * t * (3 - 2 * t); // smooth
  }
}

export async function runCameraAnimation(scene, registry, fps, startState, endState, duration, rateFuncName = "smooth") {
  const rateFunc = getRateFunc(rateFuncName);
  const numFrames = Math.max(1, Math.ceil(duration * fps));
  const dt = (duration * 1000) / numFrames;
  for (let i = 1; i <= numFrames; i++) {
    const alpha = rateFunc(i / numFrames);
    const pts = startState.points.map((sp, pi) =>
      sp.map((sv, si) => sv + (endState.points[pi][si] - sv) * alpha),
    );
    const fd =
      (startState.focal_distance || 0) +
      ((endState.focal_distance || 0) - (startState.focal_distance || 0)) * alpha;
    applyCameraState(scene, { kind: "Camera", points: pts, focal_distance: fd });
    await new Promise((r) => setTimeout(r, dt));
  }
  registry.set("#camera", endState);
}
