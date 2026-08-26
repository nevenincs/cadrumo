"""``counterparty view`` must reach the branch its own payload is justified by.

The show verb's payload docstring rests its whole design on the contradiction
path: it reports what the LADDER will answer rather than what the repository
holds, "because the resolver declines to return a fact the document's own
evidence contradicts, so a row can be stored and still settle nothing". That
sentence describes a branch the verb could not reach. The resolver raises a
contradiction only when an evidenced territory is supplied, and the verb passed
none -- so it asked the repository question while its record claimed the ladder
question, and the two answers differ in exactly the case the verb exists for.

The operator consequence is the point. Someone who confirmed one territory and
then holds a document printing another was shown the confirmed value, plainly,
with nothing indicating that a confirm against that document would refuse to
use it and raise a blocker instead. Two surfaces disagreeing about the same
counterparty, with the disagreement visible only from the one that refuses.

Every case drives the real Typer tree against a real encrypted bucket session.
No mocks, stubs or monkeypatch. What is asserted is the verb's own contract --
which question it asked, and whether the answer distinguishes the three states a
consumer must act on differently -- never a tax figure, which this verb does not
compute.

See Also:
    :func:`~application.ledger.counterparty_establishment.resolve_confirmed_counterparty_facts`
        The single resolver both this verb and the ladder ask.
    :class:`~entrypoints.cli._ledger_counterparty_payloads.CounterpartyViewResult`
        The payload whose three-state contract is pinned here.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from ....tests.cli_envelope import unwrap_schema_envelope
from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

if TYPE_CHECKING:
    from pathlib import Path

_COUNTERPARTY_CIF = "B12345674"
_CONFIRMED = "es_canarias"
_EVIDENCED = "es_mainland"


def _show(*args: str) -> dict[str, object]:
    """Run ``counterparty view`` through the real CLI and return its result payload."""
    result = _invoke(["--format", "json", "app", "ledger", "counterparty", "view", *args])
    assert result.exit_code == 0, result.output
    raw_payload = unwrap_schema_envelope(result.output)
    payload: dict[str, object] = {}
    for key, value in raw_payload.items():
        assert isinstance(key, str), result.output
        payload[key] = value
    return payload


def _confirm_canarias() -> None:
    """Record the operator's answer through the real confirm verb, not the store."""
    recorded = _invoke(
        [
            "app",
            "ledger",
            "counterparty",
            "confirm",
            _COUNTERPARTY_CIF,
            "--scope",
            _CONFIRMED,
        ],
    )
    assert recorded.exit_code == 0, recorded.output


def test_the_bare_question_reports_what_is_confirmed(tmp_path: Path) -> None:
    """Asked with no document in hand, the verb answers the narrower question.

    This is the honest baseline rather than a degraded mode: with no evidence
    there is nothing for a confirmed fact to contradict, so what the rung holds
    and what it will answer are the same value. The payload says which question
    was asked by carrying no evidenced territory.
    """
    with _open_ledger_ux_session(tmp_path):
        _confirm_canarias()
        shown = _show(_COUNTERPARTY_CIF)

    assert shown["confirmed"] is True
    assert shown["territorial_scope"] == _CONFIRMED
    assert shown["evidenced_scope"] is None
    assert shown["contradicted"] is False


def test_evidence_disagreeing_with_the_confirmation_is_visible_before_a_confirm(
    tmp_path: Path,
) -> None:
    """The branch the payload's design cites, now reachable from the verb.

    The operator confirmed one territory and holds a document placing the same
    party in another. Before this option existed the verb reported the confirmed
    value and said nothing, while a confirm against that document would settle no
    territory at all and raise a blocker -- the divergence the row names.
    """
    with _open_ledger_ux_session(tmp_path):
        _confirm_canarias()
        shown = _show(_COUNTERPARTY_CIF, "--evidenced-scope", _EVIDENCED)

    assert shown["contradicted"] is True
    assert shown["evidenced_scope"] == _EVIDENCED
    assert shown["confirmed_scope"] == _CONFIRMED
    assert shown["contradiction_detail"]
    # The rung settles nothing on a contradiction, and the payload must not
    # offer the confirmed territory in the field that means "what it will
    # answer" -- a consumer reading it there would use a value no document
    # resolves to.
    assert shown["territorial_scope"] is None
    assert shown["confirmed"] is False


