"""The retained wall advisory fires on a wedge and stays quiet on load.

Converting a perf gate from wall-clock to CPU-time is the right instrument
choice on this co-resident fleet, but it is also the change that silently
deletes the only bound able to see a test blocked on a wedged mount: a blocked
test burns no CPU however long it stalls, so a CPU ceiling can never fire on
it. :func:`~dev.ci.perf_measurement.wall_advisory_message` is what the two
converted budgets keep in that gap.

This gate exists because the advisory has two ways to be worthless and both
pass a green suite. It can be unfalsifiable -- never fire, so the wedge class
stays as unwatched as a straight conversion would have left it. Or it can be
indiscriminate -- fire whenever the box is busy, which on this machine is most
runs, and an advisory that fires on every run is one every reader learns to
skip, the decorative-guard decay already documented twice in this suite.
So both directions are asserted here, against the site-derived figures the two
consumers actually pass rather than against round numbers chosen to pass.

The advisory is a pure classifier over two measured clocks, so it is driven
directly with the readings the fleet recorded on real runs. Nothing is mocked:
the function under test IS the code the benchmarks call, and the numbers are
this repository's own measurements, quoted in the constants' derivations at
both call sites.
"""

from __future__ import annotations

import warnings
from typing import Final

import pytest

from dev._paths import REPO_ROOT

from ..perf_measurement import WallClockAdvisory, wall_advisory_message

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The in-process ledger benchmark's retained threshold and wedge ratio.
_LEDGER_WALL_S: Final[float] = 3.0
_LEDGER_RATIO: Final[float] = 4.0

#: The subprocess cold-start site's, which runs a far looser ratio because a
#: spawn's wall time is dominated by process creation the SUT does not own.
_COLD_START_WALL_S: Final[float] = 7.0
_COLD_START_RATIO: Final[float] = 12.0


def _ledger_advisory(*, wall_seconds: float, cpu_seconds: float) -> str | None:
    """Run the classifier with the ledger benchmark's own thresholds."""
    return wall_advisory_message(
        "iva_quarterly_partitioned p95",
        wall_seconds=wall_seconds,
        cpu_seconds=cpu_seconds,
        wall_advisory_seconds=_LEDGER_WALL_S,
        hang_wall_to_cpu_ratio=_LEDGER_RATIO,
    )


def test_the_measured_loaded_reading_does_not_fire() -> None:
    """The worst load this path ever measured stays quiet.

    Wall 4.10 s against 1.83 CPU-s is the loaded reading recorded in the
    benchmark's own module docstring -- a real run, on the real fleet, with the
    box saturated. It crosses the 3.0 s threshold and must still not warn: at
    2.24x it is load-shaped, and warning here would make the advisory fire on
    ordinary days and so teach every reader to ignore it.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", WallClockAdvisory)
        assert _ledger_advisory(wall_seconds=4.10, cpu_seconds=1.83) is None


def test_the_measured_quiet_reading_does_not_fire() -> None:
    """The unloaded reading is below the threshold and cannot warn."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", WallClockAdvisory)
        assert _ledger_advisory(wall_seconds=2.07, cpu_seconds=1.83) is None


def test_a_stalled_read_fires_and_names_both_clocks() -> None:
    """A wedge is caught, and the message distinguishes it from a regression.

    The shape is the one CPU-time is blind to: wall runs away while CPU holds
    at the same 1.83 s the healthy runs measured. The message must say so, or a
    reader triaging it re-reads it as the performance regression the asserted
    CPU gate has in fact just confirmed is absent.
    """
    with pytest.warns(WallClockAdvisory) as caught:
        message = _ledger_advisory(wall_seconds=45.0, cpu_seconds=1.83)

    assert message is not None
    assert len(caught) == 1
    assert message == str(caught[0].message)
    assert "45.000s" in message
    assert "1.830 CPU-s" in message
    assert "NOT a performance regression" in message


def test_a_fully_blocked_sample_fires_rather_than_dividing_by_zero() -> None:
    """Zero CPU is the wedge in its purest form, not an input to reject.

    A test blocked for its whole duration measures no CPU at all. That is the
    single reading this advisory most needs to survive, so the ratio treats it
    as unbounded rather than guarding the division and returning early.
    """
    with pytest.warns(WallClockAdvisory):
        message = _ledger_advisory(wall_seconds=45.0, cpu_seconds=0.0)

    assert message is not None
    assert "infx" in message.replace(" ", "")


def test_the_cold_start_ratio_admits_the_spawn_wait_it_must() -> None:
    """A healthy loaded SPAWN stays quiet under the looser subprocess ratio.

    6.75 s of wall against 1.45 CPU-s is the worst healthy cold start recorded
    on this box, and its 4.7x ratio would have tripped the in-process site's
    4.0x threshold. That is the whole reason the ratio is per-site: a spawn
    pays process-creation wait the SUT is not answerable for, so a single
    global ratio would have to be either noisy here or blind there.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", WallClockAdvisory)
        assert (
            wall_advisory_message(
                "aeat --version cold start",
                wall_seconds=6.75,
                cpu_seconds=1.45,
                wall_advisory_seconds=_COLD_START_WALL_S,
                hang_wall_to_cpu_ratio=_COLD_START_RATIO,
            )
            is None
        )

    assert _LEDGER_RATIO < 6.75 / 1.45, "the spawn reading no longer demonstrates why the ratio is per-site"


def test_the_cold_start_site_still_catches_a_wedged_spawn() -> None:
    """The looser ratio is loose, not vacuous: a stalled spawn still fires."""
    with pytest.warns(WallClockAdvisory):
        assert (
            wall_advisory_message(
                "aeat --version cold start",
                wall_seconds=30.0,
                cpu_seconds=1.45,
                wall_advisory_seconds=_COLD_START_WALL_S,
                hang_wall_to_cpu_ratio=_COLD_START_RATIO,
            )
            is not None
        )


def test_the_consumers_pass_the_thresholds_this_gate_asserts() -> None:
    """The site constants really are the ones proved above.

    Without this the gate drifts into testing figures no caller uses: a
    consumer could relax its threshold to silence a real wedge and every
    assertion here would keep passing against the stale copy.
    """

    repo_root = REPO_ROOT
    ledger = (repo_root / "dev" / "ci" / "tests" / "test_ledger_scale_benchmark.py").read_text(encoding="utf-8")
    cold_start = (repo_root / "dev" / "ci" / "tests" / "test_lazy_command_tree.py").read_text(encoding="utf-8")

    assert f"_P95_WALL_ADVISORY_SECONDS = {_LEDGER_WALL_S}" in ledger
    assert f"_P95_WEDGE_WALL_TO_CPU_RATIO = {_LEDGER_RATIO}" in ledger
    assert f"_COLD_START_WALL_ADVISORY_S = {_COLD_START_WALL_S}" in cold_start
    assert f"_COLD_START_WEDGE_WALL_TO_CPU_RATIO = {_COLD_START_RATIO}" in cold_start
