"""Provisioning of the Playwright Chromium build Cadrumo's browser automation drives.

The installed ``playwright`` package pins exact browser revisions in its bundled
``browsers.json`` manifest, and launches only those revisions. The probe here
therefore reads that manifest and checks the revision-exact cache directories
and their completion markers, so a stale build left by an earlier Playwright
version never reads as installed. It is a filesystem read: the Playwright driver
can hang inside the CLI process, so nothing here launches it.

:class:`PlaywrightBrowserItem` is the ``browser`` setup item of the dependency
registry. Its quick check reads the manifest, the completion markers and the
revision-exact executables; its full check also compares the executables with
the install receipt's digests and launches the headless build once, comparing
the version it reports with the manifest. Setting it up goes through injected
adapters and admits only the archives this build pins
(:mod:`.browser_archive_pins`): each is downloaded from the approved hosts and
must match its pinned size and SHA-256 before the vendor installer extracts it,
so nothing unauthenticated is ever launched. Partial builds are deleted before
each attempt, transient failures are retried, and a cancel stops the
installer's whole process tree. Only once the setup's own full check passes
does :meth:`PlaywrightBrowserItem.after_verified` write the receipt and remove
the revisions the new builds supersede.

A missing build is refused with a recovery action naming the browser setup
rather than surfacing Playwright's raw launch error.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from importlib.util import find_spec
from pathlib import Path
from typing import Annotated, Final, Protocol

from pydantic import BaseModel, StringConstraints, ValidationError, model_validator

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance
from ..core.storage_environment import configured_storage_root, resolve_storage_path
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location
from ..core.time.clock import now
from ..core.type_guards import is_object_dict, is_object_list
from .browser_archive_pins import BrowserArchivePin, BrowserArchivePins, load_browser_archive_pins
from .dependency_contracts import (
    DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S,
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyProvisionResult,
    DependencySetupEvents,
    DependencySetupStep,
)
from .dependency_network import (
    DependencyProxy,
    DependencyProxyConfigurationError,
    dependency_hosts,
    dependency_proxy_from_settings,
)
from .dependency_receipts import (
    DependencyReceipt,
    DependencyReceiptReading,
    DependencyReceiptState,
    DependencyReceiptStore,
    build_file_manifest,
    check_file_manifest,
)
from .dependency_registry import BROWSER_DECLARATION
from .dependency_transfer import (
    DEPENDENCY_RETRY_POLICY,
    DependencyRetryPolicy,
    DependencyTransferError,
    run_with_retry,
)
from .operator_actions.models import ActionReference, ConditionEvidence, PreconditionVerdict
from .provisioning import DependencyStatus
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)

__all__ = [
    "BROWSER_FULL_CHECK_LAUNCH_TIMEOUT_S",
    "BROWSER_PROVISION_ACTION_ID",
    "PLAYWRIGHT_BROWSER_INSTALL_TIMEOUT_S",
    "PLAYWRIGHT_BROWSER_SERVICE",
    "BrowserBuild",
    "BrowserBuildRemover",
    "BrowserInstallObserver",
    "BrowserInstallProcess",
    "BrowserInstallerExit",
    "BrowserInstallerRequest",
    "BrowserLaunchFailureCause",
    "BrowserLaunchReading",
    "BrowserLauncher",
    "PlaywrightBrowserItem",
    "browser_executable",
    "browser_host_platform",
    "browser_not_provisioned_verdict",
    "installed_playwright_driver_version",
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
#: build for headed launches, and the headless shell
#: a default headless launch uses.
_REQUIRED_MANIFEST_NAMES = ("chromium", "chromium-headless-shell")

#: Marker Playwright writes once a build is fully extracted.
_INSTALLATION_COMPLETE_MARKER = "INSTALLATION_COMPLETE"


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


def _build_installed(root: Path, build: BrowserBuild) -> bool:
    try:
        return (root / build.directory_name / _INSTALLATION_COMPLETE_MARKER).is_file()
    except OSError:
        return False


def probe_playwright_browser(
    cache_root: Path | None = None,
    *,
    manifest_path: Path | None = None,
    settings: Settings | None = None,
) -> DependencyStatus:
    """Report whether every Chromium build the installed Playwright launches is present.

    Missing builds are refused with the provisioning action. An unreadable
    manifest (Playwright absent or its layout unrecognised) is refused without a
    recovery action, because installing a browser cannot repair it.
    """
    root = playwright_browsers_root(cache_root, settings=settings)
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


# ---------------------------------------------------------------------------
# The ``browser`` setup item
# ---------------------------------------------------------------------------

#: Bound for the single headless launch of a full check, inside the item's 60 s budget.
BROWSER_FULL_CHECK_LAUNCH_TIMEOUT_S: Final = 45.0

_FULL_BUILD: Final = "chromium"
_HEADLESS_BUILD: Final = "chromium-headless-shell"

_MAC_CHROME_APP: Final = ("Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing")

#: Where each build keeps its executable inside its revision directory, by host platform.
#: This mirrors the vendor's own executable table for the two Chromium builds.
_EXECUTABLE_LAYOUT: Final[Mapping[str, Mapping[str, tuple[str, ...]]]] = {
    _FULL_BUILD: {
        "linux-x64": ("chrome-linux64", "chrome"),
        "linux-arm64": ("chrome-linux-arm64", "chrome"),
        "mac-x64": ("chrome-mac-x64", *_MAC_CHROME_APP),
        "mac-arm64": ("chrome-mac-arm64", *_MAC_CHROME_APP),
        "win-x64": ("chrome-win64", "chrome.exe"),
    },
    _HEADLESS_BUILD: {
        "linux-x64": ("chrome-headless-shell-linux64", "chrome-headless-shell"),
        "linux-arm64": ("chrome-headless-shell-linux-arm64", "chrome-headless-shell"),
        "mac-x64": ("chrome-headless-shell-mac-x64", "chrome-headless-shell"),
        "mac-arm64": ("chrome-headless-shell-mac-arm64", "chrome-headless-shell"),
        "win-x64": ("chrome-headless-shell-win64", "chrome-headless-shell.exe"),
    },
}

_SUPERSEDABLE_PREFIXES: Final = tuple(f"{name.replace('-', '_')}-" for name in _REQUIRED_MANIFEST_NAMES)


def browser_host_platform(*, system: str | None = None, machine: str | None = None) -> str | None:
    """Return the vendor's platform key for this computer, or ``None`` when it publishes no build for it."""
    system = sys.platform if system is None else system
    machine = (platform.machine() if machine is None else machine).lower()
    arm = machine in {"arm64", "aarch64"}
    intel = machine in {"x86_64", "amd64", "x64"}
    if system == "win32":
        return "win-x64" if intel or arm else None
    if system.startswith("linux"):
        return "linux-arm64" if arm else "linux-x64" if intel else None
    if system == "darwin":
        return "mac-arm64" if arm else "mac-x64" if intel else None
    return None