def test_a_contradiction_is_distinguishable_from_an_unanswered_counterparty(
    tmp_path: Path,
) -> None:
    """The two states that share every other field must not read alike.

    Both produce ``confirmed: false`` and a null territory, because the resolver
    withholds a fact in both cases. Their remedies are opposite -- one wants a
    first answer, the other wants one of two existing claims withdrawn -- so a
    payload that could not separate them would send an operator to the wrong
    verb. This is the assertion that makes ``contradicted`` load-bearing rather
    than decorative.
    """
    with _open_ledger_ux_session(tmp_path):
        never_asked = _show("B98765674", "--evidenced-scope", _EVIDENCED)
        _confirm_canarias()
        contradicted = _show(_COUNTERPARTY_CIF, "--evidenced-scope", _EVIDENCED)

    assert never_asked["confirmed"] == contradicted["confirmed"] is False
    assert never_asked["territorial_scope"] == contradicted["territorial_scope"] is None
    assert never_asked["contradicted"] is False
    assert contradicted["contradicted"] is True


def test_agreeing_evidence_leaves_the_confirmed_answer_standing(tmp_path: Path) -> None:
    """The other direction: matching evidence must not be reported as a conflict.

    A guard that fired whenever evidence was supplied would make the option
    useless and train an operator to stop passing it. Supplying the SAME
    territory the operator confirmed is the commonest real use -- checking a
    document against a remembered answer -- and it must come back clean with the
    fact intact.
    """
    with _open_ledger_ux_session(tmp_path):
        _confirm_canarias()
        shown = _show(_COUNTERPARTY_CIF, "--evidenced-scope", _CONFIRMED)

    assert shown["contradicted"] is False
    assert shown["confirmed"] is True
    assert shown["territorial_scope"] == _CONFIRMED
    assert shown["evidenced_scope"] == _CONFIRMED


def test_the_contradiction_reaches_the_operator_through_the_notice_channel(
    tmp_path: Path,
) -> None:
    """A disagreement is a diagnostic, so it rides the shared envelope spine.

    Asserted on the envelope rather than on the result body: the CLI contract
    routes operator-facing diagnostics through the typed notice channel and
    forbids a bespoke advisory field inside ``result``. A warning severity is
    what lifts the envelope status, so the disagreement is visible to a caller
    that reads only the spine.
    """
    with _open_ledger_ux_session(tmp_path):
        _confirm_canarias()
        result = _invoke(
            [
                "--format",
                "json",
                "app",
                "ledger",
                "counterparty",
                "view",
                _COUNTERPARTY_CIF,
                "--evidenced-scope",
                _EVIDENCED,
            ],
        )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)

    codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert "ledger.counterparty.evidence_contradicts_confirmation" in codes, envelope
    severities = {
        notice["severity"]
        for notice in envelope["notices"]
        if notice["code"] == "ledger.counterparty.evidence_contradicts_confirmation"
    }
    assert severities == {"warning"}, envelope


def test_an_unknown_territory_is_refused_with_the_accepted_set(tmp_path: Path) -> None:
    """The option declares its enum, so a typo lists what is accepted.

    The CLI contract requires a closed-value option to carry its enum as the
    Typer type rather than validating late, precisely so a parse failure names
    the accepted set instead of refusing bare. Pinned because the value of the
    option depends on an operator being able to discover the vocabulary.
    """
    with _open_ledger_ux_session(tmp_path):
        result = _invoke(
            ["app", "ledger", "counterparty", "view", _COUNTERPARTY_CIF, "--evidenced-scope", "canarias"],
        )

    assert result.exit_code != 0
    assert "es_canarias" in result.output, result.output


