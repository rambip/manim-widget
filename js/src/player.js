import {
  Add,
  Create,
  FadeIn,
  FadeOut,
  Rotate,
  ScaleInPlace,
  Transform,
  Swap,
  CyclicReplace,
  VMobject,
  VGroup,
  Write,
  GrowFromCenter,
  GrowArrow,
  MoveAlongPath,
  Rotating,
  MathTexImage,
  ImageMobject,
  Arrow,
} from "manim-web";
import * as THREE from "three";

function buildSimpleAnimation(mob, desc, registry) {
  const params = desc.params || {};
  switch (desc.kind) {
    case "Add":
      return new Add(mob);
    case "Create":
      return new Create(mob);
    case "FadeIn":
      return new FadeIn(mob);
    case "FadeOut":
      return new FadeOut(mob);
    case "Write":
      return new Write(mob);
    case "Rotate":
      return new Rotate(mob, {
        angle: params.angle ?? 0,
        axis: params.axis,
        aboutPoint: params.aboutPoint ?? params.about_point,
      });
    case "ScaleInPlace":
      return new ScaleInPlace(mob, {
        scaleFactor: params.scaleFactor ?? params.scale_factor ?? 1,
      });
    case "GrowFromCenter":
      return new GrowFromCenter(mob);
    case "GrowArrow":
      return new GrowArrow(mob);
    case "Rotating":
      return new Rotating(mob, {
        aboutPoint: params.aboutPoint ?? params.about_point,
      });
    case "MoveAlongPath":
      if (!registry || !params.path_id) {
        console.warn("MoveAlongPath missing path_id or registry");
        return null;
      }
      const path = registry.get(params.path_id);
      if (!path) {
        console.warn(`MoveAlongPath path mobject not found: ${params.path_id}`);
        return null;
      }
      return new MoveAlongPath(mob, { path });
    default:
      console.warn(`Unsupported simple animation kind: ${desc.kind}`);
      return null;
  }
}

export class Player {
  constructor(scene, registry) {
    this._scene = scene;
    this._registry = registry;
    this._sections = [];
    this._fps = 10;
    this._isPlaying = false;
    this._currentSectionIndex = 0;
  }

  setfps(fps) {
    this._fps = fps;
  }

  setSections(sections) {
    this._sections = Array.isArray(sections) ? sections : [];
  }

  get isPlaying() {
    return this._isPlaying;
  }

  async play() {
    this._isPlaying = true;
  }

  async pause() {
    this._isPlaying = false;
  }

  async stop() {
    this._isPlaying = false;
    this._currentSectionIndex = 0;
  }

  async seekToSection(index) {
    this._currentSectionIndex = index;
    if (index >= 0 && index < this._sections.length) {
      await this._playSection(this._sections[index]);
    }
  }

  _stateFromRef(section, stateRef) {
    const states = section?.states;
    if (!Array.isArray(states)) {
      throw new Error("Section is missing states array");
    }
    if (
      !Number.isInteger(stateRef) ||
      stateRef < 0 ||
      stateRef >= states.length
    ) {
      throw new Error(`Invalid state_ref: ${stateRef}`);
    }
    return states[stateRef];
  }

