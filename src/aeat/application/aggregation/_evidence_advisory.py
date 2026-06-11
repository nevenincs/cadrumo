"""Evidence-presence advisory for economically significant ledger rows.

The advisory pairs a transaction's *economic role* with its *evidence
presence*: a positive-amount business expense with a deductible IVA category
but no purchase invoice, or a cuota-bearing income with no issued invoice,
files silently with no operator alert unless a non-blocking advisory surfaces
it. This is the ledger-evidence counterpart of the calculate-path
unconsumed-declarable-IVA advisory and follows the
``no-silent-under-declaration`` discipline: never block a legitimately
evidence-free filing, but never let a missing-evidence row pass in silence.

The trigger set is deliberately narrow. An advisory fires only on an
``ACTIVE`` row with a strictly-positive gross amount whose IVA category is
legally expected to bear a deductible/devengada cuota (everything outside
:data:`aeat.domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` and the non-declarable
sentinels) and that carries no linked evidence. Non-business / personal rows,
exempt / zero-rated / not-subject categories, zero-amount rows, and non-ACTIVE
lifecycle states are excluded and never fire — a noisy advisory trains
operators to ignore it.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...domain.iva import CUOTA_LESS_M303_IVA_CATEGORIES, IvaCategory
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

#: Diagnostic ``source_kind`` for the missing-evidence advisory. Kept distinct
#: from C4's ``invoice`` and from C2's ``purchase_invoice_evidence`` source kind
#: so the advisory channel is greppable and never confused with a routed value.
MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND = "transaction_evidence"


def _gross_amount(transaction: Transaction) -> Decimal:
    """Return the non-negative gross magnitude for evidence-significance tests.

    Amounts are stored as non-negative magnitudes (flow lives on
    :attr:`Transaction.direction`); the EUR projection is preferred when the
    row was converted at import so the threshold test is currency-stable.
    """
    if transaction.value_in_eur is not None:
        return transaction.value_in_eur
    return abs(transaction.raw.amount)


def _row_has_linked_evidence(transaction: Transaction) -> bool:
    """Return whether the row already carries any linked evidence."""
    return bool(transaction.purchase_invoice_evidence_id) or bool(transaction.attachment_ids)


def _is_cuota_bearing_iva_category(category: IvaCategory | None) -> bool:
    """Return whether ``category`` is legally expected to bear a routed cuota."""
    return category is not None and category not in _EVIDENCE_EXEMPT_IVA_CATEGORIES


def _missing_evidence_diagnostic(transaction: Transaction, *, role: str) -> CalculationSourceDiagnostic:
    """Build the non-blocking missing-evidence advisory for one row."""
    return CalculationSourceDiagnostic(
        reason="missing_transaction_evidence",
        source_kind=MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND,
        binding_id=transaction.transaction_id,
        message=(
            f"{role} transaction {transaction.transaction_id!r} declares a positive "
            f"cuota-bearing amount but carries no linked evidence (no purchase invoice "
            f"and no attachment); attach the supporting document before filing."
        ),
    )


def missing_evidence_advisory_observations(
    transactions: Iterable[Transaction],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return missing-evidence advisories for economically significant rows.

    A :class:`CalculationSourceDiagnostic` (reason
    ``missing_transaction_evidence``) is emitted for each ``ACTIVE`` row with a
    strictly-positive gross amount and no linked evidence that is either:

    - an ``OUTGOING`` ``BUSINESS`` / ``MIXED`` expense whose IVA category bears
      a deductible cuota (a purchase invoice is expected), or
    - an ``INCOMING`` row whose IVA category is legally expected to bear a
      devengada cuota — i.e. not in
      :data:`aeat.domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` nor a
      non-declarable sentinel (the issued invoice is expected).

    Rows that legitimately bear no evidence requirement — non-business /
    personal, exempt / zero-rated / not-subject / sentinel IVA categories,
    zero-amount, and non-ACTIVE lifecycle states — are excluded and never fire.

    Args:
        transactions: The revision's source transactions to inspect.

    Returns:
        A tuple of non-blocking missing-evidence diagnostics, in input order.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for transaction in transactions:
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if _gross_amount(transaction) <= Decimal("0"):
            continue
        if _row_has_linked_evidence(transaction):
            continue
        if not _is_cuota_bearing_iva_category(transaction.iva_category):
            continue
        if transaction.direction is TransactionDirection.OUTGOING:
            if transaction.business_classification not in _EVIDENCE_EXPECTING_BUSINESS_STATES:
                continue
            diagnostics.append(_missing_evidence_diagnostic(transaction, role="OUTGOING business expense"))
        elif transaction.direction is TransactionDirection.INCOMING:
            diagnostics.append(_missing_evidence_diagnostic(transaction, role="INCOMING cuota-bearing income"))
    return tuple(diagnostics)


__all__ = [
    "MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND",
    "missing_evidence_advisory_observations",
]
