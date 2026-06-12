import { ThreeDScene, Scene } from "manim-web";
import { MobjectRegistry } from "./registry.js";
import { createPlayer } from "./player.js";
import { diffSceneData } from "./diff.js";

// Global registry for SharedCamera coordination across widget instances.
// Key: camera_id string. Value: { listeners: Set<(state) => void> }
// Camera state is a CameraState object {kind:"Camera", points, focal_distance}.
const _sharedCameras = (globalThis.__MW_SHARED_CAMERAS ??= new Map());

function buildUi(el) {
  el.innerHTML = `
    <div id="mw-wrapper" style="display:inline-flex;flex-direction:column;max-width:100%;">
      <div id="mw-video-area" style="position:relative;">
        <div id="mw-container" style="width:600px;height:400px;max-width:100%;"></div>
      </div>
      <div id="mw-warning" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(200,0,0,0.9);color:white;padding:14px;border-radius:8px;font-weight:bold;z-index:10;pointer-events:none;">
        Unsupported section
      </div>
      <div id="mw-controls" style="width:100%;box-sizing:border-box;display:flex;gap:0;align-items:stretch;margin-top:4px;background:rgba(200,200,200,1);">
        <div id="mw-play-area" style="padding:4px;">
          <button id="mw-play" style="font-size:2em;background:transparent;border:none;cursor:pointer;margin:0 8px;">↻</button>
        </div>
        <div id="mw-sections" style="flex:1;display:flex;flex-direction:column;padding:0;background:transparent;">
          <div style="padding:2px 8px;font-size:1em;color:black;text-align:center;font-style:italic;font-weight:bold;">Section:</div>
          <div id="mw-section-buttons" style="display:flex;gap:2px;padding:0 8px 0 8px;justify-content:center;align-items:stretch;"></div>
        </div>
        <div id="mw-3d-toggle" style="padding:4px 8px;display:flex;align-items:center;gap:4px;">
          <label style="cursor:pointer;display:flex;align-items:center;gap:4px;font-size:0.9em;color:rgba(0,0,0,0.7);"><input type="checkbox" id="mw-3d-checkbox">3D</label>
        </div>
      </div>
    </div>
  `;

  return {
    container: el.querySelector("#mw-container"),
    playBtn: el.querySelector("#mw-play"),
    sectionsDiv: el.querySelector("#mw-section-buttons"),
    warning: el.querySelector("#mw-warning"),
    d3Checkbox: el.querySelector("#mw-3d-checkbox"),
  };
}

function wireSharedCamera(model, getPlayer, getScene) {
  const cameraId = model.get("shared_camera_id");
  if (!cameraId) return;

  if (!_sharedCameras.has(cameraId)) {
    _sharedCameras.set(cameraId, { listeners: new Set() });
  }
  const entry = _sharedCameras.get(cameraId);

  // Subscribe: when another widget pushes a camera state, apply it directly
  // via the original (unpatched) method to avoid re-broadcasting.
  let origApply = null;
  const listener = (state) => {
    if (origApply) {
      origApply(state);
    } else {
      const p = getPlayer();
      if (p) p._applyCameraState(state);
    }
  };
  entry.listeners.add(listener);

  let _orbitCleanup = null;

  // Publish: patch the player's _applyCameraState to also broadcast.
  // Called after getPlayer() is guaranteed non-null (after loadScene).
  function patchPlayer() {
    const p = getPlayer();
    if (!p || p.__sharedCameraPatch) return;
    p.__sharedCameraPatch = true;
    const orig = p._applyCameraState.bind(p);
    origApply = orig; // listener uses this to avoid calling the patched version
    p._applyCameraState = (state) => {
      orig(state);
      // Broadcast to other subscribers, skipping ourselves.
      for (const l of entry.listeners) {
        if (l !== listener) l(state);
      }
    };

    // Also broadcast when the user moves the orbit controls directly —
    // those bypass _applyCameraState entirely.
    const s = getScene?.();
    if (s?.orbitControls) {
      if (_orbitCleanup) _orbitCleanup();
      const onOrbitChange = () => {
        const angles = s.camera3D.getOrbitAngles();
        const t = s.camera3D.lookAtTarget;
        const state = {
          kind: "OrbitState",
          phi: angles.phi,
          theta: angles.theta,
          distance: angles.distance,
          target: [t.x, t.y, t.z],
        };
        for (const l of entry.listeners) {
          if (l !== listener) l(state);
        }
      };
      s.orbitControls.addEventListener("change", onOrbitChange);
      _orbitCleanup = () => s.orbitControls.removeEventListener("change", onOrbitChange);
    }
  }

  return {
    cleanup: () => {
      entry.listeners.delete(listener);
      _orbitCleanup?.();
    },
    patchPlayer,
  };
}

