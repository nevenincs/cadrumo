"""Filing-grade ledger evidence gates for modelo lifecycle finish lines.

These helpers inspect the :class:`CalculationRevision` evidence bundle before
verification, export, or local filing lets deductible input IVA proceed.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from enum import StrEnum
from typing import cast

from ...core import ActionEvidenceProvenance
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
    BUSINESS_BEARING_STATES,
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ..aggregation import invoice_kind_for_direction
from ._preconditions import build_modelo_precondition_failure


def _enum_or_none[EnumT: StrEnum](enum_type: type[EnumT], value: str | None) -> EnumT | None:
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        return None


# ALT-EVIDENCE-GRADE-RATIONALE-LEDGER-GATE: deliberately looser, on the
# attachment_ids axis, than the calculate-path deductible-side test
# application.aggregation._evidence_advisory._row_has_deduction_grade_evidence
# (LIVA art. 97 enumerative there); tightening it here would create an
# unrecoverable finalized-revision dead end -- see the divergence paragraph
# in this docstring below for why it is recorded rather than closed.
def _row_has_linked_evidence(row: LedgerEvidenceRow) -> bool:
    """Return whether the bundled row carries any linked evidence at all.

    ``invoice_id`` is credited here for the same reason it is credited at
    verify time (:func:`~application.aggregation._evidence_advisory._row_has_deduction_grade_evidence`):
    without it, a row verify granted specifically BECAUSE it carried a linked,
    validated ``Invoice`` -- and only that -- would bundle with
    ``purchase_invoice_evidence_id`` and ``attachment_ids`` both empty, and
    this gate would then block export/local-filing on a revision verify just
    granted. That is not a hypothetical: it reproduced on the first version of
    the verify-time fix, caught by
    ``test_modelo_303_verify_and_file_credit_a_linked_validated_invoice``
    before this line existed. Omitting the credit here does not merely widen
    the accepted-vs-verify divergence documented below -- it manufactures a
    NEW permanent dead end, the exact failure class the surrounding campaign
    exists to close.

    Otherwise this stays DELIBERATELY looser than the verify-time deductible
    test on the ``attachment_ids`` axis, which was tightened to the
    purchase-invoice/invoice axis because LIVA art. 97 enumerates the
    documents that support a deduction. Two standards for one legal rule is a
    real divergence on THAT axis, and it is recorded rather than swept,
    because closing it here would cost more than it buys.

    Verify now blocks a deductible row lacking deduction-grade evidence, so no
    revision finalized after that promotion can reach this gate carrying
    neither ``purchase_invoice_evidence_id`` nor ``invoice_id``. Tightening
    the ``attachment_ids`` copy therefore changes behaviour only for revisions
    finalized BEFORE that promotion — and for those there is no way out: the
    bundle is frozen and never recomputed, a finalized revision cannot be
    re-verified (the idempotent guard returns the existing granting report),
    and recalculating returns the same content-addressed revision because
    attaching an invoice does not change any tax fact. That is a permanent
    dead end, which is the failure class this surface's own campaign exists to
    close. An unreachable divergence on the attachment axis is the cheaper of
    the two; a reachable one on the invoice axis is not, which is why it is
    closed rather than recorded.

    The refusal message below says "purchase invoice evidence" while this test
    accepts any attachment, which reads as an overclaim. It is not one in
    practice: a row only reaches that message with NO evidence of any kind, and
    an invoice is then exactly what the operator needs. The mismatch misleads a
    reader of this file, not an operator, which is why it is answered with this
    comment rather than a message change.
    """
    return bool(row.purchase_invoice_evidence_id) or bool(row.invoice_id) or bool(row.attachment_ids)


def _row_flow(row: LedgerEvidenceRow) -> IvaFlowDirection | None:
    direction = _enum_or_none(TransactionDirection, row.direction)
    invoice_kind = invoice_kind_for_direction(direction)
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


def ledger_evidence_row_missing_deductible_iva_evidence(row: LedgerEvidenceRow) -> bool:
    """Return whether an evidence row claims deductible IVA without linked proof."""
    lifecycle_state = _enum_or_none(TransactionLifecycleState, row.lifecycle_state)
    if lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    business_classification = _enum_or_none(BusinessClassification, row.business_classification)
    if business_classification not in BUSINESS_BEARING_STATES:
        return False
    if row.iva_amount is None or row.iva_amount <= Decimal("0"):
        return False
    if _row_has_linked_evidence(row):
        return False
    flow = _row_flow(row)
    return flow is not None and is_deducible_flow(flow)


def deductible_iva_evidence_gap_transaction_ids(revision: CalculationRevision) -> tuple[str, ...]:
    """Return ledger transaction ids whose bundled evidence cannot support deduction.

    Args:
        revision: :class:`CalculationRevision` carrying the ledger filing
            evidence rows to inspect.
    """
    evidence = revision.ledger_filing_evidence
    if evidence is None:
        return ()
    return tuple(
        sorted(row.transaction_id for row in evidence.rows if ledger_evidence_row_missing_deductible_iva_evidence(row)),
    )


def raise_if_deductible_iva_evidence_missing(
    revision: CalculationRevision,
    *,
    error_type: type[ModeloError],
) -> None:
    """Raise a typed file refusal when a finalized revision has unsupported input IVA.

    Args:
        revision: :class:`CalculationRevision` whose bundled ledger evidence is
            checked before the lifecycle finish line.
        error_type: Modelo error class raised when deductible IVA lacks evidence.
    """
    transaction_ids = deductible_iva_evidence_gap_transaction_ids(revision)
    if not transaction_ids:
        return
    error_factory = cast(Callable[..., ModeloError], error_type)
    raise error_factory(
        translated_message="application.modelo.errors.deductible_iva_evidence_missing",
        context={
            "calculation_revision_id": revision.calculation_revision_id,
            "transaction_ids": list(transaction_ids),
            "reason": "deductible_iva_evidence_missing",
        },
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.file",
            condition_id="modelo.work.file.deductible_iva_evidence.present",
            scenario_id="modelo.work.file.deductible_iva_evidence.missing",
            evidence_id="modelo.work.file.deductible_iva_evidence",
            evidence_values={
                "calculation_revision_id": revision.calculation_revision_id,
                "work_unit_id": revision.work_unit_id,
                "transaction_count": len(transaction_ids),
                "transaction_ids": "|".join(transaction_ids),
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )


__all__ = [
    "deductible_iva_evidence_gap_transaction_ids",
    "ledger_evidence_row_missing_deductible_iva_evidence",
    "raise_if_deductible_iva_evidence_missing",
]
