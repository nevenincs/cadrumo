"""Admit a KDF point measured earlier as the strengthening of a committed password envelope.

A measured point is a cost on the custody grid without a salt. It may replace
an envelope's point only when it lies on the grid, meets the fallback floor,
costs strictly more than the committed point without using less memory, and
still fits this host. Anything else is refused and nothing is weakened.
"""

from __future__ import annotations

from .....core.errors.hierarchy import CadrumoError
from .kdf_supervision import (
    profile_kdf_grid,
    profile_kdf_is_eligible,
    profile_kdf_meets_fallback_floor,
    profile_kdf_resources,
)
from .records import ProfileCustodyKdfParameters


class ProfileKdfPointRefusedError(CadrumoError):
    """Signal that a supplied KDF point would not strengthen the envelope it replaces."""


def profile_kdf_strictly_stronger(
    candidate: ProfileCustodyKdfParameters, committed: ProfileCustodyKdfParameters
) -> bool:
    """Return whether ``candidate`` costs strictly more than ``committed`` without using less memory.

    Cost is memory times passes, the same measure the fallback floor uses;
    lanes only spread that work and never count as strength.
    """
    return (
        candidate.memory_mib >= committed.memory_mib
        and candidate.memory_mib * candidate.iterations > committed.memory_mib * committed.iterations
    )


def profile_kdf_strengthening_point(
    *,
    memory_mib: int,
    iterations: int,
    parallelism: int,
    salt: bytes,
    committed: ProfileCustodyKdfParameters,
) -> ProfileCustodyKdfParameters:
    """Return the grid point for a measured strength under ``salt``, refusing any that would not strengthen.

    Raises:
        ProfileKdfPointRefusedError: The point is off the grid, below the
            fallback floor, not strictly stronger than ``committed``, or no
            longer fits this host. A strengthening is optional, so a host
            that cannot run the measured point keeps the committed envelope
            and writes nothing.
    """
    wanted = (memory_mib, iterations, parallelism)
    point = next(
        (
            parameters
            for parameters in profile_kdf_grid(salt=salt)
            if (parameters.memory_mib, parameters.iterations, parameters.parallelism) == wanted
        ),
        None,
    )
    if point is None:
        raise ProfileKdfPointRefusedError("the supplied KDF point is not on the custody grid")
    if not profile_kdf_meets_fallback_floor(point) or not profile_kdf_strictly_stronger(point, committed):
        raise ProfileKdfPointRefusedError("the supplied KDF point does not strengthen the committed envelope")
    if not profile_kdf_is_eligible(point, resources=profile_kdf_resources()):
        raise ProfileKdfPointRefusedError("the supplied KDF point does not fit this host")
    return point


__all__ = [
    "ProfileKdfPointRefusedError",
    "profile_kdf_strengthening_point",
    "profile_kdf_strictly_stronger",
]
