import { Scene } from "manim-web";
import { MobjectRegistry } from "./registry.js";
import { createPlayer } from "./player.js";

function buildUi(el) {
  el.innerHTML = `
    <div style="position:relative;width:100%;height:100%;">
      <div id="mw-container" style="width:100%;height:100%;"></div>
      <div id="mw-controls" style="position:absolute;bottom:0;left:0;right:0;padding:10px;background:rgba(0,0,0,0.55);display:flex;gap:10px;align-items:center;">
        <button id="mw-play">Play</button>
        <button id="mw-pause">Pause</button>
        <input type="range" id="mw-scrubber" min="0" max="0" value="0" style="flex:1;cursor:pointer;">
        <span id="mw-section-info" style="color:white;min-width:100px;"></span>
      </div>
      <div id="mw-warning" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(200,0,0,0.9);color:white;padding:14px;border-radius:8px;font-weight:bold;">
        Unsupported section
      </div>
    </div>
  `;

  return {
    container: el.querySelector("#mw-container"),
    playBtn: el.querySelector("#mw-play"),
    pauseBtn: el.querySelector("#mw-pause"),
    scrubber: el.querySelector("#mw-scrubber"),
    sectionInfo: el.querySelector("#mw-section-info"),
    warning: el.querySelector("#mw-warning"),
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

  async function renderSection(index) {
    if (!player || !sceneData) {
      return;
    }

    const section = sceneData.sections[index];
    if (!section) {
      return;
    }

    ui.sectionInfo.textContent = section.name || "";
    ui.scrubber.value = String(index);

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
      console.warn("Invalid V2 scene payload");
      return;
    }

    sceneData = data;
    ui.container.innerHTML = "";

    const scene = new Scene(ui.container, { width: 600, height: 400 });
    const registry = new MobjectRegistry();
    player = createPlayer(scene, registry);
    player.setfps(data.fps || 10);
    player.setSections(data.sections);

    ui.scrubber.max = String(Math.max(0, data.sections.length - 1));
    ui.scrubber.value = "0";

    if (data.sections.length > 0) {
      await renderSection(0);
    }
  }

  ui.playBtn.addEventListener("click", async () => {
    if (!player || !sceneData) {
      return;
    }

    await player.play();
    let start = Number.parseInt(ui.scrubber.value || "0", 10);
    if (!Number.isFinite(start) || start < 0) {
      start = 0;
    }

    for (let i = start; i < sceneData.sections.length; i += 1) {
      if (!player.isPlaying) {
        break;
      }
      await renderSection(i);
    }
  });

  ui.pauseBtn.addEventListener("click", async () => {
    if (player) {
      await player.pause();
    }
  });

  ui.scrubber.addEventListener("input", async () => {
    if (!sceneData) {
      return;
    }
    const index = Number.parseInt(ui.scrubber.value, 10);
    await renderSection(index);
  });

  model.on("change:scene_data", async () => {
    const data = model.get("scene_data");
    if (!data) {
      return;
    }
    await loadScene(data);
  });

  const initialData = model.get("scene_data");
  if (initialData) {
    await loadScene(initialData);
  }
}

export default { render };
