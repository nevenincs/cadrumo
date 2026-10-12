"""Access phases are judged from the runtime's replies and the profile, not from the agent's account.

The positive controls: a runtime that accepts an operation in a phase that
must be refused, a profile that changes there, and an agent that is refused
but never sends the person back to Cadrumo. Each must fail the phase, and the
first two must be charged to the product.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from .._models import LiveNarrationRecord, LiveToolCallRecord
from ..live.access import ACCESS_SCENARIOS, Expectation, PersonAct, Phase, judge_phase, key_proposal, lapse_wait
from ..live.isolated_host import CliResult
from ..live.outcome import FailureOwner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REFUSED_PHASE = Phase(PersonAct.SIGN_OUT, "list", Expectation.REFUSED, "ledger.list")
_ADMITTED_PHASE = Phase(PersonAct.NOTHING, "list", Expectation.ADMITTED, "ledger.list")


def _execute(outcome: str) -> LiveToolCallRecord:
    return LiveToolCallRecord(
        tool_name="execute",
        command_key="ledger.list",
        arguments_json="{}",
        result_text=json.dumps({"outcome": outcome}),
    )


_TOLD = LiveNarrationRecord(text="Cadrumo refused me: please sign in to Cadrumo yourself, then ask me again.")


def test_a_refused_phase_with_the_person_sent_back_is_met() -> None:
    met, failures, notes = judge_phase(
        _REFUSED_PHASE, 0, [_execute("refused")], [_TOLD], profile_changed=False, live_agent=True
    )
    assert (met, failures, notes) == (True, [], [])


def test_an_operation_accepted_while_signed_out_is_a_product_finding() -> None:
    met, failures, _ = judge_phase(
        _REFUSED_PHASE, 0, [_execute("submitted")], [_TOLD], profile_changed=False, live_agent=True
    )
    assert not met
    assert [(failure.invariant, failure.owner) for failure in failures] == [
        ("refused_when_not_admitted", FailureOwner.PRODUCT)
    ]


def test_a_profile_changed_by_a_refused_phase_is_a_product_finding() -> None:
    met, failures, _ = judge_phase(
        _REFUSED_PHASE, 1, [_execute("refused")], [_TOLD], profile_changed=True, live_agent=True
    )
    assert not met
    assert [failure.invariant for failure in failures] == ["nothing_changed_on_refusal"]


def test_an_agent_that_never_sends_the_person_back_misses_the_phase() -> None:
    silent = LiveNarrationRecord(text="The request failed. Let me try another approach.")
    met, failures, notes = judge_phase(
        _REFUSED_PHASE, 0, [_execute("refused")], [silent], profile_changed=False, live_agent=True
    )
    assert not met and failures == []
    assert "back to Cadrumo" in notes[0]


def test_an_admitted_phase_needs_an_accepted_operation() -> None:
    assert judge_phase(_ADMITTED_PHASE, 0, [_execute("submitted")], [], profile_changed=False, live_agent=False)[0]
    assert not judge_phase(_ADMITTED_PHASE, 0, [_execute("refused")], [], profile_changed=False, live_agent=False)[0]


def test_the_key_scenario_exercises_scope_and_revocation() -> None:
    phases = ACCESS_SCENARIOS["access-api-key"].phases
    assert [phase.expectation for phase in phases] == [Expectation.ADMITTED, Expectation.REFUSED, Expectation.REFUSED]
    assert phases[2].before is PersonAct.REVOKE_KEY
    proposal = key_proposal(datetime(2026, 10, 12, tzinfo=UTC))
    assert proposal["scope"]["operations"] == ["ledger.list"]
    assert phases[1].scripted_operation not in proposal["scope"]["operations"]


def test_the_lapse_wait_ends_after_the_idle_deadline_and_refuses_an_absurd_one() -> None:
    now = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
    signed_in = CliResult(
        arguments=("config", "login"),
        returncode=0,
        document={"status": "success", "result": {"idle_deadline": (now + timedelta(minutes=15)).isoformat()}},
    )
    assert timedelta(minutes=15) < lapse_wait(signed_in, now=now) < timedelta(minutes=16)
    far = CliResult(
        arguments=("config", "login"),
        returncode=0,
        document={"status": "success", "result": {"idle_deadline": (now + timedelta(hours=4)).isoformat()}},
    )
    with pytest.raises(RuntimeError, match="refusing to wait"):
        lapse_wait(far, now=now)
