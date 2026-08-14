"""Pure unit coverage for worker-replacement detection.

The installed-hook subprocess proof lives in
:mod:`cadrumo.tests.test_worker_count_hook_harness`, the explicit member of
the outer-serial ``just test-harness`` verdict. Keeping the bounded detector
logic here preserves routine unit coverage without starting nested xdist
pools.
"""

from __future__ import annotations

import pytest

from ._worker_count_hook import (
    DEFAULT_WORKER_CAP,
    replacement_occurred,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# Worker-replacement detector
#
# A crashed-and-replaced worker corrupts a run's own pass/fail totals, so a
# green run that replaced a worker is not evidence the suite passed. These
# assertions pin the ordinal boundary that discriminates a replacement from a
# legitimate worker, and the final test proves the pin is load-bearing.
# ---------------------------------------------------------------------------


def test_the_full_configured_range_is_not_a_replacement() -> None:
    """Every ordinal below the worker count is legitimate, so nothing is flagged.

    The anti-false-positive control: an ordinary healthy run uses its whole
    configured range, and must never be reported as corrupted.
    """
    healthy = [f"gw{ordinal}" for ordinal in range(DEFAULT_WORKER_CAP)]
    assert replacement_occurred(healthy, worker_count=DEFAULT_WORKER_CAP) is False


def test_the_first_ordinal_past_the_range_is_a_replacement() -> None:
    """``gw{count}`` is one past the highest legitimate ordinal, so it is a replacement.

    Asserted at the boundary rather than with an obviously-high ordinal: an
    off-by-one detector using ``>`` instead of ``>=`` passes a ``gw99`` probe
    and fails only here.
    """
    observed = [f"gw{ordinal}" for ordinal in range(DEFAULT_WORKER_CAP)]
    observed.append(f"gw{DEFAULT_WORKER_CAP}")
    assert replacement_occurred(observed, worker_count=DEFAULT_WORKER_CAP) is True


def test_no_observed_workers_reports_no_replacement() -> None:
    """A run that observed no workers has no replacement to report."""
    assert replacement_occurred([], worker_count=DEFAULT_WORKER_CAP) is False


@pytest.mark.parametrize("worker_count", [0, -1])
def test_a_non_positive_worker_count_is_refused(worker_count: int) -> None:
    """Judging replacement against a non-positive configured count is incoherent."""
    with pytest.raises(ValueError, match="worker_count must be positive"):
        replacement_occurred(["gw0"], worker_count=worker_count)


@pytest.mark.parametrize("malformed", ["gw", "worker1", "gw1x", "GW1", "", "gw-1"])
def test_an_unreadable_worker_id_is_refused_rather_than_skipped(malformed: str) -> None:
    """An id that does not parse must raise, never be silently skipped.

    This is the detector's own anti-vacuity guard. A skipping implementation
    would keep returning ``False`` forever if xdist ever changed its id
    format, reporting every corrupted run as clean -- the exact false-green
    shape this detector exists to catch. Refusing to read an id it does not
    understand is what keeps a ``False`` meaningful.
    """
    with pytest.raises(ValueError, match="Unrecognised xdist worker id"):
        replacement_occurred([malformed], worker_count=DEFAULT_WORKER_CAP)


def test_each_wrong_detector_is_caught_by_the_assertions_above() -> None:
    """Prove the assertions above fail against plausibly-wrong implementations.

    A detector nothing can falsify is decoration. Each candidate below is a
    realistic way to get this wrong; this test pins the specific input that
    exposes it, so the boundary and refusal assertions are demonstrably
    load-bearing rather than incidentally true.
    """
    boundary_id = f"gw{DEFAULT_WORKER_CAP}"

    # Off-by-one: treats the first replacement ordinal as legitimate.
    def off_by_one(worker_ids: list[str], *, worker_count: int) -> bool:
        return any(int(w.removeprefix("gw")) > worker_count for w in worker_ids)

    assert off_by_one([boundary_id], worker_count=DEFAULT_WORKER_CAP) is False
    assert replacement_occurred([boundary_id], worker_count=DEFAULT_WORKER_CAP) is True

    # Always-clean: the classic decoration, green on every input.
    def always_clean(worker_ids: list[str], *, worker_count: int) -> bool:
        return False

    assert always_clean([boundary_id], worker_count=DEFAULT_WORKER_CAP) is False

    # Skipping: ignores ids it cannot parse, so a format change silences it.
    def skips_unreadable(worker_ids: list[str], *, worker_count: int) -> bool:
        ordinals = [int(w.removeprefix("gw")) for w in worker_ids if w.startswith("gw") and w[2:].isdigit()]
        return any(ordinal >= worker_count for ordinal in ordinals)

    assert skips_unreadable(["worker1"], worker_count=DEFAULT_WORKER_CAP) is False
    with pytest.raises(ValueError, match="Unrecognised xdist worker id"):
        replacement_occurred(["worker1"], worker_count=DEFAULT_WORKER_CAP)
