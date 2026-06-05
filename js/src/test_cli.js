#!/usr/bin/env bun

// Temporary: happy-dom is needed for headless mode until manim-web provides
// a truly headless mode that doesn't require any DOM APIs.
// See: https://github.com/maloyan/manim-web/issues/214
import { GlobalRegistrator } from "@happy-dom/global-registrator";
GlobalRegistrator.register();

import * as fs from "fs";
import * as path from "path";
import { parseArgs } from "node:util";

import { Scene } from "manim-web";
import { Player } from "./player.js";
import { MobjectRegistry } from "./registry.js";

const { values: flags, positionals } = parseArgs({
  args: process.argv.slice(2),
  options: {
    verbose:      { type: "boolean", short: "v", default: false },
    "ids":        { type: "boolean", default: false },
    "end-state":  { type: "boolean", default: false },
  },
  allowPositionals: true,
});

const verbose     = flags.verbose;
const outputIds   = flags["ids"];
const outputEndState = flags["end-state"];
const filePathArg = positionals[0];

// ---------------------------------------------------------------------------
// Runtime state serialiser
// ---------------------------------------------------------------------------

const VMOBJECT_KINDS = new Set([
  "Circle", "Square", "Rectangle", "RoundedRectangle", "Triangle", "Polygon",
  "RegularPolygon", "Hexagon", "Pentagon", "Polygram", "ArcPolygon", "Line",
  "DashedLine", "CubicBezier", "Arrow", "DoubleArrow", "Vector", "CurvedArrow",
  "CurvedDoubleArrow", "Arc", "ArcBetweenPoints", "Ellipse", "Annulus",
  "AnnularSector", "Sector", "TangentialArc", "Dot", "SmallDot", "LargeDot",
  "BackgroundRectangle", "SurroundingRectangle", "Underline", "Cross", "Angle",
  "RightAngle", "Star", "Brace", "BraceBetweenPoints", "ArcBrace",
  "SVGMobject", "VMobjectFromSVGPath", "VMobject",
]);

function normalizePoints(points) {
  if (!Array.isArray(points)) return [];
  return points
    .filter((p) => Array.isArray(p) && p.length >= 3)
    .map((p) => [Number(p[0]) || 0, Number(p[1]) || 0, Number(p[2]) || 0]);
}

function serializeRuntimeState(registry) {
  const states = [];
  const seen = new Map();

  function serializeMobject(mob) {
    if (!mob) return null;
    if (seen.has(mob)) return seen.get(mob);

    const ctorName = mob.constructor?.name;
    const opacity = typeof mob.opacity === "number" ? mob.opacity : 1;
    const zIndex = typeof mob.zIndex === "number" ? mob.zIndex : undefined;

    let state;
    if (ctorName === "VGroup") {
      const children = Array.isArray(mob.submobjects)
        ? mob.submobjects.map(serializeMobject).filter((r) => r !== null)
        : [];
      state = { kind: "VGroup", children, opacity };
      if (zIndex !== undefined) state.z_index = zIndex;
    } else {
      const kind = VMOBJECT_KINDS.has(ctorName) ? ctorName : "VMobject";
      const points = typeof mob.getPoints === "function"
        ? normalizePoints(mob.getPoints())
        : [];
      state = { kind, points, opacity };
      if (typeof mob.color === "string")       state.color       = mob.color;
      if (typeof mob.fillColor === "string")   state.fill_color  = mob.fillColor;
      if (typeof mob.fillOpacity === "number") state.fill_opacity = mob.fillOpacity;
      const strokeColor = typeof mob.strokeColor === "string" ? mob.strokeColor
        : typeof mob.color === "string" ? mob.color : undefined;
      if (strokeColor)                          state.stroke_color  = strokeColor;
      if (typeof mob.strokeWidth === "number") state.stroke_width  = mob.strokeWidth;
      if (typeof mob.opacity === "number")     state.stroke_opacity = mob.opacity;
      if (zIndex !== undefined)                state.z_index        = zIndex;
      if (mob.position && typeof mob.position.x === "number")
        state.position = [mob.position.x, mob.position.y, mob.position.z];
    }

    const ref = states.length;
    seen.set(mob, ref);
    states.push(state);
    return ref;
  }

  const snapshot = {};
  for (const id of Array.from(registry._registry.keys()).sort()) {
    const ref = serializeMobject(registry._registry.get(id));
    if (ref !== null) snapshot[id] = ref;
  }
  return { snapshot, states };
}

