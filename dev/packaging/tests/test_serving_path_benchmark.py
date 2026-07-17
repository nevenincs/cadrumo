"""Acceptance gate: the serving-path benchmark meets the projected end-state.

Runs the real benchmark against the current (editable) tree -- the real ``aeat``
executable and the real warm in-process runtime, under isolated encrypted state,
no mocks -- and asserts the current-tree acceptance gates: server-mode reads and
simple writes sub-second, the heaviest calculation within the honest steady-state
bound, and the subprocess first-touch far under the former 49.6 s cliff. The
installed-cohort subprocess targets are S19/S20's to prove against the built
cohort and are deliberately not gated here.
"""

from __future__ import annotations

import pytest

from dev.packaging.serving_path_benchmark import (
    _ENVIRONMENT_IDENTITY,
    assert_acceptance,
    run_serving_path_benchmark,
)

pytestmark = [pytest.mark.integration, pytest.mark.serial, pytest.mark.hex_entrypoint]


@pytest.fixture(scope="module")
def evidence():
    """Run the benchmark once for the module (it is expensive: real serving path)."""
    return run_serving_path_benchmark()


def test_all_current_tree_acceptance_gates_hold(evidence) -> None:
    """Every gated measurement is within its threshold on the current tree."""
    assert_acceptance(evidence)
    assert evidence.gate_failures == ()


def test_every_measurement_is_environment_labelled(evidence) -> None:
    """Numbers are never cross-compared unlabelled: each carries the environment id."""
    assert evidence.environment["identity"] == _ENVIRONMENT_IDENTITY
    assert evidence.measurements
    for measurement in evidence.measurements:
        assert measurement.environment == _ENVIRONMENT_IDENTITY, measurement


def test_server_reads_and_writes_are_sub_second(evidence) -> None:
    """Server-mode reads and simple writes clear the sub-second bar, MCP surface included."""
    gated = {m.label: m for m in evidence.measurements if m.mode == "server" and m.gated}
    read = gated["modelo list read"]
    write = gated["work create (simple write, idempotent re-touch)"]
    mcp_read = gated["review.queue read (MCP memory transport)"]
    assert read.within_threshold and read.seconds <= 1.0, read
    assert write.within_threshold and write.seconds <= 1.0, write
    # The full MCP memory-transport round-trip is sub-second too, so the framing
    # overhead over the warm runtime is negligible.
    assert mcp_read.within_threshold and mcp_read.seconds <= 1.0, mcp_read


def test_heaviest_calculation_is_low_single_digit_seconds(evidence) -> None:
    """The warm steady-state calculation is within the honest 2.5 s bound."""
    steady = next(
        m for m in evidence.measurements if m.mode == "server" and m.label == "work calculate (warm steady-state)"
    )
    assert steady.gated and steady.within_threshold, steady
    assert steady.seconds <= 2.5, steady
    # The first in-process calculate carries the one-time lazy-import cost and is
    # recorded but not gated, so it cannot mask a steady-state regression.
    first = next(m for m in evidence.measurements if m.label == "work calculate (first in-process)")
    assert not first.gated


def test_subprocess_first_touch_cliff_is_gone(evidence) -> None:
    """Subprocess first-touch work create is far under the former 49.6 s cliff."""
    first_touch = next(
        m for m in evidence.measurements if m.mode == "subprocess" and m.label.startswith("work create (first-touch")
    )
    assert first_touch.gated and first_touch.within_threshold, first_touch
    # Far under the former 49.6 s cliff; the installed-cohort <= 5 s target is not
    # asserted on the editable tree (S19/S20 own that against the built cohort).
    assert first_touch.seconds <= 25.0, first_touch
