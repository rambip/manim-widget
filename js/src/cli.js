#!/usr/bin/env bun

import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register();

import { mock, spyOn, beforeEach, afterEach } from "bun:test";
import * as fs from "fs";
import * as path from "path";

const args = process.argv.slice(2);

async function readInput() {
  if (args.length === 0) {
    return new Promise((resolve, reject) => {
      let data = "";
      process.stdin.setEncoding("utf-8");
      process.stdin.on("data", chunk => data += chunk);
      process.stdin.on("end", () => resolve(data));
      process.stdin.on("error", reject);
    });
  }
  
  const specPath = path.resolve(args[0]);
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

class MockVMobject {
  constructor() {
    this.submobjects = [];
    this._points = [];
    this._opacity = 1;
    this._color = "#ffffff";
  }
  setPoints3D(pts) {
    if ((pts.length - 1) % 3 !== 0) {
      const err = `Invalid points array length: ${pts.length}. Expected 3n+1.`;
      errors.push({ error: "invalid_points", description: err });
      throw new Error(err);
    }
    this._points = pts;
    operations.push({ type: "setPoints3D", count: pts.length });
  }
  setFillOpacity(op) { this._fillOpacity = op; }
  setOpacity(op) { this._opacity = op; }
  setColor(c) { this._color = c; }
  add(mob) { this.submobjects.push(mob); }
}

class MockVGroup {
  constructor() {
    this.submobjects = [];
  }
  add(mob) { this.submobjects.push(mob); }
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

const player = new Player(mockScene, registry, (errPayload) => {
  try {
    const parsed = JSON.parse(errPayload);
    errors.push(parsed);
  } catch {
    errors.push({ raw: errPayload });
  }
});

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
console.log(`Warnings: ${warnings.length}`);
console.log(`Errors: ${errors.length}`);

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

if (args.includes("--verbose") || args.includes("-v")) {
  console.log("\n=== Operations ===");
  for (const op of operations) {
    console.log(`  ${JSON.stringify(op)}`);
  }
}

process.exit(0);
