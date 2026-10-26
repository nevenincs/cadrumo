"""Typed dependency probes for local services and optional packages.

The doctor probes in this module are read-only: each asks whether one external
service or optional package extra is usable on this workstation and returns a
typed :class:`DependencyStatus`. :mod:`cadrumo.application.cli_provisioning`
owns CLI authority admission and command storage materialization.

The local AI program's row is judged by
:func:`~cadrumo.application.local_reader.probe_local_ai_program` from the
components role's status row, so a missing program becomes an instructive
refusal instead of a raw stack trace.
The ``aeat config check`` command renders this module's
statuses as
:class:`~cadrumo.entrypoints.cli.config.check_payloads.CheckDependencyPayload`
rows beside the active profile's capability posture from
:func:`~cadrumo.application.user_profile.capabilities.resolve_active_capability`. Optional-extra
probes walk the core :data:`~cadrumo.core.optional_extras.OPTIONAL_EXTRAS` catalogue of
:class:`~cadrumo.core.optional_extras.OptionalExtra` records, so CLI diagnostics and adapter import
guards share one registry.
"""

from __future__ import annotations

import contextlib
import os
import sys

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hardware import AcceleratorKind
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.optional_extras import OPTIONAL_EXTRAS, OptionalExtra, optional_extra_available
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningOutcome,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    require_provisioning_verdict,
)

__all__ = [
    "AcceleratorDevice",
    "AcceleratorReading",
    "DependencyStatus",
    "HardwareProfile",
    "SystemMemoryReading",
    "below_capacity_floor",
    "probe_hardware_profile",
    "probe_local_inference_hardware",
    "probe_model_runtime_hardware_floor",
    "probe_optional_extra",
    "probe_optional_extras",
    "read_accelerator",
    "read_system_memory",
]


class DependencyStatus(ProvisioningOutcome):
    """Availability result for one external dependency.

    ``service`` is the stable row id shown by the configuration check. ``facts``
    records the measured state and ``precondition_verdict`` closes every unavailable
    outcome without embedding presentation or executable text. The model is intentionally
    generic so Ollama, subprocess CLIs, Playwright browser binaries, and
    :class:`~cadrumo.core.optional_extras.OptionalExtra` package extras all render through the same
    payload shape and can be validated into
    :class:`~cadrumo.entrypoints.cli.config.check_payloads.CheckDependencyPayload`.
    """

    service: str = Field(min_length=1)
    available: bool

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_availability_outcome(self) -> DependencyStatus:
        require_provisioning_verdict(failed=not self.available, verdict=self.precondition_verdict)
        return self


class SystemMemoryReading(BaseModel):
    """Measured total and free physical system memory, either of which may be unreadable.

    Both figures are carried because they answer different questions:
    ``total_bytes`` is what this computer can hold at all, the figure the
    capacity floor judges, and ``free_bytes`` is what was free when a
    diagnostic row measured it.

    ``None`` means "not measured", never "zero". See
    :class:`~core.hardware.AcceleratorKind` for the same distinction on the device side.
    """

    model_config = STRICT_FROZEN_CONFIG

    total_bytes: int | None = Field(default=None, ge=0)
    free_bytes: int | None = Field(default=None, ge=0)


