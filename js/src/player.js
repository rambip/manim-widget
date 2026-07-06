import { Transform, Swap, CyclicReplace, VMobject } from "manim-web";
import { applyCameraState, getRateFunc, runCameraAnimation } from "./camera.js";
import { applyContours, applyState, applyTexTransform, applyImageCorners, createMobjectFromState } from "./mob.js";
import { buildSimpleAnimation } from "./anim.js";

export class Player {
  constructor(scene, registry) {
    this._scene = scene;
    this._registry = registry;
    this._sections = [];
    this._states = [];
    this._fps = 10;
    this._isPlaying = false;
    this._currentSectionIndex = 0;
    // state_ref → mob[] — populated during register commands, used by updateStates
    this._stateRefToMobs = new Map();
    this._warnings = [];
  }

  setfps(fps) {
    this._fps = fps;
  }

  setSections(sections) {
    this._sections = Array.isArray(sections) ? sections : [];
  }

  setStates(states) {
    this._states = Array.isArray(states) ? states : [];
    this._warnings = [];
    for (let i = 0; i < this._states.length; i++) {
      const entry = this._states[i];
      if (entry && entry.kind === "Derived" && entry.from >= i) {
        const msg =
          `Derived state chain built out of order: state #${i} derives from #${entry.from}, ` +
          `but 'from' must be strictly less than the entry's own index. ` +
          `Only updater frame compression and image placement splits should create Derived states.`;
        console.warn(msg);
        this._warnings.push({ kind: "derived_out_of_order", index: i, from: entry.from, message: msg });
      }
    }
  }

  /** Re-apply mutated states to all registered mobs without replaying commands. */
  updateStates(states) {
    this._states = states;
    for (const [stateRef, mobs] of this._stateRefToMobs.entries()) {
      const state = states[stateRef];
      if (!state) continue;
      for (const mob of mobs) {
        applyState(mob, state);
        applyContours(mob, state);
      }
    }
    this._scene.render();
  }