def browser_executable(root: Path, build: BrowserBuild, host_platform: str) -> Path | None:
    """Return where ``build`` keeps its executable under ``root``, or ``None`` for an unknown layout."""
    layout = _EXECUTABLE_LAYOUT.get(build.name, {}).get(host_platform)
    if layout is None:
        return None
    return root.joinpath(build.directory_name, *layout)


@dataclass(frozen=True, slots=True)
class BrowserInstallerRequest:
    """One install run: where it installs, how long it may take, and exactly what it may download.

    ``archives`` are the pinned archives still to fetch, each only from
    ``allowed_hosts`` and through ``proxy``; the vendor installer is offered
    nothing else.
    """

    browsers_root: Path
    timeout_s: float
    proxy: DependencyProxy | None = None
    archives: tuple[BrowserArchivePin, ...] = ()
    allowed_hosts: tuple[str, ...] = ()


class BrowserInstallerExit(BaseModel):
    """How one installer run ended, classified from its bounded output.

    ``transient`` is true only for the failures a later attempt may get past:
    a reset, refused or timed-out connection, a temporary name lookup failure,
    or a server answering 5xx or 429.
    """

    model_config = STRICT_FROZEN_CONFIG

    exit_code: int | None
    cancelled: bool = False
    timed_out: bool = False
    failure_category: DependencyFailureCategory | None = None
    transient: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_exit(self) -> BrowserInstallerExit:
        if self.transient and self.failure_category is None:
            raise ValueError("a transient installer failure names its category")
        return self


