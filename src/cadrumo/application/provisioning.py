"""Typed external-dependency probes for graceful degradation and ``config check``.

This module is the read-only application doctor surface: each probe asks whether
one external service or optional package extra is usable on this workstation and
returns a typed :class:`DependencyStatus` with measured facts and a closed
precondition outcome when it is not. Probes do not provision, unlock, write profile state, or raise on
absence; a missing dependency is report data, not an exception path.

The vision read consults :func:`probe_ollama_vision` before expensive inference,
so a down server or an unpulled model becomes an instructive refusal instead of
a raw stack trace. The ``aeat config check`` command renders this module's
statuses as
:class:`~cadrumo.entrypoints.cli._config._check_payloads.CheckDependencyPayload`
rows beside the active profile's capability posture from
:func:`~cadrumo.application.user_profile.resolve_active_capability`. Optional-extra
probes walk the core :data:`~cadrumo.core.OPTIONAL_EXTRAS` catalogue of
:class:`~cadrumo.core.OptionalExtra` records, so CLI diagnostics and adapter import
guards share one registry.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from time import monotonic
from typing import TypedDict, cast

import httpx
from pydantic import BaseModel, Field, model_validator

from ..core import (
    LLM_EXTRA,
    OPTIONAL_EXTRAS,
    STRICT_FROZEN_CONFIG,
    AcceleratorKind,
    ContentionCause,
    DeploymentLicencePosture,
    ExternalPathRole,
    HardwareTier,
    ModelCandidate,
    ModelRole,
    ModelRuntime,
    ModelSelectionAdvisory,
    OptionalExtra,
    candidates_for_role,
    hardware_tier_for_free_bytes,
    model_candidate,
    optional_extra_available,
)
from ..core.config import Settings, load_settings
from ..core.directory_scan import (
    iter_directory,
)
from ..core.i18n import tr

__all__ = [
    "LOCAL_MODEL_PROVISIONING_SERVICE",
    "OPTIONAL_EXTRAS",
    "AcceleratorDevice",
    "AcceleratorKind",
    "AcceleratorReading",
    "ContentionCause",
    "ContentionSnapshot",
    "DependencyStatus",
    "HardwareProfile",
    "HardwareTier",
    "InstalledModel",
    "ModelSelection",
    "OptionalExtra",
    "PullOutcome",
    "PullProgress",
    "ReadinessOutcome",
    "RemoveOutcome",
    "RuntimeResident",
    "SystemMemoryReading",
    "UnloadOutcome",
    "assess_model_load_contention",
    "binding_free_bytes",
    "cadrumo_selected_models",
    "clear_ollama_vision_probe_cache",
    "probe_hardware_profile",
    "probe_local_inference_hardware",
    "probe_local_model_provisioning",
    "probe_model_runtime_hardware_floor",
    "probe_ollama_vision",
    "probe_optional_extra",
    "probe_optional_extras",
    "probe_playwright_browser",
    "pull_runtime_model",
    "read_accelerator",
    "read_installed_models",
    "read_runtime_residents",
    "read_system_memory",
    "remove_runtime_model",
    "select_model_for_role",
    "unload_runtime_model",
    "verify_model_ready",
]

from ._provisioning_contracts import (
    OLLAMA_PROBE_CACHE_TTL_S,
    OLLAMA_PROBE_TIMEOUT_S,
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
)
from ._provisioning_runtime import (
    ContentionSnapshot,
    InstalledModel,
    PullOutcome,
    PullProgress,
    ReadinessOutcome,
    RemoveOutcome,
    RuntimeResident,
    UnloadOutcome,
    assess_model_load_contention,
    cadrumo_selected_models,
    matches_selected_model,
    ollama_endpoint,
    pull_runtime_model,
    read_installed_models,
    read_runtime_residents,
    remove_runtime_model,
    unload_runtime_model,
    verify_model_ready,
)


class DependencyStatus(ProvisioningOutcome):
    """Availability result for one external dependency.

    ``service`` is the stable row id shown by the configuration check. ``facts``
    records the measured state and ``precondition_verdict`` closes every unavailable
    outcome without embedding presentation or executable text. The model is intentionally
    generic so Ollama, subprocess CLIs, Playwright browser binaries, and
    :class:`~cadrumo.core.OptionalExtra` package extras all render through the same
    payload shape and can be validated into
    :class:`~cadrumo.entrypoints.cli._config._check_payloads.CheckDependencyPayload`.
    """

    service: str = Field(min_length=1)
    available: bool

    @model_validator(mode="after")
    def _require_availability_outcome(self) -> DependencyStatus:
        require_provisioning_verdict(failed=not self.available, verdict=self.precondition_verdict)
        return self


def _ollama_tag_names(payload: object) -> set[str]:
    """Read the pulled model names out of an Ollama ``/api/tags`` payload.

    Raises:
        ValueError: When the payload is not an object carrying model entries
            with string names. The probe treats that as an unreachable server,
            because a response this shape cannot answer what is pulled.
    """
    if not isinstance(payload, dict):
        raise ValueError("Ollama tags response must be a JSON object")
    # CAST-RATIONALE-OLLAMA-TAGS-PAYLOAD: httpx.Response.json() returns
    # Any; isinstance narrows to dict but not its type parameters.
    # nosemgrep: no-cast-in-domain-application
    payload_object = cast(dict[str, object], payload)
    models = payload_object.get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama tags response must contain model objects with string names")
    # CAST-RATIONALE-OLLAMA-TAGS-MODELS: isinstance narrows to list but
    # not its element type; entries are validated individually below.
    # nosemgrep: no-cast-in-domain-application
    models = cast(list[object], models)
    names: set[str] = set()
    for entry in models:
        if not isinstance(entry, dict):
            raise ValueError("Ollama tags response must contain model objects with string names")
        # CAST-RATIONALE-OLLAMA-TAGS-MODEL-ENTRY: isinstance narrows to
        # dict but not its type parameters.
        # nosemgrep: no-cast-in-domain-application
        name = cast(dict[str, object], entry).get("name")
        if not isinstance(name, str):
            raise ValueError("Ollama tags response must contain model objects with string names")
        names.add(name)
    return names


def probe_ollama_vision(settings: Settings | None = None) -> DependencyStatus:
    """Probe Ollama and the configured vision model, returning a :class:`DependencyStatus`.

    Reads ``cadrumo_llm_ollama_chat_url`` and ``cadrumo_llm_ollama_vision_model`` from
    :class:`~cadrumo.core.config.Settings`, then performs a short-timeout
    ``GET /api/tags``. The probe never runs inference and returns unavailable
    when the server is unreachable or the configured model is not installed.
    Ledger evidence reading uses this result before local-vision inference.

    The answer is cached per ``(endpoint, model)`` for
    :data:`OLLAMA_PROBE_CACHE_TTL_S`, so a caller that asks once per document
    asks the endpoint once instead. Keying on the endpoint keeps a suite that
    stands up its own reader on an ephemeral port unaffected: a different URL is
    a different question. Use :func:`clear_ollama_vision_probe_cache` where a
    test needs the next call to reach the endpoint again.
    """
    resolved = settings if settings is not None else load_settings()
    model = resolved.cadrumo_llm_ollama_vision_model
    url = ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "tags")
    cache_key = (url, model)
    cached = _OLLAMA_VISION_PROBE_CACHE.get(cache_key)
    if cached is not None and (monotonic() - cached[0]) < OLLAMA_PROBE_CACHE_TTL_S:
        return cached[1]
    status = _probe_ollama_vision_uncached(url=url, model=model)
    _OLLAMA_VISION_PROBE_CACHE[cache_key] = (monotonic(), status)
    return status


#: Probe answers by ``(endpoint, model)``, each stamped with its monotonic
#: reading time. Monotonic, not wall clock, so a clock adjustment cannot make an
#: entry look arbitrarily fresh or stale.
_OLLAMA_VISION_PROBE_CACHE: dict[tuple[str, str], tuple[float, DependencyStatus]] = {}


def clear_ollama_vision_probe_cache() -> None:
    """Drop every cached probe answer, so the next call reaches the endpoint."""
    _OLLAMA_VISION_PROBE_CACHE.clear()


def _probe_ollama_vision_uncached(*, url: str, model: str) -> DependencyStatus:
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
            response.raise_for_status()
            names = _ollama_tag_names(response.json())
    except (httpx.HTTPError, ValueError):
        return DependencyStatus(
            service="ollama-vision",
            available=False,
            facts={"runtime_reachable": False, "runtime_url": url},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
                facts={"runtime_reachable": False, "runtime_url": url},
            ),
        )
    # Ollama lists names with the tag (e.g. "qwen2.5vl:3b"); match the configured
    # model exactly or by its untagged stem.
    present = model in names or any(name.split(":", 1)[0] == model.split(":", 1)[0] for name in names)
    if not present:
        return DependencyStatus(
            service="ollama-vision",
            available=False,
            facts={"runtime_reachable": True, "vision_model": model, "vision_model_installed": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.VISION_MODEL_INSTALLED,
                facts={"runtime_reachable": True, "vision_model": model, "vision_model_installed": False},
            ),
        )
    return DependencyStatus(
        service="ollama-vision",
        available=True,
        facts={"runtime_reachable": True, "vision_model": model, "vision_model_installed": True},
    )


PLAYWRIGHT_BROWSERS_ROOT_ROLE = ExternalPathRole.THIRD_PARTY_CACHE
"""Why the Playwright browser cache sits outside the storage taxonomy.