async function render({ model, el }) {
  if (!globalThis.__MW_ERROR_HOOKS_INSTALLED) {
    globalThis.__MW_ERROR_HOOKS_INSTALLED = true;
    globalThis.addEventListener("error", (event) => {
      try {
        console.error("[ManimWidget] window.error", {
          args: [event?.message, event?.filename, event?.lineno, event?.colno, event?.error],
          lastAnimationDebug: globalThis.__MW_LAST_ANIM_DEBUG || null,
        });
      } catch {
        // best-effort diagnostics only
      }
    });
    globalThis.addEventListener("unhandledrejection", (event) => {
      try {
        console.error("[ManimWidget] unhandledrejection", {
          reason: event?.reason,
          lastAnimationDebug: globalThis.__MW_LAST_ANIM_DEBUG || null,
        });
      } catch {
        // best-effort diagnostics only
      }
    });
  }

  const ui = buildUi(el);

  let player = null;
  let sceneData = null;
  let scene = null;
  let registry = null;

  const sharedCamWire = wireSharedCamera(model, () => player, () => scene);

  function updateSectionStyles(currentlyPlayingIndex = -1) {
    const labels = ui.sectionsDiv.querySelectorAll('.mw-section-label');
    labels.forEach((label, i) => {
      const radio = label.querySelector('input[type="radio"]');
      const span = label.querySelector('span');

      const isSelected = radio.checked;
      const isPlaying = i === currentlyPlayingIndex;

      if (isSelected) {
        // Selected: background color
        label.style.background = 'rgba(120,120,120,1)';
        label.style.border = '1px solid transparent';
        span.style.color = 'rgba(255,255,255,1)';
        span.style.fontWeight = 'bold';
      } else if (isPlaying) {
        // Currently playing: font change
        label.style.background = 'transparent';
        label.style.border = '1px solid rgba(0,0,0,0.3)';
        span.style.color = 'rgba(0,0,0,1)';
        span.style.fontWeight = 'bold';
      } else {
        // Default: border only
        label.style.background = 'transparent';
        label.style.border = '1px solid rgba(0,0,0,0.3)';
        span.style.color = 'rgba(0,0,0,0.5)';
        span.style.fontWeight = 'normal';
      }
    });
  }

  async function renderSection(index, updatePlaying = true) {
    if (!player || !sceneData) {
      return;
    }

    const section = sceneData.sections[index];
    if (!section) {
      return;
    }

    if (updatePlaying) {
      updateSectionStyles(index);
    }

    if (section.unsupported) {
      ui.warning.style.display = "block";
      ui.warning.textContent = section.unsupported_reason
        ? `Unsupported section: ${section.unsupported_reason}`
        : "Unsupported section";
      return;
    }

    ui.warning.style.display = "none";
    await player.seekToSection(index);
  }

  async function loadScene(data) {
    if (!data || data.version !== 2 || !Array.isArray(data.sections)) {
      console.warn("[manim-widget] invalid scene payload");
      return;
    }

    console.log(`[manim-widget] scene created (sections: ${data.sections.length}, states: ${(data.states || []).length})`);
    sceneData = data;
    ui.container.innerHTML = "";
    console.log("[manim-widget] scene cleared");

    const is3D = model.get("is_3d");
    const pxWidth = 600;
    const aspectRatio = (data.frame_width && data.frame_height)
      ? data.frame_width / data.frame_height
      : 16 / 9;
    const pxHeight = Math.round(pxWidth / aspectRatio);
    ui.container.style.height = `${pxHeight}px`;
    scene = is3D
      ? new ThreeDScene(ui.container, { width: pxWidth, height: pxHeight, enableOrbitControls: true, orbitControlsUp: 'z' })
      : new Scene(ui.container, { width: pxWidth, height: pxHeight });
    registry = new MobjectRegistry();
    player = createPlayer(scene, registry);
    // Allow patchPlayer to re-wire orbit controls on the new scene instance.
    delete player.__sharedCameraPatch;
    player.setfps(data.fps || 10);
    player.setStates(data.states || []);
    player.setSections(data.sections);

    ui.sectionsDiv.innerHTML = data.sections
      .map((s, i) => {
        const name = s.name || `${i + 1}`;
        return `<label class="mw-section-label" style="cursor:pointer;padding:2px 8px;border-radius:4px;border:1px solid rgba(0,0,0,0.3);background:transparent;min-width:10em;text-align:center;display:flex;align-items:center;justify-content:center;"><input type="radio" name="mw-section" value="${i}" style="display:none;"><span style="color:rgba(0,0,0,0.5);">${name}</span></label>`;
      })
      .join("");

    updateSectionStyles();

    sharedCamWire?.patchPlayer();

    // Auto-play all sections on load
    await player.play();
    for (let i = 0; i < sceneData.sections.length; i += 1) {
      if (!player.isPlaying) {
        break;
      }
      await renderSection(i);
    }
  }

  ui.playBtn.addEventListener("click", async () => {
    if (!player || !sceneData) {
      return;
    }

    const checkedRadio = ui.sectionsDiv.querySelector('input[name="mw-section"]:checked');
    if (checkedRadio) {
      // Replay just the selected section
      const currentIndex = Number.parseInt(checkedRadio.value, 10);
      await renderSection(currentIndex);
    } else {
      // No section selected - replay all sections from start
      await player.stop();
      await player.play();
      for (let i = 0; i < sceneData.sections.length; i += 1) {
        if (!player.isPlaying) {
          break;
        }
        await renderSection(i);
      }
      // Reset to default style after playing all
      updateSectionStyles(-1);
    }
  });

  ui.sectionsDiv.addEventListener("change", async (e) => {
    if (!sceneData || e.target.name !== "mw-section") {
      return;
    }
    updateSectionStyles();
    const index = Number.parseInt(e.target.value, 10);
    await renderSection(index, false);
  });

  ui.sectionsDiv.addEventListener("click", (e) => {
    if (e.target.closest('.mw-section-label')) {
      return;
    }
    // Click on background - unset all radios
    const radios = ui.sectionsDiv.querySelectorAll('input[type="radio"]');
    radios.forEach(r => { r.checked = false; });
    updateSectionStyles(-1);
  });

  const onSceneDataChange = async () => {
    const data = model.get("scene_data");
    if (!data) return;

    const diff = diffSceneData(sceneData, data);

    if (diff.kind === "none") return;

    if (diff.kind === "states" || diff.kind === "states+camera") {
      console.log(`[manim-widget] state updated (states: ${diff.states.length})`);
      sceneData = data;
      player.updateStates(diff.states);
      scene.render();
    } else if (diff.kind === "camera") {
      sceneData = data;
      player.applyCamera(diff.section, diff.camera);
    } else {
      await loadScene(data);
    }
  };
  model.on("change:scene_data", onSceneDataChange);

  const onIs3dChange = async () => {
    ui.d3Checkbox.checked = model.get("is_3d");
    if (sceneData) {
      await loadScene(sceneData);
    }
  };
  model.on("change:is_3d", onIs3dChange);

  ui.d3Checkbox.addEventListener("change", async () => {
    model.set("is_3d", ui.d3Checkbox.checked);
    model.save_changes();
  });

  // Initialize checkbox from model
  ui.d3Checkbox.checked = model.get("is_3d") || false;

  const initialData = model.get("scene_data");
  if (initialData) {
    await loadScene(initialData);
  }

  return () => {
    sharedCamWire?.cleanup();
    model.off("change:scene_data", onSceneDataChange);
    model.off("change:is_3d", onIs3dChange);
  };
}

export default { render };
