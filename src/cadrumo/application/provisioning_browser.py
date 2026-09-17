"""Provisioning of the Playwright Chromium build Cadrumo's browser automation drives.

The installed ``playwright`` package pins exact browser revisions in its bundled
``browsers.json`` manifest, and launches only those revisions. The probe here
therefore reads that manifest and checks the revision-exact cache directories
and their completion markers, so a stale build left by an earlier Playwright
version never reads as installed. It is a filesystem read: the Playwright driver
can hang inside the CLI process, so nothing here launches it.

:func:`install_playwright_browser` is the explicit acquisition step behind
``aeat config provision browser``. It is idempotent and runs the vendor
installer only through the injected runner, which the outbound browser-runtime
adapter supplies. A missing build is refused with a recovery action naming that
command rather than surfacing Playwright's raw launch error.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from importlib.util import find_spec
from pathlib import Path

from pydantic import BaseModel, model_validator

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance
from .operator_actions.models import ActionReference, ConditionEvidence, PreconditionVerdict
from .provisioning import DependencyStatus
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
)

__all__ = [
    "BROWSER_PROVISION_ACTION_ID",
    "PLAYWRIGHT_BROWSER_INSTALL_TIMEOUT_S",
    "PLAYWRIGHT_BROWSER_SERVICE",
    "BrowserBuild",
    "BrowserInstallOutcome",
    "BrowserInstallerRunner",
    "browser_not_provisioned_verdict",
    "install_playwright_browser",
    "playwright_browsers_root",
    "probe_playwright_browser",
    "required_browser_builds",
]

PLAYWRIGHT_BROWSER_SERVICE = "playwright-chromium"

#: Catalogue action whose target command provisions the browser.
BROWSER_PROVISION_ACTION_ID = "operator.provision.browser"

#: Two archives of roughly two hundred megabytes each over an operator's connection.
PLAYWRIGHT_BROWSER_INSTALL_TIMEOUT_S = 1800.0

#: The manifest entries ``playwright install chromium`` provisions: the full
#: build for headed and ``channel="chromium"`` launches, and the headless shell
#: a default headless launch uses.
_REQUIRED_MANIFEST_NAMES = ("chromium", "chromium-headless-shell")

#: Marker Playwright writes once a build is fully extracted.
_INSTALLATION_COMPLETE_MARKER = "INSTALLATION_COMPLETE"

BrowserInstallerRunner = Callable[[float], int]
"""Runs the vendor browser install within a timeout and returns its exit code."""


class BrowserBuild(BaseModel):
    """One revision-pinned browser build the installed Playwright launches."""

    model_config = STRICT_FROZEN_CONFIG

    name: str
    revision: str

    @property
    def directory_name(self) -> str:
        """Return the cache directory Playwright extracts this build into."""
        return f"{self.name.replace('-', '_')}-{self.revision}"


def playwright_browsers_root(cache_root: Path | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    """Return the directory Playwright installs browser binaries into.

    Uses an explicit ``cache_root`` when supplied, otherwise honours
    ``PLAYWRIGHT_BROWSERS_PATH`` then falls back to the per-OS default cache.
    The cache is vendor-owned: Cadrumo reads it and lets the vendor installer
    write it, and it is intentionally not a Cadrumo storage setting. ``env`` is
    injectable so the override precedence is testable without mutating the
    process environment.
    """
    if cache_root is not None:
        return cache_root
    environment = os.environ if env is None else env
    override = environment.get("PLAYWRIGHT_BROWSERS_PATH")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = environment.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def _installed_manifest_path() -> Path | None:
    """Locate the installed Playwright package's browser manifest without importing it."""
    spec = find_spec("playwright")
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin).parent / "driver" / "package" / "browsers.json"


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
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entries = document.get("browsers") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        return None
    by_name = {entry.get("name"): entry for entry in entries if isinstance(entry, dict)}
    builds: list[BrowserBuild] = []
    for name in _REQUIRED_MANIFEST_NAMES:
        entry = by_name.get(name)
        if entry is None or entry.get("revisionOverrides"):
            return None
        revision = entry.get("revision")
        if not isinstance(revision, str) or not revision:
            return None
        builds.append(BrowserBuild(name=name, revision=revision))
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