Declared as a positive statement rather than left as the root's plain absence
from :data:`~core.STORAGE_TAXONOMY` or :data:`~core.EXTERNAL_PATH_SETTINGS_FIELDS`:
Playwright installs its own Chromium build under a vendor-owned layout
convention (``PLAYWRIGHT_BROWSERS_PATH`` or a per-OS default cache directory),
so the application neither chooses this location nor writes the binaries there
-- it fails the choose test :class:`~core.ExternalPathRole` exists to name.
There is no :class:`~core.config.Settings` field to carry the declaration on
(the root is resolved from a vendor environment variable and a platform
default, never a Cadrumo setting), so it lives beside the resolver it
describes rather than in :data:`~core.EXTERNAL_PATH_SETTINGS_FIELDS`, which is
keyed by settings field name.
"""


def _playwright_browsers_root(cache_root: Path | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    """Return the directory Playwright installs browser binaries into.

    Uses an explicit ``cache_root`` when supplied, otherwise honours
    ``PLAYWRIGHT_BROWSERS_PATH`` then falls back to the per-OS default cache. A
    filesystem read only — it never launches the Playwright driver (which can
    hang inside the CLI process), so the probe stays fast and non-blocking.

    Reads ``env`` (an injectable mapping so the vendor-override precedence is
    unit-tested against real dict inputs without mutating process environment
    state; defaults to ``os.environ`` for the live probe). ``cache_root`` is not
    a substitute for it: that argument short-circuits resolution entirely, so it
    exercises a different branch than the one the override precedence lives on.

    A third-party-owned cache (see :data:`PLAYWRIGHT_BROWSERS_ROOT_ROLE`): the
    application reads this location to probe for an installed build and never
    chooses or writes to it.
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


def probe_playwright_browser(cache_root: Path | None = None) -> DependencyStatus:
    """Probe the Playwright Chromium browser binary, returning a :class:`DependencyStatus`.

    Scans the Playwright browsers cache for an installed ``chromium*`` build using
    a fast filesystem check. The Playwright sync driver can hang inside the CLI
    process, so this probe deliberately never launches it. Missing, unreadable, or
    empty cache roots return unavailable with a closed precondition outcome.
    ``cache_root`` is a testable override for the browser cache
    directory. The row complements the browser health probe in
    :mod:`cadrumo.application.diagnostics`; it checks workstation provisioning, not
    AEAT site reachability.
    """
    root = _playwright_browsers_root(cache_root)
    try:
        installed = root.is_dir() and any(
            child.name.startswith("chromium") for child in iter_directory(root, require_root=True)
        )
    except OSError:
        installed = False
    if not installed:
        return DependencyStatus(
            service="playwright-chromium",
            available=False,
            facts={"browser_cache_root": str(root), "chromium_installed": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED,
                facts={"browser_cache_root": str(root), "chromium_installed": False},
            ),
        )
    return DependencyStatus(
        service="playwright-chromium",
        available=True,
        facts={"browser_cache_root": str(root), "chromium_installed": True},
    )


