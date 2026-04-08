#!/usr/bin/env bun

import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register();

import { mock, spyOn, beforeEach, afterEach } from "bun:test";
import * as fs from "fs";
import * as path from "path";
import * as THREE from "three";

const args = process.argv.slice(2);
const verbose = args.includes("--verbose") || args.includes("-v");
const outputIds = args.includes("--output-ids");
const filePathArg = args.find(arg => !arg.startsWith("-"));

async function readInput() {
  if (!filePathArg) {
    return new Promise((resolve, reject) => {
      let data = "";
      process.stdin.setEncoding("utf-8");
      process.stdin.on("data", chunk => data += chunk);
      process.stdin.on("end", () => resolve(data));
      process.stdin.on("error", reject);
    });
  }
  
  const specPath = path.resolve(filePathArg);
  if (!fs.existsSync(specPath)) {
    console.error(`File not found: ${specPath}`);
    process.exit(1);
  }
  return fs.readFileSync(specPath, "utf-8");
}

const input = await readInput();
const spec = JSON.parse(input);

const errors = [];
const warnings = [];
const operations = [];
const mobjectTracking = new Map();
let mobjectIdCounter = 0;

function pushValidationError(error, description, details = {}) {
  errors.push({ error, description, ...details });
}

function getThreeObjectOrError(mob, context) {
  if (!mob) {
    pushValidationError(
      "null_mobject",
      `Validation context '${context}' received null mobject`,
    );
    return null;
  }
  if (typeof mob.getThreeObject !== "function") {
    pushValidationError(
      "missing_get_three_object",
      `Mobject in context '${context}' is missing getThreeObject()`,
      { mobjectId: mob._id || "unknown" },
    );
    return null;
  }

  const threeObject = mob.getThreeObject();
  if (!threeObject) {
    pushValidationError(
      "null_three_object",
      `Mobject in context '${context}' returned null three object`,
      { mobjectId: mob._id || "unknown" },
    );
    return null;
  }

  if (threeObject.visible === null || threeObject.visible === undefined) {
    pushValidationError(
      "invalid_visible",
      `Three object in context '${context}' has invalid visible`,
      { mobjectId: mob._id || "unknown" },
    );
    return null;
  }

  return threeObject;
}

function validateMobjectTree(mob, context, seen = new Set()) {
  if (!mob || seen.has(mob)) {
    return;
  }
  seen.add(mob);

  const threeObject = getThreeObjectOrError(mob, context);
  if (threeObject) {
    // Access visible explicitly to catch "...visible of null"-class issues.
    const visibleProbe = threeObject.visible;
    if (typeof visibleProbe !== "boolean") {
      pushValidationError(
        "non_boolean_visible",
        `Three object visible is not boolean in context '${context}'`,
        { mobjectId: mob._id || "unknown", visibleType: typeof visibleProbe },
      );
    }
  }

  const submobjects = Array.isArray(mob.submobjects) ? mob.submobjects : [];
  for (let i = 0; i < submobjects.length; i++) {
    const child = submobjects[i];
    if (!child) {
      pushValidationError(
        "null_submobject",
        `Null submobject at index ${i} in context '${context}'`,
        { mobjectId: mob._id || "unknown" },
      );
      continue;
    }
    validateMobjectTree(child, `${context}.submobjects[${i}]`, seen);
  }
}

function validateSceneGraph(scene, context) {
  for (const mob of scene.mobjects) {
    validateMobjectTree(mob, `${context}.scene_mobject`);
  }
}

