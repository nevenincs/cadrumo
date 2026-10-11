"""A confirmation never moves what a finalized revision sealed, and purchase evidence is a tax fact.

The ledger actions run over real secure storage, with a finalized revision
citing the row. A person who confirms the classification another party gave
such a row takes it, although nothing of the row a calculation reads may
change: equal figures can be written differently (``500`` for ``500.00``), the
revision's fingerprint hashes the written form, and a confirmation that stored
the restated form would make the sealed revision read as stale. So the stored
row is kept exactly and only who decided, and the stamp of the confirmation,
are replaced. A write that does change a value of such a row is refused as it
always was, by single and by bulk classification alike.

Linking purchase-invoice evidence is not a document beside the row: a
calculation takes the row's figures from the invoice. A link recorded under an
agent's label to a row the person classified is refused; the person's own link
to an agent's row makes the row theirs; a supplementary attachment does
neither.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.aggregation.ledger_filing_snapshot import (
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    row_fingerprint,
)
from cadrumo.application.ledger.actions_classification import bulk_classify_from_csv
from cadrumo.application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    update_manual_transaction_fields,
)
from cadrumo.application.ledger.models import (
    BulkClassifyResult,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from cadrumo.domain.transactions.classification_origin import ClassificationOrigin
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.transactions.models import Transaction

from .classification_origin_support import (
    AGENT,
    BUCKET_ID,
    BUSINESS,
    PERSON,
    Ledger,
    add_row,
    add_row_classified_by_a_rule,
    attach_attachment,
    composed_ledger,
    store_attachment,
    synthetic_invoice,
)
from .ledger_action_persistence_support import persist_verified_revision_citing_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLASSIFY = "aeat app ledger classify"
_STORED_TEXT = {"amount": "605.0", "taxable_base": "500.00", "iva_rate": "0.210", "iva_amount": "105.00"}
_RESTATED = {
    "amount": Decimal("605"),
    "taxable_base": Decimal("500"),
    "iva_rate": Decimal("0.21"),
    "iva_amount": Decimal("105"),
}
_RECORDED_BY_A_RESTATEMENT = {
    "classification_origin",
    "classified_by",
    "classified_at",
    "classification_reason",
    "classification_confidence",
    "edit_lineage",
    "modified_at",
}


@pytest.fixture
def ledger(tmp_path: Path) -> Generator[Ledger]:
    with composed_ledger(tmp_path) as composed:
        yield composed


def _written_forms(row: Transaction) -> dict[str, str]:
    return {
        "amount": str(row.raw.amount),
        "taxable_base": str(row.taxable_base),
        "iva_rate": str(row.iva_rate),
        "iva_amount": str(row.iva_amount),
    }


def _stored_apart_from_the_restatement(row: Transaction) -> object:
    """The row's stored form without the members a restatement records."""
    return json.loads(row.model_dump_json(exclude=_RECORDED_BY_A_RESTATEMENT))


def _sealed_row_an_agent_classified(ledger: Ledger) -> tuple[str, LedgerFilingSnapshot]:
    """Store an agent's business row whose figures carry trailing zeros, and seal a revision over it."""
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=BUCKET_ID,
            booked_date=date(2025, 1, 21),
            amount=Decimal(_STORED_TEXT["amount"]),
            direction=TransactionDirection.OUTGOING,
            description="classified by an agent and cited by a finalized revision",
            business_classification=BUSINESS,
            taxable_base=Decimal(_STORED_TEXT["taxable_base"]),
            iva_rate=Decimal(_STORED_TEXT["iva_rate"]),
            iva_amount=Decimal(_STORED_TEXT["iva_amount"]),
            actor=AGENT,
        ),
        ports=ledger.ports,
    )
    row = created.ref.transaction_id
    assert _written_forms(ledger.row(row)) == _STORED_TEXT
    assert ledger.row(row).classification_origin is ClassificationOrigin.AGENT
    persist_verified_revision_citing_transaction(
        ledger.objects, transaction_id=row, bucket_id=BUCKET_ID, operation=ledger.ports.operation
    )
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(row,),
        catalogue=ledger.transactions.load(),
        captured_at=datetime(2025, 2, 1, tzinfo=UTC),
    )
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False
    return row, snapshot