class SystemMemoryReading(BaseModel):
    """Measured total and free physical system memory, either of which may be unreadable.

    Both figures are carried because they answer different questions and the
    provisioning decision separates them deliberately: ``total_bytes`` is what a
    diagnostic row *reports* about the machine, ``free_bytes`` is the only figure
    a load decision may *act* on. A machine with 64 GiB installed and 2 GiB free
    cannot host a 4 GiB model, and reading the total as headroom is exactly the
    admission error the contention check exists to prevent.

    ``None`` means "not measured", never "zero". See
    :class:`~core.AcceleratorKind` for the same distinction on the device side.
    """

    model_config = STRICT_FROZEN_CONFIG

    total_bytes: int | None = Field(default=None, ge=0)
    free_bytes: int | None = Field(default=None, ge=0)


def _windows_memory_status() -> tuple[int, int] | None:
    """Return ``(total, available)`` physical bytes from ``GlobalMemoryStatusEx``, or ``None``.

    Returns ``None`` off Windows. The early exit is what establishes the
    platform inside THIS function's body: a type checker narrows on
    ``sys.platform``, and a guard at the call site is invisible to it, so
    ``ctypes.windll`` -- which exists only in the Windows typeshed stubs -- reads
    as a missing attribute when the tree is analysed for Linux. The runtime
    behaviour is unchanged; the caller already treats ``None`` as "not measured".
    """
    if sys.platform != "win32":  # pragma: no cover - the CI runner is Linux
        return None

    import ctypes

    class _MemoryStatusEx(ctypes.Structure):
        _fields_ = (
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        )

    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    try:
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys), int(status.ullAvailPhys)
    except (OSError, AttributeError):
        return None
    return None


def read_system_memory() -> SystemMemoryReading:
    """Measure total and free physical system memory, reporting either as ``None`` when unreadable.

    Dependency-free on every supported platform: POSIX reads the ``sysconf``
    page-size pair, Windows calls ``GlobalMemoryStatusEx`` through :mod:`ctypes`.
    The free counterpart costs nothing to obtain -- the Windows struct already
    carries ``ullAvailPhys`` in the same call, and POSIX exposes
    ``SC_AVPHYS_PAGES`` beside the total -- so both figures come from one
    measurement and cannot disagree about the moment they describe.

    A platform that answers nothing yields ``None``, never a guess: an unknown
    quantity must not be reported as a shortfall by
    :func:`probe_model_runtime_hardware_floor`, nor mistaken for headroom by
    :func:`assess_model_load_contention`.
    """
    if sys.platform != "win32":
        # Guarded on the platform rather than on getattr so a type checker can
        # follow it: os.sysconf is absent from the Windows stubs entirely. The
        # inner membership checks stay for POSIX variants that omit the
        # constants themselves; SC_AVPHYS_PAGES is the more commonly absent of
        # the three, so a total may be readable where a free figure is not.
        names = getattr(os, "sysconf_names", {})
        if "SC_PAGE_SIZE" in names and "SC_PHYS_PAGES" in names:
            try:
                page_size = int(os.sysconf("SC_PAGE_SIZE"))
                total = page_size * int(os.sysconf("SC_PHYS_PAGES"))
            except (OSError, ValueError):
                return SystemMemoryReading()
            free: int | None = None
            if "SC_AVPHYS_PAGES" in names:
                try:
                    free = page_size * int(os.sysconf("SC_AVPHYS_PAGES"))
                except (OSError, ValueError):
                    free = None
            return SystemMemoryReading(total_bytes=total, free_bytes=free)
        return SystemMemoryReading()
    measured = _windows_memory_status()
    if measured is None:
        return SystemMemoryReading()
    return SystemMemoryReading(total_bytes=measured[0], free_bytes=measured[1])


def read_total_system_memory_bytes() -> int | None:
    """Return total physical system memory in bytes, or ``None`` when unreadable.

    A narrowing of :func:`read_system_memory` for the hardware-floor diagnostic,
    which judges the machine's installed capacity rather than its present
    headroom. Kept as the one total-only reader so there is no second platform
    branch to drift.
    """
    return read_system_memory().total_bytes


def probe_model_runtime_hardware_floor(
    settings: Settings | None = None,
    *,
    total_memory_bytes: int | None = None,
) -> DependencyStatus:
    """Report whether this machine meets the local model runtime's memory floor.

    The third capability axis. The product already distinguishes *installed*
    (:class:`~cadrumo.core.OptionalExtra`) from *permitted*
    (:class:`~cadrumo.core.ServiceCapability`); this answers *capable* -- and is
    named for the floor it measures rather than for the word "capability",
    which already denotes four unrelated concepts in this tree (modelo-revision
    capability, terminal capability, operator service capability, optional-extra
    capability).

    Below the floor the local runtime does not refuse. It loads and thrashes, or
    is killed mid-read, and the operator sees an unexplained timeout. This probe
    turns that into a typed row naming the shortfall and the accepted floor.

    Unknown memory reports ``available`` **true** with a detail saying so. That
    is deliberate and is the safe direction for a *diagnostic*: an unreadable
    platform must not manufacture a shortfall that blocks a machine which may be
    perfectly adequate. The refusal is raised only on a *measured* shortfall.

    Args:
        settings: Settings carrying the configured floor; loaded when omitted.
        total_memory_bytes: Observed total memory, for callers that have already
            measured it. Defaults to :func:`read_total_system_memory_bytes`.

    Returns:
        A :class:`DependencyStatus` on the ``model-runtime-hardware-floor`` row.
    """
    resolved = settings if settings is not None else load_settings()
    floor = resolved.cadrumo_llm_model_runtime_memory_floor_bytes
    observed = total_memory_bytes if total_memory_bytes is not None else read_total_system_memory_bytes()
    if observed is None:
        return DependencyStatus(
            service="model-runtime-hardware-floor",
            available=True,
            facts={"total_memory_measured": False, "memory_floor_bytes": floor},
        )
    if observed < floor:
        return DependencyStatus(
            service="model-runtime-hardware-floor",
            available=False,
            facts={
                "total_memory_bytes": observed,
                "memory_floor_bytes": floor,
                "vision_model": resolved.cadrumo_llm_ollama_vision_model,
            },
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET,
                facts={
                    "total_memory_bytes": observed,
                    "memory_floor_bytes": floor,
                    "vision_model": resolved.cadrumo_llm_ollama_vision_model,
                },
            ),
        )
    return DependencyStatus(
        service="model-runtime-hardware-floor",
        available=True,
        facts={"total_memory_bytes": observed, "memory_floor_bytes": floor},
    )