def _build_installed(root: Path, build: BrowserBuild) -> bool:
    try:
        return (root / build.directory_name / _INSTALLATION_COMPLETE_MARKER).is_file()
    except OSError:
        return False


def probe_playwright_browser(
    cache_root: Path | None = None,
    *,
    manifest_path: Path | None = None,
) -> DependencyStatus:
    """Report whether every Chromium build the installed Playwright launches is present.

    Missing builds are refused with the provisioning action. An unreadable
    manifest (Playwright absent or its layout unrecognised) is refused without a
    recovery action, because installing a browser cannot repair it.
    """
    root = playwright_browsers_root(cache_root)
    builds = required_browser_builds(manifest_path)
    if builds is None:
        facts: dict[str, ProvisioningFactValue] = {
            "browser_cache_root": str(root),
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
    missing = [build.directory_name for build in builds if not _build_installed(root, build)]
    facts = {
        "browser_cache_root": str(root),
        "required_builds": ",".join(build.directory_name for build in builds),
        "chromium_installed": not missing,
    }
    if missing:
        facts["missing_builds"] = ",".join(missing)
        return DependencyStatus(
            service=PLAYWRIGHT_BROWSER_SERVICE,
            available=False,
            facts=facts,
            precondition_verdict=browser_not_provisioned_verdict(facts),
        )
    return DependencyStatus(service=PLAYWRIGHT_BROWSER_SERVICE, available=True, facts=facts)


class BrowserInstallOutcome(ProvisioningOutcome):
    """The result of a browser provisioning request, including one that needed no download."""

    installed: bool
    already_installed: bool = False
    installer_exit_code: int | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_install_outcome(self) -> BrowserInstallOutcome:
        require_provisioning_verdict(failed=not self.installed, verdict=self.precondition_verdict)
        return self


def install_playwright_browser(
    *,
    run: BrowserInstallerRunner,
    probe: Callable[[], DependencyStatus] = probe_playwright_browser,
) -> BrowserInstallOutcome:
    """Download the pinned Chromium builds when any is missing, then confirm them.

    Idempotent: when the probe already reports every build installed, nothing
    runs. Success is decided by re-probing the cache, never by the installer's
    exit code alone.

    Returns:
        A :class:`BrowserInstallOutcome`. Never raises for installer failure.
    """
    before = probe()
    if before.available:
        return BrowserInstallOutcome(installed=True, already_installed=True, facts=before.facts)
    if before.facts.get("browser_manifest_readable") is False:
        return BrowserInstallOutcome(
            installed=False,
            facts=before.facts,
            precondition_verdict=before.precondition_verdict,
        )

    def refusal(extra: Mapping[str, ProvisioningFactValue], exit_code: int | None = None) -> BrowserInstallOutcome:
        facts = {**before.facts, **extra}
        return BrowserInstallOutcome(
            installed=False,
            installer_exit_code=exit_code,
            facts=facts,
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALL_SUCCEEDED,
                facts=facts,
            ),
        )

    try:
        exit_code = run(PLAYWRIGHT_BROWSER_INSTALL_TIMEOUT_S)
    except (OSError, TimeoutError) as exc:
        return refusal({"installer_ran": False, "install_error_type": exc.__class__.__name__})
    after = probe()
    if exit_code != 0 or not after.available:
        return refusal(
            {**after.facts, "installer_ran": True, "installer_exit_code": exit_code},
            exit_code=exit_code,
        )
    return BrowserInstallOutcome(
        installed=True,
        installer_exit_code=exit_code,
        facts={**after.facts, "installer_ran": True, "installer_exit_code": 0},
    )
