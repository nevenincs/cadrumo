"""Evidence-presence advisory gate: fires on significant evidence-less rows only.

The advisory pairs a transaction's economic role with its evidence presence
(``no-silent-under-declaration``). These gates assert:

* it fires exactly one ``missing_transaction_evidence`` diagnostic on a positive
  OUTGOING BUSINESS expense with a deductible IVA category and no evidence, and
  on a positive INCOMING cuota-bearing row with no evidence;
* it does NOT fire when the row carries an attachment or a purchase invoice
  (the evidence-present counter-case);
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
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    TransactionLifecycleState,
)
from .._evidence_advisory import (
    MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND,
    missing_evidence_advisory_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _raw(provider_id: str, *, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
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
    iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL_21,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    attachment_ids: tuple[str, ...] = (),
    purchase_invoice_evidence_id: str | None = None,
) -> Transaction:
    payload: dict[str, object] = {
        "raw": _raw(provider_id, amount=amount),
        "direction": direction,
        "business_classification": business_classification,
        "iva_category": iva_category,
        "lifecycle_state": lifecycle_state,
        "attachment_ids": attachment_ids,
    }
    if business_pct is not None:
        payload["business_pct"] = business_pct
    if purchase_invoice_evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = purchase_invoice_evidence_id
    return Transaction.model_validate(payload)


# --- Fires on positive significant rows with no evidence ----------------------------
def test_advisory_fires_on_outgoing_business_expense_without_evidence() -> None:
    tx = _tx("expense-no-evidence", direction=TransactionDirection.OUTGOING)
    diagnostics = missing_evidence_advisory_observations([tx])
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.reason == "missing_transaction_evidence"
    assert diagnostic.source_kind == MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND
    assert diagnostic.binding_id == tx.transaction_id


def test_advisory_fires_on_incoming_cuota_bearing_income_without_evidence() -> None:
    tx = _tx(
        "income-no-evidence",
        direction=TransactionDirection.INCOMING,
        iva_category=IvaCategory.DOMESTIC_GENERAL_21,
    )
    diagnostics = missing_evidence_advisory_observations([tx])
    assert len(diagnostics) == 1
    assert diagnostics[0].binding_id == tx.transaction_id


def test_advisory_silent_when_attachment_present() -> None:
    tx = _tx("expense-with-attachment", attachment_ids=("a" * 64,))
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_when_purchase_invoice_present() -> None:
    tx = _tx("expense-with-invoice", purchase_invoice_evidence_id="pinv-001")
    assert missing_evidence_advisory_observations([tx]) == ()


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
    tx = _tx("zero-amount", amount=Decimal("0.00"))
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_on_non_active_row() -> None:
    """An ARCHIVED row with no evidence does not fire."""
    tx = _tx("archived-expense", lifecycle_state=TransactionLifecycleState.ARCHIVED)
    assert missing_evidence_advisory_observations([tx]) == ()


def test_advisory_silent_on_outgoing_with_no_iva_category() -> None:
    """A business expense with no IVA classification yet does not fire."""
    tx = _tx("unclassified-expense", iva_category=None)
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
    """Only the two significant evidence-less rows in a mixed batch fire."""
    rows = [
        _tx("sig-expense", direction=TransactionDirection.OUTGOING),
        _tx("sig-income", direction=TransactionDirection.INCOMING),
        _tx("has-attachment", attachment_ids=("b" * 64,)),
        _tx("personal", business_classification=BusinessClassification.PERSONAL),
        _tx("exempt", iva_category=IvaCategory.DOMESTIC_EXEMPT),
    ]
    diagnostics = missing_evidence_advisory_observations(rows)
    fired_ids = {diagnostic.binding_id for diagnostic in diagnostics}
    assert fired_ids == {rows[0].transaction_id, rows[1].transaction_id}