  /**
   * Thin delegation kept so wireSharedCamera in index.js can monkey-patch this
   * method to intercept and broadcast camera state changes.
   */
  _applyCameraState(state) {
    applyCameraState(this._scene, state);
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

  /** Wipe all mobjects from the canvas without restoring or playing a section. */
  clearScene() {
    this._scene.clear();
    this._registry.clear();
  }

  async seekToSection(index) {
    this._currentSectionIndex = index;
    if (index >= 0 && index < this._sections.length) {
      await this._playSection(this._sections[index]);
    }
  }

  _stateFromRef(section, stateRef) {
    const states = this._states;
    if (!Array.isArray(states)) {
      throw new Error("Player is missing global states array");
    }
    if (!Number.isInteger(stateRef) || stateRef < 0 || stateRef >= states.length) {
      throw new Error(`Invalid state_ref: ${stateRef}`);
    }
    const entry = states[stateRef];
    if (entry && entry.kind === "Derived") {
      const parent = states[entry.from];
      if (parent) {
        const { kind: _, from: __, ...rest } = entry;
        return { ...parent, ...rest };
      }
    }
    return entry;
  }

  _instantiateFromRef(section, stateRef) {
    const state = this._stateFromRef(section, stateRef);
    const mob = createMobjectFromState(state);
    applyState(mob, state);
    if (state.kind === "Group") {
      if (Array.isArray(state.points) && state.points.length > 0) {
        const bodyMob = new VMobject();
        applyState(bodyMob, state);
        mob.add(bodyMob);
      }
      if (Array.isArray(state.children) && state.children.length > 0) {
        for (const childRef of state.children) {
          const child = this._instantiateFromRef(section, childRef);
          mob.add(child);
        }
      }
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
        applyState(mob, state);
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
      applyTexTransform(mob, mob._pendingTransform);
      delete mob._pendingTransform;
    }
    if (mob._pendingCorners) {
      await applyImageCorners(mob, mob._pendingCorners);
      delete mob._pendingCorners;
    }
  }

  /**
   * Pin/unpin a mobject on the camera-relative HUD per its state's `fixed`
   * flag. Idempotent — safe to call on every register/snapshot-restore
   * regardless of whether fixed status actually changed, and regardless of
   * whether the mobject is already in the scene: manim-web's
   * addFixedInFrameMobjects() only records intent for a not-yet-added
   * mobject and resolves the actual HUD placement once its introducing
   * animation adds it (#505). No-ops on scenes (plain 2D `Scene`) that
   * don't expose these methods.
   */
  _syncFixed(mob, state) {
    const scene = this._scene;
    if (state?.fixed === "frame") {
      scene.addFixedInFrameMobjects?.(mob);
    } else if (state?.fixed === "orientation") {
      scene.addFixedOrientationMobjects?.(mob);
    } else {
      scene.removeFixedInFrameMobjects?.(mob);
      scene.removeFixedOrientationMobjects?.(mob);
    }
  }

  async _restoreSnapshot(snapshot, section) {
    for (const [id, value] of Object.entries(snapshot)) {
      if (id === "#camera") {
        const state = this._stateFromRef(section, value);
        this._applyCameraState(state);
        this._registry.set("#camera", state);
        continue;
      }
      const state = this._stateFromRef(section, value);
      const mob = this._instantiateFromRef(section, value);
      this._registry.set(id, mob);
      await this._finalizeMobject(mob, state);
      this._scene.add(mob);
      this._syncFixed(mob, state);
    }
  }

  async _playSection(section) {
    if (!section || section.unsupported) {
      return;
    }

    this._scene.clear();
    this._registry.clear();
    await this._restoreSnapshot(section.snapshot || {}, section);

    const commands = Array.isArray(section.construct) ? section.construct : [];
    for (const cmd of commands) {
      await this._executeCommand(cmd, section);
    }
  }

  async _executeCommand(cmd, section) {
    switch (cmd?.cmd) {
      case "register": {
        if (cmd.id === "#camera") {
          const state = this._stateFromRef(section, cmd.state_ref);
          this._applyCameraState(state);
          this._registry.set("#camera", state);
          return;
        }
        const state = this._stateFromRef(section, cmd.state_ref);

        // `register` is create-or-update: an id already in the registry means
        // this is a live mobject whose state pointer moved (e.g. a
        // add_fixed_in_frame_mobjects toggle) — update it in place rather
        // than recreating, so we don't lose its position in the scene graph.
        const existing = this._registry.get(cmd.id);
        if (existing) {
          applyState(existing, state);
          if (!this._stateRefToMobs.has(cmd.state_ref)) {
            this._stateRefToMobs.set(cmd.state_ref, []);
          }
          this._stateRefToMobs.get(cmd.state_ref).push(existing);
          this._syncFixed(existing, state);
          return;
        }

        let mob;
        if (Array.isArray(cmd.child_ids) && cmd.child_ids.length > 0) {
          // Children are already registered; create mob without adding state.children,
          // then wire the pre-registered children in order.
          mob = createMobjectFromState(state);
          applyState(mob, state);
          for (const cid of cmd.child_ids) {
            mob.add(this._registry.get(cid));
          }
        } else {
          mob = this._instantiateFromRef(section, cmd.state_ref);
        }
        this._registry.set(cmd.id, mob);
        if (!this._stateRefToMobs.has(cmd.state_ref)) {
          this._stateRefToMobs.set(cmd.state_ref, []);
        }
        this._stateRefToMobs.get(cmd.state_ref).push(mob);
        // Do NOT add to scene here — introducing animations (Add, FadeIn,
        // Create, …) handle that themselves. Adding here causes a visible
        // flash before the animation resets opacity to 0. Fixed-status
        // syncing is safe before the mob lands in the scene: manim-web's
        // Scene.add() no longer reparents already-pinned mobjects out of
        // the HUD scene (fixed upstream, #505).
        await this._finalizeMobject(mob, state);
        this._syncFixed(mob, state);
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
      case "move_camera": {
        const state = this._stateFromRef(section, cmd.state_ref);
        this._applyCameraState(state);
        return;
      }
      case "updater": {
        // Ensure all mobs referenced by updater frames are in the scene.
        // These may have been registered without an introducing animation
        // (e.g. always_redraw mobs added via self.add).
        for (const frame of (cmd.frames || [])) {
          for (const id of Object.keys(frame)) {
            if (id === "#camera") continue;
            const mob = this._registry.get(id);
            if (mob && !this._scene.mobjects.has(mob)) {
              this._scene.add(mob);
            }
          }
          break; // only need to check first frame
        }
        await this._playUpdater(cmd, section);
        return;
      }
      default:
        console.warn(`Unknown command: ${cmd?.cmd}`);
    }
  }

  async _buildAnimation(desc, section) {
    if (!desc || typeof desc !== "object") return null;
    if (desc.kind === "Wait") return null;

    if ("state_ref" in desc) {
      const mob = this._registry.get(desc.id);
      if (!mob) throw new Error(`Mobject not found: ${desc.id}`);
      const targetState = this._stateFromRef(section, desc.state_ref);
      const target = this._instantiateFromRef(section, desc.state_ref);
      await this._finalizeMobject(target, targetState);
      const animation = new Transform(mob, target);
      this._applyDescriptorRateFunc(animation, desc);
      return animation;
    }

    if ("ids" in desc) {
      const params = desc.params || {};
      const mobjects = desc.ids.map((id) => this._registry.get(id)).filter(Boolean);
      if (mobjects.length < 2) {
        console.warn(`${desc.kind} requires at least 2 mobjects, found ${mobjects.length}`);
        return null;
      }
      const options = { pathArc: params.path_arc };
      if (desc.kind === "Swap") {
        if (mobjects.length !== 2) {
          console.warn(`Swap requires exactly 2 mobjects, found ${mobjects.length}`);
          return null;
        }
        const animation = new Swap(mobjects[0], mobjects[1], options);
        this._applyDescriptorRateFunc(animation, desc);
        return animation;
      }
      if (desc.kind === "CyclicReplace") {
        const animation = new CyclicReplace(mobjects, options);
        this._applyDescriptorRateFunc(animation, desc);
        return animation;
      }
      console.warn(`Unsupported group animation: ${desc.kind}`);
      return null;
    }

    const mob = this._registry.get(desc.id);
    if (!mob) throw new Error(`Mobject not found: ${desc.id}`);
    const animation = buildSimpleAnimation(mob, desc, this._registry);
    this._applyDescriptorRateFunc(animation, desc);
    return animation;
  }

  _applyDescriptorRateFunc(animation, desc) {
    if (!animation || !desc?.rate_func) return;
    Object.defineProperty(animation, "rateFunc", {
      value: getRateFunc(desc.rate_func, desc.rate_func_params || {}),
      writable: true,
      configurable: true,
    });
  }

  async _playAnimate(cmd, section) {
    const descriptors = Array.isArray(cmd.animations) ? cmd.animations : [];
    const cmdDuration = typeof cmd.duration === "number" ? cmd.duration : 1;

    const cameraDescs = descriptors.filter((d) => d.id === "#camera" && "state_ref" in d);
    const nonCameraDescs = descriptors.filter((d) => d.id !== "#camera");

    const hasTimestamps = nonCameraDescs.some(
      (d) => d.start !== undefined || d.end !== undefined,
    );

    const runRegular = async () => {
      if (hasTimestamps) {
        const entries = [];
        for (const desc of nonCameraDescs) {
          if (desc.kind === "Wait") continue;
          const animation = await this._buildAnimation(desc, section);
          if (animation) {
            entries.push({ animation, start: desc.start ?? 0, end: desc.end ?? cmdDuration });
          }
        }
        if (entries.length > 0) {
          await this._scene.playWithTimestamps(entries);
        }
        return;
      }

      const animations = [];
      for (const desc of nonCameraDescs) {
        if (desc.kind === "Wait") {
          if (animations.length > 0) {
            await this._scene.play(...animations);
            animations.length = 0;
          }
          await this._scene.wait(cmdDuration);
          continue;
        }
        const animation = await this._buildAnimation(desc, section);
        if (animation) animations.push(animation);
      }
      if (animations.length > 0) {
        for (const anim of animations) {
          Object.defineProperty(anim, "duration", {
            value: cmdDuration,
            writable: true,
            configurable: true,
          });
        }
        await this._scene.play(...animations);
      }
    };

    const runCamera = async () => {
      for (const desc of cameraDescs) {
        const startState = this._registry.get("#camera");
        const endState = this._stateFromRef(section, desc.state_ref);
        if (startState && endState) {
          await runCameraAnimation(
            this._scene,
            this._registry,
            this._fps,
            startState,
            endState,
            cmdDuration,
            desc.rate_func,
            desc.rate_func_params || {},
          );
        }
      }
    };

    await Promise.all([runRegular(), runCamera()]);
  }

  async _playUpdater(cmd, section) {
    const frames = Array.isArray(cmd.frames) ? cmd.frames : [];
    const numFrames = frames.length;
    if (numFrames === 0) return;

    const duration = typeof cmd.duration === "number" ? cmd.duration : 0;
    const frameDuration = duration / numFrames;

    for (let i = 0; i < numFrames; i++) {
      for (const [id, frameEntry] of Object.entries(frames[i])) {
        if (id === "#camera") {
          const state = this._stateFromRef(section, frameEntry.state_ref);
          this._applyCameraState(state);
          this._registry.set("#camera", state);
          continue;
        }
        const mob = this._registry.get(id);
        if (!mob) continue;
        const state = this._stateFromRef(section, frameEntry.state_ref);
        applyState(mob, state);
      }
      await this._scene.wait(frameDuration);
    }
  }
}

export function createPlayer(scene, registry) {
  return new Player(scene, registry);
}