def _confirm(ledger: Ledger, row: str, values: dict[str, object], *, actor: str = PERSON) -> None:
    update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=row,
        patch=ManualLedgerTransactionPatch.model_validate({"business_classification": BUSINESS, **values}),
        actor=actor,
        source_command=_CLASSIFY,
        ports=ledger.ports,
    )


def _bulk(
    ledger: Ledger, row: str, classification: BusinessClassification, *, columns: str = "", cells: str = ""
) -> BulkClassifyResult:
    return bulk_classify_from_csv(
        bucket_id=BUCKET_ID,
        csv_text=f"transaction_id,classification{columns}\n{row},{classification.value}{cells}\n",
        actor=PERSON,
        ports=ledger.ports,
    )


@pytest.mark.parametrize(
    "restated",
    [
        {},
        {"taxable_base": _RESTATED["taxable_base"]},
        {"amount": _RESTATED["amount"]},
        {"iva_rate": _RESTATED["iva_rate"]},
        _RESTATED,
    ],
    ids=["class-alone", "base-500", "amount-605", "rate-0.21", "every-figure"],
)
def test_a_person_confirming_a_sealed_row_in_canonical_text_takes_it_and_moves_nothing_the_revision_sealed(
    ledger: Ledger, restated: dict[str, object]
) -> None:
    row, snapshot = _sealed_row_an_agent_classified(ledger)
    before = ledger.row(row)
    events_before = set(ledger.events.load().events)

    _confirm(ledger, row, restated)

    after = ledger.row(row)
    assert after.classification_origin is ClassificationOrigin.PERSON
    assert _written_forms(after) == _STORED_TEXT
    assert _stored_apart_from_the_restatement(after) == _stored_apart_from_the_restatement(before)
    assert after.transaction_id == before.transaction_id
    assert row_fingerprint(after) == row_fingerprint(before)
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False
    recorded = [event for event_id, event in ledger.events.load().events.items() if event_id not in events_before]
    assert {event.actor for event in recorded} == {PERSON}
    assert BucketEventType.LEDGER_TRANSACTION_CLASSIFIED in {event.event_type for event in recorded}


def test_a_bulk_confirmation_of_a_sealed_row_is_admitted_as_a_single_one_is(ledger: Ledger) -> None:
    row, snapshot = _sealed_row_an_agent_classified(ledger)
    before = ledger.row(row)

    result = _bulk(ledger, row, BUSINESS, columns=",taxable_base,iva_rate,iva_amount", cells=",500,0.21,105")

    assert (result.applied, result.skipped, result.failures) == (1, 0, ())
    after = ledger.row(row)
    assert after.classification_origin is ClassificationOrigin.PERSON
    assert _written_forms(after) == _STORED_TEXT
    assert _stored_apart_from_the_restatement(after) == _stored_apart_from_the_restatement(before)
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False


@pytest.mark.parametrize(
    "change",
    [
        {"business_classification": BusinessClassification.PERSONAL},
        {"category_id": "material_oficina"},
        {"counterparty_country": "DE", **_RESTATED},
        {"taxable_base": Decimal("550"), "iva_amount": Decimal("55"), "iva_rate": Decimal("0.1")},
    ],
    ids=["class", "category", "one-fact-among-restated-figures", "figures"],
)
def test_a_write_that_changes_a_value_of_a_sealed_row_is_refused_and_stores_nothing(
    ledger: Ledger, change: dict[str, object]
) -> None:
    row, snapshot = _sealed_row_an_agent_classified(ledger)
    before = ledger.stored()

    with pytest.raises(TransactionValidationError) as refused:
        _confirm(ledger, row, change)

    # The refusal names the finalized revision that cites the row.
    assert "calculation_revision_id" in (refused.value.context or {})
    assert ledger.stored() == before
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False