// ---------------------------------------------------------------------------
// Scene-graph validation
// ---------------------------------------------------------------------------

const errors = [];
const warnings = [];

function pushError(error, description, details = {}) {
  errors.push({ error, description, ...details });
}

function getThreeObjectOrError(mob, context) {
  if (!mob) {
    pushError("null_mobject", `Validation context '${context}' received null mobject`);
    return null;
  }
  if (typeof mob.getThreeObject !== "function") {
    pushError("missing_get_three_object",
      `Mobject in context '${context}' is missing getThreeObject()`,
      { mobjectId: mob._id ?? "unknown" });
    return null;
  }
  const obj = mob.getThreeObject();
  if (!obj) {
    pushError("null_three_object",
      `Mobject in context '${context}' returned null three object`,
      { mobjectId: mob._id ?? "unknown" });
    return null;
  }
  if (obj.visible === null || obj.visible === undefined) {
    pushError("invalid_visible",
      `Three object in context '${context}' has invalid visible`,
      { mobjectId: mob._id ?? "unknown" });
    return null;
  }
  return obj;
}

function validateMobjectTree(mob, context, seen = new Set()) {
  if (!mob || seen.has(mob)) return;
  seen.add(mob);
  const obj = getThreeObjectOrError(mob, context);
  if (obj && typeof obj.visible !== "boolean") {
    pushError("non_boolean_visible",
      `Three object visible is not boolean in context '${context}'`,
      { mobjectId: mob._id ?? "unknown", visibleType: typeof obj.visible });
  }
  const subs = Array.isArray(mob.submobjects) ? mob.submobjects : [];
  for (let i = 0; i < subs.length; i++) {
    if (!subs[i]) {
      pushError("null_submobject", `Null submobject at index ${i} in context '${context}'`,
        { mobjectId: mob._id ?? "unknown" });
      continue;
    }
    validateMobjectTree(subs[i], `${context}.submobjects[${i}]`, seen);
  }
}

function validateSceneGraph(scene, context) {
  for (const mob of scene.mobjects) {
    validateMobjectTree(mob, `${context}.scene_mobject`);
  }
}

// ---------------------------------------------------------------------------
// Input
// ---------------------------------------------------------------------------

async function readInput() {
  if (!filePathArg) {
    return new Promise((resolve, reject) => {
      let data = "";
      process.stdin.setEncoding("utf-8");
      process.stdin.on("data", (chunk) => (data += chunk));
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

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const input = await readInput();
const spec = JSON.parse(input);

const scene = Scene.createHeadless();
const registry = new MobjectRegistry();
const player = new Player(scene, registry, { debug: verbose });

player.setfps(spec.fps || 10);
player.setGlobalStates(spec.states || []);
player.setSections(spec.sections || []);

const sections = [];
const operations = [];

for (let i = 0; i < spec.sections.length; i++) {
  const section = spec.sections[i];
  operations.push({ type: "section_start", index: i, name: section.name });

  if (section.unsupported) {
    warnings.push({
      section: i,
      name: section.name,
      reason: section.unsupported_reason || "unknown",
    });
    sections.push({ name: section.name, skipped: true });
    continue;
  }

  const entry = { name: section.name };

  try {
    await player.seekToSection(i);
    validateSceneGraph(scene, `section:${section.name || i}`);
    for (const [mobId, mob] of registry._registry.entries()) {
      validateMobjectTree(mob, `registry:${mobId}`);
    }
    if (errors.length > 0) {
      throw new Error(`Scene graph validation failed after section ${section.name || i}`);
    }

    operations.push({ type: "section_end", index: i, name: section.name });
    entry.ids = Array.from(registry._registry.keys()).sort();
    if (outputEndState) entry.end_state = serializeRuntimeState(registry);
  } catch (e) {
    errors.push({
      section: i,
      name: section.name,
      error: e.message,
      stack: e.stack?.split("\n").slice(0, 3).join("\n"),
    });
    entry.failed = true;
  }

  sections.push(entry);
  if (entry.failed) break;
}

const report = {
  success: errors.length === 0,
  sections_total: spec.sections.length,
  warnings,
  errors,
  sections: outputIds || outputEndState
    ? sections
    : sections.map(({ name, skipped, failed }) => ({ name, skipped, failed })),
};
if (verbose) report.operations = operations;

// Always emit the full report as a single JSON object on stdout.
console.log(JSON.stringify(report, null, 2));

process.exit(errors.length > 0 ? 1 : 0);
