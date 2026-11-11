"""A purchase's recargo in its cost, its statement about the ledger row booking it, and the checks on a claim."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....calculations.registry.tests.authored_editions import filing_year_envelope
from ....filing_evidence import FilingEvidenceReference
from ..closing_foundations import InventoryLedgerError
from ..corrections import InventoryChangeStamp, inventory_refusal_key, state_movement_ledger_row
from ..ledger_claims import ClaimedTransactionFacts, inventory_claim_refusals, unstated_purchases
from ..records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryAcquisitionFacts,
    InventoryHistoryKind,
    InventoryLedger,
    InventoryLedgerDocument,
    MovementKind,
    MovementRecord,
    PurchaseLedgerRow,
    ValuationMethod,
    movement_identity_payload,
)
from ..valuation import compute_inventory_valuation, inventory_acquisition_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

EXERCISE = filing_year_envelope().horizon
_ROW = "1" * 64
_OTHER_ROW = "2" * 64


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def _facts(*, base: str, iva: str, recargo: str = "0.00", ratio: str = "0") -> InventoryAcquisitionFacts:
    return InventoryAcquisitionFacts(
        consideration_excluding_iva=Decimal(base),
        consideration_iva_amount=Decimal(iva),
        consideration_recargo_amount=Decimal(recargo),
        consideration_deductible_iva_ratio=Decimal(ratio),
        attributable_cost_components=(),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=_ref("invoice"),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("cost-review"),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="b" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("iva-review"),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="c" * 64,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=_ref("invoice"),
            attributable_cost_review_evidence=_ref("cost-review"),
            iva_recoverability_review_evidence=_ref("iva-review"),
        ),
    )


def _purchase(
    movement_id: str,
    *,
    base: str = "6800.00",
    iva: str = "1428.00",
    recargo: str = "353.60",
    claim: str | None = _ROW,
) -> MovementRecord:
    return MovementRecord.from_purchase_acquisition(
        movement_id=movement_id,
        movement_date=date(EXERCISE, 1, 10),
        quantity=Decimal(1),
        acquisition_cost=_facts(base=base, iva=iva, recargo=recargo).to_cost(),
        ledger_row=PurchaseLedgerRow.CLAIMED if claim is not None else PurchaseLedgerRow.UNSTATED,
        claimed_transaction_id=claim,
    )


def _book(*movements: MovementRecord, actividad_id: str = "comercio", year: int = EXERCISE) -> InventoryLedger:
    return InventoryLedger(
        actividad_id=actividad_id,
        year=year,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal(0),
        period_movements=movements,
        closing_authority_record=None,
    )


def _row(*, base: str = "6800.00", iva: str = "1428.00", recargo: str | None = "353.60", currency: str = "EUR"):
    return {
        _ROW: ClaimedTransactionFacts(
            transaction_id=_ROW,
            currency=currency,
            taxable_base=Decimal(base),
            iva_amount=Decimal(iva),
            recargo_amount=None if recargo is None else Decimal(recargo),
        )
    }


def _stamp(correction_id: str) -> InventoryChangeStamp:
    return InventoryChangeStamp(correction_id=correction_id, recorded_at=datetime.now(UTC), actor="tester")


def test_recargo_joins_the_non_recoverable_part_of_the_purchase_cost() -> None:
    cost = _facts(base="6800.00", iva="1428.00", recargo="353.60").to_cost()

    assert cost.nonrecoverable_iva_included == Decimal("1781.60")
    assert cost.recoverable_iva_excluded == Decimal("0.00")
    assert cost.total_acquisition_cost == Decimal("8581.60")


def test_a_purchase_bearing_recargo_that_deducts_iva_is_refused_with_its_typed_reason() -> None:
    with pytest.raises(InventoryLedgerError) as refused:
        _facts(base="100.00", iva="21.00", recargo="5.20", ratio="1").to_cost()

    assert refused.value.translated_message == inventory_refusal_key("recargo_with_deductible_iva")


def test_a_stated_total_that_leaves_recargo_out_is_refused() -> None:
    facts = _facts(base="100.00", iva="21.00", recargo="5.20").model_copy(
        update={"total_acquisition_cost": Decimal("121.00")}
    )

    with pytest.raises(ValidationError):
        facts.to_cost()


def test_a_purchase_stored_before_recargo_and_claims_reads_back_with_neither() -> None:
    stored = _purchase("p1", base="100.00", iva="21.00", recargo="0.00", claim=None).model_dump(mode="json")
    del stored["ledger_row"]
    del stored["claimed_transaction_id"]
    del stored["acquisition_cost"]["consideration_recargo_amount"]

    loaded = MovementRecord.model_validate_json(json.dumps(stored))

    assert loaded.ledger_row is PurchaseLedgerRow.UNSTATED
    assert loaded.claimed_transaction_id is None
    assert loaded.acquisition_cost is not None
    assert loaded.acquisition_cost.consideration_recargo_amount == Decimal("0.00")
    assert movement_identity_payload(loaded) == stored


def test_the_claim_enters_no_fingerprint_and_recargo_enters_the_acquisition_fingerprint() -> None:
    unclaimed = _purchase("p1", claim=None)
    claimed = _purchase("p1")
    without_recargo = _purchase("p1", iva="1781.60", recargo="0.00", claim=None)

    assert inventory_acquisition_fingerprint(claimed) == inventory_acquisition_fingerprint(unclaimed)
    assert inventory_acquisition_fingerprint(without_recargo) != inventory_acquisition_fingerprint(unclaimed)


def test_only_a_purchase_states_a_ledger_row_and_a_claim_names_its_row() -> None:
    with pytest.raises(ValidationError):
        MovementRecord(
            movement_id="sale",
            movement_date=date(EXERCISE, 3, 1),
            kind=MovementKind.COGS,
            quantity=Decimal(1),
            ledger_row=PurchaseLedgerRow.NONE,
        )
    claimed = _purchase("p1").model_dump(mode="json")
    with pytest.raises(ValidationError):
        MovementRecord.model_validate_json(json.dumps({**claimed, "claimed_transaction_id": None}))
    with pytest.raises(ValidationError):
        MovementRecord.model_validate_json(json.dumps({**claimed, "ledger_row": PurchaseLedgerRow.NONE.value}))


def test_a_claim_matching_its_row_to_the_cent_stands_and_a_multi_line_invoice_sums_its_lines() -> None:
    whole = _book(_purchase("p1"))
    split = _book(
        _purchase("p1", base="4000.00", iva="840.00", recargo="208.00"),
        _purchase("p2", base="2800.00", iva="588.00", recargo="145.60"),
    )

    for book in (whole, split):
        document = InventoryLedgerDocument(ledgers=(book,))
        assert inventory_claim_refusals(document, book, transactions=_row(), asset_claimed=frozenset()) == ()


@pytest.mark.parametrize(
    ("rows", "asset_claimed", "reason"),
    [
        ({}, frozenset(), "claimed_transaction_missing"),
        (_row(), frozenset({_ROW}), "claimed_transaction_double_claim"),
        (_row(base="6800.01"), frozenset(), "claimed_transaction_amount_mismatch"),
        (_row(iva="1427.99"), frozenset(), "claimed_transaction_amount_mismatch"),
        (_row(recargo=None), frozenset(), "claimed_transaction_amount_mismatch"),
        (_row(currency="USD"), frozenset(), "claimed_transaction_not_eur"),
    ],
)
def test_a_claim_that_does_not_stand_is_refused_with_its_reason(
    rows: dict[str, ClaimedTransactionFacts], asset_claimed: frozenset[str], reason: str
) -> None:
    book = _book(_purchase("p1"))

    refusals = inventory_claim_refusals(
        InventoryLedgerDocument(ledgers=(book,)), book, transactions=rows, asset_claimed=asset_claimed
    )

    assert [refusal.reason for refusal in refusals] == [reason]
    assert refusals[0].movement_ids == ("p1",)


def test_a_row_without_its_base_or_iva_cannot_be_compared_and_is_refused() -> None:
    book = _book(_purchase("p1"))
    rows = {_ROW: ClaimedTransactionFacts(_ROW, "EUR", None, Decimal("1428.00"), Decimal("353.60"))}

    refusals = inventory_claim_refusals(
        InventoryLedgerDocument(ledgers=(book,)), book, transactions=rows, asset_claimed=frozenset()
    )

    assert [refusal.reason for refusal in refusals] == ["claimed_transaction_substrate_missing"]


def test_a_row_two_books_claim_is_refused_for_each_book() -> None:
    first = _book(_purchase("p1"))
    second = _book(_purchase("q1"), actividad_id="otra")
    document = InventoryLedgerDocument(ledgers=(first, second))

    for book in (first, second):
        refusals = inventory_claim_refusals(document, book, transactions=_row(), asset_claimed=frozenset())
        assert [refusal.reason for refusal in refusals] == ["claimed_transaction_double_claim"]


def test_stating_a_claim_after_the_closing_keeps_the_prior_statement_and_replays_exactly() -> None:
    book = _book(_purchase("p1", claim=None))
    document = InventoryLedgerDocument(ledgers=(book,))
    stamp = _stamp("claim-1")

    claimed = state_movement_ledger_row(
        document,
        book,
        stamp=stamp,
        movement_id="p1",
        ledger_row=PurchaseLedgerRow.CLAIMED,
        claimed_transaction_id=_ROW,
    )
    replayed = state_movement_ledger_row(
        document,
        claimed,
        stamp=stamp,
        movement_id="p1",
        ledger_row=PurchaseLedgerRow.CLAIMED,
        claimed_transaction_id=_ROW,
    )

    assert claimed.period_movements[0].claimed_transaction_id == _ROW
    entry = claimed.history[-1]
    assert entry.kind is InventoryHistoryKind.LEDGER_ROW_STATED
    assert entry.ledger_row_change is not None
    assert entry.ledger_row_change.prior_ledger_row is PurchaseLedgerRow.UNSTATED
    assert replayed is claimed
    assert compute_inventory_valuation(claimed) == compute_inventory_valuation(book)
    assert unstated_purchases(claimed) == ()


@pytest.mark.parametrize(
    ("movement", "ledger_row", "transaction_id", "reason"),
    [
        ("p1", PurchaseLedgerRow.UNSTATED, None, "correction_changes_nothing"),
        ("missing", PurchaseLedgerRow.NONE, None, "movement_not_found"),
        ("sale", PurchaseLedgerRow.NONE, None, "ledger_row_not_purchase"),
        ("p1", PurchaseLedgerRow.CLAIMED, _OTHER_ROW, "claimed_transaction_double_claim"),
    ],
)
def test_a_statement_that_cannot_stand_is_refused(
    movement: str, ledger_row: PurchaseLedgerRow, transaction_id: str | None, reason: str
) -> None:
    sale = MovementRecord(
        movement_id="sale", movement_date=date(EXERCISE, 3, 1), kind=MovementKind.COGS, quantity=Decimal(1)
    )
    book = _book(_purchase("p1", claim=None), sale)
    other = _book(_purchase("q1", claim=_OTHER_ROW), actividad_id="otra")

    with pytest.raises(InventoryLedgerError) as refused:
        state_movement_ledger_row(
            InventoryLedgerDocument(ledgers=(book, other)),
            book,
            stamp=_stamp("claim-2"),
            movement_id=movement,
            ledger_row=ledger_row,
            claimed_transaction_id=transaction_id,
        )

    assert refused.value.translated_message == inventory_refusal_key(reason)
