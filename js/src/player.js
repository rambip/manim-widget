import {
  Create,
  FadeIn,
  FadeOut,
  Rotate,
  ScaleInPlace,
  Scene,
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
  Rotate: (mob, params) =>
    new Rotate(mob, {
      angle: params?.angle ?? 0,
      axis: params?.axis,
      aboutPoint: params?.aboutPoint ?? params?.about_point,
    }),
  ScaleInPlace: (mob, params) =>
    new ScaleInPlace(mob, {
      scaleFactor: params?.scaleFactor ?? params?.scale_factor ?? 1,
    }),
};

export class Player {
  constructor(scene, registry, options = {}) {
    this._scene = scene;
    this._registry = registry;
    this._sections = [];
    this._fps = 10;
    this._isPlaying = false;
    this._currentSectionIndex = 0;
    this._onSectionChange = null;
    this._debug = options.debug || false;
    this._lastAnimationDebug = null;
  }

  _log(...args) {
    if (this._debug) {
      console.log("[Player]", ...args);
    }
  }

  _warn(...args) {
    console.warn("[Player]", ...args);
  }

  _error(...args) {
    console.error("[Player]", ...args);
  }

  _describeMobForDebug(mob, depth = 0, maxDepth = 4) {
    if (!mob) {
      return { exists: false };
    }
    const summary = {
      exists: true,
      ctor: mob.constructor?.name || "Unknown",
      hasGetThreeObject: typeof mob.getThreeObject === "function",
      submobjects: Array.isArray(mob.submobjects) ? mob.submobjects.length : 0,
    };

    if (typeof mob.getThreeObject === "function") {
      try {
        const threeObject = mob.getThreeObject();
        summary.hasThreeObject = Boolean(threeObject);
        summary.threeCtor = threeObject?.constructor?.name || null;
        summary.threeVisible = threeObject?.visible;
        summary.threeChildren = Array.isArray(threeObject?.children) ? threeObject.children.length : null;
      } catch (e) {
        summary.getThreeObjectError = e?.message || String(e);
      }
    }

    if (depth < maxDepth && Array.isArray(mob.submobjects) && mob.submobjects.length > 0) {
      summary.children = mob.submobjects.map((child) => this._describeMobForDebug(child, depth + 1, maxDepth));
    }
    return summary;
  }

  _validateThreeTree(node, path = "root", seen = new Set()) {
    if (!node) {
      return { ok: false, reason: `null node at ${path}` };
    }
    if (seen.has(node)) {
      return { ok: true };
    }
    seen.add(node);

    if (!("visible" in node)) {
      return { ok: false, reason: `missing visible property at ${path}` };
    }

    const children = Array.isArray(node.children) ? node.children : [];
    for (let i = 0; i < children.length; i += 1) {
      const child = children[i];
      if (!child) {
        return { ok: false, reason: `null child at ${path}.children[${i}]` };
      }
      const childCheck = this._validateThreeTree(child, `${path}.children[${i}]`, seen);
      if (!childCheck.ok) {
        return childCheck;
      }
    }

    return { ok: true };
  }

  _emitAnimationFailureDiagnostics(error, desc) {
    const report = {
      error: error?.message || String(error),
      stack: error?.stack || null,
      animation: desc || null,
      debugContext: this._lastAnimationDebug,
    };

    this._error("Animation playback failed with diagnostics:", report);
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
      this._warn("_playSection: section is null or undefined");
      return;
    }

    this._log(`_playSection: playing section '${section.name || "unnamed"}'`);

    if (section.unsupported) {
      const reason = section.unsupported_reason || section.reason || "unknown reason";
      this._warn(`Section "${section.name}" is unsupported: ${reason}`);
      return;
    }

    this._scene.clear();
    this._registry.clear();

    this._log("_playSection: cleared scene and registry");

    this._restoreSnapshot(section.snapshot || {}, section);

