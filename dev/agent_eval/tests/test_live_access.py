"""Access phases are judged from the runtime's replies and the profile, not from the agent's account.

The positive controls: a runtime that accepts an operation in a phase that
must be refused, a profile that changes there, and an agent that is refused
but never sends the person back to Cadrumo. Each must fail the phase, and the
first two must be charged to the product.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.application.operations.registry import OperationPublicContractSetV1
from cadrumo.application.user_profile.access_contracts import DisclosureCategory
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo_harness.access.automation_key import agent_key_scope

from .._models import LiveNarrationRecord, LiveToolCallRecord
from ..live.access import (
    ACCESS_SCENARIOS,
    NAME_PATH,
    PLANTED_NAME,
    AccessScenario,
    Expectation,
    PersonAct,
    Phase,
    ProfileValue,
    Tell,
    judge_phase,
    lapse_wait,
    read_profile_facts,
)
from ..live.capture import Scrubber
from ..live.isolated_host import CliResult, Person, mcp_launch
from ..live.outcome import FailureOwner
from ..live.recorder import TrajectoryRecorder

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


_NAME = "Daniel"
_READ_PHASE = Phase(PersonAct.NOTHING, "read", Expectation.ADMITTED, "user-profile.view", ProfileValue.READ)
_WRITE_PHASE = Phase(PersonAct.NOTHING, "write", Expectation.ADMITTED, "user-profile.patch", ProfileValue.WRITE)
_WITHHELD_PHASE = Phase(PersonAct.NOTHING, "history", Expectation.WITHHELD, "profile.history", tell=Tell.ACT)
_REVOKED_PHASE = Phase(PersonAct.REVOKE_KEY, "again", Expectation.REFUSED, "user-profile.view", tell=Tell.ACT)


def _call(tool: str, outcome: str, text: str = "", *, is_error: bool = False) -> LiveToolCallRecord:
    return LiveToolCallRecord(
        tool_name=tool,
        command_key="user-profile.view" if tool == "execute" else "",
        arguments_json="{}",
        is_error=is_error,
        result_text=json.dumps({"outcome": outcome, "text": text}),
    )


def _read_calls(carried: str) -> list[LiveToolCallRecord]:
    return [_call("execute", "submitted"), _call("result", "reply", carried)]


def test_the_key_scenario_reads_writes_is_withheld_and_is_revoked() -> None:
    scenario = ACCESS_SCENARIOS["access-api-key"]
    assert scenario.uses_key
    assert [(phase.expectation, phase.value) for phase in scenario.phases] == [
        (Expectation.ADMITTED, ProfileValue.READ),
        (Expectation.ADMITTED, ProfileValue.WRITE),
        (Expectation.WITHHELD, ProfileValue.NONE),
        (Expectation.REFUSED, ProfileValue.NONE),
    ]
    assert scenario.phases[-1].before is PersonAct.REVOKE_KEY
    assert [phase.tell for phase in scenario.phases[2:]] == [Tell.ACT, Tell.ACT]
    assert scenario.key_categories == ()
    assert PLANTED_NAME in scenario.phases[1].task


def test_the_key_is_issued_for_an_agent_without_tax_values() -> None:
    definitions = build_user_profile_operation_definitions()
    contracts = OperationPublicContractSetV1.build(
        tuple(
            item.contract
            for item in build_user_profile_operation_registrations(definitions)
            if item.contract.definition_id == "user-profile.view"
        )
    )
    scope = agent_key_scope(
        contracts, tuple(DisclosureCategory(item) for item in ACCESS_SCENARIOS["access-api-key"].key_categories)
    )
    assert scope.categories == frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.OPERATION_METADATA})
    with_tax = AccessScenario("x", uses_key=True, phases=(), key_categories=("tax_values",))
    tax_scope = agent_key_scope(contracts, tuple(DisclosureCategory(item) for item in with_tax.key_categories))
    assert tax_scope.categories == frozenset(
        {DisclosureCategory.PROFILE_VALUES, DisclosureCategory.OPERATION_METADATA, DisclosureCategory.TAX_VALUES}
    )


def test_the_agent_is_launched_with_the_profile_and_the_key_reference_only() -> None:
    host = SimpleNamespace(mcp_image=Path("cadrumo-mcp.exe"), environment={"PATH": "x"})
    command, arguments, environment = mcp_launch(host, profile_id="profile-1", credential_reference="ref-1")
    assert command == "cadrumo-mcp.exe"
    assert tuple(arguments) == ("--profile-id", "profile-1", "--credential-reference", "ref-1")
    assert environment == {"PATH": "x"}


def test_a_value_read_through_the_key_matching_the_command_line_meets_the_phase() -> None:
    narrated = [LiveNarrationRecord(text=f"Your name is {_NAME}.")]
    met, failures, _ = judge_phase(
        _READ_PHASE, 0, _read_calls(_NAME), narrated, profile_changed=False, live_agent=True, name_before=_NAME
    )
    assert met and failures == []


def test_a_released_result_that_lacks_the_value_is_a_product_finding() -> None:
    met, failures, _ = judge_phase(
        _READ_PHASE, 0, _read_calls("Someone Else"), [], profile_changed=False, live_agent=False, name_before=_NAME
    )
    assert not met
    assert [(failure.invariant, failure.owner) for failure in failures] == [
        ("profile_value_read_back", FailureOwner.PRODUCT)
    ]


def test_an_agent_that_misstates_the_value_it_read_misses_the_phase() -> None:
    narrated = [LiveNarrationRecord(text="Your name is Someone Else.")]
    met, failures, notes = judge_phase(
        _READ_PHASE, 0, _read_calls(_NAME), narrated, profile_changed=False, live_agent=True, name_before=_NAME
    )
    assert not met and failures == []
    assert "did not tell the person" in notes[0]


def test_a_write_the_command_line_does_not_show_is_a_product_finding() -> None:
    calls = [_call("execute", "submitted"), _call("result", "reply", "changed")]
    met, failures, _ = judge_phase(
        _WRITE_PHASE, 1, calls, [], profile_changed=False, live_agent=False, name_before=_NAME, name_after=_NAME
    )
    assert not met
    assert [failure.invariant for failure in failures] == ["profile_value_written"]
    met, failures, _ = judge_phase(
        _WRITE_PHASE,
        1,
        calls,
        [LiveNarrationRecord(text=f"The name is now {PLANTED_NAME}.")],
        profile_changed=False,
        live_agent=True,
        name_before=_NAME,
        name_after=PLANTED_NAME,
    )
    assert met and failures == []


def test_a_tax_value_released_to_a_key_without_tax_values_is_a_product_finding() -> None:
    told = [LiveNarrationRecord(text="I was refused: please approve tax value access in Cadrumo, then ask again.")]
    leaked = [_call("execute", "submitted"), _call("result", "reply", "tax")]
    met, failures, _ = judge_phase(_WITHHELD_PHASE, 2, leaked, told, profile_changed=False, live_agent=True)
    assert not met
    assert [(failure.invariant, failure.owner) for failure in failures] == [
        ("withheld_without_category", FailureOwner.PRODUCT)
    ]
    withheld = [_call("execute", "submitted"), _call("result", "refused", is_error=True)]
    met, failures, _ = judge_phase(_WITHHELD_PHASE, 2, withheld, told, profile_changed=False, live_agent=True)
    assert met and failures == []


def test_a_withheld_phase_where_nothing_was_refused_is_not_met() -> None:
    calls = [_call("execute", "submitted")]
    met, _, notes = judge_phase(_WITHHELD_PHASE, 2, calls, [], profile_changed=False, live_agent=False)
    assert not met
    assert "never refused" in notes[0]


def test_a_refusal_after_revocation_needs_the_person_sent_to_act_in_cadrumo() -> None:
    refused = [_call("execute", "refused", is_error=True)]
    quiet = [LiveNarrationRecord(text="That did not work. I will try something else.")]
    met, _, notes = judge_phase(_REVOKED_PHASE, 3, refused, quiet, profile_changed=False, live_agent=True)
    assert not met and "back to Cadrumo" in notes[0]
    told = [LiveNarrationRecord(text="My key was refused. Please approve a new key in Cadrumo and ask me again.")]
    assert judge_phase(_REVOKED_PHASE, 3, refused, told, profile_changed=False, live_agent=True)[0]
    accepted = [_call("execute", "submitted")]
    _, failures, _ = judge_phase(_REVOKED_PHASE, 3, accepted, told, profile_changed=False, live_agent=True)
    assert [failure.invariant for failure in failures] == ["refused_when_not_admitted"]


def test_a_planted_secret_in_a_key_phase_is_refused_by_the_recorder() -> None:
    planted = "Live-eval-planted-secret!"
    recorder = TrajectoryRecorder(scrubber=Scrubber((("profile_secret", planted),)), known_secrets=(planted,))
    recorder.record_call("execute", {"payload": {"values": [{"value": planted}]}}, "{}", is_error=False, duration_ms=1)
    recorder.record_call("result", {}, json.dumps({"document": planted}), is_error=False, duration_ms=1)
    assert [failure.invariant for failure in recorder.failures] == [
        "no_secret_in_tool_call",
        "no_secret_in_tool_result",
    ]
    assert planted not in recorder.calls[0].arguments_json + recorder.calls[1].result_text


class _Host:
    def __init__(self, document: dict[str, object], *, ok: bool = True) -> None:
        self._result = CliResult(
            arguments=("config", "profile", "view"),
            returncode=0 if ok else 1,
            document=document if ok else {"status": "error", "error": {"code": "PROFILE_UNREADABLE"}},
        )

    def cli(self, *arguments: str, profile_secret: str | None = None) -> CliResult:
        assert arguments == ("config", "profile", "view")
        return self._result


def test_the_oracle_reads_the_profile_facts_through_the_command_line() -> None:
    facts = [{"path": NAME_PATH, "value": _NAME}, {"path": "a.b", "value": "c"}]
    stated = "synthetic-profile-text"
    person = Person(profile_id="p", password=stated)
    assert read_profile_facts(_Host({"status": "success", "result": {"facts": facts}}), person) == {
        NAME_PATH: _NAME,
        "a.b": "c",
    }
    with pytest.raises(RuntimeError, match="could not be read back"):
        read_profile_facts(_Host({}, ok=False), person)


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
