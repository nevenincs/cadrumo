"""Location of the Playwright Chromium build Cadrumo's browser automation drives.

The installed ``playwright`` package pins exact browser revisions in its bundled
``browsers.json`` manifest, and launches only those revisions. The native
component engine installs them and, once they verify, writes the browser's
record. :func:`probe_playwright_browser` only locates the browser from that
record (:mod:`~cadrumo.core.component_records`): the record must be for the
browsers folder Playwright is given and for the installed driver's version, and
the executables it names must exist, so builds left by an earlier Playwright
version, or builds no engine checked, never read as installed. Nothing here
launches the driver.

A missing build is refused with a recovery action naming the browser setup
rather than surfacing Playwright's raw launch error.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from importlib.util import find_spec
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from ..core.component_records import ComponentItem, component_records_root, locate_component
from ..core.config import Settings, load_settings
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance
from ..core.storage_environment import configured_storage_root, resolve_storage_path
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location
from ..core.type_guards import is_object_dict, is_object_list
from .operator_actions.models import ActionReference, ConditionEvidence, PreconditionVerdict
from .provisioning import DependencyStatus
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)

__all__ = [
    "BROWSER_PROVISION_ACTION_ID",
    "BROWSER_RECORD_DRIVER_FACT",
    "PLAYWRIGHT_BROWSER_SERVICE",
    "BrowserBuild",
    "browser_not_provisioned_verdict",
    "installed_playwright_driver_version",
    "playwright_browsers_root",
    "probe_playwright_browser",
    "required_browser_builds",
]

PLAYWRIGHT_BROWSER_SERVICE = "playwright-chromium"

#: Catalogue action whose target command provisions the browser.
BROWSER_PROVISION_ACTION_ID = "operator.provision.browser"

#: The manifest entries the browser item covers: the full build for headed
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
    """Return the directory Playwright installs browser binaries into.

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


def installed_playwright_driver_version(manifest_path: Path) -> str | None:
    """Return the version of the Playwright driver whose ``browsers.json`` is ``manifest_path``."""
    try:
        document: object = json.loads((manifest_path.parent / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = document.get("version") if is_object_dict(document) else None
    return version if isinstance(version, str) and version else None


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


def browser_not_provisioned_verdict(facts: Mapping[str, ProvisioningFactValue]) -> PreconditionVerdict:
    """Return the refusal for a missing browser build, recovered by the provisioning command."""
    condition = ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    return PreconditionVerdict(
        failed_condition_id=condition,
        evidence=(
            ConditionEvidence(
                condition_id=condition,
                evidence_id=f"{condition}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values=facts,
            ),
        ),
        action=ActionReference(action_id=BROWSER_PROVISION_ACTION_ID),
        conditionality=ActionConditionality.IMMEDIATE,
    )


#: The identity fact the engine's browser record carries: the driver version its builds belong to.
BROWSER_RECORD_DRIVER_FACT: Final = "playwright_driver"


def probe_playwright_browser(
    cache_root: Path | None = None,
    *,
    manifest_path: Path | None = None,
    settings: Settings | None = None,
    records_root: Path | None = None,
) -> DependencyStatus:
    """Locate the browser the component engine installed, from the record it wrote.

    This only locates: it reads the engine's browser record and confirms that
    the executables it names exist. The record must be for the browsers folder
    this process hands Playwright and for the installed driver's version,
    because the driver launches only the builds it names. A browser without
    such a record is refused with the browser setup action, which installs it
    or records builds already in place. An unreadable driver (Playwright absent
    or its manifest unrecognised) is refused without a recovery action, because
    setting the browser up cannot repair it.
    """
    # No fact names a folder or a path: the verdict is published with every
    # refusal, and a path outside the storage root is never published.
    root = playwright_browsers_root(cache_root, settings=settings)
    manifest = manifest_path if manifest_path is not None else _installed_manifest_path()
    builds = required_browser_builds(manifest)
    driver = None if manifest is None or builds is None else installed_playwright_driver_version(manifest)
    if builds is None or driver is None:
        facts: dict[str, ProvisioningFactValue] = {
            "browser_manifest_readable": False,
            "chromium_installed": False,
        }
        return DependencyStatus(
            service=PLAYWRIGHT_BROWSER_SERVICE,
            available=False,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_MANIFEST_READABLE,
                facts=facts,
            ),
        )
    located = locate_component(
        ComponentItem.BROWSER,
        records_root=component_records_root(settings) if records_root is None else records_root,
        expected_folder=root,
        expected_facts={BROWSER_RECORD_DRIVER_FACT: driver},
    )
    facts = {
        "required_builds": ",".join(build.directory_name for build in builds),
        "browser_record": located.outcome.value,
        "chromium_installed": located.located,
    }
    if located.version is not None:
        facts["browser_version"] = located.version
    if located.missing:
        # The names of the record's paths, never the paths themselves.
        facts["missing_builds"] = ",".join(located.missing)
    if not located.located:
        return DependencyStatus(
            service=PLAYWRIGHT_BROWSER_SERVICE,
            available=False,
            facts=facts,
            precondition_verdict=browser_not_provisioned_verdict(facts),
        )
    return DependencyStatus(service=PLAYWRIGHT_BROWSER_SERVICE, available=True, facts=facts)
