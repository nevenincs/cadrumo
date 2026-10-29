"""The closed value set describing the local accelerator a measurement found.

Declared in ``core/`` -- the innermost hexagonal ring -- so the probe that
measures the machine and the operator-facing diagnostic rows route on one
identifier set rather than on bare strings.

The members are consumed by
:class:`~application.workstation_probes.AcceleratorReading` and
:class:`~application.workstation_probes.HardwareProfile`. They sit beside, not
inside, :class:`~core.capabilities.ServiceCapability`: a capability records whether the
operator *permits* local inference, whereas these values record what the machine
*is*.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["AcceleratorKind"]


class AcceleratorKind(StrEnum):
    """What kind of inference accelerator this machine was measured to have.

    The distinction that matters is ``NONE`` versus ``UNKNOWN``, and it is a
    distinction between two *measurements*, not a presence flag with a fallback.
    ``NONE`` is a positive reading -- the device library initialised and
    enumerated zero devices -- so a model's capacity floor may legitimately be
    judged against system memory alone. ``UNKNOWN`` is the absence of a
    reading, which never invents a shortfall.

    The members distinguish three measured states:

    - ``NONE`` — the accelerator library initialised and reported zero devices.
    - ``NVIDIA_CUDA`` — one or more NVML-visible NVIDIA devices were enumerated.
    - ``UNKNOWN`` — no reading was obtainable: NVML was absent or
      uninitialisable, or the build cannot measure the non-NVIDIA accelerator.
    """

    NONE = "none"
    NVIDIA_CUDA = "nvidia_cuda"
    UNKNOWN = "unknown"
