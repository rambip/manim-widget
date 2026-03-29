import { Scene } from "manim-web";
import { MobjectRegistry } from "./registry.js";
import { Player } from "./player.js";

async function render({ model, el }) {
  el.innerHTML = `
    <div style="position:relative;width:100%;height:100%;">
      <div id="mw-container" style="width:100%;height:100%;"></div>
      <div id="mw-controls" style="position:absolute;bottom:0;left:0;right:0;padding:10px;background:rgba(0,0,0,0.5);display:flex;gap:10px;align-items:center;">
        <button id="mw-play">Play</button>
        <button id="mw-pause">Pause</button>
        <span id="mw-section-info" style="color:white;"></span>
      </div>
      <div id="mw-warning" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(200,0,0,0.9);color:white;padding:20px;border-radius:8px;font-weight:bold;">
        Unsupported section: geometry updates detected
      </div>
    </div>
  `;

  const container = el.querySelector("#mw-container");
  const playBtn = el.querySelector("#mw-play");
  const pauseBtn = el.querySelector("#mw-pause");
  const sectionInfo = el.querySelector("#mw-section-info");
  const warning = el.querySelector("#mw-warning");

  let scene = null;
  let registry = null;
  let player = null;

  async function loadScene(jsonData) {
    if (!jsonData || !jsonData.mobjects || !jsonData.sections) {
      console.warn("Invalid scene data");
      return;
    }

    container.innerHTML = "";

    scene = new Scene(container, { width: 600, height: 400 });
    registry = new MobjectRegistry();
    player = new Player(scene, registry);

    const mobjectMap = new Map(jsonData.mobjects.map((m) => [m.id, m]));
    registry.load(mobjectMap);
    player.setfps(jsonData.fps);

    player.setOnSectionChange((index) => {
      const section = jsonData.sections[index];
      if (section) {
        sectionInfo.textContent = section.name;
        if (!section.supported) {
          warning.style.display = "block";
        } else {
          warning.style.display = "none";
        }
      }
    });

    if (jsonData.sections.length > 0) {
      const firstSection = jsonData.sections[0];
      sectionInfo.textContent = firstSection.name;
      if (!firstSection.supported) {
        warning.style.display = "block";
      }
    }

    await player.play();
    for (const section of jsonData.sections) {
      if (!player.isPlaying) break;
      await player._playSection(section);
    }
  }

  playBtn.addEventListener("click", () => {
    if (player) player.play();
  });

  pauseBtn.addEventListener("click", () => {
    if (player) player.pause();
  });

  model.on("change:scene_data", () => {
    const jsonStr = model.get("scene_data");
    if (jsonStr) {
      try {
        const jsonData = JSON.parse(jsonStr);
        loadScene(jsonData);
      } catch (e) {
        console.error("Failed to parse scene_data:", e);
      }
    }
  });

  const initialData = model.get("scene_data");
  if (initialData) {
    try {
      const jsonData = JSON.parse(initialData);
      loadScene(jsonData);
    } catch (e) {
      console.error("Failed to parse initial scene_data:", e);
    }
  }
}

export default { render };
