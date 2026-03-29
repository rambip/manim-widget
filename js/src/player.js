import { Scene } from "manim-web";
import { buildAnimation } from "./registry.js";

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
  }

  setfps(fps) {
    this._fps = fps;
  }

  setOnSectionChange(callback) {
    this._onSectionChange = callback;
  }

  _restoreSnapshot(snapshot) {
    for (const [id, state] of Object.entries(snapshot)) {
      const mob = this._registry.get(id);
      if (!mob) continue;

      if (state.position) {
        mob.setPosition(state.position[0], state.position[1], state.position[2]);
      }
      if (state.opacity !== undefined && mob.setFillOpacity) {
        mob.setFillOpacity(state.opacity);
      }
      if (state.color && mob.setColor) {
        mob.setColor(state.color);
      }
    }
  }

  async _playSegment(segment) {
    const animations = [];
    for (const animEntry of segment.animations) {
      const anim = buildAnimation(
        animEntry.kind,
        this._registry,
        this._scene,
        animEntry
      );
      if (anim) {
        animations.push(anim);
      }
    }

    if (animations.length === 0) return;

    await this._scene.play(...animations);
  }

  async _playSection(section) {
    if (!section.supported) {
      console.warn(`Section "${section.name}" is not supported: ${section.reason}`);
    }

    this._restoreSnapshot(section.snapshot);

    for (const segment of section.segments) {
      if (!this._isPlaying) break;
      await this._playSegment(segment);
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
