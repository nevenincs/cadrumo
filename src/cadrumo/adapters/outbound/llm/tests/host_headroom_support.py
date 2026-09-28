"""A stated hardware measurement for suites that dispatch to a loopback reader.

A loopback reader is an ON-HOST runtime, so the client admits every dispatch to
it against measured free memory before the request leaves the process. Left to
probe, that verdict is whatever this machine's devices hold at that moment, and
a machine whose accelerator this build cannot read refuses -- correctly for
production -- before the code under test is reached. Suites that build their
own client hand it this measurement instead: the measurement is injected, never
the verdict, so the real comparison, margin and fail-closed arm still run.
"""

from __future__ import annotations

from typing import Final

from .....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from .....core.hardware import AcceleratorKind

__all__ = ["loopback_host_headroom"]

_GIB: Final[int] = 1024**3


def loopback_host_headroom() -> HardwareProfile:
    """Return a readable measurement with room for every catalogued on-host model load.

    The single device's free figure clears the largest catalogued local
    requirement plus the default safety margin, so no shipped role model is
    refused against it.

    Returns:
        A profile with readable system memory and one measured NVIDIA device.
    """
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=64 * _GIB, free_bytes=48 * _GIB),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(AcceleratorDevice(index=0, name="card-0", total_vram_bytes=24 * _GIB, free_vram_bytes=12 * _GIB),),
        ),
    )
