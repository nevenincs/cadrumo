"""The operator's answer must reach the ladder, not merely reach the store.

The recording function was complete, gated and unreachable: it had no production
caller and no operator surface, so the last rung of the establishment ladder --
"what has the operator already confirmed about this counterparty" -- could be
read and never written. This file is the gate over the channel that closes it,
and it is deliberately written as a LOOP rather than as a persistence check.

**Why a persistence assertion would not have been enough.** A test that invokes
the verb and then reads the store proves the verb writes. That is exactly the
property the unreachable function already had: its own suite proved it wrote,
for a year, while nothing called it. The question this file has to answer is
different -- does a real operator invocation change what the LADDER answers for
the next document? So the assertions run the verb through the CLI and then ask
the ladder, which is the consumer the design turns on.

**The identifier is positional and the retry is a no-op**, both of which are
contract rather than taste: the subject of a single-subject verb is an argument
while flags configure the operation, and this CLI's operator is an agent that
retries, so a creating verb that wrote twice would double-answer a question the
operator answered once.

Real CLI, real encrypted profile store, real ladder. Nothing is stubbed.

See Also:
    :func:`~application.ledger.establishment_ladder.resolve_draft_counterparty_establishment`
        The ladder these tests interrogate after the verb has run.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from click.testing import Result

from ....domain.iva import EUMemberState, IvaTerritorialScope
from ._cli_surface_profile_fixture import _isolated_backend
from ._cli_surface_support import (
    _invoke,
)

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A structurally valid Spanish CIF. The domestic population this channel
#: exists for: a bare identifier with no country and no postal evidence, which
#: every printed rung declines to answer.
_SUPPLIER_CIF = "B12345674"


def _confirm(*args: str):
    return _invoke(["app", "ledger", "counterparty", "confirm", *args])


def _confirm_json(*args: str):
    return _invoke(["--format", "json", "app", "ledger", "counterparty", "confirm", *args])


def _payload(result: Result) -> dict[str, Any]:
    """Parse the JSON envelope the CLI wrote to stdout.

    ``Any`` is what a parsed envelope genuinely is at this boundary: the
    ``result`` payload differs per verb, so a single annotation here would
    have to describe every command's schema at once.
    """
    return json.loads(result.output)


def _notice_codes(result: Result) -> set[str]:
    return {notice["code"] for notice in _payload(result).get("notices", [])}


def _ladder_scope() -> str | None:
    """Ask what the ladder's last rung will answer, through the operator surface.

    Deliberately routed through ``show`` rather than by constructing a repository
    in the test. Reaching past the contract would prove the store holds a row
    while leaving the question this file exists for -- does the answer reach the
    consumer -- assumed rather than measured. ``show`` asks the same resolver the
    ladder asks, so what it reports and what the next document resolves to cannot
    differ.
    """
    result = _invoke(["--format", "json", "app", "ledger", "counterparty", "show", _SUPPLIER_CIF])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, dict), result.output
    body = payload.get("result")
    assert isinstance(body, dict), result.output
    confirmed = body.get("confirmed")
    assert isinstance(confirmed, bool), result.output
    if not confirmed:
        return None
    scope = body.get("territorial_scope")
    assert isinstance(scope, str), result.output
    return scope


def test_the_ladder_answers_nothing_before_the_operator_does() -> None:
    """The precondition, and the reason the whole channel exists.

    Without this the closing assertion below would pass against a store that had
    always answered, and the file would prove nothing about the verb.
    """
    assert _ladder_scope() is None


def test_an_operator_answer_reaches_the_ladder() -> None:
    """The loop, end to end: CLI invocation in, ladder answer out.

    This is the assertion the row exists for. It deliberately does not read the
    repository: writing to a store nothing consults is the defect being closed,
    so the check has to be made at the consumer.
    """
    result = _confirm(_SUPPLIER_CIF, "--scope", IvaTerritorialScope.ES_CANARIAS.value)

    assert result.exit_code == 0, result.output
    assert _ladder_scope() == IvaTerritorialScope.ES_CANARIAS.value


def test_the_subject_is_positional() -> None:
    """A single-subject verb takes its subject as an argument, never as an option."""
    rejected = _confirm("--id", _SUPPLIER_CIF, "--scope", IvaTerritorialScope.ES_MAINLAND.value)

    assert rejected.exit_code != 0


def test_a_retry_is_a_no_op_that_says_so() -> None:
    """Idempotent on the whole record, and the operator is told it was a repeat.

    A retrying agent must not be able to turn one answer into two, and must not
    be left inferring from an unchanged timestamp that nothing happened.
    """
    first = _confirm_json(_SUPPLIER_CIF, "--scope", IvaTerritorialScope.EU_MEMBER.value)
    assert first.exit_code == 0, first.output
    assert _payload(first)["result"]["recorded"] is True

    again = _confirm_json(_SUPPLIER_CIF, "--scope", IvaTerritorialScope.EU_MEMBER.value)

    assert again.exit_code == 0, again.output
    payload = _payload(again)
    assert payload["result"]["recorded"] is False
    assert "ledger.counterparty.already_confirmed" in _notice_codes(again)
    # The provenance the FIRST call stamped has to survive, or a repeat would
    # read in an audit as a fresh confirmation the operator never made.
    assert payload["result"]["counterparty"]["asserted_at"] == _payload(first)["result"]["counterparty"]["asserted_at"]


def test_a_conflicting_answer_refuses_and_names_the_route_out() -> None:
    """A second, different answer must not silently reclassify earlier invoices.

    The refusal names ``withdraw`` — and that verb ships, which is why this
    asserts the instruction rather than only the refusal. An error naming a
    command that does not exist is a dead end wearing the shape of guidance.
    """
    assert _confirm(_SUPPLIER_CIF, "--scope", IvaTerritorialScope.ES_CANARIAS.value).exit_code == 0

    conflicted = _confirm(_SUPPLIER_CIF, "--scope", IvaTerritorialScope.THIRD_COUNTRY.value)

    assert conflicted.exit_code != 0
    assert "withdraw" in conflicted.output
    # The stored answer is untouched by the refused call.
    assert _ladder_scope() == IvaTerritorialScope.ES_CANARIAS.value


def test_withdrawing_reopens_the_question_so_a_correction_can_land() -> None:
    """The correction path, run end to end rather than asserted as available.

    Withdraw is the sanctioned way to say the earlier answer was wrong, and the
    proof it works is that the ladder goes back to answering nothing and then
    accepts the corrected answer.
    """
    assert _confirm(_SUPPLIER_CIF, "--scope", IvaTerritorialScope.ES_CANARIAS.value).exit_code == 0

    withdrawn = _invoke(["app", "ledger", "counterparty", "withdraw", _SUPPLIER_CIF])

    assert withdrawn.exit_code == 0, withdrawn.output
    assert _ladder_scope() is None

    assert _confirm(_SUPPLIER_CIF, "--scope", IvaTerritorialScope.ES_MAINLAND.value).exit_code == 0
    assert _ladder_scope() == IvaTerritorialScope.ES_MAINLAND.value


def test_withdrawing_nothing_is_a_successful_no_op() -> None:
    """A retry after a partial failure must not be worse than the first attempt."""
    result = _invoke(["--format", "json", "app", "ledger", "counterparty", "withdraw", _SUPPLIER_CIF])

    assert result.exit_code == 0, result.output
    assert _payload(result)["result"]["withdrawn"] is False
    assert "ledger.counterparty.nothing_to_withdraw" in _notice_codes(result)


def test_an_unverifiable_identifier_refuses_rather_than_storing_a_key_for_nothing() -> None:
    """There is no counterparty to answer for, so there is nothing to confirm."""
    result = _confirm("not-a-tax-id", "--scope", IvaTerritorialScope.ES_MAINLAND.value)

    assert result.exit_code != 0


def test_an_identification_only_conflict_refuses_instead_of_raising() -> None:
    """The refusal must survive the axis the operator did NOT answer.

    Establishment and IVA-identification are independent axes and either may
    stand alone, so a conflict is reachable with no ``--scope`` in the call at
    all. The refusal path read the unanswered axis to name what was asserted,
    which raises on the very invocation that most needs the instruction --
    an operator correcting only an identification State was met with a crash
    instead of the withdraw route.
    """
    assert _confirm(_SUPPLIER_CIF, "--identification-state", EUMemberState.DE.value).exit_code == 0

    conflicted = _confirm(_SUPPLIER_CIF, "--identification-state", EUMemberState.FR.value)

    assert conflicted.exit_code != 0
    # The route out, not merely a non-zero status: a refusal naming no
    # correction is the shape this surface exists to avoid.
    assert "withdraw" in conflicted.output
    # Both values are named, so the operator can see which answer is being kept.
    assert EUMemberState.DE.value in conflicted.output
    assert EUMemberState.FR.value in conflicted.output


def test_an_identification_only_retry_reports_the_stored_answer() -> None:
    """The no-op notice must describe a confirmation carrying no territory.

    The already-confirmed notice rendered the stored territory unconditionally,
    so an identification-only confirmation raised on the retry that was supposed
    to be the safe path. A retrying agent is this CLI's operator, so the no-op
    branch is the more-travelled one, not the edge.
    """
    assert _confirm(_SUPPLIER_CIF, "--identification-state", EUMemberState.DE.value).exit_code == 0

    again = _confirm_json(_SUPPLIER_CIF, "--identification-state", EUMemberState.DE.value)

    assert again.exit_code == 0, again.output
    assert _payload(again)["result"]["recorded"] is False
    assert "ledger.counterparty.already_confirmed" in _notice_codes(again)
    # The unanswered axis is absent rather than reported as a stored blank.
    notice = next(
        item for item in _payload(again)["notices"] if item["code"] == "ledger.counterparty.already_confirmed"
    )
    assert notice["context"]["identification_state"] == EUMemberState.DE.value
    assert "territorial_scope" not in notice["context"]


def test_the_accepted_scopes_are_offered_on_a_parse_failure() -> None:
    """The closed axis is declared at the boundary, so click can name the set.

    A late registry-driven refusal would be acceptable for a dynamic axis; this
    one is a closed enum, so an operator who mistypes it should be shown what
    was allowed rather than told the value was invalid.
    """
    result = _confirm(_SUPPLIER_CIF, "--scope", "canarias")

    assert result.exit_code != 0
    assert IvaTerritorialScope.ES_CANARIAS.value in result.output
