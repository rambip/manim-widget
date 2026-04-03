import {
  Create,
  FadeIn,
  FadeOut,
  Rotate,
  ScaleInPlace,
  Scene,
  Shift,
  Transform,
  VMobject,
  VGroup,
  Write,
} from "manim-web";

const SIMPLE_ANIM_BUILDERS = {
  Create: (mob) => new Create(mob),
  FadeIn: (mob) => new FadeIn(mob),
  FadeOut: (mob) => new FadeOut(mob),
  Write: (mob) => new Write(mob),
  Rotate: (mob, params) => new Rotate(mob, params?.angle, params?.axis),
  ScaleInPlace: (mob, params) => new ScaleInPlace(mob, params?.scale_factor),
};

export class Player {
  constructor(scene, registry) {
    this._scene = scene;
    this._registry = registry;
    this._sections = [];
    this._fps = 10;
    this._isPlaying = false;
    this._currentSectionIndex = 0;
    this._onSectionChange = null;
  }

  setfps(fps) {
    this._fps = fps;
  }

  setSections(sections) {
    this._sections = Array.isArray(sections) ? sections : [];
  }

  setOnSectionChange(callback) {
    this._onSectionChange = callback;
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

  async seekToSection(index) {
    this._currentSectionIndex = index;
    if (index >= 0 && index < this._sections.length) {
      await this._playSection(this._sections[index]);
    }
  }

  async _playSection(section) {
    if (!section) {
      return;
    }

    if (section.unsupported) {
      const reason = section.unsupported_reason || section.reason || "unknown reason";
      console.warn(`Section \"${section.name}\" is unsupported: ${reason}`);
      return;
    }

    this._scene.clear();
    this._registry.clear();

    this._restoreSnapshot(section.snapshot || {}, section);

    const commands = Array.isArray(section.construct) ? section.construct : [];
    for (const cmd of commands) {
      await this._executeCommand(cmd, section);
    }
  }

  _stateFromRef(section, stateRef) {
    const states = section?.states;
    if (!Array.isArray(states)) {
      throw new Error("Section is missing states array");
    }
    if (!Number.isInteger(stateRef) || stateRef < 0 || stateRef >= states.length) {
      throw new Error(`Invalid state_ref: ${stateRef}`);
    }
    return states[stateRef];
  }

  _restoreSnapshot(snapshot, section) {
    const vgroupChildren = [];

    for (const [id, state] of Object.entries(snapshot)) {
      const mob = this._ensureMobject(id, state);
      this._applyState(mob, state);
      this._scene.add(mob);
      if (state.kind === "VGroup" && Array.isArray(state.children)) {
        vgroupChildren.push([id, state.children]);
      }
    }

    for (const [parentId, childStateRefs] of vgroupChildren) {
      const parent = this._registry.get(parentId);
      this._attachVGroupChildren(parent, childStateRefs, section);
    }
  }

  _attachVGroupChildren(parent, childStateRefs, section) {
    if (!parent || typeof parent.add !== "function") {
      return;
    }
    if (!Array.isArray(childStateRefs) || childStateRefs.length === 0) {
      return;
    }
    const existingCount = Array.isArray(parent.submobjects) ? parent.submobjects.length : 0;
    if (existingCount > 0) {
      return;
    }

    for (const childStateRef of childStateRefs) {
      const childState = this._stateFromRef(section, childStateRef);
      const child = this._createMobjectFromState(childState);
      this._applyState(child, childState);
      parent.add(child);
    }
  }

  _ensureMobject(id, state) {
    const existing = this._registry.get(id);
    if (existing) {
      return existing;
    }

    const mob = this._createMobjectFromState(state);
    this._registry.set(id, mob);
    return mob;
  }

  _createMobjectFromState(state) {
    if (state?.kind === "VGroup") {
      return new VGroup();
    }

    const mob = new VMobject();
    if (Array.isArray(state?.points) && state.points.length > 0) {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(
          `Invalid points array length: ${state.points.length}. Expected 3n+1.`
        );
      }
      mob.setPoints3D(state.points);
    }
    return mob;
  }

  _applyState(mob, state) {
    if (!mob || !state) {
      return;
    }

    if (Array.isArray(state.points) && state.points.length > 0 && typeof mob.setPoints3D === "function") {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(
          `Invalid points array length: ${state.points.length}. Expected 3n+1.`
        );
      }
      mob.setPoints3D(state.points);
    }

