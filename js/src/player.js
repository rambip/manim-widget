import {
  Create,
  FadeIn,
  FadeOut,
  Rotate,
  ScaleInPlace,
  Transform,
  VMobject,
  VGroup,
  Write,
  GrowFromCenter,
  MoveAlongPath,
  Rotating,
} from "manim-web";

function buildSimpleAnimation(mob, desc, registry) {
  const params = desc.params || {};
  switch (desc.kind) {
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
    if (!Number.isInteger(stateRef) || stateRef < 0 || stateRef >= states.length) {
      throw new Error(`Invalid state_ref: ${stateRef}`);
    }
    return states[stateRef];
  }

  _createMobjectFromState(state) {
    if (state.kind === "VGroup") {
      return new VGroup();
    }

    const mob = new VMobject();
    if (Array.isArray(state.points) && state.points.length > 0) {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(`Invalid points array length: ${state.points.length}. Expected 3n+1.`);
      }
      mob.setPoints3D(state.points);
    }
    return mob;
  }

  _applyState(mob, state) {
    if (Array.isArray(state.points) && state.points.length > 0 && typeof mob.setPoints3D === "function") {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(`Invalid points array length: ${state.points.length}. Expected 3n+1.`);
      }
      mob.setPoints3D(state.points);
    }

    if (typeof state.opacity === "number") {
      if (typeof mob.setFillOpacity === "function") {
        mob.setFillOpacity(state.opacity);
      }
      if (typeof mob.setStrokeOpacity === "function") {
        mob.setStrokeOpacity(state.opacity);
      }
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
    return mob;
  }

  _restoreSnapshot(snapshot, section) {
    for (const [id, stateRef] of Object.entries(snapshot)) {
      const mob = this._instantiateFromRef(section, stateRef);
      this._registry.set(id, mob);
      this._scene.add(mob);
    }
  }

  async _playSection(section) {
    if (!section || section.unsupported) {
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

  async _executeCommand(cmd, section) {
    switch (cmd?.cmd) {
      case "add": {
        const mob = this._instantiateFromRef(section, cmd.state_ref);
        this._registry.set(cmd.id, mob);
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

  _buildAnimation(desc, section) {
    if (!desc || typeof desc !== "object") {
      return null;
    }

    if (desc.kind === "Wait") {
      return null;
    }

    const mob = this._registry.get(desc.id);
    if (!mob) {
      throw new Error(`Mobject not found: ${desc.id}`);
    }

    if (desc.type === "simple") {
      return buildSimpleAnimation(mob, desc, this._registry);
    }

    if (desc.type === "transform") {
      const target = this._instantiateFromRef(section, desc.state_ref);
      return new Transform(mob, target);
    }

    console.warn(`Unsupported animation descriptor type: ${desc.type}`);
    return null;
  }

  async _playAnimate(cmd, section) {
    const animations = Array.isArray(cmd.animations) ? cmd.animations : [];
    for (const desc of animations) {
      if (desc.kind === "Wait") {
        await this._scene.wait(cmd.duration);
        continue;
      }
      const animation = this._buildAnimation(desc, section);
      if (animation) {
        await this._scene.play(animation);
      }
    }
  }

  async _playData(cmd, section) {
    const frames = Array.isArray(cmd.frames) ? cmd.frames : [];
    if (frames.length === 0) {
      return;
    }

    const duration = typeof cmd.duration === "number" ? cmd.duration : 0;
    const frameDuration = duration / frames.length;

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
  return new Player(scene, registry);
}
