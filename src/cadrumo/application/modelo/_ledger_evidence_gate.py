"""Filing-grade ledger evidence gates for modelo lifecycle finish lines.

These helpers inspect the :class:`CalculationRevision` evidence bundle before
verification, export, or local filing lets deductible input IVA proceed.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from enum import Enum, StrEnum, auto
from typing import Final, cast

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.iva.flow import (
    IvaFlowDirection,
    derive_flow_for_classification,
    flow_direction_for_invoice_kind,
    is_deducible_flow,
)
from ...domain.iva.schema import EVIDENCE_EXEMPT_IVA_CATEGORIES, IvaCategory
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow
from ...domain.transactions.enums import (
    BUSINESS_BEARING_STATES,
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ..aggregation import invoice_kind_for_direction
from .preconditions import build_modelo_precondition_failure


class _SchemaDrift(Enum):
    """Marker for a stored enum value this build's enums no longer recognise."""

    UNPARSEABLE = auto()


#: Returned for a value that is present but uninterpretable, so a caller can
#: tell "the row says something I cannot read" apart from "the row says
#: nothing". Collapsing the two is what let an unreadable row leave this gate
#: looking clean.
_UNPARSEABLE: Final = _SchemaDrift.UNPARSEABLE


def _enum_or_none[EnumT: StrEnum](enum_type: type[EnumT], value: str | None) -> EnumT | None:
    """Parse an OPTIONAL stored enum value, treating absent and unreadable alike.

    Kept for :attr:`LedgerEvidenceRow.iva_category`, whose absence is a real
    state (an unclassified domestic row) rather than drift. Conflating the two
    is safe only there, and only because both answers route to the same
    direction-derived flow below rather than to an exemption.
    """
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        return None


def _enum_or_unparseable[EnumT: StrEnum](enum_type: type[EnumT], value: str) -> EnumT | _SchemaDrift:
    """Parse a REQUIRED stored enum value, keeping "unreadable" distinguishable.

    ``lifecycle_state``, ``business_classification`` and ``direction`` are
    ``Field(min_length=1)`` on :class:`LedgerEvidenceRow`, so they are always
    present. A value this build cannot parse is therefore not an absence and
    not a default: it is schema drift, and the row's contribution to a filing
    cannot be judged at all.
    """
    try:
        return enum_type(value)
    except ValueError:
        return _UNPARSEABLE


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
    finalized BEFORE that promotion. That used to be a permanent dead end: the
    bundle is frozen and never recomputed, a finalized revision cannot be
    re-verified (the idempotent guard returns the existing granting report),
    and recalculating returns the same content-addressed revision because
    attaching an invoice does not change any tax fact. It is no longer one --
    ``recapture_ledger_filing_evidence`` re-bundles a sealed revision's
    evidence over unchanged facts -- so the argument for keeping this axis
    loose is now only its cost, not an unrecoverable operator. The divergence
    stays recorded rather than closed on that basis, and the sibling gate above
    no longer relies on it.

    The refusal message below says "purchase invoice evidence" while this test
    accepts any attachment, which reads as an overclaim. It is not one in
    practice: a row only reaches that message with NO evidence of any kind, and
    an invoice is then exactly what the operator needs. The mismatch misleads a
    reader of this file, not an operator, which is why it is answered with this
    comment rather than a message change.
    """
    return bool(row.purchase_invoice_evidence_id) or bool(row.invoice_id) or bool(row.attachment_ids)


def _row_flow(row: LedgerEvidenceRow, *, direction: TransactionDirection) -> IvaFlowDirection | None:
    invoice_kind = invoice_kind_for_direction(direction)
    if invoice_kind is None:
        return None
    category = _enum_or_none(IvaCategory, row.iva_category)
    if category is None:
        return flow_direction_for_invoice_kind(invoice_kind)
    if category in EVIDENCE_EXEMPT_IVA_CATEGORIES:
        return None
    return derive_flow_for_classification(
        category=category,
        invoice_direction=invoice_kind,
    )


def ledger_evidence_row_missing_deductible_iva_evidence(row: LedgerEvidenceRow) -> bool:
    """Return whether an evidence row claims deductible IVA without linked proof.

    ``lifecycle_state``, ``business_classification``, ``direction`` and
    ``iva_category`` are persisted on :class:`LedgerEvidenceRow` as bare strings
    so a frozen bundle round-trips through the strict persistence boundary.
    Parsing them back can fail, and this gate refuses rather than absolves when
    it does: a row it cannot read is a row whose contribution to a filing it
    cannot vouch for, and answering "no gap" there would let a Modelo 303
    input-IVA deduction reach a filing with no documento justificativo behind
    it (LIVA art. 97 enumerates what may support one; LGT art. 105.1 puts the
    burden on the taxpayer).

    The order of the checks is load-bearing, because failing closed on a field
    that could not decide anything would refuse rows that raise no question.
    Each required field is consulted only while the row is still a candidate:
    a parseably-inactive row is excluded before its direction is read, and a
    row already carrying evidence is cleared before its cuota is. So the
    unreadable-value refusals fire only where the unreadable value would
    actually have decided the answer.

    An absent ``iva_amount`` on a row that reaches the last line is a gap, not
    a zero. By then the row is active, business-bearing, on the deducible side
    and carrying no evidence of any kind; a deduction-side claim whose cuota
    was never captured is exactly the missing-input state
    ``no-silent-under-declaration`` keeps distinct from a proven zero.

    ``iva_category`` alone is still read through :func:`_enum_or_none`, because
    its absence is a real state — an unclassified domestic row — and both
    absence and drift route to the same direction-derived flow rather than to
    an exemption, so neither can slip past on that axis.

    Tightening this was gated on a recovery path existing, not on the argument
    being sound: the note above :func:`_row_has_linked_evidence` explains that
    a refusal here used to strand a finalized revision forever. It no longer
    does. ``recapture_ledger_filing_evidence`` re-bundles a sealed revision's
    evidence over unchanged facts without moving its content address, so a row
    refused here can be answered by attaching the document and recapturing.
    """
    lifecycle_state = _enum_or_unparseable(TransactionLifecycleState, row.lifecycle_state)
    if lifecycle_state is _UNPARSEABLE:
        return True
    if lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    business_classification = _enum_or_unparseable(BusinessClassification, row.business_classification)
    if business_classification is _UNPARSEABLE:
        return True
    if business_classification not in BUSINESS_BEARING_STATES:
        return False
    direction = _enum_or_unparseable(TransactionDirection, row.direction)
    if direction is _UNPARSEABLE:
        return True
    flow = _row_flow(row, direction=direction)
    if flow is None or not is_deducible_flow(flow):
        return False
    if _row_has_linked_evidence(row):
        return False
    return row.iva_amount is None or row.iva_amount > Decimal("0")


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
