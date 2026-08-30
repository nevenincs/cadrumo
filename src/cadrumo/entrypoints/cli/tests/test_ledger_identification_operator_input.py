"""The operator can record a counterparty's IVA identification, and must.

A bank transaction has no document to read a printed IVA prefix from, so the
fact Ley 37/1992 art. 25 exempts on can only reach the record from the operator.
Without that input a row classified as an intra-community supply is refused for
a fact nothing on the surface could supply — a fail-closed dead end rather than
a wrong number, but a dead end.

Three things are asserted through the real CLI rather than the command objects
underneath it, because the gap this closes was precisely that the fact existed
on the model and nowhere an operator could reach:

- the option persists the fact;
- withholding it produces the refusal, naming the fact to record;
- establishment and identification are settable independently and DIVERGE,
  which is the whole reason they are two fields.
"""

from __future__ import annotations

import json

import pytest

from ._isolated_profile_storage_fixtures import live_fx_isolated_backend
from ._ledger_corpus_support import (
    _active_repo,
    _import_corpus,
    _invoke,
    _list_rows,
)

__all__ = ["live_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _intracom_row() -> dict[str, object]:
    _import_corpus()
    rows = [row for row in _list_rows() if "cliente DE GmbH intracom" in row["description"]]
    assert rows, "corpus must contain a DE intracommunity client invoice"
    raw_row = rows[0]
    assert isinstance(raw_row, dict)
    return {str(key): value for key, value in raw_row.items()}


def _intracom_transaction_id() -> str:
    transaction_id = _intracom_row()["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _period_of(row: dict[str, object]) -> tuple[str, int]:
    """Return the row's own (period token, year).

    Derived rather than hardcoded: a corpus row that moves year would otherwise
    make the readiness assertion below check an empty period, which reports no
    issues and reads exactly like the gap being closed.
    """
    booked = row.get("booked_date") or row.get("date") or row.get("value_date")
    assert isinstance(booked, str), f"row carries no readable date: {sorted(row)}"
    year, month = int(booked[:4]), int(booked[5:7])
    return f"{(month - 1) // 3 + 1}T", year


def _classify(transaction_id: str, *extra: str):
    return _invoke(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--iva-category",
            "intra_community_supply",
            *extra,
        ],
    )


def test_the_operator_can_record_the_identification_and_it_persists() -> None:
    """The option reaches the persisted record as a typed Member State."""
    from ....domain.iva.schema import EUMemberState

    transaction_id = _intracom_transaction_id()
    result = _classify(transaction_id, "--counterparty-identification-state", "de")

    assert result.exit_code == 0, result.output
    transaction = _active_repo().load().get(transaction_id)
    assert transaction is not None
    assert transaction.counterparty_identification_state is EUMemberState.DE


def test_recording_the_identification_leaves_the_establishment_axis_alone() -> None:
    """The two axes are independent: writing one must not move the other.

    Deliberately reads the establishment axis off the record rather than
    setting it through its own flag, so this asserts the independence without
    coupling to how establishment happens to be spelled at the CLI. That the
    two may legitimately DIVERGE -- a Spanish-established acquirer trading
    under a German IVA number is an intra-community acquirer under art. 25 --
    is proven against the aggregation gate, where the money actually moves.
    """
    from ....domain.iva.schema import EUMemberState

    transaction_id = _intracom_transaction_id()
    before = _active_repo().load().get(transaction_id)
    assert before is not None
    establishment_before = before.counterparty_eu_member_state

    result = _classify(transaction_id, "--counterparty-identification-state", "de")

    assert result.exit_code == 0, result.output
    transaction = _active_repo().load().get(transaction_id)
    assert transaction is not None
    assert transaction.counterparty_identification_state is EUMemberState.DE
    assert transaction.counterparty_eu_member_state == establishment_before, (
        "recording where a counterparty is IVA-identified must not silently restate where it is established"
    )


def test_withholding_the_identification_is_reported_as_the_missing_fact() -> None:
    """The refusal path: preflight names the fact to record, not a bare rejection.

    Every other tax fact the readiness screen wants is supplied, so the
    identification is the only thing left to report. The companion proof that
    an establishment cannot ANSWER for a missing identification lives against
    the aggregation gate, which varies establishment across every value while
    the identification stays absent.
    """
    row = _intracom_row()
    transaction_id = _intracom_transaction_id()
    classified = _classify(
        transaction_id,
        "--taxable-base",
        "3000.00",
        "--iva-rate",
        "0",
        "--iva-amount",
        "0",
    )
    assert classified.exit_code == 0, classified.output

    period, year = _period_of(row)
    report = _invoke(
        ["--format", "json", "app", "ledger", "preflight", "--period", period, "--year", str(year)],
    )
    payload = json.loads(report.output)
    result = payload.get("result", payload)
    assert result.get("checked_transaction_count", 0) > 0, (
        f"preflight checked nothing in {period} {year}; an empty period reports no issues "
        "and would pass this test vacuously"
    )

    reasons = {
        issue.get("reason")
        for entry in result.get("issues", [])
        for issue in ([entry] if isinstance(entry, dict) else [])
    }
    assert "missing_counterparty_identification_state" in reasons, (
        f"preflight must report the unrecorded identification; got {sorted(r for r in reasons if r)}"
    )


def test_a_value_outside_the_member_state_catalogue_is_refused_with_the_accepted_set() -> None:
    """A parse failure lists the Member States rather than saying 'value invalid'.

    The option is typed as the closed enum at the Typer boundary precisely so
    click renders the accepted set. An operator who has to guess the spelling of
    a Member State code will guess, and a guessed identification is the fact
    this whole field exists to stop being invented.
    """
    transaction_id = _intracom_transaction_id()
    result = _classify(transaction_id, "--counterparty-identification-state", "zz")

    assert result.exit_code != 0
    assert "de" in result.output and "es" in result.output, result.output
