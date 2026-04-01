import { Scene, VMobject, Create, FadeIn, FadeOut, Write, ReplacementTransform, Shift, Rotate, Scale } from "manim-web";

export class Player {
  constructor(scene, mobjectRegistry) {
    this._scene = scene;
    this._registry = mobjectRegistry;
    this._fps = 10;
    this._currentSectionIndex = 0;
    this._currentSegmentIndex = 0;
    this._isPlaying = false;
    this._playbackSpeed = 1.0;
    this._onSectionChange = null;
    this._sections = [];
  }

  setfps(fps) {
    this._fps = fps;
  }

  setOnSectionChange(callback) {
    this._onSectionChange = callback;
  }

  _restoreSnapshot(snapshot) {
    if (!snapshot) return;

    for (const [id, state] of Object.entries(snapshot)) {
      let mob = this._registry.get(id);

      if (!mob) {
        mob = this._createMobjectFromState(state, id);
        if (mob) {
          this._registry._registry.set(id, mob);
        }
      }

      if (mob) {
        this._applyState(mob, state);
      }
    }
  }

  _createMobjectFromState(state, id) {
    if (state.kind === "ValueTracker") {
      const vt = new VMobject();
      vt._value = state.value || 0;
      return vt;
    }

    if (state.kind === "VGroup") {
      return new VMobject();
    }

    const vmob = new VMobject();
    if (state.points && state.points.length > 0) {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(
          `Invalid points array length: ${state.points.length}. Expected 3n+1 (got ${state.points.length}, which is not 3n+1).`
        );
      }
      vmob.setPoints3D(state.points);
    }
    return vmob;
  }

  _applyState(mob, state) {
    if (state.position) {
      mob.position.set(state.position[0], state.position[1], state.position[2]);
    }
    if (state.opacity !== undefined && mob.setFillOpacity) {
      mob.setFillOpacity(state.opacity);
    }
    if (state.opacity !== undefined && mob.setOpacity) {
      mob.setOpacity(state.opacity);
    }
    if (state.color && mob.setColor) {
      mob.setColor(state.color);
    }
    if (state.fill_color && mob.fillColor) {
      mob.fillColor = state.fill_color;
    }
    if (state.fill_opacity !== undefined && mob.fillOpacity !== undefined) {
      mob.fillOpacity = state.fill_opacity;
    }
    if (state.stroke_color && mob.strokeColor) {
      mob.strokeColor = state.stroke_color;
    }
    if (state.stroke_width !== undefined && mob.strokeWidth !== undefined) {
      mob.strokeWidth = state.stroke_width;
    }
    if (state.z_index !== undefined && mob.zIndex !== undefined) {
      mob.zIndex = state.z_index;
    }
  }

  async _playSegment(segment) {
    if (!segment.animations || segment.animations.length === 0) return;

    for (const cmd of segment.animations) {
      await this._scene.play(cmd);
    }
  }

  async _playSection(section) {
    const isUnsupported = section.unsupported;
    const reason = section.unsupported_reason || section.reason;

    if (isUnsupported) {
      console.warn(`Section "${section.name}" is not supported: ${reason}`);
    }

    this._scene.clear();
    this._restoreSnapshot(section.snapshot);

    const commands = section.construct || section.segments || [];
    for (const cmd of commands) {
      await this._executeCommand(cmd);
    }
  }

  async _executeCommand(cmd) {
    switch (cmd.cmd) {
      case "add": {
        const mob = this._registry.get(cmd.id);
        if (!mob) {
          const state = cmd.state;
          const newMob = this._createMobjectFromState(state, cmd.id);
          if (newMob) {
            this._registry._registry.set(cmd.id, newMob);
            this._applyState(newMob, state);
            this._scene.add(newMob);
          }
        } else {
          this._scene.add(mob);
        }
        break;
      }
      case "remove": {
        const mob = this._registry.get(cmd.id);
        if (mob) {
          this._scene.remove(mob);
        }
        break;
      }
      case "animate":
        if (cmd.animations && cmd.animations.length > 0) {
          for (const animDesc of cmd.animations) {
            const anim = this._buildAnimation(animDesc);
            if (anim) {
              await this._scene.play(anim);
            }
          }
        }
        break;
      case "data":
        await this._playDataCommand(cmd);
        break;
    }
  }

  _buildAnimation(animEntry) {
    const { type, id, rate_func, params = {} } = animEntry;
    const mob = this._registry.get(id);
    if (!mob) {
      console.warn(`Mobject not found: ${id}`);
      return null;
    }

    const rateFunc = rate_func === "linear" ? "linear" : "smooth";

    switch (type) {
      case "Create":
      case "FadeIn":
      case "FadeOut":
      case "Write": {
        const { Create, FadeIn, FadeOut, Write } = this._getAnimClasses();
        switch (type) {
          case "Create": return new Create(mob);
          case "FadeIn": return new FadeIn(mob);
          case "FadeOut": return new FadeOut(mob);
          case "Write": return new Write(mob);
        }
        break;
      }
      case "ReplacementTransform": {
        const { ReplacementTransform } = this._getAnimClasses();
        const target = this._registry.get(params.target_id);
        if (target) {
          return new ReplacementTransform(mob, target);
        }
        break;
      }
      case "Shift": {
        const { Shift } = this._getAnimClasses();
        const vector = params.vector;
        const shiftSource = String(Shift);

        // manim-web exports Shift differently depending on build target:
        // - class-style ctor expects options object with { direction }
        // - factory-style function expects (mobject, direction)
        // Support both so notebook bundle and Playwright harness behave identically.
        if (shiftSource.startsWith("class")) {
          return new Shift(mob, { direction: vector });
        }

        return Shift(mob, vector);
      }
      case "Rotate": {
        const { Rotate } = this._getAnimClasses();
        return new Rotate(mob, params.angle, params.axis);
      }
      case "Scale": {
        const { Scale } = this._getAnimClasses();
        return new Scale(mob, params.scale_factor);
      }
    }
    return null;
  }

  _getAnimClasses() {
    return {
      Create,
      FadeIn,
      FadeOut,
      Write,
      ReplacementTransform,
      Shift,
      Rotate,
      Scale,
    };
  }

  async _playDataCommand(cmd) {
    const { frames, duration } = cmd;
    if (!frames || frames.length === 0) return;

    const frameDuration = duration / frames.length;

    for (const frame of frames) {
      for (const [id, state] of Object.entries(frame)) {
        const mob = this._registry.get(id);
        if (mob) {
          this._applyState(mob, state);
        }
      }
      await this._scene.wait(frameDuration);
    }
  }

  async play() {
    this._isPlaying = true;
  }

  async pause() {
    this._isPlaying = false;
  }

  async jumpToSection(index) {
    this._currentSectionIndex = index;
    this._currentSegmentIndex = 0;
    if (this._onSectionChange) {
      this._onSectionChange(index);
    }
  }

  async seekToSection(index) {
    this._isPlaying = false;
    this._currentSectionIndex = index;
    this._currentSegmentIndex = 0;
    if (index >= 0 && index < this._sections.length) {
      await this._playSection(this._sections[index]);
    }
  }

  setSections(sections) {
    this._sections = sections;
  }

  get currentSectionIndex() {
    return this._currentSectionIndex;
  }

  get totalSections() {
    return this._sections ? this._sections.length : 0;
  }

  get isPlaying() {
    return this._isPlaying;
  }
}
