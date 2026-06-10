import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(scope="session")
def runner():
    from js_runner import JSRunner

    debug = os.environ.get("MANIM_WIDGET_JS_DEBUG") == "1"
    return JSRunner(debug=debug)
