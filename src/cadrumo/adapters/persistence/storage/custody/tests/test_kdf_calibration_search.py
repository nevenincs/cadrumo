"""The calibration search returns exactly the point an exhaustive scan would prefer.

Every case drives the search with a synthetic timing table -- no Argon2, no
child process -- so the only thing under test is the search logic. The oracle
applies the enrollment ordering to the whole candidate grid independently:
the in-band point with the highest memory, then iterations, then parallelism.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import product

import pytest

from ..kdf_calibration_search import PROFILE_CUSTODY_KDF_NEAR_MISS_RATIO, search_profile_kdf_grid
from ..kdf_supervision import (
    PROFILE_CUSTODY_KDF_SAMPLE_COUNT,
    PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS,
    PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS,
    fixed_profile_kdf_fallback,
    profile_kdf_grid,
    profile_kdf_meets_fallback_floor,
)
from ..records import ProfileCustodyKdfParameters

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SALT = b"s" * 16
_MIN = PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS
_MAX = PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS
_CANDIDATES = tuple(point for point in profile_kdf_grid(salt=_SALT) if profile_kdf_meets_fallback_floor(point))
_Timing = Callable[[int, int, int], float]


def _key(point: ProfileCustodyKdfParameters) -> tuple[int, int, int]:
    return point.memory_mib, point.iterations, point.parallelism


def _oracle(timing: _Timing) -> tuple[int, int, int] | None:
    in_band = [_key(point) for point in _CANDIDATES if _MIN <= timing(*_key(point)) <= _MAX]
    return max(in_band) if in_band else None


class _CountingProbe:
    def __init__(self, timing: _Timing) -> None:
        self.timing = timing
        self.calls: list[tuple[int, int, int]] = []

    def __call__(self, point: ProfileCustodyKdfParameters) -> float:
        self.calls.append(_key(point))
        return self.timing(*_key(point))


def _search(probe: Callable[[ProfileCustodyKdfParameters], float]) -> tuple[int, int, int] | None:
    choice = search_profile_kdf_grid(
        _CANDIDATES,
        probe=probe,
        target_min_seconds=_MIN,
        target_max_seconds=_MAX,
        confirmation_samples=PROFILE_CUSTODY_KDF_SAMPLE_COUNT,
    )
    return None if choice is None else _key(choice.parameters)


def _proportional(per_lane_cost: dict[int, float]) -> _Timing:
    """Seconds proportional to memory x iterations, one coefficient per parallelism."""

    def timing(memory: int, iterations: int, parallelism: int) -> float:
        seconds = per_lane_cost[parallelism] * memory * iterations
        return math.inf if seconds > 2.0 else seconds

    return timing


# Coefficients fitted to medians measured on a 24-core development host:
# 256 MiB, t=10 took 1.06 s at p=4 and 3.3 s at p=1.
_MEASURED_HOST = _proportional({4: 0.000414, 2: 0.00075, 1: 0.00129})


def _lower_parallelism_wins(memory: int, iterations: int, parallelism: int) -> float:
    # At 256 MiB, p=4 is over the band from t=4 while p=2 is still in band at
    # t=4: the preferred point has MORE iterations at a LOWER parallelism.
    if memory == 256 and parallelism == 4:
        return {2: 0.30, 3: 0.45}.get(iterations, 0.60 + 0.1 * iterations)
    if memory == 256 and parallelism == 2:
        return {2: 0.26, 3: 0.37, 4: 0.48}.get(iterations, 0.70 + 0.1 * iterations)
    if memory == 256:
        return math.inf
    return 0.05 * iterations


def _parallelism_slower_at_small_memory(memory: int, iterations: int, parallelism: int) -> float:
    if memory >= 128:
        return math.inf
    # At 64 MiB lane threads cost more than they save: p=4 is the slowest column.
    per_iteration = {4: 0.19, 2: 0.12, 1: 0.10}[parallelism]
    return per_iteration * iterations


@pytest.mark.parametrize(
    "timing",
    [_MEASURED_HOST, _lower_parallelism_wins, _parallelism_slower_at_small_memory],
    ids=["measured-host", "lower-parallelism-wins", "parallelism-slower-at-small-memory"],
)
def test_the_search_returns_the_exhaustive_oracle_point(timing: _Timing) -> None:
    expected = _oracle(timing)

    assert expected is not None
    assert _search(_CountingProbe(timing)) == expected


def test_the_lower_parallelism_case_prefers_more_iterations_over_more_lanes() -> None:
    assert _search(_CountingProbe(_lower_parallelism_wins)) == (256, 4, 2)


def test_the_small_memory_case_does_not_assume_lanes_are_faster() -> None:
    # p=2 and p=1 both reach t=4 in band, and p=2 outranks p=1 there; p=4, the
    # slowest column here, has no in-band point at all.
    assert _search(_CountingProbe(_parallelism_slower_at_small_memory)) == (64, 4, 2)


def test_the_measured_host_search_probes_ten_times_not_the_whole_grid() -> None:
    probe = _CountingProbe(_MEASURED_HOST)

    assert _search(probe) == (256, 4, 4)
    # 256 MiB, p=4: bisect t=4 (in band), t=8 and t=6 (over), then five
    # confirming samples of t=4. The p=2 and p=1 columns need only one probe
    # each, at t=6, the first iteration count that could outrank t=4.
    assert probe.calls == [
        (256, 4, 4),
        (256, 8, 4),
        (256, 6, 4),
        *[(256, 4, 4)] * PROFILE_CUSTODY_KDF_SAMPLE_COUNT,
        (256, 6, 2),
        (256, 6, 1),
    ]


@pytest.mark.parametrize(
    "timing",
    [lambda _m, _t, _p: 1.5, lambda _m, _t, _p: 0.1, lambda _m, _t, _p: math.inf],
    ids=["every-point-over", "every-point-under", "every-point-times-out"],
)
def test_no_point_in_band_returns_nothing_so_the_caller_falls_back(timing: _Timing) -> None:
    assert _oracle(timing) is None
    assert _search(_CountingProbe(timing)) is None


def test_a_near_miss_probe_is_taken_again_before_it_can_discard_a_stronger_point() -> None:
    spiked: set[tuple[int, int, int]] = set()

    def probe(point: ProfileCustodyKdfParameters) -> float:
        key = _key(point)
        if key == (256, 4, 4) and key not in spiked:
            spiked.add(key)
            return _MAX * 1.1  # one transient, inside the near-miss margin
        return _MEASURED_HOST(*key)

    assert _search(probe) == (256, 4, 4)


def test_a_probe_far_over_the_band_is_decisive_at_once() -> None:
    probe = _CountingProbe(_MEASURED_HOST)
    far_over = _MAX * PROFILE_CUSTODY_KDF_NEAR_MISS_RATIO * 1.01

    def spiking(point: ProfileCustodyKdfParameters) -> float:
        if _key(point) == (256, 4, 4) and not probe.calls:
            probe.calls.append(_key(point))
            return far_over
        return probe(point)

    choice = _search(spiking)

    assert choice is not None
    assert choice < (256, 4, 4)
    assert probe.calls.count((256, 4, 4)) == 1, "a decisive over-band probe is not taken again"


def test_a_confirmation_that_leaves_the_band_reclassifies_the_point_and_resumes() -> None:
    seen: dict[tuple[int, int, int], int] = {}

    def probe(point: ProfileCustodyKdfParameters) -> float:
        key = _key(point)
        seen[key] = seen.get(key, 0) + 1
        if key == (256, 4, 4) and seen[key] > 1:
            return 0.70  # in band on the probe, over the band across the samples
        return _MEASURED_HOST(*key)

    assert _search(probe) == (256, 3, 4)


def test_the_floor_is_exactly_the_fallback_strength() -> None:
    fallback = fixed_profile_kdf_fallback(salt=_SALT)
    grid = profile_kdf_grid(salt=_SALT)

    assert profile_kdf_meets_fallback_floor(fallback)
    assert {_key(point) for point in grid if profile_kdf_meets_fallback_floor(point)} == {
        (memory, iterations, parallelism)
        for memory, iterations, parallelism in product((64, 128, 256), (2, 3, 4, 6, 8, 10), (1, 2, 4))
        if memory * iterations >= 192
    }


@pytest.mark.parametrize(
    "timing",
    [
        _MEASURED_HOST,
        _lower_parallelism_wins,
        _parallelism_slower_at_small_memory,
        # Everything in band: the strongest point overall must win.
        lambda _m, _t, _p: 0.3,
    ],
)
def test_a_search_result_is_never_weaker_than_the_fallback(timing: _Timing) -> None:
    fallback = fixed_profile_kdf_fallback(salt=_SALT)
    chosen = _search(_CountingProbe(timing))

    assert chosen is not None
    memory, iterations, _parallelism = chosen
    assert memory >= fallback.memory_mib
    assert memory * iterations >= fallback.memory_mib * fallback.iterations
