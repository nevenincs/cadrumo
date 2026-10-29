"""Read the version of a Playwright driver from the package that carries its browser manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from cadrumo.core.type_guards import is_object_list

__all__ = ["BrowserBuild", "installed_playwright_driver_version", "required_browser_builds"]


@dataclass(frozen=True, slots=True)
class BrowserBuild:
    """A Chromium build named by a Playwright driver manifest."""

    name: str
    revision: str
    browser_version: str | None

    @property
    def directory_name(self) -> str:
        """Return Playwright's build directory name."""
        return f"{self.name.replace('-', '_')}-{self.revision}"


def _installed_manifest_path() -> Path | None:
    spec = find_spec("playwright")
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin).parent / "driver" / "package" / "browsers.json"


def _manifest_entries(manifest_path: Path) -> list[object] | None:
    try:
        document: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entries = document.get("browsers") if isinstance(document, dict) else None
    return entries if is_object_list(entries) else None


def _manifest_build(entries: list[object], name: str) -> BrowserBuild | None:
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("name") == name]
    if len(matches) != 1:
        return None
    entry = matches[0]
    revision = entry.get("revision")
    if entry.get("revisionOverrides") or not isinstance(revision, str) or not revision:
        return None
    version = entry.get("browserVersion")
    return BrowserBuild(name, revision, version if isinstance(version, str) and version else None)


def required_browser_builds(manifest_path: Path | None = None) -> tuple[BrowserBuild, ...] | None:
    """Read the headed and headless Chromium builds, refusing unrecognised manifests."""
    path = manifest_path if manifest_path is not None else _installed_manifest_path()
    if path is None:
        return None
    entries = _manifest_entries(path)
    if entries is None:
        return None
    builds: list[BrowserBuild] = []
    for name in ("chromium", "chromium-headless-shell"):
        build = _manifest_build(entries, name)
        if build is None:
            return None
        builds.append(build)
    return tuple(builds)


def installed_playwright_driver_version(manifest_path: Path) -> str | None:
    """Return the version of the Playwright driver whose ``browsers.json`` is ``manifest_path``."""
    try:
        document: object = json.loads((manifest_path.parent / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = document.get("version") if isinstance(document, dict) else None
    return version if isinstance(version, str) and version else None
