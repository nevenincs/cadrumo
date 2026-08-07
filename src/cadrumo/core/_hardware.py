"""Closed value sets describing local accelerator hardware and load contention.

Declared in ``core/`` -- the innermost hexagonal ring -- so the probe that
measures the machine, the snapshot that judges whether a model load is safe, and
the operator-facing diagnostic rows all route on one identifier set rather than
on bare strings.

The members are consumed by
:class:`~application.provisioning.AcceleratorReading`,
:class:`~application.provisioning.HardwareProfile` and
:class:`~application.provisioning.ContentionSnapshot`. They sit beside, not
inside, :class:`~core.ServiceCapability`: a capability records whether the
operator *permits* local inference, whereas these values record what the machine
*is* and what is holding its memory right now.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["AcceleratorKind", "ContentionCause"]


class AcceleratorKind(StrEnum):
    """What kind of inference accelerator this machine was measured to have.

    The distinction that matters is ``NONE`` versus ``UNKNOWN``, and it is a
    distinction between two *measurements*, not a presence flag with a fallback.
    ``NONE`` is a positive reading -- the device library initialised and
    enumerated zero devices -- so a load may legitimately be judged against free
    system memory alone. ``UNKNOWN`` is the absence of a reading, and per the
    provisioning decision it fails **closed** at the act: "could not tell" is
    precisely the state that must not be read as headroom.

    Members:
        NONE: The accelerator library initialised and reported zero devices.
        NVIDIA_CUDA: One or more NVML-visible NVIDIA devices were enumerated.
        UNKNOWN: No reading was obtainable -- NVML absent, uninitialisable, or a
            non-NVIDIA accelerator this build cannot measure.
    """

    NONE = "none"
    NVIDIA_CUDA = "nvidia_cuda"
    UNKNOWN = "unknown"


class ContentionCause(StrEnum):
    """Why a model load was refused, keyed to the remediation the operator can act on.

    The split exists because the remediations are not interchangeable and one of
    them is not ours to perform. Memory held by the local runtime's own resident
    models is reclaimable by Cadrumo through an explicit unload of a
    Cadrumo-selected model; memory held by another process is reported and
    refused, never "managed" -- Cadrumo never evicts, signals, or otherwise
    touches a process it does not own. Telling an operator to unload a model
    when the pressure is a peer application's is a false instruction, which is
    why the cause travels on the snapshot rather than being inferred from the
    shortfall alone.

    Members:
        RUNTIME_RESIDENT: The local model runtime's resident models account for
            the shortfall; the explicit unload action applies.
        PEER_PROCESS: Device memory is held by processes outside the local model
            runtime; the operator must close the other application. Cadrumo
            takes no action against it.
        UNREADABLE: A figure the decision needs -- free headroom, or the resident
            set the shortfall must be attributed to -- could not be measured.
            Refuses the load rather than permitting it.
    """

    RUNTIME_RESIDENT = "runtime_resident"
    PEER_PROCESS = "peer_process"
    UNREADABLE = "unreadable"