class MockVMobject {
  constructor() {
    this._id = `vmobject_${mobjectIdCounter++}`;
    this.submobjects = [];
    this._points = [];
    this._opacity = 1;
    this._color = "#ffffff";
    this._fillOpacity = 1;
    this._fillColor = "#ffffff";
    
    // Enhanced position/scale tracking using real THREE.js types
    this._position = new THREE.Vector3(0, 0, 0);
    this._scaleVector = new THREE.Vector3(1, 1, 1);
    this._rotation = new THREE.Euler(0, 0, 0, "XYZ");
    // Lazy init like manim-web: null until getThreeObject() is called
    this._threeObject = null;
    
    // Styling state
    this.fillColor = "#ffffff";
    this.fillOpacity = 1;
    this.strokeColor = "#ffffff";
    this.strokeWidth = 2;
    this.zIndex = 0;
    
    mobjectTracking.set(this._id, {
      type: "VMobject",
      instance: this,
      children: [],
      pointsCount: 0,
      attachedTo: null,
    });
    operations.push({ type: "mobject_create", id: this._id, kind: "VMobject" });
  }

  // Position and bounds methods for interaction support
  getCenter() {
    return [this._position.x, this._position.y, this._position.z];
  }

  getBoundingBox() {
    // Simple bounding box based on position
    return {
      width: 1.0 * this._scaleVector.x,
      height: 1.0 * this._scaleVector.y,
    };
  }

  moveTo(pos) {
    if (Array.isArray(pos)) {
      this._position.x = pos[0] ?? this._position.x;
      this._position.y = pos[1] ?? this._position.y;
      this._position.z = pos[2] ?? this._position.z;
    } else if (typeof pos === "object") {
      this._position.x = pos.x ?? this._position.x;
      this._position.y = pos.y ?? this._position.y;
      this._position.z = pos.z ?? this._position.z;
    }
    operations.push({
      type: "moveTo",
      id: this._id,
      position: { x: this._position.x, y: this._position.y, z: this._position.z },
    });
  }

  getThreeObject() {
    if (!this._threeObject) {
      this._threeObject = new THREE.Object3D();
    }
    return this._threeObject;
  }

  // Property accessors
  get position() {
    return this._position;
  }

  get scaleVector() {
    return this._scaleVector;
  }

  get rotation() {
    return this._rotation;
  }

  setPoints3D(pts) {
    if ((pts.length - 1) % 3 !== 0) {
      const err = `Invalid points array length: ${pts.length}. Expected 3n+1.`;
      errors.push({ error: "invalid_points", description: err });
      throw new Error(err);
    }
    this._points = pts;
    const tracking = mobjectTracking.get(this._id);
    if (tracking) tracking.pointsCount = pts.length;
    operations.push({ type: "setPoints3D", id: this._id, count: pts.length });
  }

  setFillOpacity(op) {
    this._fillOpacity = op;
    this.fillOpacity = op;
  }

  setOpacity(op) {
    this._opacity = op;
  }

  setColor(c) {
    this._color = c;
    this.fillColor = c;
    this.strokeColor = c;
  }

  add(mob) {
    if (!mob) {
      errors.push({ error: "add_null_child", description: "Attempted to add null/undefined child to VMobject" });
      throw new Error("Cannot add null or undefined child to VMobject");
    }
    this.submobjects.push(mob);
    const childId = mob._id || "unknown";
    const tracking = mobjectTracking.get(this._id);
    if (tracking) tracking.children.push(childId);
    const childTracking = mobjectTracking.get(childId);
    if (childTracking) childTracking.attachedTo = this._id;
    operations.push({ type: "mobject_add_child", parentId: this._id, childId, parentKind: "VMobject" });
  }
}

class MockVGroup {
  constructor() {
    this._id = `vgroup_${mobjectIdCounter++}`;
    this.submobjects = [];
    
    // Enhanced position/scale tracking using real THREE.js types
    this._position = new THREE.Vector3(0, 0, 0);
    this._scaleVector = new THREE.Vector3(1, 1, 1);
    this._rotation = new THREE.Euler(0, 0, 0, "XYZ");
    // Lazy init like manim-web: null until getThreeObject() is called
    this._threeObject = null;
    
    mobjectTracking.set(this._id, {
      type: "VGroup",
      instance: this,
      children: [],
      attachedTo: null,
    });
    operations.push({ type: "mobject_create", id: this._id, kind: "VGroup" });
  }

