#!/usr/bin/env bun

import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register();

import { mock, spyOn, beforeEach, afterEach } from "bun:test";
import * as fs from "fs";
import * as path from "path";

const args = process.argv.slice(2);
const verbose = args.includes("--verbose") || args.includes("-v");
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

class MockVMobject {
  constructor() {
    this._id = `vmobject_${mobjectIdCounter++}`;
    this.submobjects = [];
    this._points = [];
    this._opacity = 1;
    this._color = "#ffffff";
    mobjectTracking.set(this._id, {
      type: "VMobject",
      instance: this,
      children: [],
      pointsCount: 0,
      attachedTo: null,
    });
    operations.push({ type: "mobject_create", id: this._id, kind: "VMobject" });
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
  setFillOpacity(op) { this._fillOpacity = op; }
  setOpacity(op) { this._opacity = op; }
  setColor(c) { this._color = c; }
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
    mobjectTracking.set(this._id, {
      type: "VGroup",
      instance: this,
      children: [],
      attachedTo: null,
    });
    operations.push({ type: "mobject_create", id: this._id, kind: "VGroup" });
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
    operations.push({ type: "scene_play", animation: anim?.constructor?.name || "unknown" });
  }
  async wait(duration) {
    operations.push({ type: "scene_wait", duration });
  }
}

const mockScene = new MockScene();

function createMockAnimation(name) {
  return class {
    constructor(mob, ...args) {
      this.mobject = mob;
      operations.push({ type: "animation_create", kind: name, mobject: mob?.constructor?.name || "unknown" });
    }
  };
}

mock.module("manim-web", () => ({
  Scene: MockScene,
  Create: createMockAnimation("Create"),
  FadeIn: createMockAnimation("FadeIn"),
  FadeOut: createMockAnimation("FadeOut"),
  Write: createMockAnimation("Write"),
  Rotate: createMockAnimation("Rotate"),
  ScaleInPlace: createMockAnimation("ScaleInPlace"),
  Shift: createMockAnimation("Shift"),
  Transform: createMockAnimation("Transform"),
  VMobject: MockVMobject,
  VGroup: MockVGroup,
}));

const { Player } = await import("./player.js");
const { MobjectRegistry } = await import("./registry.js");

const registry = new MobjectRegistry();
const player = new Player(mockScene, registry, { debug: verbose });

player.setfps(spec.fps || 10);
player.setSections(spec.sections || []);

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
    operations.push({ type: "section_end", index: i, name: section.name });
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

process.exit(0);
