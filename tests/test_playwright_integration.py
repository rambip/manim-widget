from __future__ import annotations

import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Generator

import pytest
from manim import LEFT, Circle, Create, FadeIn, Square
from playwright.sync_api import Page, expect

from manim_widget.widget import ManimWidget

SRC_DIR = Path(__file__).parent.parent / "js" / "src"


class TestPlaywrightIntegration:
    @pytest.fixture(scope="session", autouse=True)
    def http_server(self, server_dir: Path) -> Generator[str]:
        """Starts a single HTTP server on an ephemeral port for the entire test session."""

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(server_dir), **kwargs)

            def log_message(self, format, *args):
                pass  # Suppress server logs in test output

        # Port 0 asks the OS to assign an available port dynamically
        server = HTTPServer(("localhost", 0), Handler)
        port = server.server_port

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        yield f"http://localhost:{port}"

        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    @pytest.fixture(scope="session")
    def server_dir(self, tmp_path_factory) -> Path:
        return tmp_path_factory.mktemp("html_server")

    @pytest.fixture
    def js_error_tracker(self, page: Page):
        """Captures JS console errors and page errors."""
        errors = []
        page_errors = []

        def handle_console(msg):
            if msg.type == "error":
                errors.append(msg.text)

        def handle_page_error(err):
            page_errors.append(str(err))

        page.on("console", handle_console)
        page.on("pageerror", handle_page_error)

        tracker = {
            "console_errors": errors,
            "page_errors": page_errors,
            "clear": lambda: (errors.clear(), page_errors.clear()),
        }

        yield tracker

        page.remove_listener("console", handle_console)
        page.remove_listener("pageerror", handle_page_error)

    @pytest.fixture
    def render_scene(
        self, server_dir: Path, http_server: str, page: Page, js_error_tracker
    ):
        """Helper to set up the file system and navigate."""

        def _render(scene_data: str, test_name: str, check_errors: bool = True):
            js_error_tracker["clear"]()
            # 1. Copy source files to the server directory so imports work naturally
            for js_file in ["registry.js", "player.js", "index.js"]:
                content = (SRC_DIR / js_file).read_text()
                (server_dir / js_file).write_text(content)

            # 2. Build the HTML. Note: index.js is now a real file next to test.html
            escaped_data = json.dumps(scene_data)
            html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script type="importmap">
  {{
    "imports": {{
      "manim-web": "https://esm.sh/manim-web@0.3.16",
      "three": "https://esm.sh/three@0.180.0"
    }}
  }}
  </script>
</head>
<body>
  <div id="widget"></div>
  <script type="module">
    // Import the REAL file from the server
    import widgetModule from './index.js';

    const widget = document.getElementById("widget");
    const model = {{
      get: (trait) => {{
        if (trait === "scene_data") return {escaped_data};
        return null;
      }},
      on: (event, callback) => {{
        if (event === "change:scene_data") setTimeout(callback, 100);
      }}
    }};

    // Call the exported render function
    widgetModule.render({{ model, el: widget }});
  </script>