class BrowserInstallObserver(Protocol):
    """What an installer run reports to, and asks of, the setup in progress.

    Called from the installer's own thread: implementations must be thread safe.
    """

    def transferred(self, completed_bytes: int) -> None:
        """Report the bytes downloaded so far across every archive of this run."""
        ...

    @property
    def cancellation_requested(self) -> bool:
        """Whether the person asked to cancel; the installer's process tree is then stopped."""
        ...


class BrowserInstallProcess(Protocol):
    """Runs the vendor installer once, reading its output for progress, and stops it on cancel."""

    def __call__(self, request: BrowserInstallerRequest, observer: BrowserInstallObserver, /) -> BrowserInstallerExit:
        """Run one install of the pinned Chromium builds."""
        ...


class BrowserLaunchFailureCause(StrEnum):
    """Why a headless launch did not report a version, in closed words with no message text.

    It is recorded in the full check's facts beside the failure category, so a
    failed launch explains itself in a report without carrying the browser's or
    the driver's own message, which can name paths and arguments.
    """

    EXECUTABLE_MISSING = "executable_missing"
    EXECUTABLE_UNRUNNABLE = "executable_unrunnable"
    TIMED_OUT = "timed_out"
    BROWSER_EXITED = "browser_exited"
    DRIVER_FAILED = "driver_failed"
    DRIVER_UNAVAILABLE = "driver_unavailable"
    NO_VERSION = "no_version"


class BrowserLaunchReading(BaseModel):
    """The result of one headless launch: the version the browser reports, or why it did not start."""

    model_config = STRICT_FROZEN_CONFIG

    version: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None
    failure_category: DependencyFailureCategory | None = None
    failure_cause: BrowserLaunchFailureCause | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_reading(self) -> BrowserLaunchReading:
        if (self.version is None) == (self.failure_category is None):
            raise ValueError("a launch reports either the browser version or why it failed")
        if self.failure_cause is not None and self.failure_category is None:
            raise ValueError("a launch names a failure cause only beside its failure category")
        return self


class BrowserLauncher(Protocol):
    """Launches one browser executable headless, reads its version and closes it."""

    async def __call__(self, executable: Path, /, *, timeout_s: float) -> BrowserLaunchReading:
        """Return what the launch observed; never raises for a browser that does not start."""
        ...


class BrowserBuildRemover(Protocol):
    """Deletes named build directories directly under the browser root."""

    def __call__(self, root: Path, directory_names: Sequence[str], /) -> tuple[str, ...]:
        """Delete each named directory that exists and return the names removed."""
        ...


def _settings_proxy() -> DependencyProxy | None:
    return dependency_proxy_from_settings(load_settings())


@dataclass(frozen=True, slots=True)
class _CacheObservation:
    """What the browser root holds for the pinned builds."""

    executables: Mapping[str, Path]
    incomplete: tuple[str, ...]
    missing: tuple[str, ...]
    superseded: tuple[str, ...]