def test_a_bulk_row_that_changes_a_value_of_a_sealed_row_is_refused_as_a_single_write_is(ledger: Ledger) -> None:
    row, _snapshot = _sealed_row_an_agent_classified(ledger)
    before = ledger.stored()

    result = _bulk(ledger, row, BusinessClassification.PERSONAL)

    assert (result.applied, result.skipped) == (0, 0)
    assert len(result.failures) == 1
    assert ledger.stored() == before


def test_a_person_restating_their_own_sealed_row_in_canonical_text_writes_nothing(ledger: Ledger) -> None:
    """Nothing is theirs to take, so the stored forms are not touched and no event is recorded."""
    row, snapshot = _sealed_row_an_agent_classified(ledger)
    _confirm(ledger, row, {})
    before = ledger.stored()

    assert _bulk(ledger, row, BUSINESS, columns=",taxable_base", cells=",500").skipped == 1
    update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=row,
        patch=ManualLedgerTransactionPatch.model_validate({"business_classification": BUSINESS, **_RESTATED}),
        actor=PERSON,
        source_command=_CLASSIFY,
        ports=ledger.ports,
    )

    assert ledger.stored() == before
    assert _written_forms(ledger.row(row)) == _STORED_TEXT
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False


def _link_purchase_evidence(ledger: Ledger, row: str, evidence_id: str, *, actor: str) -> None:
    attach_manual_transaction_evidence(
        bucket_id=BUCKET_ID,
        transaction_id=row,
        purchase_invoice_evidence_id=evidence_id,
        actor=actor,
        ports=ledger.ports,
    )


@pytest.mark.parametrize("direction", [TransactionDirection.INCOMING, TransactionDirection.OUTGOING])
def test_an_agents_label_does_not_link_purchase_evidence_to_a_row_the_person_classified(
    ledger: Ledger, direction: TransactionDirection
) -> None:
    """A calculation would then take the row's figures from the invoice, and count an incoming row as a refund."""
    invoice = synthetic_invoice("SYNTHETIC-1")
    ledger.invoices.save(build_invoice_catalogue([invoice]))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=BUCKET_ID,
            booked_date=date(2025, 1, 21),
            amount=Decimal("121.00"),
            direction=direction,
            description="the person's row",
            business_classification=BUSINESS,
            actor=PERSON,
        ),
        ports=ledger.ports,
    )
    row = created.ref.transaction_id
    before = ledger.stored()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _link_purchase_evidence(ledger, row, invoice.invoice_id, actor=AGENT)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert ledger.stored() == before

    attach_attachment(ledger, row, store_attachment(ledger, b"supplementary"), actor=AGENT)
    assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON
    _link_purchase_evidence(ledger, row, invoice.invoice_id, actor=PERSON)
    assert ledger.row(row).purchase_invoice_evidence_id == invoice.invoice_id
    assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON


def test_linking_purchase_evidence_decides_the_rows_figures_for_whoever_links_it(ledger: Ledger) -> None:
    """The person's link to an agent's row makes it theirs; an agent's link to a rule's row makes it the agent's."""
    first, second, third = (
        synthetic_invoice("SYNTHETIC-1"),
        synthetic_invoice("SYNTHETIC-2"),
        synthetic_invoice("SYNTHETIC-3"),
    )
    ledger.invoices.save(build_invoice_catalogue([first, second, third]))
    by_an_agent = add_row(ledger, description="classified by an agent", actor=AGENT, classification=BUSINESS)
    by_rule = add_row_classified_by_a_rule(ledger, description="classified by a rule")
    unprocessed = add_row(ledger, description="unprocessed")

    _link_purchase_evidence(ledger, by_an_agent, first.invoice_id, actor=PERSON)
    _link_purchase_evidence(ledger, by_rule, second.invoice_id, actor=AGENT)
    _link_purchase_evidence(ledger, unprocessed, third.invoice_id, actor=AGENT)

    assert ledger.row(by_an_agent).classification_origin is ClassificationOrigin.PERSON
    assert ledger.row(by_rule).classification_origin is ClassificationOrigin.AGENT
    assert ledger.row(unprocessed).classification_origin is None
    assert ledger.row(unprocessed).purchase_invoice_evidence_id == third.invoice_id
