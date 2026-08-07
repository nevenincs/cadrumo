"""Typed external-dependency probes for graceful degradation and ``config check``.

This module is the read-only application doctor surface: each probe asks whether
one external service or optional package extra is usable on this workstation and
returns a typed :class:`DependencyStatus` with the exact remediation command when
it is not. Probes do not provision, unlock, write profile state, or raise on
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
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypedDict, cast

import httpx
from pydantic import BaseModel, Field

from ..core import (
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
from ..core.i18n import tr

__all__ = [
    "OPTIONAL_EXTRAS",
    "AcceleratorDevice",
    "AcceleratorKind",
    "AcceleratorReading",
    "ContentionCause",
    "ContentionSnapshot",
    "DependencyStatus",
    "HardwareProfile",
    "HardwareTier",
    "ModelSelection",
    "OptionalExtra",
    "PullOutcome",
    "PullProgress",
    "ReadinessOutcome",
    "RuntimeResident",
    "SystemMemoryReading",
    "UnloadOutcome",
    "assess_model_load_contention",
    "binding_free_bytes",
    "cadrumo_selected_models",
    "probe_hardware_profile",
    "probe_local_inference_hardware",
    "probe_model_runtime_hardware_floor",
    "probe_ollama_vision",
    "probe_optional_extra",
    "probe_optional_extras",
    "probe_playwright_browser",
    "pull_runtime_model",
    "read_accelerator",
    "read_runtime_residents",
    "read_system_memory",
    "select_model_for_role",
    "unload_runtime_model",
    "verify_model_ready",
]

_OLLAMA_PROBE_TIMEOUT_S = 2.0

# A model fetch is a multi-gigabyte download over an operator's connection, so
# it gets its own generous bound rather than the 2s probe timeout, which exists
# to keep a doctor row responsive and would abort every real pull.
_OLLAMA_PULL_TIMEOUT_S = 3600.0

# Readiness asks whether a LOADED model answers. A cold load of a small vision
# model is tens of seconds on this class of hardware, so the bound is generous
# enough not to report a working model as unready while still bounded.
_OLLAMA_READINESS_TIMEOUT_S = 120.0


class DependencyStatus(BaseModel):
    """Availability result for one external dependency.

    ``service`` is the stable row id shown by ``aeat config check``; ``detail``
    explains the observed state; ``remediation`` is the command or action the
    operator can run when ``available`` is false. The model is intentionally
    generic so Ollama, subprocess CLIs, Playwright browser binaries, and
    :class:`~cadrumo.core.OptionalExtra` package extras all render through the same
    payload shape and can be validated into
    :class:`~cadrumo.entrypoints.cli._config._check_payloads.CheckDependencyPayload`.
    """

    model_config = STRICT_FROZEN_CONFIG

    service: str = Field(min_length=1)
    available: bool
    detail: str = ""
    remediation: str = ""


def probe_ollama_vision(settings: Settings | None = None) -> DependencyStatus:
    """Probe Ollama and the configured vision model, returning a :class:`DependencyStatus`.

    Reads ``cadrumo_llm_ollama_chat_url`` and ``cadrumo_llm_ollama_vision_model`` from
    :class:`~cadrumo.core.config.Settings`, then performs a short-timeout
    ``GET /api/tags``. The probe never runs inference and returns unavailable
    when the server is unreachable (``ollama serve``) or the configured model is
    not pulled (``ollama pull <model>``). Ledger evidence reading uses this
    result before local-vision inference so
    :class:`~cadrumo.domain.transactions.LLMClassifierError` can carry the exact
    remediation.
    """
    resolved = settings if settings is not None else load_settings()
    model = resolved.cadrumo_llm_ollama_vision_model
    url = _ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "tags")
    try:
        with httpx.Client(timeout=_OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
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
    except (httpx.HTTPError, ValueError):
        return DependencyStatus(
            service="ollama-vision",
            available=False,
            detail=f"Ollama is not reachable at {url}",
            remediation="start Ollama (ollama serve) and ensure it listens on cadrumo_llm_ollama_chat_url",
        )
    # Ollama lists names with the tag (e.g. "qwen2.5vl:3b"); match the configured
    # model exactly or by its untagged stem.
    present = model in names or any(name.split(":", 1)[0] == model.split(":", 1)[0] for name in names)
    if not present:
        return DependencyStatus(
            service="ollama-vision",
            available=False,
            detail=f"Ollama is running but the vision model {model!r} is not pulled",
            remediation=f"ollama pull {model}",
        )
    return DependencyStatus(
        service="ollama-vision",
        available=True,
        detail=f"Ollama is reachable and {model!r} is pulled",
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
    empty cache roots return unavailable with the ``playwright install chromium``
    remediation. ``cache_root`` is a testable override for the browser cache
    directory. The row complements the browser health probe in
    :mod:`cadrumo.application.diagnostics`; it checks workstation provisioning, not
    AEAT site reachability.
    """
    root = _playwright_browsers_root(cache_root)
    try:
        installed = root.is_dir() and any(child.name.startswith("chromium") for child in root.iterdir())
    except OSError:
        installed = False
    if not installed:
        return DependencyStatus(
            service="playwright-chromium",
            available=False,
            detail=f"no Playwright Chromium build found under {root}",
            remediation="playwright install chromium",
        )
    return DependencyStatus(
        service="playwright-chromium",
        available=True,
        detail=f"Chromium build present under {root}",
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
    floor_gib = floor / 1024**3
    if observed is None:
        return DependencyStatus(
            service="model-runtime-hardware-floor",
            available=True,
            detail=(
                f"total system memory could not be read on this platform; the local model "
                f"runtime floor of {floor_gib:.1f} GiB was not verified"
            ),
        )
    observed_gib = observed / 1024**3
    if observed < floor:
        return DependencyStatus(
            service="model-runtime-hardware-floor",
            available=False,
            detail=(
                f"total system memory {observed_gib:.1f} GiB is below the local model "
                f"runtime floor of {floor_gib:.1f} GiB for model "
                f"{resolved.cadrumo_llm_ollama_vision_model!r}"
            ),
            remediation=(
                "resolve the vision role against this machine with select_model_for_role, which "
                "names the weakest catalogued candidate that still clears the capability bar, or "
                "lower cadrumo_llm_model_runtime_memory_floor_bytes if this machine is known good"
            ),
        )
    return DependencyStatus(
        service="model-runtime-hardware-floor",
        available=True,
        detail=f"total system memory {observed_gib:.1f} GiB meets the {floor_gib:.1f} GiB local model runtime floor",
    )


def probe_optional_extra(extra: OptionalExtra) -> DependencyStatus:
    """Probe whether an optional package extra is importable, never raising.

    Wraps the core :func:`optional_extra_available` spec-only check for one
    :class:`~cadrumo.core.OptionalExtra` (no import, no side effects) in the doctor's
    :class:`DependencyStatus`, naming the extra's ``install_hint`` as remediation
    when absent. The feature-boundary guard is the sibling core
    :func:`~cadrumo.core.require_optional_extra`, which raises the typed
    :class:`~cadrumo.core.MissingOptionalExtraError` when a command actually
    requires the feature.
    """
    if not optional_extra_available(extra):
        return DependencyStatus(
            service=f"extra:{extra.extra}",
            available=False,
            detail=f"{extra.feature} needs the '{extra.extra}' extra ({extra.import_name} not importable)",
            remediation=extra.install_hint,
        )
    return DependencyStatus(
        service=f"extra:{extra.extra}",
        available=True,
        detail=f"{extra.feature} is available ({extra.import_name} importable)",
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


def _gib(value: int | None) -> str:
    """Render a byte count as GiB for an operator-facing row, or ``unverified`` when unknown."""
    return "unverified" if value is None else f"{value / 1024**3:.1f} GiB"


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
    detail = (
        f"system memory {_gib(resolved.memory.free_bytes)} free of {_gib(resolved.memory.total_bytes)}; "
        f"accelerator {kind.value}; "
        f"VRAM {_gib(resolved.free_vram_bytes)} free of {_gib(resolved.total_vram_bytes)}"
    )
    if kind is AcceleratorKind.UNKNOWN:
        return DependencyStatus(
            service="local-inference-hardware",
            available=True,
            detail=f"{detail} ({resolved.accelerator.detail})",
            remediation=(
                "install the NVML reader (pip install cadrumo[llm]) to measure device headroom; "
                "until then a local model load is refused rather than guessed"
            ),
        )
    return DependencyStatus(service="local-inference-hardware", available=True, detail=detail)


class ModelSelection(BaseModel):
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

    model_config = STRICT_FROZEN_CONFIG

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
    detail: str = ""
    remediation: str = ""

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
        ``selected`` false carrying the reason and a remediation.
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

    eligible = [
        candidate
        for candidate in candidates_for_role(role, runtime)
        if candidate.max_context_tokens >= required_context and candidate.permitted_under(posture)
    ]
    if not eligible:
        return ModelSelection(
            **base,
            selected=False,
            detail=(
                f"no catalogued {role.value} candidate both holds the configured "
                f"{required_context}-token request window and carries a licence permitting "
                f"{posture.value} use"
            ),
            remediation=(
                "lower cadrumo_llm_ollama_num_ctx if the smaller window still fits the prompt, "
                "or name a model explicitly and accept the advisories it carries"
            ),
        )

    # A hosted candidate has no local weights, so the headroom bar does not
    # apply to it -- comparing this machine's free memory against a model that
    # never touches it would refuse a route that cannot fail that way.
    fitting = [
        candidate
        for candidate in eligible
        if candidate.memory_requirement_bytes is None
        or free is None
        or candidate.memory_requirement_bytes + margin <= free
    ]
    if not fitting:
        smallest = eligible[0]
        needed = (smallest.memory_requirement_bytes or 0) + margin
        return ModelSelection(
            **base,
            selected=False,
            advisories=(ModelSelectionAdvisory.FIT_EXCEEDS_MEASURED_HEADROOM,),
            detail=(
                f"{_gib(free)} free on a {tier.value} machine is short of the {_gib(needed)} the "
                f"smallest eligible {role.value} candidate {smallest.runtime_id!r} needs "
                f"({_gib(smallest.memory_requirement_bytes)} requirement plus a {_gib(margin)} margin)"
            ),
            remediation=(
                "close what is holding the memory, or unload a Cadrumo-selected resident model, "
                "then retry; there is no smaller catalogued candidate that clears the capability bar"
            ),
        )

    chosen = fitting[0]
    advisories: list[ModelSelectionAdvisory] = []
    if free is None and chosen.memory_requirement_bytes is not None:
        advisories.append(ModelSelectionAdvisory.FIT_UNVERIFIED)
    detail = (
        f"{role.value} resolves to {chosen.runtime_id!r} ({_gib(chosen.memory_requirement_bytes)}, "
        f"{chosen.licence.spdx_id}) -- the weakest catalogued candidate holding the "
        f"{required_context}-token window on a {tier.value} machine with {_gib(free)} free"
    )
    return ModelSelection(
        **base,
        runtime_id=chosen.runtime_id,
        candidate=chosen,
        selected=True,
        advisories=tuple(advisories),
        detail=detail,
        remediation=(
            "install the NVML reader (pip install cadrumo[llm]) so fit can be verified before the pull"
            if free is None
            else ""
        ),
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
            detail=(
                f"{override!r} was named explicitly but is not in the model catalogue, so neither "
                f"its licence nor its fit on this machine could be judged"
            ),
            remediation=(
                "add the model to the core model catalogue with its publisher-verified licence, "
                "or select a catalogued candidate"
            ),
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
        detail=(
            f"{candidate.runtime_id!r} ({_gib(candidate.memory_requirement_bytes)}, "
            f"{candidate.licence.spdx_id}) was named explicitly and overrides selection"
        ),
    )


class RuntimeResident(BaseModel):
    """One model the local runtime reports as currently loaded.

    Sourced from the runtime's own ``/api/ps`` report, which is what makes the
    figure attributable: it is memory held by models *this* runtime loaded, as
    distinct from the device-wide free shortfall NVML measures. The gap between
    the two is peer-process usage.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    size_bytes: int | None = Field(default=None, ge=0)
    size_vram_bytes: int | None = Field(default=None, ge=0)


def _ollama_endpoint(chat_url: str, path: str) -> str:
    """Derive a sibling runtime endpoint (``/api/<path>``) from the configured chat URL."""
    base = chat_url.rsplit("/api/", 1)[0] if "/api/" in chat_url else chat_url.rstrip("/")
    return f"{base}/api/{path}"


def read_runtime_residents(settings: Settings | None = None) -> tuple[RuntimeResident, ...] | None:
    """Read the local runtime's resident model set, or ``None`` when it could not be read.

    A short-timeout ``GET /api/ps``. Loads nothing and runs no inference. The
    ``None`` return is a distinct state from an empty tuple and the two must not
    be collapsed: empty means "measured, nothing is resident", which permits
    attributing a device shortfall to peer processes, while ``None`` means the
    attribution input is missing and
    :func:`assess_model_load_contention` refuses rather than guessing.
    """
    resolved = settings if settings is not None else load_settings()
    url = _ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "ps")
    try:
        with httpx.Client(timeout=_OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            return None
        # CAST-RATIONALE-OLLAMA-PS-PAYLOAD: httpx.Response.json() returns Any;
        # isinstance narrows to dict but not its type parameters.
        # nosemgrep: no-cast-in-domain-application
        entries = cast(dict[str, object], payload).get("models")
        if not isinstance(entries, list):
            return None
        # CAST-RATIONALE-OLLAMA-PS-MODELS: isinstance narrows to list but not its
        # element type; entries are validated individually below.
        # nosemgrep: no-cast-in-domain-application
        residents: list[RuntimeResident] = []
        for entry in cast(list[object], entries):
            if not isinstance(entry, dict):
                return None
            # CAST-RATIONALE-OLLAMA-PS-ENTRY: isinstance narrows to dict but not
            # its type parameters.
            # nosemgrep: no-cast-in-domain-application
            row = cast(dict[str, object], entry)
            name = row.get("name") or row.get("model")
            if not isinstance(name, str) or not name:
                return None
            size = row.get("size")
            size_vram = row.get("size_vram")
            residents.append(
                RuntimeResident(
                    name=name,
                    size_bytes=int(size) if isinstance(size, int) and size >= 0 else None,
                    size_vram_bytes=int(size_vram) if isinstance(size_vram, int) and size_vram >= 0 else None,
                ),
            )
    except (httpx.HTTPError, ValueError):
        return None
    return tuple(residents)


def cadrumo_selected_models(settings: Settings | None = None) -> frozenset[str]:
    """Return the model identifiers Cadrumo itself selected, the only ones it may unload.

    The boundary of the unload action. A model resident in the local runtime that
    Cadrumo did not select belongs to whoever loaded it, and evicting it would be
    the same overreach as signalling a peer process -- it is reported in the
    contention snapshot and never acted on.
    """
    resolved = settings if settings is not None else load_settings()
    # Every configured role, not a hand-picked pair: a role whose model is left
    # out here is one Cadrumo can load but never release, so the set is the
    # union of the role settings and grows with them.
    return frozenset(
        {
            resolved.cadrumo_llm_ollama_vision_model,
            resolved.cadrumo_llm_ollama_text_model,
            resolved.cadrumo_llm_ollama_mapping_model,
        }
    )


def _matches_selected(name: str, selected: frozenset[str]) -> bool:
    """Return whether a resident model name is one Cadrumo selected, ignoring the tag suffix."""
    stem = name.split(":", 1)[0]
    return name in selected or any(candidate.split(":", 1)[0] == stem for candidate in selected)


class _ContentionSnapshotBase(TypedDict):
    """The fields every contention verdict shares, splatted into each branch.

    Declared rather than left as an inferred mapping because the branches below
    build the snapshot with ``**base``, and an untyped dict widens every value
    to the union of all of them -- so the splat reads as passing an ``int``
    where a model expects a tuple, and the one thing worth checking here, that
    the shared fields match the model they feed, goes unchecked.
    """

    model: str
    requirement_bytes: int
    safety_margin_bytes: int
    accelerator: AcceleratorKind
    free_vram_bytes: int | None
    free_system_memory_bytes: int | None
    binding_free_bytes: int | None
    residents: tuple[RuntimeResident, ...] | None


class ContentionSnapshot(BaseModel):
    """The measured verdict on whether one model load is safe to perform right now.

    Read the fields as three separate claims. ``admitted`` is the decision.
    ``causes`` is :class:`~core.ContentionCause` and says *why* a refusal
    happened, keyed to which remediation applies -- unloading a model Cadrumo
    selected, closing a peer application, or measuring what could not be
    measured. ``residents`` is the attribution evidence: the runtime's own
    loaded set, which is what separates memory Cadrumo can reclaim from memory
    it may only observe.

    Nothing on this model evicts, signals, or otherwise touches a process
    Cadrumo does not own. Pressure caused by a peer is reported and refused,
    never managed.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str = Field(min_length=1)
    requirement_bytes: int = Field(ge=0)
    safety_margin_bytes: int = Field(ge=0)
    accelerator: AcceleratorKind
    free_vram_bytes: int | None = Field(default=None, ge=0)
    free_system_memory_bytes: int | None = Field(default=None, ge=0)
    binding_free_bytes: int | None = Field(default=None, ge=0)
    residents: tuple[RuntimeResident, ...] | None = None
    resident_attributed_bytes: int = Field(default=0, ge=0)
    unloadable_models: tuple[str, ...] = ()
    shortfall_bytes: int | None = Field(default=None, ge=0)
    admitted: bool
    causes: tuple[ContentionCause, ...] = ()
    detail: str = ""
    remediation: str = ""

    @property
    def required_bytes(self) -> int:
        """Return the requirement plus the configured safety margin -- the figure actually compared."""
        return self.requirement_bytes + self.safety_margin_bytes


def _attributed_resident_bytes(
    residents: tuple[RuntimeResident, ...],
    *,
    on_device: bool,
    names: frozenset[str] | None = None,
) -> int:
    """Sum resident memory in the binding arena, optionally restricted to named models."""
    total = 0
    for resident in residents:
        if names is not None and resident.name not in names:
            continue
        held = resident.size_vram_bytes if on_device else resident.size_bytes
        total += held or 0
    return total


def assess_model_load_contention(
    model: str,
    requirement_bytes: int,
    *,
    profile: HardwareProfile | None = None,
    residents: tuple[RuntimeResident, ...] | None = None,
    residents_measured: bool = True,
    settings: Settings | None = None,
) -> ContentionSnapshot:
    """Judge whether loading ``model`` is safe right now, failing closed on any unknown.

    **Acting fails closed where reporting fails open.** The free figures, never
    the totals, are compared against the model's declared requirement plus the
    configured safety margin. An unreadable free figure refuses the load: "could
    not tell" is not evidence of headroom, and is precisely the state that
    destroyed running work on the machine this was built for. The only escape is
    the explicit ``cadrumo_llm_contention_check_override`` setting, which admits
    an *unmeasurable* machine and never a *measured* shortfall.

    On a measured shortfall the cause is attributed rather than assumed, because
    the remediations are not interchangeable. Memory held by the runtime's own
    residents is reclaimable through :func:`unload_runtime_model` -- and only for
    the models Cadrumo selected. Memory unexplained by those residents is a peer
    process's, and the refusal says so instead of telling the operator to unload
    something they do not own.

    This function never loads, pulls, evicts, or signals anything. It reads.

    Args:
        model: The model identifier whose load is being judged.
        requirement_bytes: The model's declared memory requirement.
        profile: Measured hardware; probed when omitted.
        residents: The runtime's resident set; read when omitted. ``None``
            together with ``residents_measured`` false means unreadable.
        residents_measured: False when the resident set could not be read.
            Distinguishes an unreadable resident set from a measured-empty one.
        settings: Settings carrying the margin and override; loaded when omitted.

    Returns:
        A :class:`ContentionSnapshot`. This module never raises on absence; the
        dispatch boundary converts a non-admitted snapshot into its typed
        refusal.
    """
    resolved = settings if settings is not None else load_settings()
    margin = resolved.cadrumo_llm_contention_safety_margin_bytes
    hardware = profile if profile is not None else probe_hardware_profile()
    if residents is None and residents_measured:
        read = read_runtime_residents(resolved)
        resident_set = read
        residents_known = read is not None
    else:
        resident_set = residents
        residents_known = residents_measured and residents is not None

    kind = hardware.accelerator.kind
    free_vram = hardware.free_vram_bytes
    free_ram = hardware.memory.free_bytes
    on_device = kind is AcceleratorKind.NVIDIA_CUDA
    binding_free = binding_free_bytes(hardware)
    required = requirement_bytes + margin

    base: _ContentionSnapshotBase = {
        "model": model,
        "requirement_bytes": requirement_bytes,
        "safety_margin_bytes": margin,
        "accelerator": kind,
        "free_vram_bytes": free_vram,
        "free_system_memory_bytes": free_ram,
        "binding_free_bytes": binding_free,
        "residents": resident_set,
    }

    if binding_free is None:
        if resolved.cadrumo_llm_contention_check_override:
            return ContentionSnapshot(
                **base,
                admitted=True,
                detail=(
                    f"free memory for {model!r} could not be measured "
                    f"(accelerator {kind.value}); admitted only because "
                    f"cadrumo_llm_contention_check_override is set"
                ),
            )
        return ContentionSnapshot(
            **base,
            admitted=False,
            causes=(ContentionCause.UNREADABLE,),
            detail=(
                f"free memory could not be measured (accelerator {kind.value}), so the "
                f"{_gib(required)} needed for {model!r} cannot be shown to be available"
            ),
            remediation=(
                "install the NVML reader (pip install cadrumo[llm]) so device headroom can be "
                "measured, or set cadrumo_llm_contention_check_override on a machine known to "
                "have capacity this build cannot read"
            ),
        )

    if binding_free >= required:
        return ContentionSnapshot(
            **base,
            shortfall_bytes=0,
            admitted=True,
            detail=(
                f"{_gib(binding_free)} free meets the {_gib(required)} needed for {model!r} "
                f"({_gib(requirement_bytes)} requirement plus a {_gib(margin)} margin)"
            ),
        )

    shortfall = required - binding_free
    if not residents_known or resident_set is None:
        return ContentionSnapshot(
            **base,
            shortfall_bytes=shortfall,
            admitted=False,
            causes=(ContentionCause.UNREADABLE,),
            detail=(
                f"{_gib(binding_free)} free is {_gib(shortfall)} short of the {_gib(required)} "
                f"needed for {model!r}, and the local runtime's resident set could not be read, "
                f"so the shortfall cannot be attributed"
            ),
            remediation=(
                "start the local model runtime so its resident set can be read, then retry; "
                "the shortfall is measured and real either way"
            ),
        )

    selected = cadrumo_selected_models(resolved)
    resident_bytes = _attributed_resident_bytes(resident_set, on_device=on_device)
    unloadable = tuple(resident.name for resident in resident_set if _matches_selected(resident.name, selected))
    unloadable_bytes = _attributed_resident_bytes(
        resident_set,
        on_device=on_device,
        names=frozenset(unloadable),
    )
    peer_bytes = max(shortfall - resident_bytes, 0)

    causes: list[ContentionCause] = []
    if resident_bytes > 0:
        causes.append(ContentionCause.RUNTIME_RESIDENT)
    if peer_bytes > 0:
        causes.append(ContentionCause.PEER_PROCESS)
    if not causes:
        # Nothing is resident and nothing is unexplained only when the shortfall
        # is zero, which the admitted branch above already returned; reaching
        # here means the shortfall is entirely outside this runtime.
        causes.append(ContentionCause.PEER_PROCESS)

    resident_names = ", ".join(resident.name for resident in resident_set) or "none"
    detail = (
        f"{_gib(binding_free)} free is {_gib(shortfall)} short of the {_gib(required)} needed for "
        f"{model!r}; the local runtime holds {_gib(resident_bytes)} across residents [{resident_names}] "
        f"and {_gib(peer_bytes)} of the shortfall is held outside it"
    )
    if peer_bytes > 0 and unloadable_bytes > 0:
        remediation = (
            f"unload the Cadrumo-selected resident model(s) {', '.join(unloadable)} to reclaim "
            f"{_gib(unloadable_bytes)}, and close the other application holding {_gib(peer_bytes)}; "
            f"Cadrumo does not touch a process it did not start"
        )
    elif peer_bytes > 0:
        remediation = (
            f"close the other application holding {_gib(peer_bytes)} of device memory, then retry; "
            f"no Cadrumo-selected model is resident, so there is nothing here for Cadrumo to unload"
        )
    elif unloadable_bytes > 0:
        remediation = (
            f"unload the Cadrumo-selected resident model(s) {', '.join(unloadable)} to reclaim "
            f"{_gib(unloadable_bytes)}, then retry"
        )
    else:
        remediation = (
            f"the local runtime holds {_gib(resident_bytes)} in models Cadrumo did not select "
            f"([{resident_names}]); ask whoever loaded them to release them -- Cadrumo unloads "
            f"only the models it selected"
        )

    return ContentionSnapshot(
        **base,
        resident_attributed_bytes=resident_bytes,
        unloadable_models=unloadable,
        shortfall_bytes=shortfall,
        admitted=False,
        causes=tuple(causes),
        detail=detail,
        remediation=remediation,
    )


class UnloadOutcome(BaseModel):
    """The result of an explicit unload of one Cadrumo-selected resident model.

    Never raises and never escalates: a model Cadrumo did not select, or one that
    is not resident, returns ``unloaded`` false with the reason. The action is
    self-scoped by construction -- it asks the local runtime to release a model
    *it* loaded on Cadrumo's behalf, and has no mechanism to affect any other
    process on the device.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str = Field(min_length=1)
    unloaded: bool
    was_resident: bool = False
    detail: str = ""
    remediation: str = ""


def unload_runtime_model(
    model: str,
    *,
    residents: tuple[RuntimeResident, ...] | None = None,
    residents_measured: bool = True,
    settings: Settings | None = None,
) -> UnloadOutcome:
    """Release one Cadrumo-selected model from the local runtime, touching nothing else.

    Two guards, in order, and both matter. The model must be one
    :func:`cadrumo_selected_models` names, so Cadrumo cannot evict a model
    another operator or application loaded into the shared runtime. It must then
    be **resident**, which is what keeps this action from becoming a load: the
    runtime's release call would otherwise bring a non-resident model in before
    releasing it, and this module must never cause a model load.

    The release is a zero-keep-alive request carrying no prompt, so the runtime
    drops the model without running inference.

    Args:
        model: The model identifier to release.
        residents: The resident set; read via :func:`read_runtime_residents`
            when omitted.
        residents_measured: False when the resident set could not be read.
        settings: Settings carrying the runtime endpoint; loaded when omitted.

    Returns:
        An :class:`UnloadOutcome` describing what happened and, on refusal, why.
    """
    resolved = settings if settings is not None else load_settings()
    if not _matches_selected(model, cadrumo_selected_models(resolved)):
        return UnloadOutcome(
            model=model,
            unloaded=False,
            detail=f"{model!r} is not a model Cadrumo selected, so Cadrumo will not unload it",
            remediation=(
                "Cadrumo releases only the models it loaded; ask the owner of the other model to "
                "release it, or point cadrumo_llm_ollama_vision_model / _text_model at it"
            ),
        )
    if residents is None and residents_measured:
        resident_set = read_runtime_residents(resolved)
    else:
        resident_set = residents if residents_measured else None
    if resident_set is None:
        return UnloadOutcome(
            model=model,
            unloaded=False,
            detail="the local runtime's resident set could not be read, so nothing was released",
            remediation="start the local model runtime, then retry",
        )
    if not any(_matches_selected(resident.name, frozenset({model})) for resident in resident_set):
        return UnloadOutcome(
            model=model,
            unloaded=False,
            was_resident=False,
            detail=f"{model!r} is not resident in the local runtime; nothing to release",
        )
    url = _ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "generate")
    try:
        with httpx.Client(timeout=_OLLAMA_PROBE_TIMEOUT_S) as client:
            response = client.post(url, json={"model": model, "keep_alive": 0})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return UnloadOutcome(
            model=model,
            unloaded=False,
            was_resident=True,
            detail=f"the local runtime refused the release request for {model!r} ({exc.__class__.__name__})",
            remediation="check that the local model runtime is reachable at cadrumo_llm_ollama_chat_url",
        )
    return UnloadOutcome(
        model=model,
        unloaded=True,
        was_resident=True,
        detail=f"released {model!r} from the local runtime",
    )


class PullProgress(BaseModel):
    """One progress report from an in-flight model fetch.

    ``total_bytes`` is absent early in a pull, before the runtime has resolved
    the manifest, so a renderer must tolerate a percentless report rather than
    computing a ratio against zero.
    """

    model_config = STRICT_FROZEN_CONFIG

    status: str = ""
    completed_bytes: int | None = Field(default=None, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)

    @property
    def percent(self) -> int | None:
        """Return whole-percent progress, or ``None`` when the total is not yet known."""
        if not self.total_bytes or self.completed_bytes is None:
            return None
        return min(100, int(self.completed_bytes * 100 / self.total_bytes))


class PullOutcome(BaseModel):
    """The result of an explicit model fetch, including a fetch that never started.

    ``contention`` is populated when the pre-fetch admission check refused, and
    is the reason no bytes moved. Keeping the snapshot rather than flattening it
    to a string is what lets the caller name WHICH cause applied -- unloading a
    resident Cadrumo selected and closing a peer application are different
    instructions and only one of them is ours to offer.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str = Field(min_length=1)
    pulled: bool
    contention: ContentionSnapshot | None = None
    bytes_fetched: int | None = Field(default=None, ge=0)
    detail: str = ""
    remediation: str = ""


def pull_runtime_model(
    model: str,
    requirement_bytes: int,
    *,
    profile: HardwareProfile | None = None,
    settings: Settings | None = None,
    on_progress: Callable[[PullProgress], None] | None = None,
) -> PullOutcome:
    """Fetch ``model`` into the local runtime, refusing BEFORE any bytes move.

    The admission check runs first and a refusal returns without contacting the
    runtime at all. That ordering is the point of the action: a multi-gigabyte
    download that completes and then cannot be loaded has spent the operator's
    bandwidth to arrive at the refusal it could have been given immediately.

    Never raises, in keeping with every other action here. An unreachable
    runtime is a typed outcome naming ``ollama serve`` -- this function does not
    start a daemon, and nothing on this path pulls implicitly: reaching it at
    all requires an operator to have asked.

    Args:
        model: Runtime identifier to fetch.
        requirement_bytes: The model's declared memory requirement, checked
            against measured headroom before fetching.
        profile: A measured hardware profile; probed when omitted.
        settings: Resolved settings; loaded when omitted.
        on_progress: Called for each progress report the runtime emits. Failures
            in the callback are the caller's to handle; nothing here swallows
            them.

    Returns:
        A :class:`PullOutcome`. ``pulled`` false with ``contention`` populated
        means the fetch was refused before it began.
    """
    resolved = settings if settings is not None else load_settings()
    snapshot = assess_model_load_contention(model, requirement_bytes, profile=profile, settings=resolved)
    if not snapshot.admitted:
        return PullOutcome(
            model=model,
            pulled=False,
            contention=snapshot,
            detail=snapshot.detail,
            remediation=snapshot.remediation,
        )

    url = _ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "pull")
    fetched: int | None = None
    try:
        with (
            httpx.Client(timeout=_OLLAMA_PULL_TIMEOUT_S) as client,
            client.stream("POST", url, json={"model": model, "stream": True}) as response,
        ):
            response.raise_for_status()
            for line in response.iter_lines():
                progress = _pull_progress(line)
                if progress is None:
                    continue
                if progress.completed_bytes is not None:
                    fetched = progress.completed_bytes
                if on_progress is not None:
                    on_progress(progress)
    except httpx.HTTPError as exc:
        return PullOutcome(
            model=model,
            pulled=False,
            bytes_fetched=fetched,
            detail=f"the local model runtime could not be reached to fetch {model!r} ({exc.__class__.__name__})",
            remediation="start the local model runtime with 'ollama serve', then retry",
        )
    return PullOutcome(
        model=model,
        pulled=True,
        bytes_fetched=fetched,
        detail=f"{model!r} is present in the local runtime",
    )


def _pull_progress(line: str) -> PullProgress | None:
    """Parse one NDJSON progress line, or ``None`` when it carries no report."""
    text = line.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    # CAST-RATIONALE-OLLAMA-PULL-PAYLOAD: json.loads returns Any; isinstance
    # narrows to dict but not its type parameters.
    # nosemgrep: no-cast-in-domain-application
    row = cast(dict[str, object], payload)
    completed = row.get("completed")
    total = row.get("total")
    status = row.get("status")
    return PullProgress(
        status=status if isinstance(status, str) else "",
        completed_bytes=completed if isinstance(completed, int) and completed >= 0 else None,
        total_bytes=total if isinstance(total, int) and total >= 0 else None,
    )


class ReadinessOutcome(BaseModel):
    """Whether a model is loaded and actually answering, not merely present.

    ``resident`` and ``answered`` are separate claims on purpose. A model can be
    present on disk and not loaded, or loaded and too slow to be useful, and an
    operator debugging a stalled read needs to know which of the two they have.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str = Field(min_length=1)
    ready: bool
    resident: bool = False
    answered: bool = False
    elapsed_ms: int | None = Field(default=None, ge=0)
    detail: str = ""
    remediation: str = ""


def verify_model_ready(
    model: str,
    *,
    settings: Settings | None = None,
    timeout_s: float | None = None,
) -> ReadinessOutcome:
    """Confirm ``model`` is resident and answers a trivial prompt within a bound.

    The prompt is deliberately minimal and its CONTENT is irrelevant -- this
    verifies the transport and the load, not the model's quality, so nothing
    here inspects what came back beyond the fact that something did.

    Never raises. An unreachable runtime names ``ollama serve``; a model that is
    absent names the provision verb rather than pulling it, because an implicit
    multi-gigabyte fetch triggered by a verification command is exactly what the
    lifecycle design forbids.
    """
    resolved = settings if settings is not None else load_settings()
    bound = timeout_s if timeout_s is not None else _OLLAMA_READINESS_TIMEOUT_S
    residents = read_runtime_residents(resolved)
    if residents is None:
        return ReadinessOutcome(
            model=model,
            ready=False,
            detail="the local model runtime could not be reached",
            remediation="start the local model runtime with 'ollama serve', then retry",
        )
    resident = any(_matches_selected(entry.name, frozenset({model})) for entry in residents)

    url = _ollama_endpoint(resolved.cadrumo_llm_ollama_chat_url, "generate")
    started = time.monotonic()
    try:
        with httpx.Client(timeout=bound) as client:
            response = client.post(url, json={"model": model, "prompt": "ok", "stream": False})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return ReadinessOutcome(
            model=model,
            ready=False,
            resident=resident,
            elapsed_ms=elapsed,
            detail=f"{model!r} did not answer within {bound:g}s ({exc.__class__.__name__})",
            remediation=f"aeat config provision pull --model {model}",
        )
    elapsed = int((time.monotonic() - started) * 1000)
    return ReadinessOutcome(
        model=model,
        ready=True,
        resident=resident,
        answered=True,
        elapsed_ms=elapsed,
        detail=f"{model!r} answered in {elapsed} ms",
    )


def probe_optional_extras() -> tuple[DependencyStatus, ...]:
    """Probe every capability-gated :class:`~cadrumo.core.OptionalExtra` into :class:`DependencyStatus` rows.

    The result set is keyed by the same :data:`~cadrumo.core.OPTIONAL_EXTRAS`
    catalogue used by :func:`~cadrumo.core.require_optional_extra`, keeping
    ``aeat config check`` and runtime feature guards aligned.
    """
    return tuple(probe_optional_extra(extra) for extra in OPTIONAL_EXTRAS)
