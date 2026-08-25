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

__all__ = [
    "HARDWARE_TIER_CAPABLE_FLOOR_BYTES",
    "HARDWARE_TIER_MODEST_FLOOR_BYTES",
    "AcceleratorKind",
    "ContentionCause",
    "HardwareTier",
    "hardware_tier_for_free_bytes",
]


class AcceleratorKind(StrEnum):
    """What kind of inference accelerator this machine was measured to have.

    The distinction that matters is ``NONE`` versus ``UNKNOWN``, and it is a
    distinction between two *measurements*, not a presence flag with a fallback.
    ``NONE`` is a positive reading -- the device library initialised and
    enumerated zero devices -- so a load may legitimately be judged against free
    system memory alone. ``UNKNOWN`` is the absence of a reading, and per the
    provisioning decision it fails **closed** at the act: "could not tell" is
    precisely the state that must not be read as headroom.

    The members distinguish three measured states:

    - ``NONE`` — the accelerator library initialised and reported zero devices.
    - ``NVIDIA_CUDA`` — one or more NVML-visible NVIDIA devices were enumerated.
    - ``UNKNOWN`` — no reading was obtainable: NVML was absent or
      uninitialisable, or the build cannot measure the non-NVIDIA accelerator.
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


class HardwareTier(StrEnum):
    """The measured headroom band this machine falls in, for reporting a selection.

    A band, never the decision. Model selection and the contention check both
    compare **measured bytes** against a candidate's declared requirement plus
    the configured margin; collapsing that comparison to a tier would round a
    real shortfall away. The tier exists so an operator-facing selection row can
    say *why* a machine got the model it got without reprinting byte counts, and
    so a selection test can assert the band it covers.

    ``UNMEASURED`` is the same distinction :class:`AcceleratorKind` draws
    between ``NONE`` and ``UNKNOWN``: an unreadable free figure is the absence
    of a measurement, never a measured zero.

    Members:

        UNMEASURED: Free memory in the binding arena could not be read.
        CONSTRAINED: Below :data:`HARDWARE_TIER_MODEST_FLOOR_BYTES` free.
        MODEST: At the modest floor, below :data:`HARDWARE_TIER_CAPABLE_FLOOR_BYTES`.
        CAPABLE: At or above the capable floor.
    """

    UNMEASURED = "unmeasured"
    CONSTRAINED = "constrained"
    MODEST = "modest"
    CAPABLE = "capable"


HARDWARE_TIER_MODEST_FLOOR_BYTES = 4 * 1024**3
"""Free bytes at which a machine stops being :attr:`HardwareTier.CONSTRAINED`.

Sized against the catalogue rather than chosen roundly: the smallest
vision-capable candidate that clears the default context window declares a
requirement just under 2 GB, and the shipped safety margin adds 1 GiB, so a
machine with less than 4 GiB free cannot host it with the headroom the
contention check demands.
"""

HARDWARE_TIER_CAPABLE_FLOOR_BYTES = 8 * 1024**3
"""Free bytes at which a machine is reported :attr:`HardwareTier.CAPABLE`.

Matches the shipped ``cadrumo_llm_model_runtime_memory_floor_bytes`` total-memory
floor, so the reporting band and the provisioning floor agree about what a
comfortably-provisioned machine looks like.
"""


def hardware_tier_for_free_bytes(free_bytes: int | None) -> HardwareTier:
    """Classify measured free bytes in the binding arena into a :class:`HardwareTier`.

    Args:
        free_bytes: Free bytes measured in whichever arena binds the load
            (device memory on a readable accelerator, system memory on a
            measured-absent one), or ``None`` when unreadable.

    Returns:
        The band, with ``None`` mapping to :attr:`HardwareTier.UNMEASURED`
        rather than to the lowest band -- unknown is not a small machine.
    """
    if free_bytes is None:
        return HardwareTier.UNMEASURED
    if free_bytes < HARDWARE_TIER_MODEST_FLOOR_BYTES:
        return HardwareTier.CONSTRAINED
    if free_bytes < HARDWARE_TIER_CAPABLE_FLOOR_BYTES:
        return HardwareTier.MODEST
    return HardwareTier.CAPABLE
