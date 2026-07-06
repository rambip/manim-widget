import { ThreeDScene, Scene } from "manim-web";
import { MobjectRegistry } from "./registry.js";
import { createPlayer } from "./player.js";
import { diffSceneData } from "./diff.js";

// Global registry for SharedCamera coordination across widget instances.
// Key: camera_id string. Value: { listeners: Set<(state) => void> }
// Camera state is a CameraState object {kind:"Camera", points, focal_distance}.
const _sharedCameras = (globalThis.__MW_SHARED_CAMERAS ??= new Map());

// CSS lives in style.css (loaded via anywidget's _css, the same way index.js
// is loaded via _esm) rather than being inlined here.
function buildUi(el) {
  el.innerHTML = `
    <div id="mw-wrapper">
      <div id="mw-video-area">
        <div id="mw-container"></div>
        <button id="mw-overlay-play" title="Play"><span class="mw-play-icon">▶</span></button>
      </div>
      <div id="mw-warning">Unsupported section</div>
      <div id="mw-controls">
        <div id="mw-play-area">
          <button id="mw-play" title="Play">↻</button>
        </div>
        <div id="mw-sections">
          <div id="mw-sections-header">
            <span class="mw-label">Section:</span>
            <button id="mw-deselect" title="Unselect section">×</button>
          </div>
          <div id="mw-section-buttons"></div>
        </div>
        <div id="mw-3d-toggle">
          <label><input type="checkbox" id="mw-3d-checkbox">3D</label>
        </div>
      </div>
    </div>
  `;

  return {
    wrapper: el.querySelector("#mw-wrapper"),
    container: el.querySelector("#mw-container"),
    controlsDiv: el.querySelector("#mw-controls"),
    playBtn: el.querySelector("#mw-play"),
    overlayPlayBtn: el.querySelector("#mw-overlay-play"),
    deselectBtn: el.querySelector("#mw-deselect"),
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
  // Index of the currently radio-selected section, or -1 when none selected.
  let selectedIndex = -1;

  const sharedCamWire = wireSharedCamera(model, () => player, () => scene);

  function updateSectionStyles(currentlyPlayingIndex = -1) {
    const labels = ui.sectionsDiv.querySelectorAll('.mw-section-label');
    labels.forEach((label, i) => {
      const radio = label.querySelector('input[type="radio"]');
      const isSelected = radio.checked;
      const isPlaying = i === currentlyPlayingIndex;

      label.classList.toggle('selected', isSelected);
      label.classList.toggle('playing', !isSelected && isPlaying);
    });
    const hasSelection = Array.from(labels).some(l => l.querySelector('input').checked);
    ui.deselectBtn.style.display = hasSelection ? 'inline' : 'none';

    // Scroll the currently playing section into view at the left edge, in
    // one smooth motion — but only when it's at least partly clipped by the
    // scrollable area, so playback within the visible range doesn't jitter
    // the scroll position.
    const playingLabel = labels[currentlyPlayingIndex];
    if (playingLabel) {
      const container = ui.sectionsDiv;
      const labelLeft = playingLabel.offsetLeft;
      const labelRight = labelLeft + playingLabel.offsetWidth;
      const viewLeft = container.scrollLeft;
      const viewRight = viewLeft + container.clientWidth;
      const fullyVisible = labelLeft >= viewLeft && labelRight <= viewRight;
      if (!fullyVisible) {
        container.scrollTo({ left: labelLeft, behavior: 'smooth' });
      }
    }
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

  async function playFromSection(startIndex) {
    ui.overlayPlayBtn.style.display = "none";
    await player.play();
    for (let i = startIndex; i < sceneData.sections.length; i += 1) {
      if (!player.isPlaying) {
        break;
      }
      await renderSection(i);
    }
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
    const orbitControlsUp = model.get("orbit_controls_up") || "z";
    const aspectRatio = (data.frame_width && data.frame_height)
      ? data.frame_width / data.frame_height
      : 16 / 9;
    // canvas_width/canvas_height are mutually exclusive (enforced Python-side):
    // only one pixel dimension can be set explicitly, the other is always
    // derived from the frame's aspect ratio so pixels and world units stay
    // in sync.
    const canvasHeightOpt = model.get("canvas_height");
    let pxWidth;
    let pxHeight;
    if (canvasHeightOpt) {
      pxHeight = canvasHeightOpt;
      pxWidth = Math.round(pxHeight * aspectRatio);
    } else {
      pxWidth = model.get("canvas_width") || 600;
      pxHeight = Math.round(pxWidth / aspectRatio);
    }
    const backgroundColor = data.background_color ?? '#000000';
    ui.wrapper.style.width = `${pxWidth}px`;
    ui.container.style.width = `${pxWidth}px`;
    ui.container.style.height = `${pxHeight}px`;
    scene = is3D
      ? new ThreeDScene(ui.container, { width: pxWidth, height: pxHeight, enableOrbitControls: true, orbitControlsUp, backgroundColor })
      : new Scene(ui.container, { width: pxWidth, height: pxHeight, backgroundColor });
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
        return `<label class="mw-section-label"><input type="radio" name="mw-section" value="${i}" style="display:none;"><span>${name}</span></label>`;
      })
      .join("");

    ui.controlsDiv.style.display = model.get("show_controls") === false ? "none" : "";

    updateSectionStyles();
    selectedIndex = -1;

    sharedCamWire?.patchPlayer();

    if (model.get("autoplay") !== false) {
      await playFromSection(0);
    } else {
      ui.overlayPlayBtn.style.display = "flex";
    }
  }

  ui.overlayPlayBtn.addEventListener("click", async () => {
    if (!player || !sceneData) {
      return;
    }
    await playFromSection(0);
  });

  function clearSectionSelection() {
    const radios = ui.sectionsDiv.querySelectorAll('input[type="radio"]');
    radios.forEach(r => { r.checked = false; });
    updateSectionStyles(-1);
    selectedIndex = -1;
  }

  ui.playBtn.addEventListener("click", async () => {
    if (!player || !sceneData) {
      return;
    }

    // Reset: jump back to the start. If autoplay is on, replay immediately;
    // otherwise clear the canvas and show the overlay Play button again.
    await player.stop();
    clearSectionSelection();
    if (model.get("autoplay") !== false) {
      await playFromSection(0);
    } else {
      player.clearScene();
      ui.overlayPlayBtn.style.display = "flex";
    }
  });

  ui.sectionsDiv.addEventListener("change", async (e) => {
    if (!sceneData || e.target.name !== "mw-section") {
      return;
    }
    updateSectionStyles();
    ui.overlayPlayBtn.style.display = "none";
    const index = Number.parseInt(e.target.value, 10);
    selectedIndex = index;
    await renderSection(index, false);
  });

  async function unselectSection() {
    if (!player || !sceneData) {
      return;
    }
    const resumeFrom = selectedIndex >= 0 ? selectedIndex : 0;
    clearSectionSelection();
    await playFromSection(resumeFrom);
  }

  ui.deselectBtn.addEventListener("click", unselectSection);

  ui.sectionsDiv.addEventListener("click", (e) => {
    if (e.target.closest('.mw-section-label')) {
      return;
    }
    // Click on background - unselect, same as the deselect button
    unselectSection();
  });

  const onSceneDataChange = async () => {
    const data = model.get("data");
    if (!data) return;

    const diff = diffSceneData(sceneData, data);

    if (diff.kind === "none") return;

    if (diff.kind === "states" || diff.kind === "states+camera") {
      console.log(`[manim-widget] state updated (states: ${diff.states.length})`);
      sceneData = data;
      player.updateStates(diff.states);
      if (diff.bgColor) scene.renderer.backgroundColor = diff.bgColor;
      scene.render();
    } else if (diff.kind === "camera") {
      sceneData = data;
      if (diff.bgColor) scene.renderer.backgroundColor = diff.bgColor;
      player.applyCamera(diff.section, diff.camera);
    } else {
      await loadScene(data);
    }
  };
  model.on("change:data", onSceneDataChange);

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

  const initialData = model.get("data");
  if (initialData) {
    await loadScene(initialData);
  }

  return () => {
    sharedCamWire?.cleanup();
    model.off("change:data", onSceneDataChange);
    model.off("change:is_3d", onIs3dChange);
  };
}

export default { render };
