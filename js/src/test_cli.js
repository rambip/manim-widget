#!/usr/bin/env bun

// Temporary: happy-dom is needed for headless mode until manim-web provides
// a truly headless mode that doesn't require any DOM APIs.
// See: https://github.com/maloyan/manim-web/issues/214
import { GlobalRegistrator } from "@happy-dom/global-registrator";
GlobalRegistrator.register();

import * as fs from "fs";
import * as path from "path";

import { Scene, Create, FadeIn, FadeOut, Write, Rotate, ScaleInPlace, Transform, ReplacementTransform, Circle, Square, VMobject, VGroup } from "manim-web";
import { Player } from "./player.js";
import { MobjectRegistry } from "./registry.js";

const args = process.argv.slice(2);
const verbose = args.includes("--verbose") || args.includes("-v");
const outputIds = args.includes("--output-ids");
const outputEndState = args.includes("--output-end-state");
const filePathArg = args.find(arg => !arg.startsWith("-"));

const VMOBJECT_KINDS = new Set([
  "Circle",
  "Square",
  "Rectangle",
  "RoundedRectangle",
  "Triangle",
  "Polygon",
  "RegularPolygon",
  "Hexagon",
  "Pentagon",
  "Polygram",
  "ArcPolygon",
  "Line",
  "DashedLine",
  "CubicBezier",
  "Arrow",
  "DoubleArrow",
  "Vector",
  "CurvedArrow",
  "CurvedDoubleArrow",
  "Arc",
  "ArcBetweenPoints",
  "Ellipse",
  "Annulus",
  "AnnularSector",
  "Sector",
  "TangentialArc",
  "Dot",
  "SmallDot",
  "LargeDot",
  "BackgroundRectangle",
  "SurroundingRectangle",
  "Underline",
  "Cross",
  "Angle",
  "RightAngle",
  "Star",
  "Brace",
  "BraceBetweenPoints",
  "ArcBrace",
  "SVGMobject",
  "VMobjectFromSVGPath",
  "VMobject",
]);

function normalizePoints(points) {
  if (!Array.isArray(points)) {
    return [];
  }
  return points
    .filter((p) => Array.isArray(p) && p.length >= 3)
    .map((p) => [Number(p[0]) || 0, Number(p[1]) || 0, Number(p[2]) || 0]);
}

function serializeRuntimeState(registry) {
  const states = [];
  const seen = new Map();

  function serializeMobject(mob) {
    if (!mob) {
      return null;
    }
    if (seen.has(mob)) {
      return seen.get(mob);
    }

    const ctorName = mob.constructor?.name;
    const opacity = typeof mob.opacity === "number" ? mob.opacity : 1;
    const zIndex = typeof mob.zIndex === "number" ? mob.zIndex : undefined;

    let state;
    if (ctorName === "VGroup") {
      const children = Array.isArray(mob.submobjects)
        ? mob.submobjects.map(serializeMobject).filter((ref) => ref !== null)
        : [];
      state = {
        kind: "VGroup",
        children,
        opacity,
      };
      if (zIndex !== undefined) {
        state.z_index = zIndex;
      }
    } else {
      const kind = VMOBJECT_KINDS.has(ctorName) ? ctorName : "VMobject";
      const points = typeof mob.getPoints === "function" ? normalizePoints(mob.getPoints()) : [];

      state = {
        kind,
        points,
        opacity,
      };

      if (typeof mob.color === "string") {
        state.color = mob.color;
      }
      if (typeof mob.fillColor === "string") {
        state.fill_color = mob.fillColor;
      }
      if (typeof mob.fillOpacity === "number") {
        state.fill_opacity = mob.fillOpacity;
      }

      const strokeColor =
        typeof mob.strokeColor === "string"
          ? mob.strokeColor
          : typeof mob.color === "string"
            ? mob.color
            : undefined;
      if (typeof strokeColor === "string") {
        state.stroke_color = strokeColor;
      }
      if (typeof mob.strokeWidth === "number") {
        state.stroke_width = mob.strokeWidth;
      }
      if (typeof mob.opacity === "number") {
        state.stroke_opacity = mob.opacity;
      }
      if (zIndex !== undefined) {
        state.z_index = zIndex;
      }
    }

    const ref = states.length;
    seen.set(mob, ref);
    states.push(state);
    return ref;
  }

  const snapshot = {};
  const sortedIds = Array.from(registry._registry.keys()).sort();
  for (const id of sortedIds) {
    const mob = registry._registry.get(id);
    const ref = serializeMobject(mob);
    if (ref !== null) {
      snapshot[id] = ref;
    }
  }

  return { snapshot, states };
}

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

const scene = Scene.createHeadless();
const registry = new MobjectRegistry();
const player = new Player(scene, registry, { debug: verbose });

player.setfps(spec.fps || 10);
player.setSections(spec.sections || []);

const sectionIds = [];
const sectionEndStates = [];

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
    validateSceneGraph(scene, `section:${section.name || i}`);

    for (const [mobId, mob] of registry._registry.entries()) {
      validateMobjectTree(mob, `registry:${mobId}`);
    }

    if (errors.length > 0) {
      throw new Error(`Scene graph validation failed after section ${section.name || i}`);
    }

    operations.push({ type: "section_end", index: i, name: section.name });
    
    const ids = Array.from(registry._registry.keys());
    sectionIds.push({
      name: section.name,
      ids: ids.sort(),
    });

    if (outputEndState) {
      sectionEndStates.push({
        name: section.name,
        end_state: serializeRuntimeState(registry),
      });
    }
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

if (verbose) {
  console.log("\n=== Operations ===");
  for (const op of operations) {
    console.log(`  ${JSON.stringify(op)}`);
  }
}

if (outputEndState) {
  console.log("\n=== Section End State ===");
  const output = { sections: sectionEndStates };
  console.log(JSON.stringify(output, null, 2));
}

if (outputIds) {
  console.log("\n=== Section Mobject IDs ===");
  const output = { sections: sectionIds };
  console.log(JSON.stringify(output, null, 2));
}

process.exit(0);
