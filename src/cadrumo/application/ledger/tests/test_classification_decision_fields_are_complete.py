"""The one set of tax-bearing facts covers everything a ledger write can set.

Whose decision a row's classification is turns on one declared set of fields.
A field a write can set and the set does not name is a hole in the record: a
party sets it and the row does not record that party as the one who decided.
So every field the ledger's command can carry is required to be either in the
set or declared here as bearing on no tax, with its reason, and the request
models of classification, bulk classification and update are held inside the
two. A field added to any of them reddens this until it is placed.

The exclusions are checked against an independent reading: the filing
snapshot's fingerprint of a row's tax facts does not move when one changes.
The set is wider than that fingerprint by the link to purchase-invoice
evidence, which the fingerprint leaves out and a calculation reads: the linked
invoice supplies the row's figures.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from ....domain.transactions.classification_origin import CLASSIFICATION_DECISION_FIELDS, classification_facts
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...aggregation.ledger_filing_snapshot import row_fingerprint
from ..classify_requests import LedgerClassifyPatch
from ..models import BulkClassifyRow, ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ..update_contracts import LedgerUpdatePatch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_NOT_A_ROW_FACT: dict[str, str] = {
    "bucket_id": "scopes the write to a profile",
    "actor": "names who ran the write",
    "source_command": "names the command that ran the write",
    "idempotency_key": "identifies a retried creation",
    "classified_by_override": "names the mechanism of the write, which the origin is recorded beside",
}
"""Command members that describe the invocation and are stored as no fact of the row."""

_BEARS_ON_NO_TAX: dict[str, str] = {
    "counterparty": "the other party's display name",
    "description": "the movement's narrative",
    "notes": "the person's free text and the reason shown for a classification",
    "group_label": "a personal grouping label",
    "own_account_id": "which of the person's accounts the movement belongs to",
    "attachment_ids": "supplementary documents no calculation reads, protected by who linked them",
}
"""Row facts a write can set that decide nothing about how the row is taxed."""

_REQUEST_ONLY_NAMES: dict[str, str] = {
    "transaction_id": "the row's identity in a bulk table",
    "classification": "the bulk table's column for business_classification",
}
"""Members of a request model that name the row or carry a decision field under another name."""


def test_every_field_the_ledger_command_can_carry_is_a_decision_field_or_declared_not_to_be() -> None:
    carried = set(ManualLedgerTransactionCommand.model_fields)
    declared = CLASSIFICATION_DECISION_FIELDS | set(_BEARS_ON_NO_TAX) | set(_NOT_A_ROW_FACT)

    assert carried - declared == set(), "fields a write can set that neither the set nor an exclusion places"
    assert declared - carried == set(), "placed fields the command no longer carries"
    assert not CLASSIFICATION_DECISION_FIELDS & (set(_BEARS_ON_NO_TAX) | set(_NOT_A_ROW_FACT))


@pytest.mark.parametrize(
    "request_model", [ManualLedgerTransactionPatch, LedgerClassifyPatch, LedgerUpdatePatch, BulkClassifyRow]
)
def test_every_field_a_classification_update_or_bulk_request_can_set_is_placed(
    request_model: type[BaseModel],
) -> None:
    """The patch every write goes through, and each request model that feeds it."""
    settable = set(request_model.model_fields) - set(_REQUEST_ONLY_NAMES)

    assert settable <= CLASSIFICATION_DECISION_FIELDS | set(_BEARS_ON_NO_TAX), request_model.__name__


def test_what_classification_sets_beyond_a_note_is_a_decision_field() -> None:
    """The M210 answers reach the row as one further field, which the classify request selects by name."""
    classified = (set(LedgerClassifyPatch.model_fields) | {"m210_income_classification"}) - {"notes"}

    assert classified <= CLASSIFICATION_DECISION_FIELDS
    assert set(BulkClassifyRow.model_fields) - set(_REQUEST_ONLY_NAMES) <= CLASSIFICATION_DECISION_FIELDS


def test_the_link_to_purchase_invoice_evidence_is_a_decision_field_the_fingerprint_leaves_out() -> None:
    """A link changes the facts the origin is read from; the sealed fingerprint does not read it, and an attachment is no fact."""
    row = _row()
    linked = row.model_copy(update={"purchase_invoice_evidence_id": "c" * 64})

    assert "purchase_invoice_evidence_id" in CLASSIFICATION_DECISION_FIELDS
    assert "attachment_ids" not in CLASSIFICATION_DECISION_FIELDS
    assert classification_facts(linked) != classification_facts(row)
    assert row_fingerprint(linked) == row_fingerprint(row)


def _row() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="synthetic-decision-fields-row",
                booked_date=date(2026, 4, 10),
                amount=Decimal("121.00"),
                currency="EUR",
                counterparty="Synthetic Supplier",
                description="synthetic row",
                provenance=RawProvenance(
                    source_path=Path("synthetic-decision-fields.csv"),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
                    provider_name="csv",
                ),
                raw_fields={"source": "synthetic"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
        },
    )


_ANOTHER_VALUE: dict[str, object] = {
    "counterparty": "Another Supplier",
    "description": "another narrative",
    "notes": "another note",
    "group_label": "another label",
    "own_account_id": "synthetic-account",
    "attachment_ids": ("d" * 64,),
}


def test_a_field_declared_as_bearing_on_no_tax_does_not_move_the_rows_tax_fingerprint() -> None:
    row = _row()

    assert set(_ANOTHER_VALUE) == set(_BEARS_ON_NO_TAX)
    for field, value in _ANOTHER_VALUE.items():
        if field in {"counterparty", "description"}:
            changed = row.model_copy(update={"raw": row.raw.model_copy(update={field: value})})
        else:
            changed = row.model_copy(update={field: value})
        assert changed != row, field
        assert row_fingerprint(changed) == row_fingerprint(row), field


def test_a_decision_field_the_fingerprint_reads_moves_it() -> None:
    """The reading the exclusions are checked against does tell a tax fact from the rest."""
    row = _row()

    for field, value in {"counterparty_country": "DE", "source_jurisdiction": "FR", "category_id": "x"}.items():
        assert field in CLASSIFICATION_DECISION_FIELDS
        assert row_fingerprint(row.model_copy(update={field: value})) != row_fingerprint(row), field