    if (typeof state.opacity === "number") {
      if (typeof mob.setFillOpacity === "function") {
        mob.setFillOpacity(state.opacity);
      }
      if (typeof mob.setOpacity === "function") {
        mob.setOpacity(state.opacity);
      }
    }
    if (typeof state.color === "string" && typeof mob.setColor === "function") {
      mob.setColor(state.color);
    }
    if (typeof state.fill_color === "string" && "fillColor" in mob) {
      mob.fillColor = state.fill_color;
    }
    if (typeof state.fill_opacity === "number" && "fillOpacity" in mob) {
      mob.fillOpacity = state.fill_opacity;
    }
    if (typeof state.stroke_color === "string" && "strokeColor" in mob) {
      mob.strokeColor = state.stroke_color;
    }
    if (typeof state.stroke_width === "number" && "strokeWidth" in mob) {
      mob.strokeWidth = state.stroke_width;
    }
    if (typeof state.z_index === "number" && "zIndex" in mob) {
      mob.zIndex = state.z_index;
    }
  }

  async _executeCommand(cmd, section) {
    switch (cmd?.cmd) {
      case "add": {
        const state = this._stateFromRef(section, cmd.state_ref);
        const mob = this._ensureMobject(cmd.id, state);
        this._applyState(mob, state);
        if (state.kind === "VGroup" && Array.isArray(state.children)) {
          this._attachVGroupChildren(mob, state.children, section);
        }
        this._scene.add(mob);
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
      case "data": {
        await this._playData(cmd, section);
        return;
      }
      default:
        console.warn(`Unknown command: ${cmd?.cmd}`);
    }
  }

  async _playAnimate(cmd, section) {
    const animations = Array.isArray(cmd.animations) ? cmd.animations : [];
    for (const desc of animations) {
      const built = this._buildAnimation(desc, section);
      if (built) {
        await this._scene.play(built);
      }
    }
  }

  _buildAnimation(desc, section) {
    if (!desc || typeof desc !== "object") {
      return null;
    }

    if (desc.type === "simple") {
      return this._buildSimpleAnimation(desc);
    }

    if (desc.type === "transform") {
      return this._buildTransformAnimation(desc, section);
    }

    console.warn(`Unsupported animation descriptor type: ${desc.type}`);
    return null;
  }

  _buildSimpleAnimation(desc) {
    const mob = this._registry.get(desc.id);
    if (!mob) {
      console.warn(`Mobject not found: ${desc.id}`);
      return null;
    }

    if (desc.kind === "Shift") {
      return this._buildShiftAnimation(mob, desc.params?.vector);
    }

    const builder = SIMPLE_ANIM_BUILDERS[desc.kind];
    if (!builder) {
      console.warn(`Unsupported simple animation kind: ${desc.kind}`);
      return null;
    }

    return builder(mob, desc.params || {});
  }

  _buildShiftAnimation(mob, vector) {
    const source = String(Shift);
    if (source.startsWith("class")) {
      return new Shift(mob, { direction: vector });
    }
    return Shift(mob, vector);
  }

  _buildTransformAnimation(desc, section) {
    const mob = this._registry.get(desc.id);
    if (!mob) {
      console.warn(`Mobject not found: ${desc.id}`);
      return null;
    }

    const targetState = this._stateFromRef(section, desc.state_ref);
    const target = this._createMobjectFromState(targetState);
    this._applyState(target, targetState);

    const transformSource = String(Transform);
    if (transformSource.startsWith("class")) {
      return new Transform(mob, target);
    }
    return Transform(mob, target);
  }

  async _playData(cmd, section) {
    const frames = Array.isArray(cmd.frames) ? cmd.frames : [];
    if (frames.length === 0) {
      return;
    }

    const duration = typeof cmd.duration === "number" ? cmd.duration : 0;
    const frameDuration = frames.length > 0 ? duration / frames.length : 0;

    for (const frame of frames) {
      for (const [id, frameEntry] of Object.entries(frame)) {
        const mob = this._registry.get(id);
        if (!mob) {
          continue;
        }
        const state = this._stateFromRef(section, frameEntry.state_ref);
        this._applyState(mob, state);
      }
      await this._scene.wait(frameDuration);
    }
  }
}

export function createPlayer(scene, registry) {
  if (!(scene instanceof Scene)) {
    throw new Error("Player requires a valid Scene instance");
  }
  return new Player(scene, registry);
}