def _windows_memory_status() -> tuple[int, int] | None:
    """Return ``(total, available)`` physical bytes from ``GlobalMemoryStatusEx``, or ``None``.

    Returns ``None`` off Windows. The ``sys.platform == "win32"`` block, rather
    than an early return off Windows, is what establishes the platform inside
    THIS function's body: a guard at the call site is invisible to a checker,
    and the positive block is the only guard shape every checker this project
    runs narrows on, so ``ctypes.windll`` -- which exists only in the Windows
    typeshed stubs -- resolves when the tree is analysed for Linux or macOS.
    The runtime behaviour is unchanged; the caller already treats ``None`` as
    "not measured".
    """
    if sys.platform == "win32":  # pragma: no cover - the CI runner is Linux
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
    :func:`probe_model_runtime_hardware_floor`.
    """
    if sys.platform == "win32":
        # The positive block, rather than an early return off Windows, is what
        # establishes the platform for each direction of this branch: it is the
        # only guard shape every checker this project runs narrows on, so the
        # Windows reader above and the POSIX `os.sysconf` calls below each
        # resolve on the platform that ships them.
        measured = _windows_memory_status()
        if measured is None:
            return SystemMemoryReading()
        return SystemMemoryReading(total_bytes=measured[0], free_bytes=measured[1])
    else:
        # An explicit `else`, not a fallthrough: the positive block narrows the
        # Windows arm in every checker, but only the written `else` narrows the
        # POSIX arm, so `os.sysconf` -- absent from the Windows stubs entirely
        # -- resolves when the tree is analysed for Windows.
        #
        # The getattr and the inner membership checks stay for POSIX variants
        # that omit the constants themselves; SC_AVPHYS_PAGES is the more
        # commonly absent of the three, so a total may be readable where a free
        # figure is not.
        names = getattr(os, "sysconf_names", {})
        if "SC_PAGE_SIZE" in names and "SC_PHYS_PAGES" in names:
            try:
                page_size = os.sysconf("SC_PAGE_SIZE")
                total = page_size * os.sysconf("SC_PHYS_PAGES")
            except (OSError, ValueError):
                return SystemMemoryReading()
            free: int | None = None
            if "SC_AVPHYS_PAGES" in names:
                try:
                    free = page_size * os.sysconf("SC_AVPHYS_PAGES")
                except (OSError, ValueError):
                    free = None
            return SystemMemoryReading(total_bytes=total, free_bytes=free)
        return SystemMemoryReading()


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
    (:class:`~cadrumo.core.optional_extras.OptionalExtra`) from *permitted*
    (:class:`~cadrumo.core.capabilities.ServiceCapability`); this answers *capable* -- and is
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
            facts={"total_memory_bytes": observed, "memory_floor_bytes": floor},
            precondition_verdict=provisioning_no_recovery_verdict(
                ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET,
                facts={"total_memory_bytes": observed, "memory_floor_bytes": floor},
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
    :class:`~cadrumo.core.optional_extras.OptionalExtra` (no import, no side effects) in the doctor's
    :class:`DependencyStatus`, retaining only the extra's machine identity when
    absent. The feature-boundary guard is the sibling core
    :func:`~cadrumo.core.optional_extras.require_optional_extra`, which raises the typed
    :class:`~cadrumo.core.optional_extras.MissingOptionalExtraError` when a command actually
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
    cards with 3 GiB each cannot hold a 4 GiB model. The aggregation rules that
    follow from that live on :class:`HardwareProfile`.
    """

    model_config = STRICT_FROZEN_CONFIG

    index: NonNegativeInt
    name: str = Field(min_length=1)
    total_vram_bytes: int | None = Field(default=None, ge=0)
    free_vram_bytes: int | None = Field(default=None, ge=0)