def _observe_cache(root: Path, builds: Sequence[BrowserBuild], host_platform: str) -> _CacheObservation:
    """Read which pinned builds are complete: marker and revision-exact executable both present."""
    executables: dict[str, Path] = {}
    incomplete: list[str] = []
    missing: list[str] = []
    for build in builds:
        directory = root / build.directory_name
        executable = browser_executable(root, build, host_platform)
        marker = (directory / _INSTALLATION_COMPLETE_MARKER).is_file()
        if marker and executable is not None and executable.is_file():
            executables[build.name] = executable
            continue
        missing.append(build.directory_name)
        if directory.exists():
            incomplete.append(build.directory_name)
    required = {build.directory_name for build in builds}
    superseded: list[str] = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            name = entry.name
            if name in required or not entry.is_dir():
                continue
            prefix = next((p for p in _SUPERSEDABLE_PREFIXES if name.startswith(p)), None)
            if prefix is not None and name.removeprefix(prefix).isdigit():
                superseded.append(name)
    return _CacheObservation(
        executables=executables,
        incomplete=tuple(incomplete),
        missing=tuple(missing),
        superseded=tuple(superseded),
    )


def _executable_paths(root: Path, observation: _CacheObservation) -> tuple[str, ...]:
    return tuple(sorted(path.relative_to(root).as_posix() for path in observation.executables.values()))


def _applicable_receipt(
    reading: DependencyReceiptReading | None, builds: Sequence[BrowserBuild], executables: Sequence[str]
) -> DependencyReceipt | None:
    """Return the receipt when it describes these builds: their version and both executables."""
    if reading is None or reading.receipt is None:
        return None
    receipt = reading.receipt
    recorded = {entry.path for entry in receipt.files}
    if receipt.version != _target_version(builds) or not set(executables) <= recorded:
        return None
    return receipt


def _target_version(builds: Sequence[BrowserBuild]) -> str:
    full = next(build for build in builds if build.name == _FULL_BUILD)
    return full.browser_version or f"revision {full.revision}"


def _pending_archives(root: Path, pins: Sequence[BrowserArchivePin]) -> tuple[BrowserArchivePin, ...]:
    """Return the pinned archives whose build the installer would still download: no completion marker."""
    return tuple(pin for pin in pins if not (root / pin.directory_name / _INSTALLATION_COMPLETE_MARKER).is_file())


