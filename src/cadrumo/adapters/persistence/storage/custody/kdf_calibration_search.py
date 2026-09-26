"""Search the finite Argon2id grid for the strongest point inside the enrollment band.

The search measures nothing itself: it asks a caller-supplied probe for one
derivation time at a time. It relies on one ordering only, which holds on any
host: at fixed memory and parallelism, more iterations mean strictly more
block work and so a longer derivation. Nothing is inferred across
parallelism, where lane threads can make more lanes slower, and nothing is
predicted from a cost model, so no stronger in-band point is ever skipped.

The point returned is the one the enrollment ordering prefers -- highest
memory, then iterations, then parallelism, among the points whose confirmed
median is in band -- which is why the search can stop at the first memory
level that holds one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import groupby
from statistics import median
from typing import Final

from .records import ProfileCustodyKdfParameters

PROFILE_CUSTODY_KDF_NEAR_MISS_RATIO: Final = 1.25
"""A probe this close above the band maximum is taken once more before it counts as over.

One transient on a loaded host must not discard a stronger point; a probe
further over, or one that timed out, is decisive at once.
"""


@dataclass(frozen=True, slots=True)
class ProfileKdfSearchChoice:
    """The strongest confirmed in-band point and the median that confirmed it."""

    parameters: ProfileCustodyKdfParameters
    median_seconds: float


@dataclass(slots=True)
class _Search:
    probe: Callable[[ProfileCustodyKdfParameters], float]
    target_min_seconds: float
    target_max_seconds: float
    confirmation_samples: int
    seconds: dict[ProfileCustodyKdfParameters, float]

    def observed(self, point: ProfileCustodyKdfParameters) -> float:
        known = self.seconds.get(point)
        if known is not None:
            return known
        observed = self.probe(point)
        if self.target_max_seconds < observed <= self.target_max_seconds * PROFILE_CUSTODY_KDF_NEAR_MISS_RATIO:
            observed = self.probe(point)
        self.seconds[point] = observed
        return observed

    def over(self, point: ProfileCustodyKdfParameters) -> bool:
        return self.observed(point) > self.target_max_seconds

    def column(self, points: Sequence[ProfileCustodyKdfParameters]) -> ProfileKdfSearchChoice | None:
        """Return the confirmed in-band point with the most iterations in one column, if any.

        ``points`` share memory and parallelism and ascend in iterations, so
        "over the band" is false up to some index and true after it.
        """
        while True:
            last_within = -1
            low, high = 0, len(points) - 1
            while low <= high:
                middle = (low + high) // 2
                if self.over(points[middle]):
                    high = middle - 1
                else:
                    last_within = middle
                    low = middle + 1
            if last_within < 0:
                return None
            point = points[last_within]
            if self.observed(point) < self.target_min_seconds:
                # Every point with more iterations is over the band and every
                # point with fewer is faster still, so this column has none.
                return None
            # The in-band probe was the discarded warm-up; these samples decide.
            confirmed = median(self.probe(point) for _ in range(self.confirmation_samples))
            self.seconds[point] = confirmed
            if self.target_min_seconds <= confirmed <= self.target_max_seconds:
                return ProfileKdfSearchChoice(parameters=point, median_seconds=confirmed)
            if confirmed < self.target_min_seconds:
                return None


def search_profile_kdf_grid(
    candidates: Sequence[ProfileCustodyKdfParameters],
    *,
    probe: Callable[[ProfileCustodyKdfParameters], float],
    target_min_seconds: float,
    target_max_seconds: float,
    confirmation_samples: int,
) -> ProfileKdfSearchChoice | None:
    """Return the strongest candidate whose confirmed median lies in the band, or ``None``.

    ``probe`` returns one derivation's seconds, :data:`math.inf` for a point
    that timed out or exceeded a resource limit, and raises to abandon the
    whole search. ``candidates`` are already filtered to the eligible points
    the caller may select.
    """
    if confirmation_samples < 1 or not 0 < target_min_seconds <= target_max_seconds:
        raise ValueError("profile KDF calibration band and sample count are invalid")
    search = _Search(
        probe=probe,
        target_min_seconds=target_min_seconds,
        target_max_seconds=target_max_seconds,
        confirmation_samples=confirmation_samples,
        seconds={},
    )
    by_memory = sorted(candidates, key=lambda point: point.memory_mib, reverse=True)
    for _memory, level in groupby(by_memory, key=lambda point: point.memory_mib):
        columns: dict[int, list[ProfileCustodyKdfParameters]] = {}
        for point in level:
            columns.setdefault(point.parallelism, []).append(point)
        best: ProfileKdfSearchChoice | None = None
        for parallelism in sorted(columns, reverse=True):
            column = sorted(columns[parallelism], key=lambda point: point.iterations)
            if best is not None:
                # A tie in iterations already loses to the higher parallelism found first.
                floor_iterations = best.parameters.iterations
                column = [point for point in column if point.iterations > floor_iterations]
                if not column or search.over(column[0]):
                    continue
            choice = search.column(column)
            if choice is not None:
                best = choice
        if best is not None:
            return best
    return None


__all__ = [
    "PROFILE_CUSTODY_KDF_NEAR_MISS_RATIO",
    "ProfileKdfSearchChoice",
    "search_profile_kdf_grid",
]