class AcceleratorReading(BaseModel):
    """What the accelerator measurement found: a kind, and the devices behind it.

    ``kind`` is :class:`~core.hardware.AcceleratorKind`; an empty ``devices`` tuple is
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
    axis. Totals say what this computer can hold at all, which the capacity
    floor judges; free amounts are reported as they were at the measurement.
    Whether a model fits the memory free when it loads is the agent's answer at
    the load, never this profile's.

    Every figure is independently optional. ``None`` means the measurement was
    not obtainable, and a diagnostic row reports it as **unverified** and stays
    available. See :func:`probe_hardware_profile`.
    """

    model_config = STRICT_FROZEN_CONFIG

    memory: SystemMemoryReading
    accelerator: AcceleratorReading

    @property
    def total_vram_bytes(self) -> int | None:
        """Return summed device VRAM for REPORTING, or ``None`` when any device is unreadable.

        Summed because the reporting question is "what is installed in this
        machine", which is additive.
        """
        devices = self.accelerator.devices
        if not devices or any(device.total_vram_bytes is None for device in devices):
            return None
        return sum(device.total_vram_bytes or 0 for device in devices)

    @property
    def free_vram_bytes(self) -> int | None:
        """Return the largest single-device free VRAM, or ``None`` when unreadable.

        The maximum, never the sum: a model is resident on one device, and
        summing would report capacity no allocation can reach. Devices whose
        free figure is unreadable are skipped rather than counted as zero.

        ``None`` when no device reported a free figure at all.
        """
        readable = [device.free_vram_bytes for device in self.accelerator.devices if device.free_vram_bytes is not None]
        if not readable:
            return None
        return max(readable)


def read_accelerator() -> AcceleratorReading:
    """Measure the local accelerator through NVML, never raising and never loading a model.

    NVML (the ``nvidia-ml-py`` binding declared in the ``llm`` extra) is
    preferred over a ``nvidia-smi`` shell-out because it yields **per-device**
    total and free figures from an in-process query with no subprocess.

    Returns :attr:`~core.hardware.AcceleratorKind.UNKNOWN` when NVML is absent or
    uninitialisable, and :attr:`~core.hardware.AcceleratorKind.NONE` only on the positive
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
            count = pynvml.nvmlDeviceGetCount()
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
                name = raw_name.decode("utf-8", "replace") if isinstance(raw_name, bytes) else raw_name
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total = info.total
                free = info.free
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
    internals, so every branch of the profile is exercised against real model
    construction with real readings -- a test must never depend on this host's
    actual device state, which changes minute to minute while an automation fleet
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


def below_capacity_floor(profile: HardwareProfile, requirement_bytes: int) -> bool:
    """Return whether this computer cannot hold a model needing ``requirement_bytes`` at all.

    A capacity judgement, never a momentary one: the installed system memory
    and the largest NVIDIA card's installed memory are compared against the
    model's floor, the same rule the native component engine applies to a
    role's quick status. Free memory is not consulted, because a model already
    resident, or another program's load, lowers it for a while without changing
    what the computer can hold; whether a load fits the memory free is the
    agent's answer at the load. A computer whose total memory was not measured is
    never held back, and neither is one whose accelerator could not be read,
    because an unread value must not invent a shortfall.
    """
    total = profile.memory.total_bytes
    if total is None or total >= requirement_bytes:
        return False
    kind = profile.accelerator.kind
    if kind is AcceleratorKind.NONE:
        return True
    if kind is not AcceleratorKind.NVIDIA_CUDA:
        return False
    cards = [device.total_vram_bytes for device in profile.accelerator.devices if device.total_vram_bytes is not None]
    return bool(cards) and max(cards) < requirement_bytes


def probe_local_inference_hardware(profile: HardwareProfile | None = None) -> DependencyStatus:
    """Report the measured hardware profile as a diagnostic row, unknown shown as unverified.

    Follows the shipped direction of :func:`probe_model_runtime_hardware_floor`:
    an unreadable figure keeps ``available`` **true** and is rendered as
    ``unverified``, because a *diagnostic* must not manufacture a shortfall on a
    platform it merely cannot measure.

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


def probe_optional_extras() -> tuple[DependencyStatus, ...]:
    """Probe each :class:`~cadrumo.core.optional_extras.OptionalExtra` into :class:`DependencyStatus` rows.

    The result set is keyed by the same :data:`~cadrumo.core.optional_extras.OPTIONAL_EXTRAS`
    catalogue used by :func:`~cadrumo.core.optional_extras.require_optional_extra`, keeping
    ``aeat config check`` and runtime feature guards aligned.
    """
    return tuple(probe_optional_extra(extra) for extra in OPTIONAL_EXTRAS)
