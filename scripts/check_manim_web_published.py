#!/usr/bin/env python3
"""Check that the manim-web version pinned by js/build-remote.ts is published.

js/build-remote.ts bakes the manim-web submodule's package.json version into
a jsDelivr URL for ManimWidget(js="remote")'s _esm. If that version hasn't
actually been published to npm yet, a PyPI release would ship a remote
pointer that 404s in the browser. This hits jsDelivr (which mirrors npm)
directly, so it also verifies the CDN copy is live, not just the registry.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

package_json = json.loads(Path("manim-web/package.json").read_text())
version = package_json["version"]

url = f"https://cdn.jsdelivr.net/npm/manim-web@{version}/dist/manim-web.browser.js"

request = urllib.request.Request(url, method="HEAD")
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        status = response.status
except urllib.error.HTTPError as exc:
    status = exc.code
except urllib.error.URLError as exc:
    print(f"ERROR: could not reach {url}: {exc.reason}")
    sys.exit(1)

if status != 200:
    print(
        f"ERROR: manim-web@{version} is not published (or not yet mirrored) "
        f"on jsDelivr: {url} returned HTTP {status}.\n"
        "js/build-remote.ts would bake this into the remote bundle, breaking "
        'ManimWidget(js="remote") for anyone loading it before the version '
        "is live."
    )
    sys.exit(1)

print(f"OK: manim-web@{version} is published and live at {url}.")
