import {
  Circle,
  Square,
  Line,
  Arrow,
  Text,
  MathTex,
  VGroup,
  ValueTracker,
  Create,
  FadeIn,
  FadeOut,
  Write,
  ReplacementTransform,
  ApplyMatrix,
  smooth,
  linear,
} from "manim-web";

const KIND_MAP = {
  Circle,
  Square,
  Line,
  Arrow,
  Text,
  MathTex,
  VGroup,
  ValueTracker,
};

const RATE_FUNC_MAP = {
  smooth,
  linear,
};

export class MobjectRegistry {
  constructor() {
    this._registry = new Map();
    this._scene = null;
  }

  _kindToClass(kind) {
    const cls = KIND_MAP[kind];
    if (!cls) {
      console.warn(`Unknown mobject kind: ${kind}`);
      return null;
    }
    return cls;
  }

  _createMobject(entry) {
    const cls = this._kindToClass(entry.kind);
    if (!cls) return null;

    let mob;
    switch (entry.kind) {
      case "Circle":
        mob = new cls({ radius: 1 });
        break;
      case "Square":
        mob = new cls({ sideLength: 1 });
        break;
      case "Line":
        mob = new cls();
        break;
      case "Arrow":
        mob = new cls();
        break;
      case "Text":
        mob = new cls({ text: entry.tex_string || "" });
        break;
      case "MathTex":
        mob = new cls({ texString: entry.tex_string || "" });
        break;
      case "VGroup":
        mob = new cls();
        break;
      case "ValueTracker":
        mob = new cls({ value: entry.value || 0 });
        break;
      default:
        mob = new cls();
    }

    mob._id = entry.id;
    mob._entry = entry;
    return mob;
  }

  load(mobjectData) {
    this._registry.clear();

    const entries = Array.from(mobjectData.values());

    for (const entry of entries) {
      const mob = this._createMobject(entry);
      if (mob) {
        this._registry.set(entry.id, mob);
      }
    }

    for (const entry of entries) {
      if (entry.children && entry.children.length > 0) {
        const parent = this._registry.get(entry.id);
        if (parent && entry.kind === "VGroup") {
          for (const childId of entry.children) {
            const child = this._registry.get(childId);
            if (child) {
              parent.add(child);
            }
          }
        }
      }
    }

    return this._registry;
  }

  get(id) {
    return this._registry.get(id);
  }

  getAll() {
    return Array.from(this._registry.values());
  }

  applyMatrix(mob, matrix, scene) {
    if (!scene || !mob) return;
    const anim = new ApplyMatrix(mob, { matrix });
    scene.play(anim);
  }
}

export function buildAnimation(kind, mobjectRegistry, scene, animEntry) {
  const mob = mobjectRegistry.get(animEntry.mob_id);
  if (!mob) {
    console.warn(`Mobject not found: ${animEntry.mob_id}`);
    return null;
  }

  const rateFunc = RATE_FUNC_MAP[animEntry.rate_func] || smooth;

  switch (kind) {
    case "Create":
      return new Create(mob, { rateFunc });
    case "FadeIn":
      return new FadeIn(mob, { rateFunc });
    case "FadeOut":
      return new FadeOut(mob, { rateFunc });
    case "Write":
      return new Write(mob, { rateFunc });
    case "ReplacementTransform":
      return new ReplacementTransform(mob, mob, { rateFunc });
    default:
      console.warn(`Unknown animation kind: ${kind}`);
      return null;
  }
}