class _TransferBridge:
    """Carries the installer thread's byte counts onto the event loop, one figure at a time."""

    def __init__(self, events: DependencySetupEvents, *, total: int | None, loop: asyncio.AbstractEventLoop) -> None:
        self._events = events
        self._total = total
        self._loop = loop
        self._latest = 0
        self._sent = 0
        self._closed = False
        self._wake = asyncio.Event()

    @property
    def highest(self) -> int:
        return self._latest

    @property
    def cancellation_requested(self) -> bool:
        return self._events.cancellation_requested

    def transferred(self, completed_bytes: int) -> None:
        self._loop.call_soon_threadsafe(self._update, completed_bytes)

    def _update(self, completed_bytes: int) -> None:
        value = completed_bytes if self._total is None else min(completed_bytes, self._total)
        if value > self._latest:
            self._latest = value
            self._wake.set()

    def close(self) -> None:
        self._closed = True
        self._wake.set()

    async def pump(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            if self._latest > self._sent:
                self._sent = self._latest
                await self._events.transferred(completed=self._sent, total=self._total)
            if self._closed:
                return


@dataclass(slots=True)
class _SetupProgress:
    """What the attempts of one setup have done so far."""

    attempts: int = 0
    changed: bool = False
    transferred: int = 0
    reinstall: bool = False
    facts: dict[str, ProvisioningFactValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _Sources:
    """What one setup may download and from where: the pinned archives, the approved hosts, the proxy."""

    pins: tuple[BrowserArchivePin, ...]
    hosts: tuple[str, ...]
    proxy: DependencyProxy | None


type _LocatedBuilds = tuple[Path, tuple[BrowserBuild, ...], _CacheObservation]


class PlaywrightBrowserItem:
    """The ``browser`` setup item: the two Chromium builds the bundled Playwright launches.

    Every outside effect is injected: the installer run, the headless launch
    and the build-directory removal. ``archive_pins`` supplies the table of
    archives this build trusts. The receipt store is the shared setup receipt
    store; without one the checks rest on the files alone.
    """

    def __init__(
        self,
        *,
        install: BrowserInstallProcess,
        launch: BrowserLauncher,
        remove_builds: BrowserBuildRemover,
        receipts: DependencyReceiptStore | None = None,
        browsers_root: Callable[[], Path] = playwright_browsers_root,
        manifest_path: Callable[[], Path | None] = _installed_manifest_path,
        archive_pins: Callable[[], BrowserArchivePins | None] = load_browser_archive_pins,
        proxy: Callable[[], DependencyProxy | None] = _settings_proxy,
        host_platform: Callable[[], str | None] = browser_host_platform,
        install_timeout_s: float = PLAYWRIGHT_BROWSER_INSTALL_TIMEOUT_S,
        retry_policy: DependencyRetryPolicy = DEPENDENCY_RETRY_POLICY,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] | None = None,
    ) -> None:
        """Bind the adapters and the location resolvers the item reads and acts through."""
        self._install = install
        self._launch = launch
        self._remove_builds = remove_builds
        self._receipts = receipts
        self._browsers_root = browsers_root
        self._manifest_path = manifest_path
        self._archive_pins = archive_pins
        self._proxy = proxy
        self._host_platform = host_platform
        self._install_timeout_s = install_timeout_s
        self._retry_policy = retry_policy
        self._sleep = sleep
        self._monotonic = monotonic
        self._jitter = jitter

    @property
    def declaration(self) -> DependencyItemDeclaration:
        """The registry declaration this item answers for."""
        return BROWSER_DECLARATION

    # -- checks --------------------------------------------------------------

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        """Return the browser's reading; a full check also verifies every digest and launches it once."""
        try:
            reading, located = await asyncio.to_thread(self._local_reading, mode)
            if mode is DependencyCheckMode.FULL and located is not None:
                reading = await self._exercise(reading, located)
        except (OSError, ValueError) as exc:
            return _reading(mode, DependencyProbeOutcome.UNREADABLE, facts={"read_error": type(exc).__name__})
        return reading

    def _required_builds(self) -> tuple[BrowserBuild, ...] | None:
        path = self._manifest_path()
        return None if path is None else required_browser_builds(path)

    def _pinned_archives(self, builds: Sequence[BrowserBuild], host: str) -> tuple[BrowserArchivePin, ...] | None:
        """Return this platform's pinned archives when they cover the installed driver's builds."""
        path = self._manifest_path()
        if path is None:
            return None
        try:
            pins = self._archive_pins()
        except (OSError, ValidationError):
            return None
        if pins is None:
            return None
        names = [build.directory_name for build in builds]
        return pins.covering(host, installed_playwright_driver_version(path), names)

    def _read_receipt(self) -> DependencyReceiptReading | None:
        return None if self._receipts is None else self._receipts.read(BROWSER_DECLARATION.item_id)

    def _local_reading(self, mode: DependencyCheckMode) -> tuple[DependencyProbeReading, _LocatedBuilds | None]:
        if self._manifest_path() is None:
            blocked = _reading(mode, DependencyProbeOutcome.BLOCKED, blocked=DependencyBlockedReason.NOT_IN_THIS_BUILD)
            return blocked, None
        builds = self._required_builds()
        host = self._host_platform()
        if builds is None or host is None:
            unread: dict[str, ProvisioningFactValue] = {
                "browser_manifest_readable": builds is not None,
                "browser_platform_known": host is not None,
            }
            return _reading(mode, DependencyProbeOutcome.UNREADABLE, facts=unread), None
        root = self._browsers_root()
        observation = _observe_cache(root, builds, host)
        facts: dict[str, ProvisioningFactValue] = {
            "required_builds": ",".join(build.directory_name for build in builds),
        }
        if observation.superseded:
            facts["superseded_builds"] = ",".join(observation.superseded)
        if observation.missing:
            facts["missing_builds"] = ",".join(observation.missing)
            if self._pinned_archives(builds, host) is None:
                # Setup would refuse to download what no pin can authenticate, so none is offered.
                facts["browser_archives_pinned"] = False
                blocked = _reading(
                    mode, DependencyProbeOutcome.BLOCKED, blocked=DependencyBlockedReason.NOT_IN_THIS_BUILD, facts=facts
                )
                return blocked, None
            return _reading(mode, DependencyProbeOutcome.ABSENT, facts=facts), None
        stored = self._read_receipt()
        executables = _executable_paths(root, observation)
        receipt = _applicable_receipt(stored, builds, executables)
        facts["receipt_matches_builds"] = receipt is not None
        if stored is not None and stored.state is DependencyReceiptState.UNREADABLE:
            facts["receipt_readable"] = False
        if receipt is not None:
            # The quick check hashes the executables alone; the full check every recorded file.
            only = executables if mode is DependencyCheckMode.QUICK else None
            compared = check_file_manifest(root, receipt, only=only)
            if not compared.intact:
                facts["damaged_files"] = len(compared.missing) + len(compared.changed)
                failed = _reading(
                    mode,
                    DependencyProbeOutcome.FAILED,
                    failure=DependencyFailureCategory.DAMAGED_DOWNLOAD,
                    facts=facts,
                )
                return failed, None
        present = _reading(mode, DependencyProbeOutcome.PRESENT, version=_target_version(builds), facts=facts)
        return present, (root, builds, observation)

    async def _exercise(self, reading: DependencyProbeReading, located: _LocatedBuilds) -> DependencyProbeReading:
        _root, builds, observation = located
        headless = next(build for build in builds if build.name == _HEADLESS_BUILD)
        executable = observation.executables[headless.name]
        timeout_s = min(BROWSER_FULL_CHECK_LAUNCH_TIMEOUT_S, DEPENDENCY_FULL_CHECK_ITEM_BUDGET_S)
        launched = await self._launch(executable, timeout_s=timeout_s)
        facts = dict(reading.facts)
        if launched.version is None:
            facts["launched"] = False
            if launched.failure_cause is not None:
                facts["launch_failure_cause"] = launched.failure_cause.value
            return _reading(
                reading.mode,
                DependencyProbeOutcome.FAILED,
                failure=launched.failure_category or DependencyFailureCategory.UNEXPECTED,
                facts=facts,
            )
        facts.update(launched=True, launched_version=launched.version)
        if headless.browser_version is not None and launched.version != headless.browser_version:
            return _reading(
                reading.mode,
                DependencyProbeOutcome.FAILED,
                failure=DependencyFailureCategory.DAMAGED_DOWNLOAD,
                facts=facts,
            )
        return reading.model_copy(update={"facts": facts})

    # -- setup ---------------------------------------------------------------

    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        """Return what setting the browser up downloads: the pinned archives still missing, from the declared hosts.

        Nothing is fetched or asked of the network. The size is unknown when
        this build pins no archives for the installed driver on this platform,
        and setup then refuses.
        """
        del model_name
        declared = dependency_hosts(BROWSER_DECLARATION.network_host_group)
        builds = await asyncio.to_thread(self._required_builds)
        if builds is None:
            return DependencyPlanEntry(
                item_id=BROWSER_DECLARATION.item_id,
                download_bytes=None,
                source_hosts=declared,
                destination=StorageCategory.PLAYWRIGHT_BROWSERS,
            )
        host = self._host_platform()
        pins = None if host is None else await asyncio.to_thread(self._pinned_archives, builds, host)
        download_bytes: int | None = None
        if pins is not None:
            pending = await asyncio.to_thread(_pending_archives, self._browsers_root(), pins)
            download_bytes = sum(pin.download_bytes for pin in pending)
        return DependencyPlanEntry(
            item_id=BROWSER_DECLARATION.item_id,
            download_bytes=download_bytes,
            source_hosts=declared,
            destination=StorageCategory.PLAYWRIGHT_BROWSERS,
            target_version=_target_version(builds),
        )

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        """Install exactly the approved builds, retrying transient failures; readiness is the setup's own check."""
        if entry.item_id != BROWSER_DECLARATION.item_id:
            raise ValueError("plan entry belongs to another setup item")
        if self._manifest_path() is None:
            return _result(changed=False, failure=DependencyFailureCategory.NOT_IN_THIS_BUILD)
        builds = await asyncio.to_thread(self._required_builds)
        host = self._host_platform()
        if builds is None or host is None:
            return _result(changed=False, failure=DependencyFailureCategory.UNEXPECTED)
        if entry.target_version != _target_version(builds):
            # The approved plan names other builds than this Playwright pins, so it needs a new plan.
            return _result(
                changed=False, failure=DependencyFailureCategory.UNEXPECTED, facts={"plan_matches_builds": False}
            )
        pins = await asyncio.to_thread(self._pinned_archives, builds, host)
        if pins is None:
            # Without a pin nothing could authenticate the download, so nothing is downloaded.
            return _result(
                changed=False,
                failure=DependencyFailureCategory.NOT_IN_THIS_BUILD,
                facts={"browser_archives_pinned": False},
            )
        declared = dependency_hosts(BROWSER_DECLARATION.network_host_group)
        approved = tuple(source for source in entry.source_hosts if source in declared)
        try:
            sources = _Sources(pins=pins, hosts=approved, proxy=self._proxy())
        except DependencyProxyConfigurationError:
            return _result(
                changed=False, failure=DependencyFailureCategory.UNEXPECTED, facts={"proxy_settings_usable": False}
            )
        if events.cancellation_requested:
            return _result(changed=False, failure=DependencyFailureCategory.CANCELLED)
        root = self._browsers_root()
        await events.step(DependencySetupStep.DOWNLOAD)
        progress = _SetupProgress(reinstall=await asyncio.to_thread(self._receipt_finds_damage, root, builds, host))
        try:
            await run_with_retry(
                lambda: self._attempt(root, builds, host, entry, sources, events, progress),
                events=events,
                policy=self._retry_policy,
                sleep=self._sleep,
                monotonic=self._monotonic,
                jitter=self._jitter,
            )
        except DependencyTransferError as failure:
            return _result(
                changed=progress.changed,
                failure=failure.category,
                transferred=progress.transferred,
                facts={**progress.facts, **failure.facts, "attempts": progress.attempts},
            )
        facts: dict[str, ProvisioningFactValue] = {**progress.facts, "attempts": progress.attempts}
        return _result(changed=progress.changed, transferred=progress.transferred, facts=facts)

    async def after_verified(self, entry: DependencyPlanEntry) -> None:
        """Record the receipt of the verified builds and remove the revisions they supersede.

        The setup calls this only after its own full check found the browser
        usable, inside its irreversible section.
        """
        if entry.item_id != BROWSER_DECLARATION.item_id:
            raise ValueError("plan entry belongs to another setup item")
        builds = await asyncio.to_thread(self._required_builds)
        host = self._host_platform()
        if builds is None or host is None:
            return
        await asyncio.to_thread(self._settle, self._browsers_root(), builds, host, entry)

    def _receipt_finds_damage(self, root: Path, builds: Sequence[BrowserBuild], host: str) -> bool:
        observation = _observe_cache(root, builds, host)
        if observation.missing:
            return False
        receipt = _applicable_receipt(self._read_receipt(), builds, _executable_paths(root, observation))
        return receipt is not None and not check_file_manifest(root, receipt).intact

    async def _attempt(
        self,
        root: Path,
        builds: tuple[BrowserBuild, ...],
        host: str,
        entry: DependencyPlanEntry,
        sources: _Sources,
        events: DependencySetupEvents,
        progress: _SetupProgress,
    ) -> None:
        """Run the installer once for whatever is missing; raise the classified failure when it fails."""
        observation = await asyncio.to_thread(_observe_cache, root, builds, host)
        pending = tuple(build.directory_name for build in builds) if progress.reinstall else observation.missing
        progress.reinstall = False
        if not pending:
            return
        progress.attempts += 1
        if self._receipts is not None:
            # The receipt described the files about to be replaced; a new one follows verification.
            await asyncio.to_thread(self._receipts.remove, BROWSER_DECLARATION.item_id)
        # A build without its completion marker is deleted so that build alone downloads again.
        if any((root / name).exists() for name in pending):
            removed = await asyncio.to_thread(self._remove_builds, root, pending)
            progress.changed = progress.changed or bool(removed)
        request = BrowserInstallerRequest(
            browsers_root=root,
            timeout_s=self._install_timeout_s,
            proxy=sources.proxy,
            archives=await asyncio.to_thread(_pending_archives, root, sources.pins),
            allowed_hosts=sources.hosts,
        )
        bridge = _TransferBridge(events, total=entry.download_bytes, loop=asyncio.get_running_loop())
        pump = asyncio.create_task(bridge.pump())
        try:
            ended = await asyncio.to_thread(self._install, request, bridge)
        finally:
            bridge.close()
            await pump
        progress.changed = True
        progress.transferred = max(progress.transferred, bridge.highest)
        if ended.exit_code is not None:
            progress.facts["installer_exit_code"] = ended.exit_code
        if ended.cancelled:
            raise DependencyTransferError(DependencyFailureCategory.CANCELLED, transient=False)
        after = await asyncio.to_thread(_observe_cache, root, builds, host)
        if not after.missing:
            return
        category = ended.failure_category or (
            DependencyFailureCategory.DAMAGED_DOWNLOAD if ended.exit_code == 0 else DependencyFailureCategory.UNEXPECTED
        )
        raise DependencyTransferError(category, transient=ended.transient)

    def _settle(
        self, root: Path, builds: Sequence[BrowserBuild], host: str, entry: DependencyPlanEntry
    ) -> dict[str, ProvisioningFactValue]:
        """Record the receipt for the new builds and remove the revisions they supersede."""
        facts: dict[str, ProvisioningFactValue] = {}
        observation = _observe_cache(root, builds, host)
        if observation.missing:
            return facts
        if self._receipts is not None:
            installed = [
                path for build in builds for path in sorted((root / build.directory_name).rglob("*")) if path.is_file()
            ]
            receipt = DependencyReceipt(
                item_id=BROWSER_DECLARATION.item_id,
                version=_target_version(builds),
                files=build_file_manifest(root, installed),
                verified_at=now(),
                hosts=entry.source_hosts,
            )
            try:
                self._receipts.write(receipt)
            except OSError:
                # A receipt is evidence only: without one the checks rest on the files themselves.
                facts["receipt_written"] = False
            else:
                facts["receipt_written"] = True
        if observation.superseded:
            try:
                removed = self._remove_builds(root, observation.superseded)
            except OSError:
                facts["superseded_cleanup_failed"] = True
            else:
                facts["superseded_removed"] = len(removed)
        return facts


def _reading(
    mode: DependencyCheckMode,
    outcome: DependencyProbeOutcome,
    *,
    failure: DependencyFailureCategory | None = None,
    blocked: DependencyBlockedReason | None = None,
    version: str | None = None,
    facts: Mapping[str, ProvisioningFactValue] | None = None,
) -> DependencyProbeReading:
    return DependencyProbeReading(
        item_id=BROWSER_DECLARATION.item_id,
        mode=mode,
        outcome=outcome,
        failure_category=failure,
        blocked_reason=blocked,
        version=version,
        facts={} if facts is None else dict(facts),
    )


def _result(
    *,
    changed: bool,
    failure: DependencyFailureCategory | None = None,
    transferred: int = 0,
    facts: Mapping[str, ProvisioningFactValue] | None = None,
) -> DependencyProvisionResult:
    return DependencyProvisionResult(
        item_id=BROWSER_DECLARATION.item_id,
        changed=changed,
        failure_category=failure,
        transferred_bytes=transferred,
        facts={} if facts is None else dict(facts),
    )
