"""Confirm only the strongest provisional point without weakening grid selection."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence

import pytest

from ..kdf_calibration_search import ProfileKdfSearchChoice, search_profile_kdf_grid
from ..kdf_supervision import (
    PROFILE_CUSTODY_KDF_SAMPLE_COUNT,
    PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS,
    PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS,
    profile_kdf_grid,
    profile_kdf_meets_fallback_floor,
)
from ..records import ProfileCustodyKdfParameters

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

type _Key = tuple[int, int, int]

_MIN = PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS
_MAX = PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS
_SAMPLES = PROFILE_CUSTODY_KDF_SAMPLE_COUNT
_CANDIDATES = tuple(point for point in profile_kdf_grid(salt=b"s" * 16) if profile_kdf_meets_fallback_floor(point))


def _key(point: ProfileCustodyKdfParameters) -> _Key:
    return point.memory_mib, point.iterations, point.parallelism


def _points(keys: Sequence[_Key]) -> tuple[ProfileCustodyKdfParameters, ...]:
    by_key = {_key(point): point for point in _CANDIDATES}
    return tuple(by_key[key] for key in keys)


class _Probe:
    def __init__(self, timings: dict[_Key, float], confirmations: Mapping[_Key, Sequence[float]] | None = None) -> None:
        self.timings = timings
        self.confirmations: Mapping[_Key, Sequence[float]] = confirmations or {}
        self.calls: list[_Key] = []
        self.counts: Counter[_Key] = Counter()

    def __call__(self, point: ProfileCustodyKdfParameters) -> float:
        key = _key(point)
        self.calls.append(key)
        self.counts[key] += 1
        samples = self.confirmations.get(key)
        if samples is not None and self.counts[key] > 1:
            # A rejected confirmation must be cached, rather than sampled again.
            return samples[self.counts[key] - 2]
        return self.timings[key]


def _search(
    points: Sequence[ProfileCustodyKdfParameters], probe: Callable[[ProfileCustodyKdfParameters], float]
) -> ProfileKdfSearchChoice | None:
    return search_profile_kdf_grid(
        points,
        probe=probe,
        target_min_seconds=_MIN,
        target_max_seconds=_MAX,
        confirmation_samples=_SAMPLES,
    )


@pytest.mark.parametrize("seed", range(24))
def test_independent_monotone_lane_tables_match_the_exhaustive_oracle(seed: int) -> None:
    timings: dict[_Key, float] = {}
    for memory in (64, 128, 256):
        for parallelism in (1, 2, 4):
            keys = sorted(
                _key(point) for point in _CANDIDATES if point.memory_mib == memory and point.parallelism == parallelism
            )
            # Each memory/lane column is independent; only its iterations are ordered.
            values = sorted(
                20 + ((seed * 97 + memory * 11 + parallelism * 137 + index * 173) % 881) for index in range(len(keys))
            )
            timings.update((key, value / 1000) for key, value in zip(keys, values, strict=True))
    points = sorted(
        _CANDIDATES,
        key=lambda point: (point.memory_mib * 11 + point.iterations * 173 + point.parallelism * 137 + seed * 97) % 881,
    )
    in_band = [key for key, seconds in timings.items() if _MIN <= seconds <= _MAX]
    expected = max(in_band) if in_band else None

    choice = _search(points, _Probe(timings))

    assert (None if choice is None else _key(choice.parameters)) == expected
    if choice is not None:
        assert profile_kdf_meets_fallback_floor(choice.parameters)
        assert choice.median_seconds == timings[_key(choice.parameters)]


def test_superseded_provisional_candidates_get_no_confirmation_batch() -> None:
    timings = {
        (256, 2, 4): 0.15,
        (256, 3, 4): 0.35,
        (256, 4, 4): 0.70,
        (256, 6, 4): 0.90,
        (256, 2, 2): 0.10,
        (256, 3, 2): 0.20,
        (256, 4, 2): 0.40,
        (256, 6, 2): 0.80,
        (256, 2, 1): 0.10,
        (256, 3, 1): 0.20,
        (256, 4, 1): 0.30,
        (256, 6, 1): 0.45,
    }
    probe = _Probe(timings)

    choice = _search(_points(tuple(timings)), probe)

    assert choice is not None
    assert _key(choice.parameters) == (256, 6, 1)
    assert probe.counts[(256, 3, 4)] == 1
    assert probe.counts[(256, 4, 2)] == 1
    assert probe.counts[(256, 6, 1)] == 1 + _SAMPLES
    assert probe.calls[-_SAMPLES:] == [(256, 6, 1)] * _SAMPLES


@pytest.mark.parametrize("rejected_median", [0.10, 0.80], ids=["under-band", "over-band"])
def test_reclassification_revisits_a_lower_lane_pruned_by_the_provisional(rejected_median: float) -> None:
    timings = {(256, 3, 4): 0.20, (256, 4, 4): 0.40, (256, 3, 2): 0.30, (256, 4, 2): 0.45}
    rejected = (256, 4, 4)
    probe = _Probe(timings, {rejected: [rejected_median] * _SAMPLES})

    choice = _search(_points(tuple(timings)), probe)

    assert choice is not None
    assert _key(choice.parameters) == (256, 4, 2)
    assert probe.counts[rejected] == 1 + _SAMPLES
    assert probe.counts[(256, 4, 2)] == 1 + _SAMPLES
    # The tied lower lane was skipped before confirmation, then considered afresh.
    last_rejected = max(index for index, key in enumerate(probe.calls) if key == rejected)
    assert probe.calls.index((256, 4, 2)) > last_rejected


def test_over_band_reclassification_can_find_weaker_iterations_at_the_same_memory() -> None:
    timings = {(256, 2, 4): 0.10, (256, 3, 4): 0.30, (256, 4, 4): 0.40}
    probe = _Probe(timings, {(256, 4, 4): [0.55] * _SAMPLES})

    choice = _search(_points(tuple(timings)), probe)

    assert choice is not None
    assert _key(choice.parameters) == (256, 3, 4)
    # A rejected median in the near-miss range is not another discovery probe.
    assert probe.counts[(256, 4, 4)] == 1 + _SAMPLES
    assert probe.counts[(256, 3, 4)] == 1 + _SAMPLES


@pytest.mark.parametrize("rejected_median", [0.10, 0.80], ids=["under-band", "over-band"])
def test_reclassification_exhausts_the_materialized_level_before_lower_memory(rejected_median: float) -> None:
    timings = {(256, 2, 4): 0.10, (256, 3, 4): 0.30, (256, 4, 4): 0.40, (128, 4, 4): 0.35}
    confirmations = {
        (256, 4, 4): [rejected_median] * _SAMPLES,
        (256, 3, 4): [rejected_median] * _SAMPLES,
    }
    probe = _Probe(timings, confirmations)

    choice = _search(_points(tuple(timings)), probe)

    assert choice is not None
    assert _key(choice.parameters) == (128, 4, 4)
    assert probe.counts[(256, 4, 4)] == 1 + _SAMPLES
    # Under-band at the maximum iteration discards its entire monotone column.
    assert probe.counts[(256, 3, 4)] == (1 if rejected_median < _MIN else 1 + _SAMPLES)
    assert probe.counts[(128, 4, 4)] == 1 + _SAMPLES


def test_near_miss_warmup_retry_precedes_exactly_five_confirmations() -> None:
    key = (256, 4, 4)
    probe = _Probe({key: 0.55}, {key: [0.40, *([0.35] * _SAMPLES)]})

    choice = _search(_points([key]), probe)

    assert choice is not None
    assert choice.median_seconds == 0.35
    assert probe.counts[key] == 2 + _SAMPLES


def test_confirmation_uses_the_median_without_retrying_individual_samples() -> None:
    key = (256, 4, 4)
    probe = _Probe({key: 0.40}, {key: [0.10, 0.30, 0.40, 0.55, math.inf]})

    choice = _search(_points([key]), probe)

    assert choice is not None
    assert choice.median_seconds == 0.40
    assert probe.counts[key] == 1 + _SAMPLES


@pytest.mark.parametrize("failure_call", [1, 3], ids=["discovery", "confirmation"])
def test_arbitrary_probe_exceptions_escape_by_identity_without_more_work(failure_call: int) -> None:
    error = RuntimeError("synthetic probe failure")
    calls = 0

    def probe(_point: ProfileCustodyKdfParameters) -> float:
        nonlocal calls
        calls += 1
        if calls == failure_call:
            raise error
        return 0.40

    with pytest.raises(RuntimeError) as captured:
        _search(_points([(256, 4, 4)]), probe)

    assert captured.value is error
    assert calls == failure_call


def test_a_later_discovery_failure_cannot_abandon_an_already_confirmed_weaker_point() -> None:
    weaker = (256, 3, 4)
    stronger = (256, 4, 2)
    error = RuntimeError("synthetic stronger column failure")
    calls: list[_Key] = []

    def probe(point: ProfileCustodyKdfParameters) -> float:
        key = _key(point)
        calls.append(key)
        if key == stronger:
            raise error
        return 0.30

    with pytest.raises(RuntimeError) as captured:
        _search(_points([weaker, stronger]), probe)

    assert captured.value is error
    assert calls == [weaker, stronger]