def probe_optional_extra(extra: OptionalExtra) -> DependencyStatus:
    """Probe whether an optional package extra is importable, never raising.

    Wraps the core :func:`optional_extra_available` spec-only check for one
    :class:`~cadrumo.core.OptionalExtra` (no import, no side effects) in the doctor's
    :class:`DependencyStatus`, retaining only the extra's machine identity when
    absent. The feature-boundary guard is the sibling core
    :func:`~cadrumo.core.require_optional_extra`, which raises the typed
    :class:`~cadrumo.core.MissingOptionalExtraError` when a command actually
    requires the feature.
    """
    if not optional_extra_available(extra):
        return DependencyStatus(
            service=f"extra:{extra.extra}",
            available=False,
            facts={"extra": extra.extra, "import_name": extra.import_name, "importable": False},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.OPTIONAL_EXTRA_IMPORTABLE,
                facts={"extra": extra.extra, "import_name": extra.import_name, "importable": False},
            ),
        )
    return DependencyStatus(
        service=f"extra:{extra.extra}",
        available=True,
        facts={"extra": extra.extra, "import_name": extra.import_name, "importable": True},
    )


class AcceleratorDevice(BaseModel):
    """One enumerated accelerator device and its measured VRAM figures.

    Per-device rather than aggregated because a model loads onto ONE device: two
    cards with 3 GiB free each are not 6 GiB of headroom for a 4 GiB model. The
    aggregation rules that follow from that live on
    :class:`HardwareProfile`.
    """

    model_config = STRICT_FROZEN_CONFIG

    index: int = Field(ge=0)
    name: str = Field(min_length=1)
    total_vram_bytes: int | None = Field(default=None, ge=0)
    free_vram_bytes: int | None = Field(default=None, ge=0)


