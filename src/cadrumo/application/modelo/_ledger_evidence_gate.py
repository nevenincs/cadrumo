"""Filing-grade ledger evidence gates for modelo lifecycle finish lines.

These helpers inspect the :class:`CalculationRevision` evidence bundle before
verification, export, or local filing lets deductible input IVA proceed.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from ...domain.iva import (
    EVIDENCE_EXEMPT_IVA_CATEGORIES,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    derive_flow_for_classification,
    is_deducible_flow,
)
from ...domain.modelos import CalculationRevision, LedgerEvidenceRow, ModeloError
from ...domain.transactions import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)

_EVIDENCE_EXPECTING_BUSINESS_STATES: frozenset[BusinessClassification] = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    },
)


def _enum_or_none[EnumT: StrEnum](enum_type: type[EnumT], value: str | None) -> EnumT | None:
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        return None


def _row_has_linked_evidence(row: LedgerEvidenceRow) -> bool:
    """Return whether the bundled row carries any linked evidence at all.

    This is DELIBERATELY looser than the verify-time deductible test, which was
    tightened to the purchase-invoice axis because LIVA art. 97 enumerates the
    documents that support a deduction. Two standards for one legal rule is a
    real divergence, and it is recorded rather than swept, because closing it
    here would cost more than it buys.

    Verify now blocks a deductible row lacking deduction-grade evidence, so no
    revision finalized after that promotion can reach this gate carrying one.
    Tightening this copy therefore changes behaviour only for revisions
    finalized BEFORE it — and for those there is no way out: the bundle is
    frozen and never recomputed, a finalized revision cannot be re-verified (the
    idempotent guard returns the existing granting report), and recalculating
    returns the same content-addressed revision because attaching an invoice
    does not change any tax fact. That is a permanent dead end, which is the
    failure class this surface's own campaign exists to close. An unreachable
    divergence is the cheaper of the two.

    The refusal message below says "purchase invoice evidence" while this test
    accepts any attachment, which reads as an overclaim. It is not one in
    practice: a row only reaches that message with NO evidence of any kind, and
    an invoice is then exactly what the operator needs. The mismatch misleads a
    reader of this file, not an operator, which is why it is answered with this
    comment rather than a message change.
    """
    return bool(row.purchase_invoice_evidence_id) or bool(row.attachment_ids)


def _invoice_kind_for(direction: TransactionDirection | None) -> InvoiceKind | None:
    if direction is TransactionDirection.INCOMING:
        return InvoiceKind.ISSUED
    if direction is TransactionDirection.OUTGOING:
        return InvoiceKind.RECEIVED
    return None


def _row_flow(row: LedgerEvidenceRow) -> IvaFlowDirection | None:
    direction = _enum_or_none(TransactionDirection, row.direction)
    invoice_kind = _invoice_kind_for(direction)
    if invoice_kind is None:
        return None
    category = _enum_or_none(IvaCategory, row.iva_category)
    if category is None:
        return IvaFlowDirection.REPERCUTIDO if invoice_kind is InvoiceKind.ISSUED else IvaFlowDirection.SOPORTADO
    if category in EVIDENCE_EXEMPT_IVA_CATEGORIES:
        return None
    return derive_flow_for_classification(
        category=category,
        invoice_direction=invoice_kind,
    )


def ledger_evidence_row_missing_deductible_vat_evidence(row: LedgerEvidenceRow) -> bool:
    """Return whether an evidence row claims deductible IVA without linked proof."""
    lifecycle_state = _enum_or_none(TransactionLifecycleState, row.lifecycle_state)
    if lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    business_classification = _enum_or_none(BusinessClassification, row.business_classification)
    if business_classification not in _EVIDENCE_EXPECTING_BUSINESS_STATES:
        return False
    if row.iva_amount is None or row.iva_amount <= Decimal("0"):
        return False
    if _row_has_linked_evidence(row):
        return False
    flow = _row_flow(row)
    return flow is not None and is_deducible_flow(flow)


def deductible_vat_evidence_gap_transaction_ids(revision: CalculationRevision) -> tuple[str, ...]:
    """Return ledger transaction ids whose bundled evidence cannot support deduction.

    Args:
        revision: :class:`CalculationRevision` carrying the ledger filing
            evidence rows to inspect.
    """
    evidence = revision.ledger_filing_evidence
    if evidence is None:
        return ()
    return tuple(
        sorted(row.transaction_id for row in evidence.rows if ledger_evidence_row_missing_deductible_vat_evidence(row)),
    )


def raise_if_deductible_vat_evidence_missing(
    revision: CalculationRevision,
    *,
    error_type: type[ModeloError],
    surface: str,
    suggestion: str,
) -> None:
    """Raise ``error_type`` when a finalized revision has unsupported input IVA.

    Args:
        revision: :class:`CalculationRevision` whose bundled ledger evidence is
            checked before the lifecycle finish line.
        error_type: Modelo error class raised when deductible IVA lacks evidence.
        surface: Human-readable lifecycle surface used in the refusal message.
        suggestion: Operator command or action hint attached to the refusal.
    """
    transaction_ids = deductible_vat_evidence_gap_transaction_ids(revision)
    if not transaction_ids:
        return
    raise error_type(
        f"deductible VAT rows require linked purchase invoice evidence before {surface}",
        translated_message="application.modelo.errors.deductible_vat_evidence_missing",
        context={
            "calculation_revision_id": revision.calculation_revision_id,
            "transaction_ids": list(transaction_ids),
            "reason": "deductible_vat_evidence_missing",
        },
        suggestion=suggestion,
    )


__all__ = [
    "deductible_vat_evidence_gap_transaction_ids",
    "ledger_evidence_row_missing_deductible_vat_evidence",
    "raise_if_deductible_vat_evidence_missing",
]
