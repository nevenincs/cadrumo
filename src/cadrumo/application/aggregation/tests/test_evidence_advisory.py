"""Evidence-presence advisory gate: fires on significant evidence-less rows only.

The diagnostics pair a transaction's IVA settlement side with its evidence presence
(``no-silent-under-declaration``). These gates assert:

* it fires exactly one ``missing_transaction_evidence`` diagnostic on a positive
  OUTGOING BUSINESS expense with deductible IVA and no evidence, and on a
  positive INCOMING output-IVA row with no evidence;
* it does NOT fire on a deductible row carrying a purchase invoice, and DOES
  still fire on one carrying only a generic attachment, because LIVA art. 97
  enumerates the documents that establish the right to deduct;
* it does NOT fire on an output-IVA row carrying any linked document, which is
  the deliberate asymmetry: art. 97 governs deduction only, and no CLI path
  mints issued-invoice evidence;
* it does NOT fire on the false-positive set: a cuota-less (exempt) IVA
  category, a PERSONAL / non-business row, a zero-amount row, or a non-ACTIVE
  lifecycle state.

Real :class:`Transaction` models; the expected trigger is derived from the
row's economic role, not from any formula under test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.iva import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._evidence_advisory import (
    MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND,
    MISSING_OUTPUT_IVA_EVIDENCE_SOURCE_KIND,
    missing_evidence_advisory_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _raw(provider_id: str, *, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 15),
        value_date=date(2026, 4, 15),
        amount=amount,
        currency="EUR",
        counterparty="ACME SL",
        description=f"evidence advisory {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _tx(
    provider_id: str,
    *,
    amount: Decimal = Decimal("121.00"),
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    attachment_ids: tuple[str, ...] = (),
    purchase_invoice_evidence_id: str | None = None,
    invoice_id: str | None = None,
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
) -> Transaction:
    payload: dict[str, object] = {
        "raw": _raw(provider_id, amount=amount),
        "direction": direction,
        "business_classification": business_classification,
        "source_jurisdiction": "ES",
        "group_label": None,
        "iva_category": iva_category,
        "lifecycle_state": lifecycle_state,
        "attachment_ids": attachment_ids,
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
    }
    if business_pct is not None:
        payload["business_pct"] = business_pct
    if purchase_invoice_evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = purchase_invoice_evidence_id
    if invoice_id is not None:
        payload["invoice_id"] = invoice_id
    return Transaction.model_validate(payload)


# --- Fires on positive significant rows with no evidence ----------------------------
def test_advisory_fires_on_outgoing_business_expense_without_evidence() -> None:
    tx = _tx("expense-no-evidence", direction=TransactionDirection.OUTGOING)
    diagnostics = missing_evidence_advisory_observations([tx])
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.reason == "missing_transaction_evidence"
    assert diagnostic.source_kind == MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND
    assert diagnostic.binding_id == tx.transaction_id


def test_advisory_fires_on_incoming_cuota_bearing_income_without_evidence() -> None:
    tx = _tx(
        "income-no-evidence",
        direction=TransactionDirection.INCOMING,
        iva_category=IvaCategory.DOMESTIC_GENERAL,
    )
    diagnostics = missing_evidence_advisory_observations([tx])
    assert len(diagnostics) == 1
    assert diagnostics[0].binding_id == tx.transaction_id
    assert diagnostics[0].source_kind == MISSING_OUTPUT_IVA_EVIDENCE_SOURCE_KIND


def test_deductible_row_still_fires_when_only_a_generic_attachment_is_present() -> None:
    """A bare attachment does not establish the right to deduct, so the gap stands.

    This assertion is inverted from what it was. The predicate previously treated
    any attachment as sufficient on both sides, which held a BLOCKING gate to a
    laxer standard than the statute it cites: LIVA art. 97 enumerates the
    documents that establish the right to deduct and an attachment -- a bank
    statement, a delivery note, a photograph -- is not among them.
    """
    tx = _tx("expense-with-attachment", attachment_ids=("a" * 64,))
    diagnostics = missing_evidence_advisory_observations([tx])
    assert len(diagnostics) == 1
    assert diagnostics[0].source_kind == MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND
    assert diagnostics[0].binding_id == tx.transaction_id


def test_output_row_stays_silent_when_only_a_generic_attachment_is_present() -> None:
    """The output side keeps the looser test, and that asymmetry is deliberate.

    Art. 97 governs the right to deduct and says nothing about evidencing output
    IVA, and no CLI path mints issued-invoice evidence. Tightening this side would
    refuse a taxpayer who has no way to comply, so any linked document silences it.
    """
    tx = _tx(
        "income-with-attachment",
        direction=TransactionDirection.INCOMING,
        attachment_ids=("a" * 64,),
    )
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_when_purchase_invoice_present() -> None:
    tx = _tx("expense-with-invoice", purchase_invoice_evidence_id="pinv-001")
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_when_a_validated_invoice_is_linked() -> None:
    """A row linked to a reconciliation-catalogue ``Invoice`` also silences the gap.

    ``ledger link`` refuses to stamp ``invoice_id`` unless it resolves to a
    record already in the ``Invoice`` catalogue, which only exists behind the
    sanctioned catalogue writer's RD 1619/2012 art. 6 content validators. That
    is STRONGER evidence than a bare ``PurchaseInvoiceEvidence`` blob (every
    field optional, no content check), so crediting it here only widens what
    already passes and cannot narrow what already blocks -- proven by the
    sibling "no evidence at all" test below, which is unaffected by this row's
    ``invoice_id`` being unset.
    """
    tx = _tx("expense-with-linked-invoice", invoice_id="inv-001")
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_still_fires_when_neither_invoice_id_nor_evidence_id_is_set() -> None:
    """The widening above must not have narrowed the base case.

    Explicit companion to
    ``test_advisory_fires_on_outgoing_business_expense_without_evidence``: a row
    with NEITHER carrier set is exactly what the deductible-evidence rule exists
    to catch, and it must still block. A regression that always returned
    ``True`` from ``_row_has_deduction_grade_evidence`` (over-crediting every
    row) would pass every OTHER test in this module but fail this one.
    """
    tx = _tx("expense-with-nothing", purchase_invoice_evidence_id=None, invoice_id=None)
    diagnostics = missing_evidence_advisory_observations([tx])
    assert len(diagnostics) == 1
    assert diagnostics[0].source_kind == MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND
    assert diagnostics[0].binding_id == tx.transaction_id


# --- False-positive guards ----------------------------------------------------------
def test_advisory_silent_on_exempt_iva_category() -> None:
    """A cuota-less (exempt) OUTGOING row with no evidence does not fire."""
    tx = _tx("exempt-expense", iva_category=IvaCategory.DOMESTIC_EXEMPT)
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_on_personal_non_business_row() -> None:
    """A PERSONAL OUTGOING row with no evidence does not fire."""
    tx = _tx("personal-expense", business_classification=BusinessClassification.PERSONAL)
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_on_zero_amount_row() -> None:
    """A zero-amount row with no evidence does not fire."""
    tx = _tx(
        "zero-amount",
        amount=Decimal("0.00"),
        taxable_base=Decimal("0.00"),
        iva_amount=Decimal("0.00"),
    )
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_on_non_active_row() -> None:
    """An ARCHIVED row with no evidence does not fire."""
    tx = _tx("archived-expense", lifecycle_state=TransactionLifecycleState.ARCHIVED)
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_fires_on_outgoing_with_positive_iva_and_no_explicit_category() -> None:
    """A domestic-rate row with no explicit IVA category still feeds M303."""
    tx = _tx("unclassified-expense", iva_category=None)
    diagnostics = missing_evidence_advisory_observations([tx])
    assert len(diagnostics) == 1
    assert diagnostics[0].source_kind == MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND


def test_advisory_silent_without_positive_iva_quota() -> None:
    """A row with no stored IVA quota does not fire even if gross is positive."""
    tx = _tx(
        "no-iva-quota",
        amount=Decimal("121.00"),
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_on_incoming_exempt_category() -> None:
    """An exempt INCOMING row (e.g. intra-community supply) does not fire."""
    tx = _tx(
        "exempt-income",
        direction=TransactionDirection.INCOMING,
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_on_internal_transfer() -> None:
    """An internal transfer is never tax-relevant and never fires."""
    tx = _tx("internal", direction=TransactionDirection.INTERNAL_TRANSFER)
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_fires_once_per_significant_row_in_a_mixed_batch() -> None:
    """Only the significant evidence-short rows in a mixed batch fire.

    The deductible row carrying only a generic attachment is among them: an
    attachment is not one of the documents art. 97 enumerates, so it leaves the
    deduction unsupported. The invoice-bearing row is the silent counter-case
    that keeps this from passing vacuously.
    """
    rows = [
        _tx("sig-expense", direction=TransactionDirection.OUTGOING),
        _tx("sig-income", direction=TransactionDirection.INCOMING),
        _tx("has-attachment", attachment_ids=("b" * 64,)),
        _tx("has-invoice", purchase_invoice_evidence_id="pinv-batch"),
        _tx("personal", business_classification=BusinessClassification.PERSONAL),
        _tx("exempt", iva_category=IvaCategory.DOMESTIC_EXEMPT),
    ]
    diagnostics = missing_evidence_advisory_observations(rows)
    fired_ids = {diagnostic.binding_id for diagnostic in diagnostics}
    assert fired_ids == {
        rows[0].transaction_id,
        rows[1].transaction_id,
        rows[2].transaction_id,
    }
