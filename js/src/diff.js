/**
 * Diff two scene_data payloads and classify the change.
 *
 * Returns one of:
 *   { kind: "full" }                          — structure changed, full reload needed
 *   { kind: "states", states, bgColor? }      — only state objects (and optionally bg) mutated
 *   { kind: "camera", section, camera, bgColor? }
 *   { kind: "states+camera", states, section, camera, bgColor? }
 *   { kind: "none" }                          — identical
 *
 * bgColor is set when background_color changed but no full reload is needed.
 */
export function diffSceneData(prev, next) {
  if (!prev || !next) return { kind: "full" };
  if (prev.version !== next.version) return { kind: "full" };
  if (prev.fps !== next.fps) return { kind: "full" };
  if (prev.frame_width !== next.frame_width) return { kind: "full" };
  if (prev.frame_height !== next.frame_height) return { kind: "full" };

  const prevBg = prev.background_color ?? '#000000';
  const nextBg = next.background_color ?? '#000000';
  const bgColor = prevBg !== nextBg ? nextBg : null;

  const ps = prev.sections;
  const ns = next.sections;
  if (!ps || !ns || ps.length !== ns.length) return { kind: "full" };

  let statesChanged = false;
  let cameraSection = null;
  let cameraValue = null;

  // Compare global state bank
  const prevStates = prev.states;
  const nextStates = next.states;
  if (!prevStates || !nextStates || prevStates.length !== nextStates.length) return { kind: "full" };
  if (JSON.stringify(prevStates) !== JSON.stringify(nextStates)) statesChanged = true;

  for (let i = 0; i < ps.length; i++) {
    const p = ps[i];
    const n = ns[i];

    if (p.name !== n.name) return { kind: "full" };

    // snapshot and construct must be identical
    if (JSON.stringify(p.snapshot) !== JSON.stringify(n.snapshot)) return { kind: "full" };
    if (JSON.stringify(p.construct) !== JSON.stringify(n.construct)) return { kind: "full" };

    // camera may differ on at most one section
    const camSame = JSON.stringify(p.camera) === JSON.stringify(n.camera);
    if (!camSame) {
      if (cameraSection !== null) return { kind: "full" }; // two sections differ
      cameraSection = i;
      cameraValue = n.camera;
    }
  }

  if (!statesChanged && cameraSection === null && !bgColor) return { kind: "none" };

  const states = nextStates;

  if (statesChanged && cameraSection !== null) {
    return { kind: "states+camera", states, section: cameraSection, camera: cameraValue, bgColor };
  }
  if (statesChanged) {
    return { kind: "states", states, bgColor };
  }
  return { kind: "camera", section: cameraSection, camera: cameraValue, bgColor };
}
