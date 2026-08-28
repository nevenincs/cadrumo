"""Evidence-presence diagnostics for IVA-bearing ledger rows.

The diagnostics pair a transaction's IVA settlement side with its evidence
presence: a positive deductible input-IVA row must carry supplier evidence,
while a positive output-IVA row without a linked document remains visible to the
operator. This is the ledger-evidence counterpart of the calculate-path
unconsumed-declarable-IVA advisory and follows the
``no-silent-under-declaration`` discipline: never let a missing-evidence row
pass in silence, and let the filing-grade verification layer decide which
legally grounded side blocks.

What counts as evidence differs by side, and the difference is statutory rather
than a severity preference. LIVA art. 97 is enumerative — "únicamente se
considerarán documentos justificativos del derecho a la deducción" followed by a
closed list — so only the purchase-invoice evidence axis or a linked, validated
reconciliation-catalogue invoice silences the deductible side. The output side
has no equivalent constitutive requirement and no CLI path that mints
issued-invoice evidence, so any linked document silences it. Holding the
deductible side to the looser test would leave the blocking gate laxer than the
statute it cites.

The trigger set is deliberately narrow. A diagnostic fires only on an ``ACTIVE``
business/mixed row with a strictly-positive IVA quota that lacks the evidence its
side requires. Explicit exempt / zero-rated / not-subject IVA categories and
non-declarable sentinels are excluded because they do not route an M303 quota.
Rows with no explicit ``iva_category`` but with a positive ``iva_amount`` remain
in scope: the IVA aggregation layer derives their domestic category from the
stored rate and bank direction before feeding M303.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...domain.iva import (
    EVIDENCE_EXEMPT_IVA_CATEGORIES,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    derive_flow_for_classification,
    is_deducible_flow,
    is_devengada_flow,
)
from ...domain.transactions import (
    BUSINESS_BEARING_STATES,
    Transaction,
    TransactionLifecycleState,
)
from ._invoice_kind import invoice_kind_for_direction
from ._source_mesh import CalculationSourceDiagnostic

#: Diagnostic ``source_kind`` for missing supplier evidence on positive
#: deductible input IVA. Verification treats this as filing-grade blocking.
MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND = "deductible_iva_evidence"

#: Diagnostic ``source_kind`` for missing linked evidence on positive output IVA.
#: The current transaction model cannot yet distinguish all valid issued-invoice
#: evidence paths, so verification keeps this visible but non-blocking.
MISSING_OUTPUT_IVA_EVIDENCE_SOURCE_KIND = "output_iva_evidence"


def _positive_iva_quota(transaction: Transaction) -> bool:
    """Return whether the row contributes a strictly positive IVA quota."""
    return transaction.iva_amount is not None and transaction.iva_amount > Decimal("0")


def _row_has_linked_evidence(transaction: Transaction) -> bool:
    """Return whether the row carries any linked evidence at all.

    This is the OUTPUT-IVA test, where the requirement is visibility rather than
    legal sufficiency. Use :func:`_row_has_deduction_grade_evidence` for the
    deductible side, which is held to a stricter, statutory standard.
    """
    return bool(transaction.purchase_invoice_evidence_id) or bool(transaction.attachment_ids)


# ALT-EVIDENCE-GRADE-RATIONALE-ADVISORY: this calculate-path test is
# deliberately stricter, on the attachment_ids axis, than
# application.modelo._ledger_evidence_gate._row_has_linked_evidence, the
# filing-grade gate's deductible-side test. LIVA art. 97 is enumerative for
# this side; the filing gate's looser attachment_ids acceptance is a recorded
# divergence (see that function's own docstring), not an oversight.
def _row_has_deduction_grade_evidence(transaction: Transaction) -> bool:
    """Return whether the row carries evidence capable of supporting a deduction.

    LIVA art. 97 is enumerative, not merely constitutive: "únicamente se
    considerarán documentos justificativos del derecho a la deducción" followed
    by a closed list — the original factura, the intra-community supplier's
    factura, the customs liquidation document on an import, and the factura or
    justificante contable under reverse charge. A generic attachment is not in
    that list, so a bank statement, a delivery note or a photograph cannot make a
    deduction defensible however plausible it looks.

    The purchase-invoice evidence axis is the carrier for every one of those four
    document classes; the record's supplier and invoice metadata are optional
    precisely so a customs liquidation or a justificante contable can be
    registered through it. Accepting a bare attachment here would hold the
    blocking gate to a laxer standard than the statute it cites.

    ``invoice_id`` is credited alongside ``purchase_invoice_evidence_id``, not
    instead of it. It references the reconciliation-catalogue
    :class:`~cadrumo.domain.invoices.Invoice` record, which only exists behind
    the sanctioned catalogue writer's content validators (RD 1619/2012 art. 6),
    and ``ledger link`` refuses to stamp a ``Transaction.invoice_id`` that does
    not resolve to one already in that catalogue -- so its mere presence on the
    row is evidence the referenced record passed validation, without this
    module reaching into a repository to re-check it. A validated ``Invoice`` is
    STRONGER evidence than a bare ``PurchaseInvoiceEvidence`` blob (whose fields
    are all optional and carry no art. 6 content check), so crediting it here
    only widens what already passes; it never narrows what already blocks.
    """
    return bool(transaction.purchase_invoice_evidence_id) or bool(transaction.invoice_id)


def _is_cuota_bearing_iva_category(category: IvaCategory | None) -> bool:
    """Return whether ``category`` is legally expected to bear a routed cuota.

    ``None`` is treated as "not yet a cuota-bearing classification" and is
    likewise excluded, alongside the categories named in
    :data:`~cadrumo.domain.iva.EVIDENCE_EXEMPT_IVA_CATEGORIES`.
    """
    return category is None or category not in EVIDENCE_EXEMPT_IVA_CATEGORIES


def _flow_for_transaction(transaction: Transaction) -> IvaFlowDirection | None:
    """Return the IVA settlement flow for an evidence-significance test."""
    invoice_kind = invoice_kind_for_direction(transaction.direction)
    if invoice_kind is None:
        return None
    if transaction.iva_category is None:
        return IvaFlowDirection.REPERCUTIDO if invoice_kind is InvoiceKind.ISSUED else IvaFlowDirection.SOPORTADO
    if not _is_cuota_bearing_iva_category(transaction.iva_category):
        return None
    return derive_flow_for_classification(
        category=transaction.iva_category,
        invoice_direction=invoice_kind,
    )


def _transaction_missing_evidence_flow(transaction: Transaction) -> IvaFlowDirection | None:
    """Return the IVA flow requiring evidence, or ``None`` when out of scope.

    The evidence test is applied per settlement side rather than once up front,
    because the two sides answer to different standards. The deductible side is
    held to LIVA art. 97's closed list of documents that establish the right to
    deduct; the output side, which has no equivalent constitutive requirement and
    no CLI path that mints issued-invoice evidence, is satisfied by any linked
    document. That asymmetry mirrors the per-category severity split downstream,
    where only the deductible finding blocks.
    """
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return None
    if transaction.business_classification not in BUSINESS_BEARING_STATES:
        return None
    if not _positive_iva_quota(transaction):
        return None
    if not _is_cuota_bearing_iva_category(transaction.iva_category):
        return None
    flow = _flow_for_transaction(transaction)
    if flow is None:
        return None
    if is_deducible_flow(flow):
        return None if _row_has_deduction_grade_evidence(transaction) else flow
    return None if _row_has_linked_evidence(transaction) else flow


def transaction_missing_deductible_iva_evidence(transaction: Transaction) -> bool:
    """Return whether ``transaction`` claims deductible IVA without evidence."""
    flow = _transaction_missing_evidence_flow(transaction)
    return flow is not None and is_deducible_flow(flow)


def transaction_missing_output_iva_evidence(transaction: Transaction) -> bool:
    """Return whether ``transaction`` declares output IVA without linked evidence."""
    flow = _transaction_missing_evidence_flow(transaction)
    return flow is not None and is_devengada_flow(flow) and not is_deducible_flow(flow)


def _missing_evidence_diagnostic(
    transaction: Transaction,
    *,
    role: str,
    source_kind: str,
    gap: str,
) -> CalculationSourceDiagnostic:
    """Build the missing-evidence diagnostic for one IVA-bearing row.

    ``gap`` states what is actually absent, which differs by side. Saying "no
    attachment" on a deductible row that carries one would be false, and a
    refusal an operator can disprove by looking at the row teaches them to
    distrust the gate.
    """
    return CalculationSourceDiagnostic(
        reason="missing_transaction_evidence",
        source_kind=source_kind,
        binding_id=transaction.transaction_id,
        message=(f"{role} transaction {transaction.transaction_id!r} declares a positive IVA quota but {gap}."),
    )


def missing_evidence_advisory_observations(
    transactions: Iterable[Transaction],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return missing-evidence diagnostics for positive IVA rows.

    A :class:`CalculationSourceDiagnostic` (reason
    ``missing_transaction_evidence``) is emitted for each ``ACTIVE``
    business/mixed row with a strictly-positive IVA quota that lacks the evidence
    its settlement side requires:

    - a deductible input-IVA row carrying no purchase-invoice evidence and no
      linked, validated reconciliation-catalogue invoice. A generic attachment
      does NOT satisfy this side: LIVA art. 97 enumerates the documents that
      establish the right to deduct and an attachment is not among them. This
      diagnostic blocks verification downstream.
    - an output-IVA row whose IVA category is legally expected to bear a
      devengada cuota — i.e. not in
      :data:`~cadrumo.domain.iva.EVIDENCE_EXEMPT_IVA_CATEGORIES` — carrying no
      linked evidence of any kind (the issued-invoice evidence gap remains
      visible but advisory).

    Rows that legitimately bear no evidence requirement — non-business /
    personal, exempt / zero-rated / not-subject / sentinel IVA categories, no
    positive IVA quota, and non-ACTIVE lifecycle states — are excluded and never
    fire.

    Args:
        transactions: The revision's source transactions to inspect.

    Returns:
        A tuple of non-blocking missing-evidence diagnostics, in input order.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for transaction in transactions:
        flow = _transaction_missing_evidence_flow(transaction)
        if flow is None:
            continue
        if is_deducible_flow(flow):
            diagnostics.append(
                _missing_evidence_diagnostic(
                    transaction,
                    role="deductible IVA",
                    source_kind=MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND,
                    gap=(
                        "carries no purchase invoice evidence; LIVA art. 97 lists the "
                        "documents that establish the right to deduct, and a generic "
                        "attachment is not one of them, so register the invoice and "
                        "link it before filing"
                    ),
                ),
            )
        elif is_devengada_flow(flow):
            diagnostics.append(
                _missing_evidence_diagnostic(
                    transaction,
                    role="output IVA",
                    source_kind=MISSING_OUTPUT_IVA_EVIDENCE_SOURCE_KIND,
                    gap=(
                        "carries no linked evidence (no purchase invoice and no "
                        "attachment); attach the supporting document before filing"
                    ),
                ),
            )
    return tuple(diagnostics)


__all__ = [
    "MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND",
    "MISSING_OUTPUT_IVA_EVIDENCE_SOURCE_KIND",
    "missing_evidence_advisory_observations",
    "transaction_missing_deductible_iva_evidence",
    "transaction_missing_output_iva_evidence",
]
