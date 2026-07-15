import {
  VMobject,
  VGroup,
  MathTexImage,
  ImageMobject,
  PMobject,
  THREE,
} from "manim-web";

// Apply contours + holes from a VMobject state onto a mob.
// Contours (CCW) and holes (CW) are concatenated into one flat points array;
// subpath lengths are recorded via setBaseSubpathLengths so the renderer
// can apply the correct fill rule per subpath.
export function applyContours(mob, state) {
  const subpaths = [
    ...(Array.isArray(state.contours) ? state.contours : []),
    ...(Array.isArray(state.holes) ? state.holes : []),
  ];
  if (subpaths.length === 0) return;

  const flat = [];
  const lengths = [];
  for (const sp of subpaths) {
    if (!Array.isArray(sp) || sp.length === 0) continue;
    if ((sp.length - 1) % 3 !== 0) {
      throw new Error(`Invalid contour length ${sp.length}: expected 3n+1.`);
    }
    flat.push(...sp);
    lengths.push(sp.length);
  }
  if (flat.length > 0) {
    mob.setPoints3D(flat);
    if (typeof mob.setBaseSubpathLengths === "function") {
      mob.setBaseSubpathLengths(lengths.length > 1 ? lengths : undefined);
    }
  }
}

export function applyState(mob, state) {
  if (!(mob instanceof VGroup) && typeof mob.setPoints3D === "function") {
    applyContours(mob, state);
  }
  if (typeof state.color === "string" && typeof mob.setColor === "function") {
    mob.setColor(state.color);
  }
  if (typeof state.fill_opacity === "number" && "fillOpacity" in mob) {
    mob.fillOpacity = state.fill_opacity;
  }
  if (typeof state.stroke_opacity === "number" && typeof mob.setStyle === "function") {
    mob.setStyle({ strokeOpacity: state.stroke_opacity });
  }
  if (typeof state.stroke_color === "string") {
    if (typeof mob.setColor === "function") {
      mob.setColor(state.stroke_color);
    }
    if ("strokeColor" in mob) {
      mob.strokeColor = state.stroke_color;
    }
  }
  if (typeof state.fill_color === "string" && "fillColor" in mob) {
    mob.fillColor = state.fill_color;
  }
  if (typeof state.stroke_width === "number" && "strokeWidth" in mob) {
    mob.strokeWidth = state.stroke_width;
  }
  if (typeof state.z_index === "number" && "zIndex" in mob) {
    mob.zIndex = state.z_index;
  }
}

export function applyBasisTransform(
  mob,
  origin,
  rightVec,
  upVec,
  center = origin,
  { uniformScale = false, baseBox = null, normalizeToBase = true } = {},
) {
  const right = new THREE.Vector3(rightVec[0], rightVec[1], rightVec[2]);
  const upRaw = new THREE.Vector3(upVec[0], upVec[1], upVec[2]);

  const rightLen = right.length();
  const upLen = upRaw.length();
  if (rightLen < 1e-9 || upLen < 1e-9) {
    throw new Error("Basis transform has a degenerate axis (zero edge length)");
  }

  const rightUnit = right.clone().normalize();
  const upProjected = upRaw
    .clone()
    .sub(rightUnit.clone().multiplyScalar(upRaw.dot(rightUnit)));
  const upProjectedLen = upProjected.length();
  if (upProjectedLen < 1e-9) {
    throw new Error("Basis transform axes are collinear; cannot orient object");
  }
  const upUnit = upProjected.multiplyScalar(1 / upProjectedLen);

  const nonOrtho = Math.abs(rightUnit.dot(upRaw.clone().normalize()));
  if (nonOrtho > 1e-3) {
    throw new Error(
      `Unsupported basis with shear (dot=${nonOrtho.toFixed(6)}). Expected near-orthogonal right/up axes.`,
    );
  }

  if (
    typeof mob.getBoundingBox === "function" &&
    typeof mob.scaleVector?.set === "function"
  ) {
    let sx;
    let sy;
    if (normalizeToBase) {
      const resolvedBaseBox =
        baseBox && typeof baseBox === "object" ? baseBox : mob.getBoundingBox();
      const w = resolvedBaseBox?.width || 1;
      const h = resolvedBaseBox?.height || 1;
      sx = rightLen / (w || 1);
      sy = upLen / (h || 1);
    } else {
      sx = rightLen;
      sy = upLen;
    }
    if (uniformScale) {
      const s = Math.sqrt(Math.max(sx, 1e-12) * Math.max(sy, 1e-12));
      mob.scaleVector.set(s, s, mob.scaleVector.z ?? 1);
    } else {
      mob.scaleVector.set(sx, sy, mob.scaleVector.z ?? 1);
    }
  }

  if (mob.rotation && typeof mob.rotation.setFromQuaternion === "function") {
    const xAxis = new THREE.Vector3(1, 0, 0);
    const yAxis = new THREE.Vector3(0, 1, 0);

    const q1 = new THREE.Quaternion().setFromUnitVectors(xAxis, rightUnit);
    const yAfterQ1 = yAxis.clone().applyQuaternion(q1);

    const cross = yAfterQ1.clone().cross(upUnit);
    const sin = cross.dot(rightUnit);
    const cos = yAfterQ1.dot(upUnit);
    const angle = Math.atan2(sin, cos);
    const q2 = new THREE.Quaternion().setFromAxisAngle(rightUnit, angle);

    const q = q2.multiply(q1);
    mob.rotation.setFromQuaternion(q);
  } else if (mob.rotation && typeof mob.rotation.set === "function") {
    const angle = Math.atan2(rightVec[1], rightVec[0]);
    mob.rotation.set(mob.rotation.x ?? 0, mob.rotation.y ?? 0, angle);
  }

  if (typeof mob.getCenter === "function" && typeof mob.shift === "function") {
    // FIXME: Translation can appear scale-dependent for MathTexImage after
    // basis scaling in manim-web. We currently apply center via shift delta;
    // investigate transform-order / world-vs-local translation semantics.
    const currentCenter = mob.getCenter();
    mob.shift([
      center[0] - currentCenter[0],
      center[1] - currentCenter[1],
      center[2] - currentCenter[2],
    ]);
  }

  if (typeof mob._markDirty === "function") {
    mob._markDirty();
  }
}