  // Position and bounds methods for interaction support
  getCenter() {
    // For groups, compute center from children if available
    if (this.submobjects.length > 0) {
      let sumX = 0, sumY = 0, sumZ = 0;
      for (const child of this.submobjects) {
        if (typeof child.getCenter === "function") {
          const center = child.getCenter();
          sumX += center[0] || 0;
          sumY += center[1] || 0;
          sumZ += center[2] || 0;
        }
      }
      const n = this.submobjects.length;
      return [sumX / n, sumY / n, sumZ / n];
    }
    return [this._position.x, this._position.y, this._position.z];
  }

  getBoundingBox() {
    // For groups, compute bounds from children
    if (this.submobjects.length > 0) {
      let maxWidth = 0, maxHeight = 0;
      for (const child of this.submobjects) {
        if (typeof child.getBoundingBox === "function") {
          const bb = child.getBoundingBox();
          maxWidth = Math.max(maxWidth, bb.width);
          maxHeight = Math.max(maxHeight, bb.height);
        }
      }
      return { width: maxWidth, height: maxHeight };
    }
    return {
      width: 1.0 * this._scaleVector.x,
      height: 1.0 * this._scaleVector.y,
    };
  }

  moveTo(pos) {
    if (Array.isArray(pos)) {
      this._position.x = pos[0] ?? this._position.x;
      this._position.y = pos[1] ?? this._position.y;
      this._position.z = pos[2] ?? this._position.z;
    } else if (typeof pos === "object") {
      this._position.x = pos.x ?? this._position.x;
      this._position.y = pos.y ?? this._position.y;
      this._position.z = pos.z ?? this._position.z;
    }
    operations.push({
      type: "moveTo",
      id: this._id,
      position: { x: this._position.x, y: this._position.y, z: this._position.z },
    });
  }

  getThreeObject() {
    if (!this._threeObject) {
      this._threeObject = new THREE.Object3D();
    }
    return this._threeObject;
  }

  get position() {
    return this._position;
  }

  get scaleVector() {
    return this._scaleVector;
  }

  get rotation() {
    return this._rotation;
  }

  add(mob) {
    if (!mob) {
      errors.push({ error: "add_null_child", description: "Attempted to add null/undefined child to VGroup" });
      throw new Error("Cannot add null or undefined child to VGroup");
    }
    this.submobjects.push(mob);
    const childId = mob._id || "unknown";
    const tracking = mobjectTracking.get(this._id);
    if (tracking) tracking.children.push(childId);
    const childTracking = mobjectTracking.get(childId);
    if (childTracking) childTracking.attachedTo = this._id;
    operations.push({ type: "mobject_add_child", parentId: this._id, childId, parentKind: "VGroup" });
  }
}

class MockScene {
  constructor() {
    this.mobjects = new Set();
    
    // Canvas mock with getBoundingClientRect for interaction coordinate mapping
    this._canvas = {
      width: 800,
      height: 600,
      getBoundingClientRect() {
        return {
          width: 800,
          height: 600,
          left: 0,
          top: 0,
          right: 800,
          bottom: 600,
          x: 0,
          y: 0,
        };
      },
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent() { return true; },
      style: {},
    };
    
    // Camera mock for coordinate transformations
    this._camera = {
      frameWidth: 14,
      frameHeight: 8,
      frameCenter: [0, 0, 0],
    };
  }

  getCanvas() {
    return this._canvas;
  }

  get camera() {
    return this._camera;
  }

  add(mob) {
    this.mobjects.add(mob);
    operations.push({ type: "scene_add", mob: mob?.constructor?.name || "unknown" });
  }

  remove(mob) {
    this.mobjects.delete(mob);
    operations.push({ type: "scene_remove", mob: mob?.constructor?.name || "unknown" });
  }

  clear() {
    this.mobjects.clear();
    operations.push({ type: "scene_clear" });
  }

  async play(anim) {
    operations.push({
      type: "scene_play",
      animation: anim?.constructor?.name || "unknown",
      // Track animation parameters for better testing
      params: anim?._params || {},
    });

    if (anim?.mobject) {
      validateMobjectTree(anim.mobject, "scene.play.source");
    }
    if (anim?._params?.target) {
      validateMobjectTree(anim._params.target, "scene.play.target");
    }
    validateSceneGraph(this, "scene.play");

    if (errors.length > 0) {
      throw new Error(`Scene graph validation failed during play (${errors.length} errors)`);
    }
  }

