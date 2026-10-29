"""Location of the Playwright Chromium build Cadrumo's browser automation drives.

The installed ``playwright`` package pins exact browser revisions in its bundled
``browsers.json`` manifest, and launches only those revisions. A build is in
place when its revision folder under the browsers folder Playwright is given
holds the ``INSTALLATION_COMPLETE`` marker Playwright itself writes after
unpacking it, so builds left by an earlier Playwright version never read as
present. Nothing here launches the driver.

A missing build is refused with a plain statement that the browser is not
available, rather than surfacing Playwright's raw launch error.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from importlib.util import find_spec
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from ..core.config import Settings, load_settings
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.storage_environment import configured_storage_root, resolve_storage_path
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location
from ..core.type_guards import is_object_dict, is_object_list
from .probe_outcomes import (
    ProbeFactValue,
    ProbePreconditionCondition,
    probe_no_recovery_verdict,
)
from .workstation_probes import DependencyStatus

__all__ = [
    "PLAYWRIGHT_BROWSER_SERVICE",
    "BrowserBuild",
    "playwright_browsers_root",
    "probe_playwright_browser",
    "required_browser_builds",
]

PLAYWRIGHT_BROWSER_SERVICE = "playwright-chromium"

#: The file Playwright writes into a build's folder once the build is unpacked.
_INSTALLATION_MARKER: Final = "INSTALLATION_COMPLETE"

#: The manifest entries the browser covers: the full build for headed
#: launches, and the headless shell a default headless launch uses.
_REQUIRED_MANIFEST_NAMES = ("chromium", "chromium-headless-shell")


class BrowserBuild(BaseModel):
    """One revision-pinned browser build the installed Playwright launches."""

    model_config = STRICT_FROZEN_CONFIG

    name: str
    revision: str
    browser_version: str | None = None

    @property
    def directory_name(self) -> str:
        """Return the cache directory Playwright extracts this build into."""
        return f"{self.name.replace('-', '_')}-{self.revision}"


def playwright_browsers_root(
    cache_root: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    settings: Settings | None = None,
) -> Path:
    """Return the directory Playwright keeps browser binaries in.

    Uses an explicit ``cache_root`` when supplied. Otherwise the Cadrumo
    ``CADRUMO_PLAYWRIGHT_BROWSERS_DIR`` setting controls the managed cache,
    rooted under the configured storage root by default. Injectable ``env`` and
    ``settings`` allow precedence checks without changing ambient process state.
    """
    if cache_root is not None:
        return cache_root
    environment = os.environ if env is None else env
    if settings is not None and "cadrumo_playwright_browsers_dir" in settings.model_fields_set:
        return settings.cadrumo_playwright_browsers_dir
    storage_root = configured_storage_root(environ=environment)
    cadrumo_override = environment.get("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", "").strip()
    if cadrumo_override:
        return resolve_storage_path(cadrumo_override, root=storage_root)
    if settings is not None:
        return settings.cadrumo_playwright_browsers_dir
    if env is None:
        return load_settings().cadrumo_playwright_browsers_dir
    default = storage_location(StorageCategory.PLAYWRIGHT_BROWSERS).relative_path()
    return resolve_storage_path(default, root=storage_root)


def _installed_manifest_path() -> Path | None:
    """Locate the installed Playwright package's browser manifest without importing it."""
    spec = find_spec("playwright")
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin).parent / "driver" / "package" / "browsers.json"


def _browser_manifest_entries(document: object) -> dict[object, dict[object, object]] | None:
    if not is_object_dict(document):
        return None
    entries = document.get("browsers")
    if not is_object_list(entries):
        return None
    by_name: dict[object, dict[object, object]] = {}
    for entry in entries:
        if is_object_dict(entry):
            by_name[entry.get("name")] = entry
    return by_name


def _browser_build_from_manifest(
    name: str,
    by_name: dict[object, dict[object, object]],
) -> BrowserBuild | None:
    found = by_name.get(name)
    if found is None or found.get("revisionOverrides"):
        return None
    revision = found.get("revision")
    if not isinstance(revision, str) or not revision:
        return None
    version = found.get("browserVersion")
    return BrowserBuild(
        name=name,
        revision=revision,
        browser_version=version if isinstance(version, str) and version else None,
    )


def required_browser_builds(manifest_path: Path | None = None) -> tuple[BrowserBuild, ...] | None:
    """Return the Chromium builds the installed Playwright pins, or ``None`` when unreadable.

    A manifest entry carrying per-host revision overrides is treated as
    unreadable rather than guessed, because the host key it is selected by is
    Playwright's own internal classification.
    """
    path = manifest_path if manifest_path is not None else _installed_manifest_path()
    if path is None:
        return None
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    by_name = _browser_manifest_entries(document)
    if by_name is None:
        return None
    builds: list[BrowserBuild] = []
    for name in _REQUIRED_MANIFEST_NAMES:
        build = _browser_build_from_manifest(name, by_name)
        if build is None:
            return None
        builds.append(build)
    return tuple(builds)


def probe_playwright_browser(
    cache_root: Path | None = None,
    *,
    manifest_path: Path | None = None,
    settings: Settings | None = None,
) -> DependencyStatus:
    """Locate the browser builds the installed Playwright driver launches.

    This only locates: it confirms that every build the driver names has its
    revision folder, with Playwright's completion marker, under the browsers
    folder this process hands Playwright. An unreadable driver (Playwright
    absent or its manifest unrecognised) and a missing build are both refused as
    a browser that is not available.
    """
    # No fact names a folder or a path: the verdict is published with every
    # refusal, and a path outside the storage root is never published.
    root = playwright_browsers_root(cache_root, settings=settings)
    builds = required_browser_builds(manifest_path)
    if builds is None:
        facts: dict[str, ProbeFactValue] = {
            "browser_manifest_readable": False,
            "chromium_installed": False,
        }
        return DependencyStatus(
            service=PLAYWRIGHT_BROWSER_SERVICE,
            available=False,
            facts=facts,
            precondition_verdict=probe_no_recovery_verdict(
                ProbePreconditionCondition.PLAYWRIGHT_BROWSER_MANIFEST_READABLE,
                facts=facts,
            ),
        )
    missing = tuple(
        build.directory_name for build in builds if not (root / build.directory_name / _INSTALLATION_MARKER).is_file()
    )
    facts = {
        "required_builds": ",".join(build.directory_name for build in builds),
        "chromium_installed": not missing,
    }
    if builds[0].browser_version is not None:
        facts["browser_version"] = builds[0].browser_version
    if missing:
        facts["missing_builds"] = ",".join(missing)
        return DependencyStatus(
            service=PLAYWRIGHT_BROWSER_SERVICE,
            available=False,
            facts=facts,
            precondition_verdict=probe_no_recovery_verdict(
                ProbePreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED,
                facts=facts,
            ),
        )
    return DependencyStatus(service=PLAYWRIGHT_BROWSER_SERVICE, available=True, facts=facts)