  _createMobjectFromState(state) {
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

    if (state.kind === "VGroup") {
      return new VGroup();
    }

    if (state.kind === "Arrow") {
      // Create dummy Arrow; shaft/tip content replaced in _instantiateFromRef
      return new Arrow();
    }

    const mob = new VMobject();
    if (Array.isArray(state.points) && state.points.length > 0) {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(
          `Invalid points array length: ${state.points.length}. Expected 3n+1.`,
        );
      }
      mob.setPoints3D(state.points);
    }
    return mob;
  }

  _applyState(mob, state) {
    if (
      !(mob instanceof VGroup) &&
      Array.isArray(state.points) &&
      state.points.length > 0 &&
      typeof mob.setPoints3D === "function"
    ) {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(
          `Invalid points array length: ${state.points.length}. Expected 3n+1.`,
        );
      }
      mob.setPoints3D(state.points);
    }

    if (typeof state.color === "string" && typeof mob.setColor === "function") {
      mob.setColor(state.color);
    }
    if (typeof state.fill_opacity === "number" && "fillOpacity" in mob) {
      mob.fillOpacity = state.fill_opacity;
    }
    if (
      typeof state.stroke_opacity === "number" &&
      typeof mob.setStyle === "function"
    ) {
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

  _applyBasisTransform(
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
      throw new Error(
        "Basis transform has a degenerate axis (zero edge length)",
      );
    }

    const rightUnit = right.clone().normalize();
    const upProjected = upRaw
      .clone()
      .sub(rightUnit.clone().multiplyScalar(upRaw.dot(rightUnit)));
    const upProjectedLen = upProjected.length();
    if (upProjectedLen < 1e-9) {
      throw new Error(
        "Basis transform axes are collinear; cannot orient object",
      );
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
          baseBox && typeof baseBox === "object"
            ? baseBox
            : mob.getBoundingBox();
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

    if (
      typeof mob.getCenter === "function" &&
      typeof mob.shift === "function"
    ) {
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

  _applyTexTransform(mob, points) {
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

    this._applyBasisTransform(mob, topLeft, rightVec, upVec, center, {
      uniformScale: true,
      baseBox: mob._baseTexBox || null,
      normalizeToBase: false,
    });
  }

  async _waitForImageLoad(mob, timeoutMs = 1000) {
    if (typeof mob.waitForLoad !== "function") {
      return true;
    }

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

  async _applyImageCorners(mob, corners) {
    if (!corners || corners.length !== 4) return;

    // In headless test environments (happy-dom), image loading may never resolve.
    // Do not block playback forever.
    await this._waitForImageLoad(mob);

    // Corners are [UL, UR, DL, DR]
    const [ul, ur, dl] = corners;

    const rightVec = [ur[0] - ul[0], ur[1] - ul[1], ur[2] - ul[2]];
    const upVec = [ul[0] - dl[0], ul[1] - dl[1], ul[2] - dl[2]];

    const center = [
      dl[0] + rightVec[0] / 2 + upVec[0] / 2,
      dl[1] + rightVec[1] / 2 + upVec[1] / 2,
      dl[2] + rightVec[2] / 2 + upVec[2] / 2,
    ];

    this._applyBasisTransform(mob, ul, rightVec, upVec, center);
  }

  _instantiateFromRef(section, stateRef) {
    const state = this._stateFromRef(section, stateRef);
    const mob = this._createMobjectFromState(state);
    this._applyState(mob, state);
    if (state.kind === "VGroup") {
      if (Array.isArray(state.points) && state.points.length > 0) {
        const bodyMob = new VMobject();
        this._applyState(bodyMob, state);
        mob.add(bodyMob);
      }
      if (Array.isArray(state.children) && state.children.length > 0) {
        for (const childRef of state.children) {
          const child = this._instantiateFromRef(section, childRef);
          mob.add(child);
        }
      }
    }
    if (state.kind === "Arrow") {
      const shaftPoints = Array.isArray(state.points) ? state.points : [];
      const tipState =
        Array.isArray(state.children) && state.children.length > 0
          ? this._stateFromRef(section, state.children[0])
          : null;
      const tipPoints = Array.isArray(tipState?.points) ? tipState.points : [];

      const start = shaftPoints.length > 0 ? shaftPoints[0] : [0, 0, 0];
      const shaftEnd = shaftPoints.length > 0 ? shaftPoints[shaftPoints.length - 1] : null;

      // Find the apex: the tip point farthest along the shaft direction.
      // tipPoints[0] is a base corner, not the apex — point order varies.
      const dir = shaftEnd
        ? [shaftEnd[0] - start[0], shaftEnd[1] - start[1], shaftEnd[2] - start[2]]
        : [1, 0, 0];
      const end =
        tipPoints.length > 0
          ? tipPoints.reduce(
              (best, p) => {
                const d = p[0] * dir[0] + p[1] * dir[1] + p[2] * dir[2];
                return d > best.d ? { p, d } : best;
              },
              { p: tipPoints[0], d: -Infinity },
            ).p
          : [1, 0, 0];
      const tipLength =
        shaftEnd && tipPoints.length > 0
          ? Math.hypot(
              end[0] - shaftEnd[0],
              end[1] - shaftEnd[1],
              end[2] - shaftEnd[2],
            )
          : undefined;

      const tipWidth =
        shaftEnd && tipPoints.length > 0
          ? (() => {
              const axis = [end[0] - start[0], end[1] - start[1], end[2] - start[2]];
              const axisLen = Math.hypot(axis[0], axis[1], axis[2]);
              if (axisLen <= 1e-9) return undefined;
              const u = [axis[0] / axisLen, axis[1] / axisLen, axis[2] / axisLen];

              // tipWidth convention in Arrow: perpendicular offset from tip-base center.
              // shaftEnd is tip-base center for canonical serialized arrows.
              return Math.max(
                ...tipPoints.map((p) => {
                  const v = [p[0] - shaftEnd[0], p[1] - shaftEnd[1], p[2] - shaftEnd[2]];
                  const parallel = v[0] * u[0] + v[1] * u[1] + v[2] * u[2];
                  const perp = [
                    v[0] - parallel * u[0],
                    v[1] - parallel * u[1],
                    v[2] - parallel * u[2],
                  ];
                  return Math.hypot(perp[0], perp[1], perp[2]);
                }),
              );
            })()
          : undefined;

      const arrow = new Arrow({
        start,
        end,
        color: state.stroke_color,
        strokeWidth: state.stroke_width,
        ...(typeof tipLength === "number" && tipLength > 0 ? { tipLength } : {}),
        ...(typeof tipWidth === "number" && tipWidth > 0 ? { tipWidth } : {}),
      });
      this._applyState(arrow, state);
      return arrow;
    }
    return mob;
  }

  async _finalizeMobject(mob, state) {
    if (!mob) return;

    // Finalize children first so nested async/textured mobjects are fully
    // mutated before their parent is attached to the scene.
    if (Array.isArray(mob.submobjects) && mob.submobjects.length > 0) {
      for (const child of mob.submobjects) {
        await this._finalizeMobject(child, null);
      }
    }

    if (typeof mob.waitForRender === "function") {
      await mob.waitForRender();
      if (state) {
        this._applyState(mob, state);
      }
      if (
        state?.kind === "MathTexSource" &&
        !mob._baseTexBox &&
        typeof mob.getBoundingBox === "function"
      ) {
        const box = mob.getBoundingBox();
        if (box?.width > 0 && box?.height > 0) {
          mob._baseTexBox = { width: box.width, height: box.height };
        }
      }
    }
    if (mob._pendingTransform) {
      this._applyTexTransform(mob, mob._pendingTransform);
      delete mob._pendingTransform;
    }
    if (mob._pendingCorners) {
      await this._applyImageCorners(mob, mob._pendingCorners);
      delete mob._pendingCorners;
    }
  }

  async _restoreSnapshot(snapshot, section) {
    for (const [id, stateRef] of Object.entries(snapshot)) {
      const state = this._stateFromRef(section, stateRef);
      const mob = this._instantiateFromRef(section, stateRef);
      this._registry.set(id, mob);
      await this._finalizeMobject(mob, state);
      this._scene.add(mob);
    }
  }

  async _playSection(section) {
    if (!section || section.unsupported) {
      return;
    }

    this._scene.clear();
    this._registry.clear();
    await this._restoreSnapshot(section.snapshot || {}, section);

    // Set initial camera state for section (3D scenes only)
    if (
      section.camera &&
      typeof this._scene.setCameraOrientation === "function"
    ) {
      const { phi, theta, distance, fov } = section.camera;
      this._scene.setCameraOrientation(phi, theta, distance);
      if (fov !== undefined && this._scene.camera3D) {
        this._scene.camera3D.setFov(fov);
      }
    }

    const commands = Array.isArray(section.construct) ? section.construct : [];
    for (const cmd of commands) {
      await this._executeCommand(cmd, section);
    }

  }

  async _executeCommand(cmd, section) {
    switch (cmd?.cmd) {
      case "register": {
        const state = this._stateFromRef(section, cmd.state_ref);
        const mob = this._instantiateFromRef(section, cmd.state_ref);
        this._registry.set(cmd.id, mob);
        await this._finalizeMobject(mob, state);
        return;
      }
      case "remove": {
        const mob = this._registry.get(cmd.id);
        if (mob) {
          this._scene.remove(mob);
          this._registry.delete(cmd.id);
        }
        return;
      }
      case "rebind": {
        this._registry.rebind(cmd.source_id, cmd.target_id);
        return;
      }
      case "animate": {
        await this._playAnimate(cmd, section);
        return;
      }
      case "updater": {
        await this._playUpdater(cmd, section);
        return;
      }
      default:
        console.warn(`Unknown command: ${cmd?.cmd}`);
    }
  }

  async _buildAnimation(desc, section) {
    if (!desc || typeof desc !== "object") {
      return null;
    }

    if (desc.kind === "Wait") {
      return null;
    }

    if ("state_ref" in desc) {
      const mob = this._registry.get(desc.id);
      if (!mob) {
        throw new Error(`Mobject not found: ${desc.id}`);
      }
      const targetState = this._stateFromRef(section, desc.state_ref);
      const target = this._instantiateFromRef(section, desc.state_ref);
      await this._finalizeMobject(target, targetState);
      return new Transform(mob, target);
    }

    if ("ids" in desc) {
      const params = desc.params || {};
      const mobjects = desc.ids
        .map((id) => this._registry.get(id))
        .filter(Boolean);
      if (mobjects.length < 2) {
        console.warn(
          `${desc.kind} requires at least 2 mobjects, found ${mobjects.length}`,
        );
        return null;
      }
      const options = {
        pathArc: params.path_arc,
      };
      if (desc.kind === "Swap") {
        if (mobjects.length !== 2) {
          console.warn(
            `Swap requires exactly 2 mobjects, found ${mobjects.length}`,
          );
          return null;
        }
        return new Swap(mobjects[0], mobjects[1], options);
      }
      if (desc.kind === "CyclicReplace") {
        return new CyclicReplace(mobjects, options);
      }
      console.warn(`Unsupported group animation: ${desc.kind}`);
      return null;
    }

    const mob = this._registry.get(desc.id);
    if (!mob) {
      throw new Error(`Mobject not found: ${desc.id}`);
    }

    return buildSimpleAnimation(mob, desc, this._registry);
  }

  async _playAnimate(cmd, section) {
    const descriptors = Array.isArray(cmd.animations) ? cmd.animations : [];
    const cmdDuration = typeof cmd.duration === "number" ? cmd.duration : 1;

    // Check if any descriptor carries explicit start/end timestamps.
    const hasTimestamps = descriptors.some(
      (d) => d.start !== undefined || d.end !== undefined,
    );

    if (hasTimestamps) {
      const entries = [];
      for (const desc of descriptors) {
        if (desc.kind === "Wait") continue;
        const animation = await this._buildAnimation(desc, section);
        if (animation) {
          entries.push({
            animation,
            start: desc.start ?? 0,
            end: desc.end ?? cmdDuration,
          });
        }
      }
      if (entries.length > 0) {
        await this._scene.playWithTimestamps(entries);
      }
      return;
    }

    const animations = [];
    for (const desc of descriptors) {
      if (desc.kind === "Wait") {
        // Wait needs to be handled separately - play accumulated animations first
        if (animations.length > 0) {
          await this._scene.play(...animations);
          animations.length = 0;
        }
        await this._scene.wait(cmdDuration);
        continue;
      }
      const animation = await this._buildAnimation(desc, section);
      if (animation) {
        animations.push(animation);
      }
    }

    // Play all accumulated animations together
    if (animations.length > 0) {
      await this._scene.play(...animations);
    }
  }

  async _playUpdater(cmd, section) {
    const frames = Array.isArray(cmd.frames) ? cmd.frames : [];
    const cameraUpdates = Array.isArray(cmd.camera_updates)
      ? cmd.camera_updates
      : [];
    const hasCameraUpdates = cameraUpdates.length > 0;
    const numFrames = Math.max(frames.length, cameraUpdates.length);

    if (numFrames === 0) {
      return;
    }

    const duration = typeof cmd.duration === "number" ? cmd.duration : 0;
    const frameDuration = duration / numFrames;

    for (let i = 0; i < numFrames; i++) {
      // Apply mobject frame
      if (i < frames.length) {
        for (const [id, frameEntry] of Object.entries(frames[i])) {
          const mob = this._registry.get(id);
          if (!mob) {
            continue;
          }
          const state = this._stateFromRef(section, frameEntry.state_ref);
          this._applyState(mob, state);
        }
      }

      // Apply camera frame
      if (hasCameraUpdates && i < cameraUpdates.length) {
        const cam = cameraUpdates[i];
        if (typeof this._scene.setCameraOrientation === "function") {
          this._scene.setCameraOrientation(cam.phi, cam.theta, cam.distance);
          if (cam.fov !== undefined && this._scene.camera3D) {
            this._scene.camera3D.setFov(cam.fov);
          }
        }
      }

      await this._scene.wait(frameDuration);
    }
  }
}

export function createPlayer(scene, registry) {
  return new Player(scene, registry);
}