class AcceleratorReading(BaseModel):
    """What the accelerator measurement found: a kind, and the devices behind it.

    ``kind`` is :class:`~core.AcceleratorKind`; an empty ``devices`` tuple is
    consistent with both ``NONE`` (measured: there are none) and ``UNKNOWN``
    (not measured), which is precisely why the kind is carried separately rather
    than inferred from the tuple being empty.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: AcceleratorKind
    devices: tuple[AcceleratorDevice, ...] = ()
    detail: str = ""


class HardwareProfile(BaseModel):
    """The measured local-inference capacity of this machine.

    Carries totals AND free amounts on both the system-memory and the device
    axis, and the two are not interchangeable: **totals are for reporting, free
    amounts are for acting.** A diagnostic row may say "16 GiB card"; a load
    decision may only consult :attr:`free_vram_bytes`. Deciding on a total is the
    concrete defect this model exists to prevent -- the machine this was built
    for has a 16 GiB card with under 4 GiB free, shared with a resident search
    service, and a load admitted against the total takes the host down with every
    running process on it.

    Every figure is independently optional. ``None`` means the measurement was
    not obtainable, and per the provisioning decision the two directions differ:
    diagnostic rows report an unreadable figure as **unverified** and stay
    available, while :func:`assess_model_load_contention` treats it as a refusal
    input. See :func:`probe_hardware_profile`.
    """

    model_config = STRICT_FROZEN_CONFIG

    memory: SystemMemoryReading
    accelerator: AcceleratorReading

    @property
    def total_vram_bytes(self) -> int | None:
        """Return summed device VRAM for REPORTING, or ``None`` when any device is unreadable.

        Summed because the reporting question is "what is installed in this
        machine", which is additive. Deliberately NOT the figure any load
        decision consults -- see :attr:`free_vram_bytes`.
        """
        devices = self.accelerator.devices
        if not devices or any(device.total_vram_bytes is None for device in devices):
            return None
        return sum(device.total_vram_bytes or 0 for device in devices)

    @property
    def free_vram_bytes(self) -> int | None:
        """Return the largest single-device free VRAM for ACTING, or ``None`` when unreadable.

        The maximum, never the sum: a model is resident on one device, so the
        headroom that decides admission is the best single device's, and summing
        would manufacture capacity that no allocation can reach. Devices whose
        free figure is unreadable are skipped rather than counted as zero --
        they cannot host the load either way, and treating them as zero would
        not change the maximum.

        ``None`` when no device reported a free figure at all, which fails
        closed at the act.
        """
        readable = [device.free_vram_bytes for device in self.accelerator.devices if device.free_vram_bytes is not None]
        if not readable:
            return None
        return max(readable)


def read_accelerator() -> AcceleratorReading:
    """Measure the local accelerator through NVML, never raising and never loading a model.

    NVML (the ``nvidia-ml-py`` binding declared in the ``llm`` extra) is
    preferred over a ``nvidia-smi`` shell-out because it yields **per-device**
    total and free figures from an in-process query with no subprocess. The
    distinction is load-bearing for attribution: a whole-device free figure is
    contaminated by every process on the card, which is exactly the quantity
    :func:`assess_model_load_contention` must split between this runtime's
    residents and peer processes -- so NVML is authoritative for the free-VRAM
    figure, and the runtime's own ``/api/ps`` report (see
    :func:`read_runtime_residents`) is authoritative for how much of it is ours.

    Returns :attr:`~core.AcceleratorKind.UNKNOWN` when NVML is absent or
    uninitialisable, and :attr:`~core.AcceleratorKind.NONE` only on the positive
    reading that NVML initialised and enumerated zero devices.
    """
    try:
        import pynvml
    except ImportError:
        return AcceleratorReading(
            kind=AcceleratorKind.UNKNOWN,
            detail="NVML is not installed, so device memory could not be measured",
        )
    try:
        pynvml.nvmlInit()
    except (pynvml.NVMLError, OSError) as exc:
        return AcceleratorReading(
            kind=AcceleratorKind.UNKNOWN,
            detail=f"NVML is installed but did not initialise ({exc.__class__.__name__})",
        )
    try:
        try:
            count = int(pynvml.nvmlDeviceGetCount())
        except (pynvml.NVMLError, OSError, ValueError):
            return AcceleratorReading(
                kind=AcceleratorKind.UNKNOWN,
                detail="NVML initialised but the device count could not be read",
            )
        if count == 0:
            return AcceleratorReading(
                kind=AcceleratorKind.NONE,
                detail="NVML initialised and enumerated no devices",
            )
        devices: list[AcceleratorDevice] = []
        for index in range(count):
            name = f"device {index}"
            total: int | None = None
            free: int | None = None
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                raw_name = pynvml.nvmlDeviceGetName(handle)
                name = raw_name.decode("utf-8", "replace") if isinstance(raw_name, bytes) else str(raw_name)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total = int(info.total)
                free = int(info.free)
            except (pynvml.NVMLError, OSError, ValueError, AttributeError):
                # A device that answers nothing stays enumerated with unreadable
                # figures rather than being dropped: its presence is a real
                # measurement even when its memory is not.
                pass
            devices.append(
                AcceleratorDevice(
                    index=index,
                    name=name or f"device {index}",
                    total_vram_bytes=total,
                    free_vram_bytes=free,
                ),
            )
        return AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=tuple(devices),
            detail=f"NVML enumerated {count} device(s)",
        )
    finally:
        with contextlib.suppress(pynvml.NVMLError, OSError):
            pynvml.nvmlShutdown()


def probe_hardware_profile(
    *,
    memory: SystemMemoryReading | None = None,
    accelerator: AcceleratorReading | None = None,
) -> HardwareProfile:
    """Measure this machine into a :class:`HardwareProfile`, never raising.

    Both measurements are injectable arguments rather than patched module
    internals, so every branch of the profile and of
    :func:`assess_model_load_contention` is exercised against real model
    construction with real readings -- a test must never depend on this host's
    actual device state, which changes minute to minute while an agent fleet
    runs on it.

    Args:
        memory: A system-memory reading; measured via :func:`read_system_memory`
            when omitted.
        accelerator: An accelerator reading; measured via
            :func:`read_accelerator` when omitted.

    Returns:
        The composed :class:`HardwareProfile`.
    """
    return HardwareProfile(
        memory=memory if memory is not None else read_system_memory(),
        accelerator=accelerator if accelerator is not None else read_accelerator(),
    )


def binding_free_bytes(profile: HardwareProfile) -> int | None:
    """Return free memory in the arena that actually binds a model load, or ``None``.

    The one place the arena rule lives, shared by
    :func:`assess_model_load_contention` (which acts on it) and
    :func:`select_model_for_role` (which plans against it), so the two can never
    disagree about which figure binds. A device load is bound by device memory,
    a measured-accelerator-free machine by system memory, and an *unmeasurable*
    accelerator by nothing that may be trusted -- which is ``None``, and is why
    :attr:`~core.AcceleratorKind.UNKNOWN` does not fall through to system
    memory: a card this build cannot read may still be holding the memory a
    load needs.
    """
    kind = profile.accelerator.kind
    if kind is AcceleratorKind.NVIDIA_CUDA:
        return profile.free_vram_bytes
    if kind is AcceleratorKind.NONE:
        return profile.memory.free_bytes
    return None


def probe_local_inference_hardware(profile: HardwareProfile | None = None) -> DependencyStatus:
    """Report the measured hardware profile as a diagnostic row, unknown shown as unverified.

    Follows the shipped direction of :func:`probe_model_runtime_hardware_floor`:
    an unreadable figure keeps ``available`` **true** and is rendered as
    ``unverified``, because a *diagnostic* must not manufacture a shortfall on a
    platform it merely cannot measure. The opposite direction governs
    :func:`assess_model_load_contention`, which acts rather than reports and so
    refuses on the same unknown.

    Args:
        profile: A measured profile; probed via :func:`probe_hardware_profile`
            when omitted.

    Returns:
        A :class:`DependencyStatus` on the ``local-inference-hardware`` row.
    """
    resolved = profile if profile is not None else probe_hardware_profile()
    kind = resolved.accelerator.kind
    facts: dict[str, ProvisioningFactValue] = {
        "accelerator_kind": kind.value,
        "total_memory_measured": resolved.memory.total_bytes is not None,
        "free_memory_measured": resolved.memory.free_bytes is not None,
        "total_vram_measured": resolved.total_vram_bytes is not None,
        "free_vram_measured": resolved.free_vram_bytes is not None,
    }
    if resolved.memory.total_bytes is not None:
        facts["total_memory_bytes"] = resolved.memory.total_bytes
    if resolved.memory.free_bytes is not None:
        facts["free_memory_bytes"] = resolved.memory.free_bytes
    if resolved.total_vram_bytes is not None:
        facts["total_vram_bytes"] = resolved.total_vram_bytes
    if resolved.free_vram_bytes is not None:
        facts["free_vram_bytes"] = resolved.free_vram_bytes
    if kind is AcceleratorKind.UNKNOWN:
        return DependencyStatus(
            service="local-inference-hardware",
            available=True,
            facts=facts,
        )
    return DependencyStatus(service="local-inference-hardware", available=True, facts=facts)


class ModelSelection(ProvisioningOutcome):
    """Which model a role resolved to, and everything the operator should know about it.

    A *planning* result, not an admission decision. It answers "which model
    should this role use on this machine"; whether that model may be loaded
    right now is :func:`assess_model_load_contention`'s question, asked later
    and against readings taken at that moment. Keeping the two apart is what
    lets selection stay useful on a machine whose headroom is momentarily gone.

    ``selected`` false means no catalogued candidate cleared the bars, and
    ``runtime_id`` is then ``None`` rather than a fallback -- naming a model
    that cannot serve the role would push the failure into inference, where it
    surfaces as a timeout instead of as a refusal.

    ``advisories`` is never empty for an override that carries a licence,
    context or headroom concern. An override is honoured, because the operator's
    explicit setting outranks the catalogue's preference -- but it is never
    honoured silently.
    """

    role: ModelRole
    runtime: ModelRuntime
    runtime_id: str | None = None
    candidate: ModelCandidate | None = None
    posture: DeploymentLicencePosture
    tier: HardwareTier
    binding_free_bytes: int | None = Field(default=None, ge=0)
    required_context_tokens: int = Field(gt=0)
    safety_margin_bytes: int = Field(ge=0)
    override_applied: bool = False
    selected: bool
    advisories: tuple[ModelSelectionAdvisory, ...] = ()

    @model_validator(mode="after")
    def _require_selection_outcome(self) -> ModelSelection:
        require_provisioning_verdict(failed=not self.selected, verdict=self.precondition_verdict)
        return self

    @property
    def assessable_load(self) -> tuple[str, int] | None:
        """Return ``(runtime_id, required_bytes)`` when a load can be assessed at all.

        ``None`` when this role selected nothing, or when the chosen candidate
        declares no memory requirement. The second case matters as much as the
        first and is easier to miss: an unknown requirement read as zero flows
        into :func:`assess_model_load_contention` as the amount the model
        needs, so the check reports the load ADMITTED on evidence nobody has.

        Owned here because every caller was re-deriving the same three-part
        guard -- selected, runtime id, candidate -- and each one that forgot the
        fourth part (the requirement itself being optional) fail-opened in its
        own way. A caller that cannot assess should say so rather than assess
        against an invented number.
        """
        if not self.selected or self.runtime_id is None or self.candidate is None:
            return None
        requirement = self.candidate.memory_requirement_bytes
        return None if requirement is None else (self.runtime_id, requirement)

    @property
    def licence_advisory(self) -> str:
        """Return the localised non-commercial licence advisory, or an empty string.

        Non-empty exactly when
        :attr:`~core.ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED` is
        present, which automatic selection can never produce -- so this string
        appearing is itself the signal that an override reached past the
        commercial posture.
        """
        if ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED not in self.advisories:
            return ""
        candidate = self.candidate
        if candidate is None:
            return ""
        return tr(
            "provisioning.model.licence.non_commercial_advisory",
            model=candidate.runtime_id,
            licence=candidate.licence.name,
        )


class _SelectionContext(TypedDict):
    """The fields every :class:`ModelSelection` branch shares.

    A TypedDict rather than a bare mapping so the splat below stays checked:
    every return path in this surface builds one ``ModelSelection`` from a
    common context plus its own outcome fields, and an untyped splat would let a
    renamed or mistyped shared field through to runtime.
    """

    role: ModelRole
    runtime: ModelRuntime
    posture: DeploymentLicencePosture
    tier: HardwareTier
    binding_free_bytes: int | None
    required_context_tokens: int
    safety_margin_bytes: int


def select_model_for_role(
    role: ModelRole,
    *,
    profile: HardwareProfile | None = None,
    settings: Settings | None = None,
    override: str | None = None,
    posture: DeploymentLicencePosture = DeploymentLicencePosture.COMMERCIAL,
    runtime: ModelRuntime = ModelRuntime.LOCAL_OLLAMA,
) -> ModelSelection:
    """Resolve ``role`` to the weakest catalogued model that clears every bar.

    **Bounded from below, never maximised.** Candidates are ordered by ascending
    memory requirement and the FIRST survivor wins, so a machine with headroom
    to spare still gets the small model. A larger model is an operator's
    explicit choice, which is why nothing here ranks on capability above the
    floor.

    Three bars, applied in this order and each for a different reason:

    * **Context window.** A model whose window cannot hold the configured
      request window is excluded on *capability*, not preference -- it cannot do
      the job at any price.
    * **Licence.** Under a ``COMMERCIAL`` posture a candidate whose publisher
      text bars commercial use is not eligible. This is the bar that moved the
      shipped default.
    * **Measured headroom.** Requirement plus the configured safety margin
      against free memory in the binding arena.

    An unmeasurable machine does **not** refuse here, and that is deliberate
    rather than a softening of the fail-closed rule: refusing to *name* a model
    because headroom is momentarily unreadable would break provisioning on
    exactly the machines that most need to pull one, while the load itself is
    still failed closed by :func:`assess_model_load_contention` at the act. The
    selection says so with
    :attr:`~core.ModelSelectionAdvisory.FIT_UNVERIFIED`.

    Args:
        role: The role to resolve.
        profile: Measured hardware; probed when omitted.
        settings: Settings carrying the context window and safety margin; loaded
            when omitted.
        override: An operator-named runtime id that outranks selection. Honoured
            even when uncatalogued or licence-barred, always with advisories.
        posture: The deployment's licence posture; commercial by default,
            because that is what this product is.
        runtime: Which runtime to resolve against; on-host by default, because
            the on-host route is the one the product prefers and the one that
            keeps evidence on the operator's machine. A hosted runtime skips the
            headroom bar (nothing runs here) and keeps the capability and licence
            bars, which apply wherever the prompt is served.

    Returns:
        A :class:`ModelSelection`. Never raises: an unsatisfiable role returns
        ``selected`` false carrying the measured reason and closed outcome.
    """
    resolved = settings if settings is not None else load_settings()
    hardware = profile if profile is not None else probe_hardware_profile()
    free = binding_free_bytes(hardware)
    tier = hardware_tier_for_free_bytes(free)
    required_context = resolved.cadrumo_llm_ollama_num_ctx
    margin = resolved.cadrumo_llm_contention_safety_margin_bytes
    base = _SelectionContext(
        role=role,
        runtime=runtime,
        posture=posture,
        tier=tier,
        binding_free_bytes=free,
        required_context_tokens=required_context,
        safety_margin_bytes=margin,
    )

    if override is not None:
        return _selection_from_override(
            override,
            base=base,
            posture=posture,
            free=free,
            margin=margin,
            context=required_context,
        )

    eligible = _eligible_model_candidates(
        role,
        runtime=runtime,
        required_context=required_context,
        posture=posture,
    )
    if not eligible:
        return _selection_without_eligible_candidate(
            base,
            role=role,
            runtime=runtime,
            required_context=required_context,
            posture=posture,
        )

    fitting = _fitting_model_candidates(eligible, free=free, margin=margin)
    if not fitting:
        return _selection_without_fitting_candidate(
            base,
            role=role,
            runtime=runtime,
            free=free,
            margin=margin,
            smallest=eligible[0],
        )

    return _selected_model_selection(base, candidate=fitting[0], free=free)


def _eligible_model_candidates(
    role: ModelRole,
    *,
    runtime: ModelRuntime,
    required_context: int,
    posture: DeploymentLicencePosture,
) -> tuple[ModelCandidate, ...]:
    """Return ordered candidates that clear the capability and licence bars."""
    return tuple(
        candidate
        for candidate in candidates_for_role(role, runtime)
        if candidate.max_context_tokens >= required_context and candidate.permitted_under(posture)
    )


def _fitting_model_candidates(
    candidates: tuple[ModelCandidate, ...],
    *,
    free: int | None,
    margin: int,
) -> tuple[ModelCandidate, ...]:
    """Return eligible candidates that fit local headroom, preserving catalogue order."""
    # A hosted candidate has no local weights, so the headroom bar does not
    # apply to it -- comparing this machine's free memory against a model that
    # never touches it would refuse a route that cannot fail that way.
    return tuple(
        candidate
        for candidate in candidates
        if candidate.memory_requirement_bytes is None
        or free is None
        or candidate.memory_requirement_bytes + margin <= free
    )


def _selection_without_eligible_candidate(
    base: _SelectionContext,
    *,
    role: ModelRole,
    runtime: ModelRuntime,
    required_context: int,
    posture: DeploymentLicencePosture,
) -> ModelSelection:
    """Return the typed refusal when capability and licence filters leave no candidate."""
    facts: dict[str, ProvisioningFactValue] = {
        "role": role.value,
        "runtime": runtime.value,
        "required_context_tokens": required_context,
        "deployment_posture": posture.value,
        "eligible_candidate_count": 0,
    }
    return _selection_refusal(
        base,
        condition=ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE,
        facts=facts,
    )


def _selection_without_fitting_candidate(
    base: _SelectionContext,
    *,
    role: ModelRole,
    runtime: ModelRuntime,
    free: int | None,
    margin: int,
    smallest: ModelCandidate,
) -> ModelSelection:
    """Return the typed refusal when the first eligible model cannot fit."""
    needed = (smallest.memory_requirement_bytes or 0) + margin
    facts: dict[str, ProvisioningFactValue] = {
        "role": role.value,
        "runtime": runtime.value,
        "binding_free_bytes": free if free is not None else 0,
        "required_bytes": needed,
        "selected_model": smallest.runtime_id,
    }
    return _selection_refusal(
        base,
        condition=ProvisioningPreconditionCondition.SELECTED_MODEL_FITS,
        facts=facts,
        advisories=(ModelSelectionAdvisory.FIT_EXCEEDS_MEASURED_HEADROOM,),
    )


def _selection_refusal(
    base: _SelectionContext,
    *,
    condition: ProvisioningPreconditionCondition,
    facts: Mapping[str, ProvisioningFactValue],
    advisories: tuple[ModelSelectionAdvisory, ...] = (),
) -> ModelSelection:
    """Build one failed selection with its immutable evidence and verdict."""
    return ModelSelection(
        **base,
        selected=False,
        advisories=advisories,
        facts=facts,
        precondition_verdict=provisioning_no_recovery_verdict(condition, facts=facts),
    )


def _selected_model_selection(
    base: _SelectionContext,
    *,
    candidate: ModelCandidate,
    free: int | None,
) -> ModelSelection:
    """Project the first fitting candidate, retaining unknown-fit evidence."""
    advisories: list[ModelSelectionAdvisory] = []
    if free is None and candidate.memory_requirement_bytes is not None:
        advisories.append(ModelSelectionAdvisory.FIT_UNVERIFIED)
    return ModelSelection(
        **base,
        runtime_id=candidate.runtime_id,
        candidate=candidate,
        selected=True,
        advisories=tuple(advisories),
        facts={
            "role": base["role"].value,
            "runtime": base["runtime"].value,
            "selected_model": candidate.runtime_id,
            "required_context_tokens": base["required_context_tokens"],
            "selected_model_requirement_known": candidate.memory_requirement_bytes is not None,
            "binding_free_measured": free is not None,
        },
    )


def _selection_from_override(
    override: str,
    *,
    base: _SelectionContext,
    posture: DeploymentLicencePosture,
    free: int | None,
    margin: int,
    context: int,
) -> ModelSelection:
    """Honour an operator-named model, attaching every concern it carries.

    The override always wins -- an operator who names a model has made a
    decision this function is not entitled to overturn. What it is entitled to
    do is refuse to be quiet about it, which is the whole of this helper.
    """
    candidate = model_candidate(override)
    if candidate is None:
        return ModelSelection(
            **base,
            runtime_id=override,
            selected=True,
            override_applied=True,
            advisories=(
                ModelSelectionAdvisory.OVERRIDE_NOT_IN_CATALOGUE,
                ModelSelectionAdvisory.LICENCE_UNVERIFIED,
            ),
            facts={
                "selected_model": override,
                "selected_model_catalogued": False,
                "override_applied": True,
            },
        )

    advisories: list[ModelSelectionAdvisory] = []
    if not candidate.permitted_under(posture):
        advisories.append(ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED)
    if candidate.max_context_tokens < context:
        advisories.append(ModelSelectionAdvisory.OVERRIDE_BELOW_CONTEXT_FLOOR)
    if candidate.memory_requirement_bytes is None:
        pass  # hosted: nothing runs on this machine, so there is no fit to judge
    elif free is None:
        advisories.append(ModelSelectionAdvisory.FIT_UNVERIFIED)
    elif candidate.memory_requirement_bytes + margin > free:
        advisories.append(ModelSelectionAdvisory.FIT_EXCEEDS_MEASURED_HEADROOM)

    return ModelSelection(
        **base,
        runtime_id=candidate.runtime_id,
        candidate=candidate,
        selected=True,
        override_applied=True,
        advisories=tuple(advisories),
        facts={
            "selected_model": candidate.runtime_id,
            "selected_model_catalogued": True,
            "override_applied": True,
            "selected_model_requirement_known": candidate.memory_requirement_bytes is not None,
        },
    )


#: The doctor row id for the local-inference provisioning coherence check.
LOCAL_MODEL_PROVISIONING_SERVICE = "local_model_provisioning"


def probe_local_model_provisioning(
    *,
    installed: tuple[InstalledModel, ...] | None = None,
    installed_measured: bool = True,
    settings: Settings | None = None,
) -> DependencyStatus:
    """Detect a PARTIALLY-installed local-inference posture, in both directions.

    Local inference has two independent halves: the ``llm`` package extra, which
    an operator installs with pip, and the models themselves, which an operator
    pulls into the runtime. Either half can be present without the other, and the
    two broken states are not variations of one problem -- they have different
    causes and different remedies, so a row detecting only one strands every
    operator who lands in the other with no signal at all.

    * **Extra present, no selected model installed.** The code path is live and
      the model it would load is absent. The remedy is a pull.
    * **A selected model installed, extra absent.** Multi-gigabyte models occupy
      disk that nothing can use, typically after a core reinstall. The remedy is
      the extra's install command -- or a removal, to reclaim the disk.

    The two conditions are disjoint by construction: each requires the extra
    state the other forbids, so neither can be satisfied by the other's evidence
    and a check for one can never stand in for the other.

    Coherent postures -- both halves present, or neither -- report available. So
    does the case where the inventory cannot be read while the extra is ALSO
    absent: nothing indicates an opted-in local-inference posture, and the
    detail says plainly that the inventory was not readable so the
    models-without-extra direction could not be ruled out. When the extra IS
    present, an unreadable inventory is itself reported, because an operator who
    opted into local inference and cannot be told what is installed has a real
    problem rather than an absence.

    Args:
        installed: The on-disk inventory; read via :func:`read_installed_models`
            when omitted.
        installed_measured: False when the inventory could not be read.
        settings: Settings carrying the runtime endpoint and role models.

    Returns:
        A :class:`DependencyStatus` naming the direction and its remedy.
    """
    resolved = settings if settings is not None else load_settings()
    extra_present = optional_extra_available(LLM_EXTRA)
    if installed is None and installed_measured:
        inventory = read_installed_models(resolved)
    else:
        inventory = installed if installed_measured else None

    if inventory is None:
        if extra_present:
            return DependencyStatus(
                service=LOCAL_MODEL_PROVISIONING_SERVICE,
                available=False,
                facts={"extra": LLM_EXTRA.extra, "extra_importable": True, "installed_model_inventory_readable": False},
                precondition_verdict=provisioning_no_recovery_verdict(
                    ProvisioningPreconditionCondition.LOCAL_MODEL_INVENTORY_READABLE,
                    facts={
                        "extra": LLM_EXTRA.extra,
                        "extra_importable": True,
                        "installed_model_inventory_readable": False,
                    },
                ),
            )
        return DependencyStatus(
            service=LOCAL_MODEL_PROVISIONING_SERVICE,
            available=True,
            facts={"extra": LLM_EXTRA.extra, "extra_importable": False, "installed_model_inventory_readable": False},
        )

    selected = cadrumo_selected_models(resolved)
    present = tuple(sorted(row.name for row in inventory if matches_selected_model(row.name, selected)))

    if extra_present and not present:
        return DependencyStatus(
            service=LOCAL_MODEL_PROVISIONING_SERVICE,
            available=False,
            facts={
                "extra": LLM_EXTRA.extra,
                "extra_importable": True,
                "selected_model_count": len(selected),
                "present_selected_model_count": 0,
            },
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.LOCAL_MODEL_EXTRA_REQUIRES_MODEL,
                facts={
                    "extra": LLM_EXTRA.extra,
                    "extra_importable": True,
                    "selected_model_count": len(selected),
                    "present_selected_model_count": 0,
                },
            ),
        )
    if present and not extra_present:
        return DependencyStatus(
            service=LOCAL_MODEL_PROVISIONING_SERVICE,
            available=False,
            facts={
                "extra": LLM_EXTRA.extra,
                "extra_importable": False,
                "present_selected_model_count": len(present),
            },
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.LOCAL_MODEL_MODEL_REQUIRES_EXTRA,
                facts={
                    "extra": LLM_EXTRA.extra,
                    "extra_importable": False,
                    "present_selected_model_count": len(present),
                },
            ),
        )
    if extra_present:
        return DependencyStatus(
            service=LOCAL_MODEL_PROVISIONING_SERVICE,
            available=True,
            facts={
                "extra": LLM_EXTRA.extra,
                "extra_importable": True,
                "present_selected_model_count": len(present),
            },
        )
    return DependencyStatus(
        service=LOCAL_MODEL_PROVISIONING_SERVICE,
        available=True,
        facts={"extra": LLM_EXTRA.extra, "extra_importable": False, "present_selected_model_count": 0},
    )


def probe_optional_extras() -> tuple[DependencyStatus, ...]:
    """Probe every capability-gated :class:`~cadrumo.core.OptionalExtra` into :class:`DependencyStatus` rows.

    The result set is keyed by the same :data:`~cadrumo.core.OPTIONAL_EXTRAS`
    catalogue used by :func:`~cadrumo.core.require_optional_extra`, keeping
    ``aeat config check`` and runtime feature guards aligned.
    """
    return tuple(probe_optional_extra(extra) for extra in OPTIONAL_EXTRAS)
