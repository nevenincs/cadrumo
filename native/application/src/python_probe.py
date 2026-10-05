"""Fixed read-only interpreter probe; domain policy stays with its Python owners."""

import importlib.metadata
import json
import platform
import struct
import sys
from pathlib import Path

request = json.load(sys.stdin)
distributions = {}
for name in request["distributions"]:
    try:
        distributions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        distributions[name] = None

browser = None
if request["browser"]:
    from cadrumo.core.optional_extras import BROWSER_EXTRA, optional_extra_available

    if not optional_extra_available(BROWSER_EXTRA):
        browser = {"state": "missing_dependency", "builds": [], "owner_report": None}
    else:
        from cadrumo.application.provisioning_browser import (
            probe_playwright_browser,
            required_browser_builds,
        )

        builds = required_browser_builds()
        root = request["browser_root"]
        report = probe_playwright_browser(Path(root) if root is not None else None)
        browser = {
            "state": ("unreadable_manifest" if builds is None else "ready" if report.available else "missing_builds"),
            "builds": [
                {"name": build.name, "revision": build.revision, "directory_name": build.directory_name}
                for build in builds or ()
            ],
            "owner_report": report.model_dump(mode="json"),
        }

json.dump(
    {
        "schema": 1,
        "implementation": sys.implementation.name,
        "version": platform.python_version(),
        "pointer_bits": struct.calcsize("P") * 8,
        "executable": sys.executable,
        "distributions": distributions,
        "browser": browser,
    },
    sys.stdout,
)
