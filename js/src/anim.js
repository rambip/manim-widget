import {
  Add,
  Create,
  FadeIn,
  FadeOut,
  Rotate,
  ScaleInPlace,
  Write,
  GrowFromCenter,
  GrowArrow,
  MoveAlongPath,
  Rotating,
} from "manim-web";

export function buildSimpleAnimation(mob, desc, registry) {
  const params = desc.params || {};
  switch (desc.kind) {
    case "Add":
      return new Add(mob);
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
    case "GrowArrow":
      return new GrowArrow(mob);
    case "Rotating":
      return new Rotating(mob, {
        aboutPoint: params.aboutPoint ?? params.about_point,
      });
    case "MoveAlongPath": {
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
    }
    default:
      console.warn(`Unsupported simple animation kind: ${desc.kind}`);
      return null;
  }
}