  async wait(duration) {
    operations.push({ type: "scene_wait", duration });
  }
}

const mockScene = new MockScene();

function createMockAnimation(name) {
  return class MockAnimation {
    constructor(mob, ...args) {
      this.mobject = mob;
      this._params = {};
      this._name = name;
      
      // Extract params from args based on animation type
      if (args.length > 0) {
        if (name === "Rotate" && args.length >= 1) {
          const opts = args[0];
          if (opts && typeof opts === "object" && !Array.isArray(opts)) {
            this._params = { ...this._params, ...opts };
          } else {
            this._params.angle = opts;
            if (args.length >= 2) this._params.axis = args[1];
          }
        } else if (name === "ScaleInPlace" && args.length >= 1) {
          const opts = args[0];
          if (opts && typeof opts === "object" && !Array.isArray(opts)) {
            this._params = { ...this._params, ...opts };
          } else {
            this._params.scaleFactor = opts;
          }
        } else if (name === "Transform" && args.length >= 1) {
          this._params.target = args[0];
          if (args[0]?._id) {
            this._params.targetId = args[0]._id;
          }
        } else {
          // Generic param capture
          this._params.args = args;
        }
      }
      
      operations.push({
        type: "animation_create",
        kind: name,
        mobject: mob?._id || mob?.constructor?.name || "unknown",
        params: this._params,
      });
    }
    
    // Allow setting rate_func and other animation properties
    set rate_func(fn) {
      this._params.rate_func = fn;
    }
    
    get rate_func() {
      return this._params.rate_func;
    }
  };
}

// Create animation classes with enhanced tracking
const MockCreate = createMockAnimation("Create");
const MockFadeIn = createMockAnimation("FadeIn");
const MockFadeOut = createMockAnimation("FadeOut");
const MockWrite = createMockAnimation("Write");
const MockRotate = createMockAnimation("Rotate");
const MockScaleInPlace = createMockAnimation("ScaleInPlace");
const MockTransform = createMockAnimation("Transform");

mock.module("manim-web", () => ({
  Scene: MockScene,
  Create: MockCreate,
  FadeIn: MockFadeIn,
  FadeOut: MockFadeOut,
  Write: MockWrite,
  Rotate: MockRotate,
  ScaleInPlace: MockScaleInPlace,
  Transform: MockTransform,
  VMobject: MockVMobject,
  VGroup: MockVGroup,
}));

const { Player } = await import("./player.js");
const { MobjectRegistry } = await import("./registry.js");

const registry = new MobjectRegistry();
const player = new Player(mockScene, registry, { debug: verbose });

player.setfps(spec.fps || 10);
player.setSections(spec.sections || []);

// Track mobject IDs at the end of each section
const sectionIds = [];

for (let i = 0; i < spec.sections.length; i++) {
  const section = spec.sections[i];
  operations.push({ type: "section_start", index: i, name: section.name });

  if (section.unsupported) {
    warnings.push({
      section: i,
      name: section.name,
      reason: section.unsupported_reason || "unknown",
    });
    continue;
  }

  try {
    await player.seekToSection(i);
    validateSceneGraph(mockScene, `section:${section.name || i}`);

    for (const [mobId, mob] of registry._registry.entries()) {
      validateMobjectTree(mob, `registry:${mobId}`);
    }

    if (errors.length > 0) {
      throw new Error(`Scene graph validation failed after section ${section.name || i}`);
    }

    operations.push({ type: "section_end", index: i, name: section.name });
    
    // Capture mobject IDs at the end of this section
    const ids = [];
    for (const mob of mockScene.mobjects) {
      if (mob._id) {
        ids.push(mob._id);
      }
    }
    sectionIds.push({
      name: section.name,
      ids: ids.sort(), // Sort for deterministic output
    });
  } catch (e) {
    errors.push({
      section: i,
      name: section.name,
      error: e.message,
      stack: e.stack?.split("\n").slice(0, 3).join("\n"),
    });
    break;
  }
}

