"""Evidence-presence diagnostics for IVA-bearing ledger rows.

The diagnostics pair a transaction's IVA settlement side with its evidence
presence: a positive deductible input-IVA row must carry supplier evidence,
while a positive output-IVA row without a linked document remains visible to the
operator. This is the ledger-evidence counterpart of the calculate-path
unconsumed-declarable-IVA advisory and follows the
``no-silent-under-declaration`` discipline: never let a missing-evidence row
pass in silence, and let the filing-grade verification layer decide which
legally grounded side blocks.

The trigger set is deliberately narrow. An advisory fires only on an
``ACTIVE`` business/mixed row with a strictly-positive IVA quota and no linked
evidence. Explicit exempt / zero-rated / not-subject IVA categories and
non-declarable sentinels are excluded because they do not route an M303 quota.
Rows with no explicit ``iva_category`` but with a positive ``iva_amount`` remain
in scope: the IVA aggregation layer derives their domestic category from the
stored rate and bank direction before feeding M303.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...domain.iva import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    derive_flow_for_classification,
    is_deducible_flow,
    is_devengada_flow,
)
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionDirection,
    TransactionLifecycleState,
)
from ._source_mesh import CalculationSourceDiagnostic

# IVA categories that never bear a deductible (input) or devengada (output)
# cuota a binding would route, so an evidence-presence advisory on them would
# be noise. Extends the by-law cuota-less set with the non-declarable
# sentinels (recargo de equivalencia is filed under a separate regime;
# unknown / erroneous carry no settled cuota). A None category is treated as
# "not yet a cuota-bearing classification" and likewise excluded.
_EVIDENCE_EXEMPT_IVA_CATEGORIES: frozenset[IvaCategory] = CUOTA_LESS_M303_IVA_CATEGORIES | frozenset(
    {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.ERRONEOUS_INVOICE,
        IvaCategory.UNKNOWN,
    },
)

#: Business classifications that carry a deductible / declarable economic role.
_EVIDENCE_EXPECTING_BUSINESS_STATES: frozenset[BusinessClassification] = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    },
)

#: Legacy diagnostic ``source_kind`` retained for callers that only need the
#: generic reason. New diagnostics use the settlement-side-specific source
#: kinds below.
MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND = "transaction_evidence"

#: Diagnostic ``source_kind`` for missing supplier evidence on positive
#: deductible input IVA. Verification treats this as filing-grade blocking.
MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND = "deductible_vat_evidence"

#: Diagnostic ``source_kind`` for missing linked evidence on positive output IVA.
#: The current transaction model cannot yet distinguish all valid issued-invoice
#: evidence paths, so verification keeps this visible but non-blocking.
MISSING_OUTPUT_VAT_EVIDENCE_SOURCE_KIND = "output_vat_evidence"


def _positive_iva_quota(transaction: Transaction) -> bool:
    """Return whether the row contributes a strictly positive IVA quota."""
    return transaction.iva_amount is not None and transaction.iva_amount > Decimal("0")


def _row_has_linked_evidence(transaction: Transaction) -> bool:
    """Return whether the row already carries any linked evidence."""
    return bool(transaction.purchase_invoice_evidence_id) or bool(transaction.attachment_ids)


def _is_cuota_bearing_iva_category(category: IvaCategory | None) -> bool:
    """Return whether ``category`` is legally expected to bear a routed cuota."""
    return category is None or category not in _EVIDENCE_EXEMPT_IVA_CATEGORIES


def _invoice_kind_for(direction: TransactionDirection) -> InvoiceKind | None:
    """Map bank direction onto the invoice issuance axis used by IVA flow."""
    if direction is TransactionDirection.INCOMING:
        return InvoiceKind.ISSUED
    if direction is TransactionDirection.OUTGOING:
        return InvoiceKind.RECEIVED
    return None


def _flow_for_transaction(transaction: Transaction) -> IvaFlowDirection | None:
    """Return the IVA settlement flow for an evidence-significance test."""
    invoice_kind = _invoice_kind_for(transaction.direction)
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
    """Return the IVA flow requiring evidence, or ``None`` when out of scope."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return None
    if transaction.business_classification not in _EVIDENCE_EXPECTING_BUSINESS_STATES:
        return None
    if not _positive_iva_quota(transaction):
        return None
    if _row_has_linked_evidence(transaction):
        return None
    if not _is_cuota_bearing_iva_category(transaction.iva_category):
        return None
    return _flow_for_transaction(transaction)


def transaction_missing_deductible_vat_evidence(transaction: Transaction) -> bool:
    """Return whether ``transaction`` claims deductible IVA without evidence."""
    flow = _transaction_missing_evidence_flow(transaction)
    return flow is not None and is_deducible_flow(flow)


def transaction_missing_output_vat_evidence(transaction: Transaction) -> bool:
    """Return whether ``transaction`` declares output IVA without linked evidence."""
    flow = _transaction_missing_evidence_flow(transaction)
    return flow is not None and is_devengada_flow(flow) and not is_deducible_flow(flow)


def _missing_evidence_diagnostic(
    transaction: Transaction,
    *,
    role: str,
    source_kind: str,
) -> CalculationSourceDiagnostic:
    """Build the missing-evidence diagnostic for one IVA-bearing row."""
    return CalculationSourceDiagnostic(
        reason="missing_transaction_evidence",
        source_kind=source_kind,
        binding_id=transaction.transaction_id,
        message=(
            f"{role} transaction {transaction.transaction_id!r} declares a positive "
            f"IVA quota but carries no linked evidence (no purchase invoice "
            f"and no attachment); attach the supporting document before filing."
        ),
    )


def missing_evidence_advisory_observations(
    transactions: Iterable[Transaction],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return missing-evidence diagnostics for positive IVA rows.

    A :class:`CalculationSourceDiagnostic` (reason
    ``missing_transaction_evidence``) is emitted for each ``ACTIVE``
    business/mixed row with a strictly-positive IVA quota and no linked
    evidence that is either:

    - a deductible input-IVA row (a supplier purchase invoice/evidence is
      required for filing-grade verification), or
    - an output-IVA row whose IVA category is legally expected to bear a
      devengada cuota — i.e. not in
      :data:`aeat.domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` nor a
      non-declarable sentinel (the issued-invoice evidence gap remains visible).

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
                    role="deductible VAT",
                    source_kind=MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND,
                ),
            )
        elif is_devengada_flow(flow):
            diagnostics.append(
                _missing_evidence_diagnostic(
                    transaction,
                    role="output VAT",
                    source_kind=MISSING_OUTPUT_VAT_EVIDENCE_SOURCE_KIND,
                ),
            )
    return tuple(diagnostics)


__all__ = [
    "MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND",
    "MISSING_OUTPUT_VAT_EVIDENCE_SOURCE_KIND",
    "MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND",
    "missing_evidence_advisory_observations",
    "transaction_missing_deductible_vat_evidence",
    "transaction_missing_output_vat_evidence",
]
