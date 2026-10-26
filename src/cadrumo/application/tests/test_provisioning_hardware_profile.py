"""Real-behavior tests for the hardware profile and its diagnostic row.

Hardware figures arrive as injected
:class:`~application.provisioning.SystemMemoryReading` /
:class:`~application.provisioning.AcceleratorReading` **measurements** through
the probe's own arguments, so every branch runs the production model
construction -- nothing about this host's actual GPU state can reach the
assertions. Whether a model fits the memory free is the agent's answer when it
loads the model, so nothing here judges a load.
"""

from __future__ import annotations

import pytest

from ...core.hardware import AcceleratorKind
from ..provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
    probe_local_inference_hardware,
    read_system_memory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

GIB = 1024**3


# ---------------------------------------------------------------------------
# Injected-measurement helpers
# ---------------------------------------------------------------------------


def _profile(
    *,
    kind: AcceleratorKind,
    devices: tuple[AcceleratorDevice, ...] = (),
    total_ram: int | None = 32 * GIB,
    free_ram: int | None = 16 * GIB,
) -> HardwareProfile:
    """Compose a profile from injected measurements, never from this host."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=total_ram, free_bytes=free_ram),
        accelerator=AcceleratorReading(kind=kind, devices=devices),
    )


def _device(index: int, *, total: int | None, free: int | None) -> AcceleratorDevice:
    return AcceleratorDevice(index=index, name=f"card-{index}", total_vram_bytes=total, free_vram_bytes=free)


# ---------------------------------------------------------------------------
# the hardware profile
# ---------------------------------------------------------------------------


def test_live_system_memory_reading_returns_a_typed_pair() -> None:
    """The live platform reader answers a typed reading with non-negative or absent figures."""
    reading = read_system_memory()
    assert isinstance(reading, SystemMemoryReading)
    for value in (reading.total_bytes, reading.free_bytes):
        assert value is None or value >= 0
    if reading.total_bytes is not None and reading.free_bytes is not None:
        assert reading.free_bytes <= reading.total_bytes


def test_total_vram_sums_devices_but_free_vram_takes_the_largest_single_device() -> None:
    """Totals aggregate for reporting; free VRAM never sums, because a model loads onto one device."""
    profile = _profile(
        kind=AcceleratorKind.NVIDIA_CUDA,
        devices=(_device(0, total=8 * GIB, free=3 * GIB), _device(1, total=8 * GIB, free=2 * GIB)),
    )
    assert profile.total_vram_bytes == 16 * GIB
    # The defect this asserts against: 3 + 2 = 5 GiB is capacity no allocation
    # can reach, and admitting a 4 GiB model on it is the overflow.
    assert profile.free_vram_bytes == 3 * GIB


def test_total_vram_is_unreadable_when_any_device_total_is_unreadable() -> None:
    """A partially readable device set yields no total, rather than a silently short one."""
    profile = _profile(
        kind=AcceleratorKind.NVIDIA_CUDA,
        devices=(_device(0, total=8 * GIB, free=3 * GIB), _device(1, total=None, free=None)),
    )
    assert profile.total_vram_bytes is None
    # The readable device still bounds what can be acted on.
    assert profile.free_vram_bytes == 3 * GIB


def test_free_vram_is_none_when_no_device_reports_a_free_figure() -> None:
    """An enumerated but unreadable device set reports unknown, never zero and never plenty."""
    profile = _profile(kind=AcceleratorKind.NVIDIA_CUDA, devices=(_device(0, total=None, free=None),))
    assert profile.free_vram_bytes is None


def test_absent_accelerator_reports_no_vram_on_either_axis() -> None:
    """A measured-zero-device machine carries no VRAM figures at all."""
    profile = _profile(kind=AcceleratorKind.NONE)
    assert profile.total_vram_bytes is None
    assert profile.free_vram_bytes is None


@pytest.mark.parametrize(
    "kind",
    [AcceleratorKind.NONE, AcceleratorKind.NVIDIA_CUDA, AcceleratorKind.UNKNOWN],
)
def test_diagnostic_row_stays_available_on_every_accelerator_kind(kind: AcceleratorKind) -> None:
    """Reporting fails OPEN: no accelerator kind turns the diagnostic row into a shortfall."""
    status = probe_local_inference_hardware(_profile(kind=kind))
    assert status.service == "local-inference-hardware"
    assert status.available is True


def test_diagnostic_row_renders_unreadable_figures_as_unverified() -> None:
    """Unknown is shown as unverified on the row, never as a number and never as a refusal."""
    status = probe_local_inference_hardware(
        _profile(kind=AcceleratorKind.UNKNOWN, total_ram=None, free_ram=None),
    )
    assert status.available is True
    assert status.facts["accelerator_kind"] == "unknown"
    assert status.precondition_verdict is None


def test_diagnostic_row_renders_measured_figures_as_numbers() -> None:
    """Positive control for the row: a fully measured machine shows figures, not unverified."""
    status = probe_local_inference_hardware(
        _profile(kind=AcceleratorKind.NVIDIA_CUDA, devices=(_device(0, total=16 * GIB, free=4 * GIB),)),
    )
    assert status.facts["accelerator_kind"] == "nvidia_cuda"
    assert status.facts["total_vram_bytes"] == 16 * GIB
    assert status.facts["free_vram_bytes"] == 4 * GIB
    assert status.precondition_verdict is None
