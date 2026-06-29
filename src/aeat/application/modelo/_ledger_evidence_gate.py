"""Filing-grade ledger evidence gates for modelo lifecycle finish lines.

These helpers inspect the :class:`CalculationRevision` evidence bundle before
verification, export, or local filing lets deductible input IVA proceed.
"""

from __future__ import annotations

from decimal import Decimal

from ...domain.iva import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    derive_flow_for_classification,
    is_deducible_flow,
)
from ...domain.modelos._calculation_revision import CalculationRevision
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._ledger_filing_snapshot import LedgerEvidenceRow
from ...domain.transactions import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)

_EVIDENCE_EXEMPT_IVA_CATEGORIES: frozenset[IvaCategory] = CUOTA_LESS_M303_IVA_CATEGORIES | frozenset(
    {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.ERRONEOUS_INVOICE,
        IvaCategory.UNKNOWN,
    },
)

_EVIDENCE_EXPECTING_BUSINESS_STATES: frozenset[BusinessClassification] = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    },
)


def _enum_or_none(enum_type: type, value: str | None) -> object | None:
    if value is None:
        return None
    try:
        return enum_type(value)  # type: ignore[call-arg]
    except ValueError:
        return None


def _row_has_linked_evidence(row: LedgerEvidenceRow) -> bool:
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
    if category in _EVIDENCE_EXEMPT_IVA_CATEGORIES:
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
        sorted(
            row.transaction_id
            for row in evidence.rows
            if ledger_evidence_row_missing_deductible_vat_evidence(row)
        ),
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
