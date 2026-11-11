"""A measured Argon2id cost point held by a profile worker to strengthen a fallback password envelope."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProfileKdfStrength:
    """A measured Argon2id cost point, without a salt, held to strengthen an envelope later.

    It carries no secret and names no profile: it is what this host measured,
    and the mint that uses it checks it again against the grid, the host's
    resources, the fallback floor and the envelope it would supersede.
    """

    memory_mib: int
    iterations: int
    parallelism: int


__all__ = ["ProfileKdfStrength"]
