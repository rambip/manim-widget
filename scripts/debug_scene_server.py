from __future__ import annotations

import argparse
import importlib
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from manim_widget import ManimWidget


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>manim-widget debug viewer</title>
    <style>
      :root {
        color-scheme: light;
        font-family: "Iosevka Web", "JetBrains Mono", ui-monospace, monospace;
        --bg: #f2f1ed;
        --panel: #ffffff;
        --ink: #1c1c1a;
        --muted: #6c6a62;
        --accent: #1f6feb;
      }

      html,
      body {
        margin: 0;
        background: radial-gradient(circle at 20% 10%, #fff, var(--bg) 55%);
        color: var(--ink);
      }

      .layout {
        display: grid;
        gap: 12px;
        max-width: 1120px;
        margin: 18px auto;
        padding: 0 14px 18px;
      }

      .panel {
        background: var(--panel);
        border: 1px solid #d9d4c7;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(30, 24, 8, 0.07);
      }

      .toolbar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        padding: 12px;
      }

      button,
      input[type="range"] {
        font: inherit;
      }

      button {
        border-radius: 8px;
        border: 1px solid #c3c0b5;
        background: #fff;
        color: var(--ink);
        padding: 6px 10px;
        cursor: pointer;
      }

      button.primary {
        border-color: transparent;
        background: var(--accent);
        color: #fff;
      }

      #viewer {
        height: 560px;
        min-height: 320px;
        border-top: 1px solid #e4dfd3;
      }

      #status {
        color: var(--muted);
      }

      #error {
        margin: 0;
        padding: 10px 12px;
        border-top: 1px solid #ecd3d3;
        background: #fff8f8;
        color: #8b1f1f;
        min-height: 1.3em;
        white-space: pre-wrap;
      }

      #sceneMeta {
        padding: 0 12px 12px;
        color: var(--muted);
      }
    </style>
    <script type="importmap">
      {
        "imports": {
          "manim-web": "__MANIM_WEB_URL__"
        }
      }
    </script>
  </head>
  <body>
    <main class="layout">
      <section class="panel">
        <div class="toolbar">
          <button id="reload" class="primary">Reload scene</button>
          <button id="play">Play</button>
          <button id="pause">Pause</button>
          <button id="copyError">Copy error</button>
          <input id="section" type="range" min="0" max="0" value="0" />
          <span id="status">idle</span>
        </div>
        <div id="viewer"></div>
        <pre id="error"></pre>
        <div id="sceneMeta"></div>
      </section>
    </main>

    <script type="module">
      import { Scene } from "manim-web";

      const dom = {
        reload: document.querySelector("#reload"),
        play: document.querySelector("#play"),
        pause: document.querySelector("#pause"),
        copyError: document.querySelector("#copyError"),
        section: document.querySelector("#section"),
        status: document.querySelector("#status"),
        viewer: document.querySelector("#viewer"),
        error: document.querySelector("#error"),
        sceneMeta: document.querySelector("#sceneMeta"),
      };

      let runtime = {
        data: null,
        player: null,
      };

      let runtimeModules = {
        Player: null,
        MobjectRegistry: null,
      };

      async function loadRuntimeModules() {
        const cacheBust = Date.now();
        const [playerModule, registryModule] = await Promise.all([
          import(`/js/src/player.js?v=${cacheBust}`),
          import(`/js/src/registry.js?v=${cacheBust}`),
        ]);
        runtimeModules = {
          Player: playerModule.Player,
          MobjectRegistry: registryModule.MobjectRegistry,
        };
      }

      const seenErrorBlocks = new Set();

      function stringifyErrorLike(value) {
        if (!value) {
          return "";
        }
        if (typeof value === "string") {
          return value;
        }
        const message = value.message ? String(value.message) : "";
        const stack = value.stack ? String(value.stack) : "";
        if (message && stack) {
          if (stack.startsWith(message)) {
            return stack;
          }
          return `${message}\n${stack}`;
        }
        return message || stack || String(value);
      }

      function setError(value) {
        if (!value) {
          dom.error.textContent = "";
          seenErrorBlocks.clear();
          return;
        }
        if (!dom.error.textContent) {
          dom.error.textContent = value;
          seenErrorBlocks.add(value);
        }
      }

      function appendErrorDetail(value) {
        if (!value) {
          return;
        }
        if (seenErrorBlocks.has(value)) {
          return;
        }
        if (!dom.error.textContent) {
          dom.error.textContent = value;
          seenErrorBlocks.add(value);
          return;
        }
        dom.error.textContent = `${dom.error.textContent}\n\n---\n${value}`;
        seenErrorBlocks.add(value);
      }

      async function renderSection(index) {
        if (!runtime.player || !runtime.data) {
          return;
        }

        const sections = runtime.data.sections || [];
        const section = sections[index];
        if (!section) {
          return;
        }

        dom.status.textContent = `section ${index + 1}/${sections.length}: ${section.name || "unnamed"}`;
        dom.section.value = String(index);
        await runtime.player.seekToSection(index);
      }

      async function loadScene() {
        setError("");
        dom.status.textContent = "loading scene...";

        await loadRuntimeModules();

        const response = await fetch("/scene.json", { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Failed to fetch /scene.json: HTTP ${response.status}`);
        }

        const data = await response.json();
        const sections = Array.isArray(data.sections) ? data.sections : [];
        dom.sceneMeta.textContent = `version=${data.version} fps=${data.fps} sections=${sections.length}`;

        dom.viewer.innerHTML = "";
        const scene = new Scene(dom.viewer, { width: 960, height: 540 });
        const registry = new runtimeModules.MobjectRegistry();
        const player = new runtimeModules.Player(scene, registry, { debug: true });
        player.setfps(data.fps || 10);
        player.setSections(sections);

        runtime = { data, player };

        dom.section.max = String(Math.max(0, sections.length - 1));
        dom.section.value = "0";

        if (sections.length > 0) {
          await renderSection(0);
        } else {
          dom.status.textContent = "no sections";
        }
      }

      dom.reload.addEventListener("click", async () => {
        try {
          await loadScene();
        } catch (error) {
          console.error(error);
          setError(error?.stack || String(error));
          dom.status.textContent = "reload failed";
        }
      });

      dom.play.addEventListener("click", async () => {
        if (!runtime.player || !runtime.data) {
          return;
        }
        await runtime.player.play();
        const start = Number.parseInt(dom.section.value || "0", 10);
        const sections = runtime.data.sections || [];
        for (let i = start; i < sections.length; i += 1) {
          if (!runtime.player.isPlaying) {
            break;
          }
          await renderSection(i);
        }
      });

      dom.pause.addEventListener("click", async () => {
        if (!runtime.player) {
          return;
        }
        await runtime.player.pause();
      });

      dom.copyError.addEventListener("click", async () => {
        const text = dom.error.textContent || "";
        if (!text) {
          return;
        }
        try {
          await navigator.clipboard.writeText(text);
          dom.status.textContent = "error copied";
        } catch (error) {
          console.error(error);
          setError(error?.stack || String(error));
        }
      });

      dom.section.addEventListener("input", async () => {
        try {
          const index = Number.parseInt(dom.section.value || "0", 10);
          await renderSection(index);
        } catch (error) {
          console.error(error);
          setError(error?.stack || String(error));
        }
      });

      globalThis.addEventListener("error", (event) => {
        const stack = stringifyErrorLike(event?.error) || event?.message || "window.error";
        const playerDebug = globalThis.__MW_LAST_PLAYER_DEBUG
          ? `\n\nlastPlayerDebug:\n${JSON.stringify(globalThis.__MW_LAST_PLAYER_DEBUG, null, 2)}`
          : "";
        setError(`${stack}${playerDebug}`);
      });

      globalThis.addEventListener("unhandledrejection", (event) => {
        const reason = event?.reason;
        const stack = stringifyErrorLike(reason) || String(reason);
        const playerDebug = globalThis.__MW_LAST_PLAYER_DEBUG
          ? `\n\nlastPlayerDebug:\n${JSON.stringify(globalThis.__MW_LAST_PLAYER_DEBUG, null, 2)}`
          : "";
        setError(`${stack}${playerDebug}`);
      });

      const originalConsoleError = console.error.bind(console);
      console.error = (...args) => {
        originalConsoleError(...args);
        const text = args.map((part) => stringifyErrorLike(part)).filter(Boolean).join(" ");
        if (!text) {
          return;
        }
        if (text.includes("material.visible") || text.includes("material is null")) {
          const playerDebug = globalThis.__MW_LAST_PLAYER_DEBUG
            ? `\n\nlastPlayerDebug:\n${JSON.stringify(globalThis.__MW_LAST_PLAYER_DEBUG, null, 2)}`
            : "";
          appendErrorDetail(`console.error: ${text}${playerDebug}`);
        }
      };

      try {
        await loadScene();
      } catch (error) {
        console.error(error);
        setError(error?.stack || String(error));
        dom.status.textContent = "initial load failed";
      }
    </script>
  </body>
</html>
"""


def parse_scene_ref(scene_ref: str) -> tuple[str, str]:
    if ":" not in scene_ref:
        raise ValueError("scene ref must be in the form 'module.path:ClassName'")
    module_name, class_name = scene_ref.split(":", 1)
    if not module_name or not class_name:
        raise ValueError("scene ref must be in the form 'module.path:ClassName'")
    return module_name, class_name


def load_scene_payload(scene_ref: str) -> dict:
    module_name, class_name = parse_scene_ref(scene_ref)
    existing = sys.modules.get(module_name)
    if existing is None:
        module = importlib.import_module(module_name)
    else:
        module = importlib.reload(existing)
    scene_cls = getattr(module, class_name)
    if not isinstance(scene_cls, type) or not issubclass(scene_cls, ManimWidget):
        raise TypeError(f"{scene_ref} must point to a ManimWidget subclass")
    scene = scene_cls()
    return json.loads(scene.scene_data)


def resolve_static_path(raw_path: str) -> Path | None:
    path = urlparse(raw_path).path
    if path == "/":
        return None
    normalized = path.lstrip("/")
    if not normalized:
        return None
    candidate = (PROJECT_ROOT / normalized).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def make_handler(scene_ref: str, manim_web_url: str):
    class Handler(BaseHTTPRequestHandler):
        def _write(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path

            if path == "/":
                html = HTML_TEMPLATE.replace("__MANIM_WEB_URL__", manim_web_url)
                self._write(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return

            if path == "/scene.json":
                try:
                    payload = load_scene_payload(scene_ref)
                except Exception as exc:
                    err = {
                        "error": str(exc),
                        "scene_ref": scene_ref,
                    }
                    self._write(
                        500,
                        json.dumps(err, indent=2).encode("utf-8"),
                        "application/json; charset=utf-8",
                    )
                    return

                self._write(
                    200,
                    json.dumps(payload, indent=2).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return

            static_path = resolve_static_path(self.path)
            if static_path is not None:
                if static_path.suffix == ".js":
                    content_type = "application/javascript; charset=utf-8"
                elif static_path.suffix == ".json":
                    content_type = "application/json; charset=utf-8"
                elif static_path.suffix == ".css":
                    content_type = "text/css; charset=utf-8"
                elif static_path.suffix == ".html":
                    content_type = "text/html; charset=utf-8"
                else:
                    content_type = "application/octet-stream"
                self._write(200, static_path.read_bytes(), content_type)
                return

            self._write(404, b"Not found", "text/plain; charset=utf-8")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve a debug viewer with live scene JSON and unbundled manim-web.",
    )
    parser.add_argument(
        "scene",
        help="Scene reference in the form module.path:ClassName",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the Python debug server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the Python debug server (default: 8765)",
    )
    parser.add_argument(
        "--manim-web-url",
        default="http://127.0.0.1:5173/src/index.ts",
        help="Module URL to unbundled manim-web served by Vite.",
    )
    args = parser.parse_args()

    parse_scene_ref(args.scene)
    handler = make_handler(args.scene, args.manim_web_url)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print("Debug viewer ready")
    print(f"- Scene: {args.scene}")
    print(f"- URL:   http://{args.host}:{args.port}/")
    print(f"- manim-web module URL: {args.manim_web_url}")
    print("- Start manim-web dev server in another terminal:")
    print("  cd manim-web && npm run dev -- --host 127.0.0.1 --port 5173 --cors")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
