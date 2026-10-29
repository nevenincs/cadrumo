"""Read the version of a Playwright driver from the package that carries its browser manifest."""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["installed_playwright_driver_version"]


def installed_playwright_driver_version(manifest_path: Path) -> str | None:
    """Return the version of the Playwright driver whose ``browsers.json`` is ``manifest_path``."""
    try:
        document: object = json.loads((manifest_path.parent / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = document.get("version") if isinstance(document, dict) else None
    return version if isinstance(version, str) and version else None