export function applyTexTransform(mob, points) {
  if (!points || points.length !== 4) return;
  const [topLeft, topRight, bottomRight, bottomLeft] = points;

  // Keep MathTex centered before applying shared basis transform.
  if (typeof mob.centerPointsAroundPosition === "function") {
    mob.centerPointsAroundPosition();
  }

  const rightVec = [
    (topRight[0] - topLeft[0]) / 2,
    (topRight[1] - topLeft[1]) / 2,
    (topRight[2] - topLeft[2]) / 2,
  ];
  const upVec = [
    (topLeft[0] - bottomLeft[0]) / 2,
    (topLeft[1] - bottomLeft[1]) / 2,
    (topLeft[2] - bottomLeft[2]) / 2,
  ];
  const center = [
    (topLeft[0] + bottomRight[0]) / 2,
    (topLeft[1] + bottomRight[1]) / 2,
    (topLeft[2] + bottomRight[2]) / 2,
  ];

  applyBasisTransform(mob, topLeft, rightVec, upVec, center, {
    uniformScale: true,
    baseBox: mob._baseTexBox || null,
    normalizeToBase: false,
  });
}

export async function waitForImageLoad(mob, timeoutMs = 1000) {
  if (typeof mob.waitForLoad !== "function") return true;
  try {
    await Promise.race([
      mob.waitForLoad(),
      new Promise((resolve) => setTimeout(resolve, timeoutMs)),
    ]);
    return true;
  } catch (error) {
    console.warn("Image load failed, continuing without blocking", error);
    return false;
  }
}

export async function applyImageCorners(mob, corners) {
  if (!corners || corners.length !== 4) return;

  // In headless test environments (happy-dom), image loading may never resolve.
  // Do not block playback forever.
  await waitForImageLoad(mob);

  const [ul, ur, dl] = corners;
  const rightVec = [ur[0] - ul[0], ur[1] - ul[1], ur[2] - ul[2]];
  const upVec = [ul[0] - dl[0], ul[1] - dl[1], ul[2] - dl[2]];
  const center = [
    dl[0] + rightVec[0] / 2 + upVec[0] / 2,
    dl[1] + rightVec[1] / 2 + upVec[1] / 2,
    dl[2] + rightVec[2] / 2 + upVec[2] / 2,
  ];

  applyBasisTransform(mob, ul, rightVec, upVec, center);
}

export function createMobjectFromState(state) {
  if (state.kind === "MathTexSource") {
    // Temporary fix: use 'katex' renderer to work around MathTex async
    // sizing issues with Create animation.
    // Ref: https://github.com/maloyan/manim-web/issues/324
    const opts = { latex: state.latex, renderer: "katex" };
    if (state.color) opts.color = state.color;
    // Do not use font size from state. MathTexSource.points already encode
    // geometry scale (unit square convention at font_size=48).
    const mob = new MathTexImage(opts);
    if (Array.isArray(state.points) && state.points.length === 4) {
      mob._pendingTransform = state.points;
    }
    return mob;
  }

  if (state.kind === "ImageMobject") {
    const opts = { source: state.source };
    if (state.opacity !== undefined) opts.opacity = state.opacity;
    const mob = new ImageMobject(opts);
    if (Array.isArray(state.points) && state.points.length === 4) {
      mob._pendingCorners = state.points;
    }
    return mob;
  }

  if (state.kind === "PMobject") {
    const positions = Array.isArray(state.points) ? state.points : [];
    const colors = Array.isArray(state.colors) ? state.colors : [];
    const opacities = Array.isArray(state.opacities) ? state.opacities : [];
    const points = positions.map((position, i) => {
      const point = { position };
      if (typeof colors[i] === "string") point.color = colors[i];
      if (typeof opacities[i] === "number") point.opacity = opacities[i];
      return point;
    });
    const opts = { points };
    if (typeof state.stroke_width === "number") opts.pointSize = state.stroke_width;
    return new PMobject(opts);
  }

  if (state.kind === "Group") {
    return new VGroup();
  }

  const mob = new VMobject();
  applyContours(mob, state);
  return mob;
}