def test_the_identification_an_operator_confirmed_is_readable(tmp_path: Path) -> None:
    """A settable fact must be readable, or it cannot be reviewed or corrected.

    ``--identification-state`` was accepted by confirm while show emitted the
    territorial side alone, so the value could be written and never read back.
    A write-only fact at the operator boundary is worse than an absent one: it
    cannot be told apart from a value nobody supplied.
    """
    with _open_ledger_ux_session(tmp_path):
        recorded = _invoke(
            [
                "app",
                "ledger",
                "counterparty",
                "confirm",
                _COUNTERPARTY_CIF,
                "--scope",
                _CONFIRMED,
                "--identification-state",
                "de",
            ],
        )
        assert recorded.exit_code == 0, recorded.output
        shown = _show(_COUNTERPARTY_CIF)

    assert shown["identification_state"] == "de"
    assert shown["identification_source"] is not None


def test_an_unconfirmed_identification_reads_as_absent_not_as_a_default(tmp_path: Path) -> None:
    """The control. Without it the field could be reporting a constant.

    Confirming only a territory must leave the identification empty rather than
    inventing one, which is the same refusal every rung on this axis makes: an
    unstated fact is absent, never a default.
    """
    with _open_ledger_ux_session(tmp_path):
        _confirm_canarias()
        shown = _show(_COUNTERPARTY_CIF)

    assert shown["identification_state"] is None
    assert shown["territorial_scope"] == _CONFIRMED


def test_an_identification_can_be_confirmed_without_a_territory(tmp_path: Path) -> None:
    """The two facts are independent, so either may be answered alone.

    An operator may know which State IVA-identifies a counterparty without
    knowing where it is established -- that is the whole reason the axis was
    split -- and requiring the territory made the half they knew unrecordable.
    """
    with _open_ledger_ux_session(tmp_path):
        recorded = _invoke(
            [
                "app",
                "ledger",
                "counterparty",
                "confirm",
                _COUNTERPARTY_CIF,
                "--identification-state",
                "fr",
            ],
        )
        assert recorded.exit_code == 0, recorded.output
        shown = _show(_COUNTERPARTY_CIF)

    assert shown["identification_state"] == "fr"


def test_an_unanswered_territory_settles_nothing_and_never_defaults(tmp_path: Path) -> None:
    """The load-bearing half. Absence must mean not asked, never Spain.

    The mainland is the majority answer, so a default there is invisible in
    testing while placing Canarian and Ceutan counterparties inside a territory
    their operations are not subject to. A record answering only the
    identification must leave the rung settling nothing.
    """
    with _open_ledger_ux_session(tmp_path):
        _invoke(
            [
                "app",
                "ledger",
                "counterparty",
                "confirm",
                _COUNTERPARTY_CIF,
                "--identification-state",
                "fr",
            ],
        )
        shown = _show(_COUNTERPARTY_CIF)

    assert shown["territorial_scope"] is None
    assert shown["confirmed"] is False


def test_a_confirmation_asserting_neither_fact_is_refused(tmp_path: Path) -> None:
    """An empty record is worse than no record.

    It addresses a counterparty, occupies the key, and answers every later
    question with a silence that reads as a confirmed absence. The refusal names
    both flags, so an operator who supplied neither learns what either would do.
    """
    with _open_ledger_ux_session(tmp_path):
        refused = _invoke(
            ["app", "ledger", "counterparty", "confirm", _COUNTERPARTY_CIF],
        )

    assert refused.exit_code != 0
    assert "--identification-state" in refused.output


def test_a_territory_only_confirmation_still_works(tmp_path: Path) -> None:
    """Positive control on the relaxation: the original shape is unaffected."""
    with _open_ledger_ux_session(tmp_path):
        _confirm_canarias()
        shown = _show(_COUNTERPARTY_CIF)

    assert shown["confirmed"] is True
    assert shown["territorial_scope"] == _CONFIRMED
    assert shown["identification_state"] is None