    const commands = Array.isArray(section.construct) ? section.construct : [];
    this._log(`_playSection: executing ${commands.length} commands`);
    for (let i = 0; i < commands.length; i++) {
      this._log(`_playSection: command ${i}/${commands.length}`);
      await this._executeCommand(commands[i], section);
    }
    this._log(`_playSection: completed section '${section.name || "unnamed"}'`);
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
    // Snapshot is { mob_id: state_ref }, resolve to actual states.
    const snapshotGroupChildren = [];
    const entries = Object.entries(snapshot);
    
    this._log(`_restoreSnapshot: restoring ${entries.length} mobjects from snapshot`);

    for (const [id, stateRef] of entries) {
      const state = this._stateFromRef(section, stateRef);
      this._log(`_restoreSnapshot: restoring mobject '${id}' (kind='${state?.kind || "unknown"}')`);
      const mob = this._ensureMobject(id, state);
      this._applyState(mob, state);
      this._scene.add(mob);
      if (state.kind === "VGroup" && Array.isArray(state.children)) {
        snapshotGroupChildren.push([id, state.children]);
        this._log(`_restoreSnapshot: VGroup '${id}' has ${state.children.length} snapshot children`);
      }
    }

    if (snapshotGroupChildren.length > 0) {
      this._log(`_restoreSnapshot: attaching children to ${snapshotGroupChildren.length} VGroups`);
    }
    for (const [parentId, childRefs] of snapshotGroupChildren) {
      const parent = this._registry.get(parentId);
      if (!parent) {
        throw new Error(`_restoreSnapshot: parent VGroup '${parentId}' not found in registry`);
      }
      this._attachVGroupChildren(parent, childRefs, section);
    }
  }

  _attachVGroupChildren(parent, childRefs, section) {
    if (!parent) {
      throw new Error("_attachVGroupChildren: parent is null or undefined");
    }
    if (typeof parent.add !== "function") {
      throw new Error(`_attachVGroupChildren: parent does not have 'add' method (got ${typeof parent})`);
    }
    if (!Array.isArray(childRefs)) {
      throw new Error(`_attachVGroupChildren: childRefs is not an array (got ${typeof childRefs})`);
    }
    if (childRefs.length === 0) {
      this._log("_attachVGroupChildren: no children to attach");
      return;
    }
    const existingCount = Array.isArray(parent.submobjects) ? parent.submobjects.length : 0;
    if (existingCount > 0) {
      this._log(`_attachVGroupChildren: parent already has ${existingCount} submobjects, skipping`);
      return;
    }

    this._log(`_attachVGroupChildren: attaching ${childRefs.length} children to VGroup`);
    for (let i = 0; i < childRefs.length; i++) {
      const childRef = childRefs[i];
      let childState;
      try {
        childState = this._stateFromRef(section, childRef);
      } catch (e) {
        throw new Error(`_attachVGroupChildren: failed to resolve state_ref ${childRef} for child ${i}: ${e.message}`);
      }
      
      let child;
      try {
        child = this._createMobjectFromState(childState);
      } catch (e) {
        throw new Error(`_attachVGroupChildren: failed to create mobject for child ${i} with state_ref ${childRef}: ${e.message}`);
      }
      
      if (!child) {
        throw new Error(`_attachVGroupChildren: _createMobjectFromState returned null for child ${i} with state_ref ${childRef}`);
      }
      
      this._applyState(child, childState);
      
      if (childState.kind === "VGroup" && Array.isArray(childState.children)) {
        try {
          this._attachVGroupChildren(child, childState.children, section);
        } catch (e) {
          throw new Error(`_attachVGroupChildren: failed to attach nested VGroup children for child ${i}: ${e.message}`);
        }
      }
      
      parent.add(child);
      this._log(`_attachVGroupChildren: attached child ${i} (state_ref=${childRef})`);
    }
  }

  _ensureThreeObjects(mob) {
    if (!mob) {
      throw new Error("_ensureThreeObjects: mob is null or undefined");
    }
    if (typeof mob.getThreeObject !== "function") {
      throw new Error("_ensureThreeObjects: mob is missing getThreeObject()");
    }

    const threeObject = mob.getThreeObject();
    if (!threeObject) {
      throw new Error("_ensureThreeObjects: getThreeObject() returned null");
    }

    const submobjects = Array.isArray(mob.submobjects) ? mob.submobjects : [];
    for (const child of submobjects) {
      this._ensureThreeObjects(child);
    }
  }

  _ensureMobject(id, state) {
    if (!id || typeof id !== "string") {
      throw new Error(`_ensureMobject: invalid id (got ${typeof id})`);
    }
    
    const existing = this._registry.get(id);
    if (existing) {
      this._log(`_ensureMobject: returning existing mobject for id '${id}'`);
      return existing;
    }

    if (!state || typeof state !== "object") {
      throw new Error(`_ensureMobject: invalid state for id '${id}' (got ${typeof state})`);
    }

    let mob;
    try {
      mob = this._createMobjectFromState(state);
    } catch (e) {
      throw new Error(`_ensureMobject: failed to create mobject for id '${id}': ${e.message}`);
    }
    
    if (!mob) {
      throw new Error(`_ensureMobject: _createMobjectFromState returned null for id '${id}'`);
    }
    
    this._registry.set(id, mob);
    this._log(`_ensureMobject: created and registered mobject for id '${id}'`);
    return mob;
  }

  _createMobjectFromState(state) {
    if (!state || typeof state !== "object") {
      throw new Error(`_createMobjectFromState: invalid state (got ${typeof state})`);
    }
    
    if (state.kind === "VGroup") {
      this._log(`_createMobjectFromState: creating VGroup for kind='${state.kind}'`);
      return new VGroup();
    }

    this._log(`_createMobjectFromState: creating VMobject for kind='${state.kind || 'unknown'}'`);
    const mob = new VMobject();
    if (Array.isArray(state.points) && state.points.length > 0) {
      if ((state.points.length - 1) % 3 !== 0) {
        throw new Error(
          `Invalid points array length: ${state.points.length}. Expected 3n+1.`
        );
      }
      mob.setPoints3D(state.points);
      this._log(`_createMobjectFromState: set ${state.points.length} points`);
    }
    return mob;
  }

  _applyState(mob, state) {
    if (!mob) {
      throw new Error("_applyState: mob is null or undefined");
    }
    if (!state) {
      throw new Error("_applyState: state is null or undefined");
    }
    if (typeof state !== "object") {
      throw new Error(`_applyState: state must be an object (got ${typeof state})`);
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
    if (!cmd || typeof cmd !== "object") {
      throw new Error(`_executeCommand: invalid command (got ${typeof cmd})`);
    }
    
    this._log(`_executeCommand: executing '${cmd.cmd}'`);
    
    switch (cmd.cmd) {
      case "add": {
        if (!cmd.id) {
          throw new Error("_executeCommand 'add': missing 'id' field");
        }
        if (cmd.state_ref === undefined || cmd.state_ref === null) {
          throw new Error(`_executeCommand 'add': missing 'state_ref' field for id '${cmd.id}'`);
        }
        
        let state;
        try {
          state = this._stateFromRef(section, cmd.state_ref);
        } catch (e) {
          throw new Error(`_executeCommand 'add': failed to resolve state_ref ${cmd.state_ref} for id '${cmd.id}': ${e.message}`);
        }
        
        let mob;
        try {
          mob = this._ensureMobject(cmd.id, state);
        } catch (e) {
          throw new Error(`_executeCommand 'add': failed to ensure mobject for id '${cmd.id}': ${e.message}`);
        }
        
        this._applyState(mob, state);
        
        if (state.kind === "VGroup" && Array.isArray(state.children)) {
          this._log(`_executeCommand 'add': VGroup with ${state.children.length} children`);
          try {
            this._attachVGroupChildren(mob, state.children, section);
          } catch (e) {
            throw new Error(`_executeCommand 'add': failed to attach VGroup children for id '${cmd.id}': ${e.message}`);
          }
        }
        
        this._scene.add(mob);
        this._log(`_executeCommand 'add': added mobject '${cmd.id}' to scene`);
        return;
      }
      case "remove": {
        if (!cmd.id) {
          throw new Error("_executeCommand 'remove': missing 'id' field");
        }
        const mob = this._registry.get(cmd.id);
        if (mob) {
          this._scene.remove(mob);
          this._registry.delete(cmd.id);
          this._log(`_executeCommand 'remove': removed mobject '${cmd.id}' from scene`);
        } else {
          this._warn(`_executeCommand 'remove': mobject '${cmd.id}' not found in registry`);
        }
        return;
      }
      case "rebind": {
        if (!cmd.source_id || !cmd.target_id) {
          throw new Error("_executeCommand 'rebind': missing 'source_id' or 'target_id' field");
        }
        this._registry.rebind(cmd.source_id, cmd.target_id);
        this._log(`_executeCommand 'rebind': rebound '${cmd.source_id}' to '${cmd.target_id}'`);
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
        this._warn(`Unknown command: ${cmd.cmd}`);
    }
  }

  async _playAnimate(cmd, section) {
    const animations = Array.isArray(cmd.animations) ? cmd.animations : [];
    for (const desc of animations) {
      const built = this._buildAnimation(desc, section);
      if (built) {
        const tempTarget = built?._mwTempTarget || null;
        let tempTargetThree = null;
        let shouldCleanupTarget = false;
        try {
          if (tempTarget) {
            this._scene.add(tempTarget);
            shouldCleanupTarget = true;
            if (typeof tempTarget.getThreeObject === "function") {
              tempTargetThree = tempTarget.getThreeObject();
              if (tempTargetThree && "visible" in tempTargetThree) {
                tempTargetThree.visible = false;
              }
            }
          }
          await this._scene.play(built);
        } catch (error) {
          this._emitAnimationFailureDiagnostics(error, desc);
          throw error;
        } finally {
          this._lastAnimationDebug = null;
        }
        if (shouldCleanupTarget && tempTarget) {
          // Allow one scene tick before removing temporary target so manim-web
          // post-play internals can finish reading target visibility safely.
          await this._scene.wait(0);
          this._scene.remove(tempTarget);
        }
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
      throw new Error(`mobject_not_found - Mobject not found: ${desc.id}`);
    }

    const builder = SIMPLE_ANIM_BUILDERS[desc.kind];
    if (!builder) {
      console.warn(`Unsupported simple animation kind: ${desc.kind}`);
      return null;
    }

    return builder(mob, desc.params || {});
  }

  _buildTransformAnimation(desc, section) {
    const mob = this._registry.get(desc.id);
    if (!mob) {
      throw new Error(`mobject_not_found - Mobject not found: ${desc.id}`);
    }

    const targetState = this._stateFromRef(section, desc.state_ref);
    const target = this._createMobjectFromState(targetState);
    this._applyState(target, targetState);
    if (targetState.kind === "VGroup" && Array.isArray(targetState.children)) {
      this._attachVGroupChildren(target, targetState.children, section);
    }

    this._ensureThreeObjects(mob);
    this._ensureThreeObjects(target);

    const mobThree = mob.getThreeObject();
    const targetThree = target.getThreeObject();
    const sourceTreeCheck = this._validateThreeTree(mobThree, "sourceThree");
    const targetTreeCheck = this._validateThreeTree(targetThree, "targetThree");

    this._lastAnimationDebug = {
      type: "transform",
      id: desc.id,
      state_ref: desc.state_ref,
      source: this._describeMobForDebug(mob),
      target: this._describeMobForDebug(target),
      sourceTreeCheck,
      targetTreeCheck,
    };
    globalThis.__MW_LAST_ANIM_DEBUG = this._lastAnimationDebug;

    if (!sourceTreeCheck.ok || !targetTreeCheck.ok) {
      throw new Error(
        `three_tree_invalid - ${sourceTreeCheck.ok ? targetTreeCheck.reason : sourceTreeCheck.reason}`
      );
    }

    const transformSource = String(Transform);
    let built;
    if (transformSource.startsWith("class")) {
      built = new Transform(mob, target);
    } else {
      built = Transform(mob, target);
    }
    if (built && typeof built === "object") {
      built._mwTempTarget = target;
    }
    return built;
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
