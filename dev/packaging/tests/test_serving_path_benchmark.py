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

import json

import pytest

from ..serving_path_benchmark import (
    _ENVIRONMENT_IDENTITY,
    ServingPathEvidence,
    assert_acceptance,
    run_serving_path_benchmark,
    subprocess_failure_message,
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


_ARGV = ("aeat.exe", "--format", "json", "config", "profile", "create")
_REFUSAL = json.dumps(
    {
        "command": "config.profile.create",
        "error": {
            "category": "REFUSED",
            "code": "REFUSED_CLI_BOUNDARY",
            "message": "No passphrase channel is available. Run this verb at a terminal.",
        },
        "status": "error",
    },
)


@pytest.mark.parametrize("stream", ["stderr", "stdout"])
def test_a_typed_refusal_is_named_ahead_of_the_raw_child_detail(stream: str) -> None:
    """The cause, not the symptom, is the first thing a reader sees.

    Every measured call runs under this module's module-scoped fixture, so one
    refusing child errors every test here at setup with identical text. A bare
    return code followed by a full argv dump names nothing, and the reader has
    to reconstruct the boundary refusal the product already reported.

    Parametrised over both streams because the product writes a refusal to
    STDERR and leaves stdout empty -- measured against the live CLI. A summary
    that read stdout alone would name nothing on precisely the failures this
    exists to explain, and would look correct in a test that fed it stdout.
    """
    stdout, stderr = (_REFUSAL, "") if stream == "stdout" else ("", _REFUSAL)

    message = subprocess_failure_message(2, _ARGV, stdout, stderr)

    summary = message.splitlines()[0]
    assert "REFUSED_CLI_BOUNDARY" in summary, message
    assert "No passphrase channel is available" in summary, message
    assert "argv" not in summary, f"the argv dump displaced the named cause: {message}"


def test_the_named_summary_never_replaces_the_raw_child_detail() -> None:
    """Naming the refusal must add to the report, not censor it.

    A summary that swallowed stdout would trade one unreadable failure for a
    lossy one, and the raw envelope is what a reader needs once the name is not
    enough.
    """
    message = subprocess_failure_message(2, _ARGV, _REFUSAL, "stderr detail")

    assert _REFUSAL in message
    assert "stderr detail" in message
    assert repr(_ARGV) in message


def test_a_child_that_returns_no_envelope_still_reports_everything_it_had() -> None:
    """Not every failing child speaks the envelope; that one must not be degraded.

    A crash writes a traceback to stderr and nothing parseable to stdout. The
    summary falls back to the return code and carries the raw streams intact,
    rather than raising while trying to explain a failure.
    """
    message = subprocess_failure_message(9, _ARGV, "not json at all", "Traceback (most recent call last)")

    assert "subprocess call failed (9)" in message.splitlines()[0]
    assert "not json at all" in message
    assert "Traceback (most recent call last)" in message


@pytest.mark.parametrize(
    "stdout",
    ["[]", '{"error": null}', '{"error": {}}', '{"error": "opaque"}', ""],
)
def test_a_payload_carrying_no_named_refusal_is_reported_plainly(stdout: str) -> None:
    """Shapes that carry no name must not be dressed up as one.

    A JSON list, a null or empty error, a non-mapping error, and an empty
    stdout each reach this differently; none of them names a refusal, so the
    summary must stay the plain return code rather than inventing a cause.
    """
    message = subprocess_failure_message(1, _ARGV, stdout, "")

    assert message.splitlines()[0] == "subprocess call failed (1)", message