</body>
</html>"""

            html_file = server_dir / f"{test_name}.html"
            html_file.write_text(html_content)
            page.goto(f"{http_server}/{test_name}.html")
            page.wait_for_timeout(500)

            if check_errors:
                all_errors = (
                    js_error_tracker["console_errors"] + js_error_tracker["page_errors"]
                )
                assert len(all_errors) == 0, (
                    f"JS errors detected: console={js_error_tracker['console_errors']}, page={js_error_tracker['page_errors']}"
                )

        return _render

    def test_canvas_element_created(self, simple_scene_data, render_scene, page: Page):
        # This will now work because ./index.js, ./registry.js, and ./player.js
        # are all sitting in the same folder on your test server.
        render_scene(simple_scene_data, "canvas_test")

        # Use a locator that waits for the canvas
        canvas = page.locator("#mw-container canvas")
        expect(canvas).to_be_attached(timeout=5000)

    @pytest.fixture
    def simple_scene_data(self) -> str:
        class SimpleScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))

        scene = SimpleScene()
        return scene.scene_data

    @pytest.fixture
    def animate_shift_left_data(self) -> str:
        class AnimateShiftLeftScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.play(c.animate.shift(LEFT))

        scene = AnimateShiftLeftScene()
        return scene.scene_data

    def test_animate_shift_left(
        self, animate_shift_left_data, render_scene, page: Page, js_error_tracker
    ):
        render_scene(animate_shift_left_data, "test_shift_left.html")

        container = page.locator("#mw-container")
        expect(container).to_be_visible()
        warning = page.locator("#mw-warning")
        expect(warning).to_be_hidden()

        scrubber = page.locator("#mw-scrubber")
        expect(scrubber).to_be_visible()

        initial_text = page.locator("#mw-section-info")
        expect(initial_text).to_have_text("initial")

        payload = json.loads(animate_shift_left_data)
        total_duration_s = 0.0
        for section in payload.get("sections", []):
            commands = section.get("construct") or section.get("segments") or []
            for cmd in commands:
                total_duration_s += float(cmd.get("duration", cmd.get("run_time", 0.0)))

        wait_ms = int(total_duration_s * 1000) + 500

        page.locator("#mw-play").click()
        page.wait_for_timeout(wait_ms)
        all_errors = (
            js_error_tracker["console_errors"] + js_error_tracker["page_errors"]
        )
        assert len(all_errors) == 0, (
            f"JS errors detected after playback: console={js_error_tracker['console_errors']}, page={js_error_tracker['page_errors']}"
        )

    @pytest.fixture
    def multi_section_data(self) -> str:
        class MultiSectionScene(ManimWidget):
            def construct(self):
                c = Circle()
                self.play(Create(c))
                self.next_section("second")
                s = Square()
                self.play(FadeIn(s))

        scene = MultiSectionScene()
        return scene.scene_data

    def test_simple_scene_loads_in_browser(
        self, simple_scene_data, render_scene, page: Page
    ):
        render_scene(simple_scene_data, "test_scene.html")

        # Playwright's locator and expect handle waiting implicitly
        container = page.locator("#mw-container")
        expect(container).to_be_visible()

        warning = page.locator("#mw-warning")
        expect(warning).to_be_hidden()

    def test_scene_has_play_controls(self, simple_scene_data, render_scene, page: Page):
        render_scene(simple_scene_data, "test_controls.html")

        expect(page.locator("#mw-play")).to_be_visible()
        expect(
            page.locator("#mw-pause")
        ).to_be_attached()  # Might be hidden initially, so check attachment
        expect(page.locator("#mw-scrubber")).to_be_visible()

    def test_section_info_shows_initial(
        self, simple_scene_data, render_scene, page: Page
    ):
        render_scene(simple_scene_data, "test_section_info.html")

        section_info = page.locator("#mw-section-info")
        expect(section_info).to_have_text("initial")

    def test_multi_section_scene(self, multi_section_data, render_scene, page: Page):
        render_scene(multi_section_data, "test_multi_section.html")

        scrubber = page.locator("#mw-scrubber")
        expect(scrubber).to_be_visible()
        expect(scrubber).to_have_attribute("max", "1")

    def test_invalid_points_raises_js_error(self, render_scene, page: Page):
        invalid_scene_data = {
            "version": 1,
            "fps": 10,
            "sections": [
                {
                    "name": "intro",
                    "construct": [
                        {
                            "cmd": "add",
                            "id": "circle1",
                            "state": {
                                "kind": "Circle",
                                "points": [
                                    [0, 0, 0],
                                    [1, 1, 1],
                                    [2, 0, 0],
                                    [3, 1, 1],
                                    [4, 0, 0],
                                    [5, 1, 1],
                                    [6, 0, 0],
                                    [7, 1, 1],
                                    [8, 0, 0],
                                ],
                                "position": [0, 0, 0],
                                "opacity": 1,
                            },
                        }
                    ],
                }
            ],
        }

        errors = []
        page_errors = []

        def handle_console(msg):
            if msg.type == "error":
                errors.append(msg.text)

        def handle_page_error(err):
            page_errors.append(str(err))

        page.on("console", handle_console)
        page.on("pageerror", handle_page_error)
        render_scene(
            json.dumps(invalid_scene_data),
            "test_invalid_points.html",
            check_errors=False,
        )
        page.wait_for_timeout(1000)

        all_errors = errors + page_errors
        assert len(all_errors) > 0, (
            f"Expected a JS error for invalid 3n+1 points. console: {errors}, page: {page_errors}"
        )
        assert "3n+1" in all_errors[0] or "9" in all_errors[0]
