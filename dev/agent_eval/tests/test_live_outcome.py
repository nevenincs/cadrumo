"""The live lane's pass rule and outcome classes.

The rule is the accepted one: three runs, every hard invariant held in each,
and at least two reaching the end state. A missing prerequisite is unavailable,
never a pass, and a product disagreement outranks anything the agent did.
"""

from __future__ import annotations

import pytest

from ..live.outcome import (
    EXIT_CODES,
    FailureOwner,
    InvariantFailure,
    Outcome,
    RunVerdict,
    UnavailableError,
    lane_verdict,
    required_end_states,
    unavailable_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _run(index: int, *, reached: bool, failure: InvariantFailure | None = None, oracle: str = "") -> RunVerdict:
    return RunVerdict(
        run_index=index,
        end_state_reached=reached,
        invariant_failures=() if failure is None else (failure,),
        oracle_disagreements=(oracle,) if oracle else (),
    )


def test_two_of_three_end_states_with_every_invariant_held_passes() -> None:
    verdict = lane_verdict((_run(0, reached=True), _run(1, reached=False), _run(2, reached=True)), runs=3)
    assert verdict.outcome is Outcome.PASSED
    assert verdict.exit_code == 0


def test_one_of_three_end_states_is_an_agent_failure() -> None:
    verdict = lane_verdict((_run(0, reached=True), _run(1, reached=False), _run(2, reached=False)), runs=3)
    assert verdict.outcome is Outcome.AGENT_FAILURE


def test_a_broken_invariant_fails_the_lane_even_when_every_run_reached_the_end() -> None:
    secret = InvariantFailure(invariant="no_secret", owner=FailureOwner.AGENT, detail="tool argument named secret")
    verdict = lane_verdict(
        (_run(0, reached=True), _run(1, reached=True, failure=secret), _run(2, reached=True)), runs=3
    )
    assert verdict.outcome is Outcome.AGENT_FAILURE
    assert verdict.runs_reaching_end_state == 2


def test_a_product_disagreement_outranks_the_agent() -> None:
    surface = InvariantFailure(invariant="no_secret_offered", owner=FailureOwner.PRODUCT, detail="session tool")
    assert lane_verdict((_run(0, reached=True, failure=surface),), runs=1).outcome is Outcome.PRODUCT_FINDING
    disagreement = lane_verdict((_run(0, reached=True, oracle="export 07 != ledger"),), runs=1)
    assert disagreement.outcome is Outcome.PRODUCT_FINDING


def test_missing_runs_never_pass() -> None:
    assert lane_verdict((_run(0, reached=True), _run(1, reached=True)), runs=3).outcome is Outcome.HARNESS_ERROR


def test_unavailable_is_its_own_class_and_exit_code() -> None:
    verdict = unavailable_verdict(UnavailableError("credential_store_unavailable", "WinError 1312"), runs=3)
    assert verdict.outcome is Outcome.UNAVAILABLE
    assert verdict.exit_code == 3
    assert "WinError 1312" in verdict.reasons[0]
    assert len(set(EXIT_CODES.values())) == len(Outcome)


def test_the_required_count_is_two_of_three() -> None:
    assert [required_end_states(runs) for runs in (1, 2, 3, 6)] == [1, 2, 2, 4]