console.log("=== Playback Complete ===");
console.log(`Sections: ${spec.sections.length}`);
console.log(`Operations: ${operations.length}`);
console.log(`Mobjects created: ${mobjectTracking.size}`);
console.log(`Warnings: ${warnings.length}`);
console.log(`Errors: ${errors.length}`);

// Validate that VGroups with expected children actually have children attached
const vgroupsNeedingValidation = [];
for (const section of spec.sections || []) {
  // Check snapshot VGroups
  if (section.snapshot) {
    for (const [id, state] of Object.entries(section.snapshot)) {
      if (state.kind === "VGroup" && Array.isArray(state.children) && state.children.length > 0) {
        vgroupsNeedingValidation.push({ id, section: section.name, expectedChildren: state.children.length, source: "snapshot" });
      }
    }
  }
  // Check construct StateGroups
  if (section.construct) {
    for (const cmd of section.construct) {
      if (cmd.cmd === "add" && cmd.state_ref !== undefined) {
        const state = section.states?.[cmd.state_ref];
        if (state?.kind === "StateGroup" && Array.isArray(state.state_children) && state.state_children.length > 0) {
          vgroupsNeedingValidation.push({ id: cmd.id, section: section.name, expectedChildren: state.state_children.length, source: "construct" });
        }
      }
    }
  }
}

// Verify each VGroup has expected children
const validationErrors = [];
for (const vg of vgroupsNeedingValidation) {
  const tracking = Array.from(mobjectTracking.values()).find(t => 
    t.type === "VGroup" && t.children && t.children.length === vg.expectedChildren
  );
  
  // Find VGroup by checking operations for mobject creation and add_child
  const vgroupOps = operations.filter(op => 
    (op.type === "mobject_create" && op.kind === "VGroup") ||
    (op.type === "mobject_add_child" && op.parentKind === "VGroup")
  );
  
  // Check if we have any VGroup adds matching expected children
  const addChildOps = operations.filter(op => 
    op.type === "mobject_add_child" && (op.parentKind === "VGroup" || op.parentKind === "VMobject")
  );
  
  const matchingAdds = addChildOps.filter(op => {
    // Find the parent tracking to check children count
    const parentTracking = mobjectTracking.get(op.parentId);
    return parentTracking && parentTracking.children.length > 0;
  });
  
  if (vg.expectedChildren > 0 && matchingAdds.length === 0) {
    validationErrors.push({
      error: "stategroup_children_not_attached",
      description: `VGroup '${vg.id}' in section '${vg.section}' expected ${vg.expectedChildren} children but none were attached (${vg.source})`,
    });
  }
}

if (validationErrors.length > 0) {
  console.log("\n=== Validation Errors ===");
  for (const e of validationErrors) {
    console.log(`  ${e.description}`);
    errors.push(e);
  }
}

if (warnings.length > 0) {
  console.log("\n=== Warnings ===");
  for (const w of warnings) {
    console.log(`  Section ${w.section} (${w.name}): ${w.reason}`);
  }
}

if (errors.length > 0) {
  console.log("\n=== Errors ===");
  for (const e of errors) {
    console.log(`  ${JSON.stringify(e, null, 2)}`);
  }
  process.exit(1);
}

if (verbose) {
  console.log("\n=== Mobject Tracking ===");
  for (const [id, info] of mobjectTracking) {
    console.log(`  ${id}: type=${info.type}, children=${info.children.length}, attachedTo=${info.attachedTo || "scene"}`);
  }
  
  console.log("\n=== Operations ===");
  for (const op of operations) {
    console.log(`  ${JSON.stringify(op)}`);
  }
}

// Output section mobject IDs if requested
if (outputIds) {
  console.log("\n=== Section Mobject IDs ===");
  const output = { sections: sectionIds };
  console.log(JSON.stringify(output, null, 2));
}

process.exit(0);
