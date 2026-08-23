"""Acceptance gate: the serving-path benchmark meets the projected end-state.

Runs the real benchmark against the current (editable) tree -- the real ``aeat``
executable and the real warm in-process runtime, under isolated encrypted state,
no mocks -- and asserts the current-tree acceptance gates in PROCESS CPU-TIME.

Why CPU-time (perf-gate-honesty, 2026-07-21): the fleet runs three jobs per
physical machine, so co-resident load steals wall-clock from a compute-bound
measurement while its CPU seconds stay constant -- the former wall gates
red-flagged transient machine load, not regressions (2.64 s wall vs the 2.5 s
bar under ``-n auto`` contention; 5/5 green sequentially on the same tree).
Wall-clock stays measured and is PRINTED as an advisory table (run with ``-s``
to surface it in job logs), never asserted.

Measured CPU baseline (workstation, 2026-07-21): server-mode modelo-list read
0.094, simple write 0.281, MCP memory-transport read 0.312, warm steady-state
calculate 1.97 CPU-s quiet / 3.23 under full co-resident load (SMT contention
inflates CPU-time; wait-time is still excluded); subprocess first-touch work
create 21.6 child-CPU-s while its WALL was 106 s under heavy disk load -- the
divergence CPU gating exists for. Ceilings are baseline plus that contention
margin and mirror the module constants; loosening either side alone fails
loudly.

Placement: ``perf`` + ``integration`` + ``serial`` (the taxonomy hook demands
an execution marker; ``serial`` keeps it out of every ``integration and not
serial`` selector, and the serial passes that WOULD collect it carry
``not perf``), enrolled explicitly in the dispatch-only ci-full lane
(test_perf_gate_policy.py pins the placement).
"""

from __future__ import annotations

import pytest

from ..serving_path_benchmark import (
    _ENVIRONMENT_IDENTITY,
    ServingPathEvidence,
    assert_acceptance,
    run_serving_path_benchmark,
)

pytestmark = [pytest.mark.perf, pytest.mark.integration, pytest.mark.serial, pytest.mark.hex_entrypoint]


@pytest.fixture(scope="module")
def evidence() -> ServingPathEvidence:
    """Run the benchmark once for the module (it is expensive: real serving path)."""
    return run_serving_path_benchmark()


def test_advisory_wall_clock_table_is_published(evidence: ServingPathEvidence) -> None:
    """Print the wall-clock advisory table (greppable in job logs, never asserted)."""
    for measurement in evidence.measurements:
        cpu = "n/a" if measurement.cpu_seconds is None else f"{measurement.cpu_seconds:.3f}"
        print(
            f"[perf advisory] {measurement.mode}/{measurement.label}: "
            f"wall={measurement.seconds:.3f}s cpu={cpu}s "
            f"(gate={'cpu<=' + str(measurement.threshold_cpu_seconds) if measurement.gated else 'none'})",
        )
    assert evidence.measurements


def test_all_current_tree_acceptance_gates_hold(evidence: ServingPathEvidence) -> None:
    """Every gated measurement is within its CPU-time threshold on the current tree."""
    assert_acceptance(evidence)
    assert evidence.gate_failures == ()


def test_every_measurement_is_environment_labelled(evidence: ServingPathEvidence) -> None:
    """Numbers are never cross-compared unlabelled: each carries the environment id."""
    assert evidence.environment["identity"] == _ENVIRONMENT_IDENTITY
    assert evidence.measurements
    for measurement in evidence.measurements:
        assert measurement.environment == _ENVIRONMENT_IDENTITY, measurement


def test_every_measurement_records_wall_and_cpu(evidence: ServingPathEvidence) -> None:
    """Both clocks ride every row: wall for the advisory, CPU for the gates."""
    for measurement in evidence.measurements:
        assert measurement.seconds >= 0.0, measurement
        assert measurement.cpu_seconds is not None and measurement.cpu_seconds >= 0.0, measurement


def test_server_reads_and_writes_are_sub_second_cpu(evidence: ServingPathEvidence) -> None:
    """Server-mode reads and simple writes clear the sub-CPU-second bar, MCP included.

    Measured baseline 0.09-0.31 CPU-s each; the 1.0 ceiling mirrors the
    module constant so neither side can silently loosen.
    """
    gated = {m.label: m for m in evidence.measurements if m.mode == "server" and m.gated}
    read = gated["modelo list read"]
    write = gated["work create (simple write, idempotent re-touch)"]
    mcp_read = gated["review.queue read (MCP memory transport)"]
    assert read.within_threshold and read.cpu_seconds is not None and read.cpu_seconds <= 1.0, read
    assert write.within_threshold and write.cpu_seconds is not None and write.cpu_seconds <= 1.0, write
    # The full MCP memory-transport round-trip is sub-CPU-second too, so the
    # framing overhead over the warm runtime is negligible.
    assert mcp_read.within_threshold and mcp_read.cpu_seconds is not None and mcp_read.cpu_seconds <= 1.0, mcp_read


def test_heaviest_calculation_is_low_single_digit_cpu_seconds(evidence: ServingPathEvidence) -> None:
    """The warm steady-state calculation is within the honest 4.5 CPU-second bound.

    Measured baseline 1.97 CPU-s quiet / 3.23 under full co-resident SMT load
    (16-input M200 oracle); 4.5 mirrors the module constant and stays an
    order of magnitude under the regression class this gate catches.
    """
    steady = next(
        m for m in evidence.measurements if m.mode == "server" and m.label == "work calculate (warm steady-state)"
    )
    assert steady.gated and steady.within_threshold, steady
    assert steady.cpu_seconds is not None and steady.cpu_seconds <= 4.5, steady
    # The first in-process calculate carries the one-time lazy-import cost and is
    # recorded but not gated, so it cannot mask a steady-state regression.
    first = next(m for m in evidence.measurements if m.label == "work calculate (first in-process)")
    assert not first.gated


def test_subprocess_first_touch_cliff_is_gone(evidence: ServingPathEvidence) -> None:
    """Subprocess first-touch work create is far under the former 49.6 s cliff.

    Gated in child-TREE CPU seconds (the cliff was compute, not waiting);
    measured baseline 21.6 child-CPU-s on the editable tree, ceiling 35
    mirrors the module constant and stays under the ~50 s cliff class. The
    installed-cohort <= 5 s target is not asserted on the editable tree
    (the installed-cohort gates own that against the built cohort).
    """
    first_touch = next(
        m for m in evidence.measurements if m.mode == "subprocess" and m.label.startswith("work create (first-touch")
    )
    assert first_touch.gated and first_touch.within_threshold, first_touch
    assert first_touch.cpu_seconds is not None and first_touch.cpu_seconds <= 35.0, first_touch
