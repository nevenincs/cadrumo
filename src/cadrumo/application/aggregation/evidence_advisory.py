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
business/mixed row that lacks the evidence its side requires. Explicit exempt /
zero-rated / not-subject IVA categories and non-declarable sentinels are
excluded because they do not route an M303 quota. Rows with no explicit
``iva_category`` remain in scope: the IVA aggregation layer derives their
domestic category from the stored rate and bank direction before feeding M303.

The two sides read the cuota differently. The output side fires only on a
strictly-positive ``iva_amount``. The deductible side also fires on an ABSENT
``iva_amount``, but only for a revision that claims IVA at all, which is a
revision whose registry declares ``ledger_iva_aggregation`` bindings. There a
deduction-side row whose cuota was never captured is a missing input, not a
proven zero, and only an explicit ``0.00`` clears it. A revision without those
bindings -- an IRPF return such as Modelo 130 or 100 -- makes no IVA claim, so
a base-only expense with no cuota claims no IVA deduction and is not an IVA
gap. A positive cuota is still judged on every revision, as before.

:func:`iva_evidence_flow`, :func:`calculation_revision_claims_ledger_iva` and
:func:`deductible_iva_evidence_gap` are the one evaluation of the deductible
side. Verification applies them to the live :class:`Transaction` rows here, and
the export and local-filing gate in ``application.modelo._ledger_evidence_gate``
applies them to the frozen evidence bundle, so verify cannot grant a revision
those gates then refuse. Only the evidence test is supplied per caller, and
verify's is the stricter one, so whatever verify clears the later gates clear
too.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.iva.components import registry_category_projection
from ...domain.iva.flow import (
    IvaFlowDirection,
    derive_flow_for_classification,
    flow_direction_for_invoice_kind,
    is_deducible_flow,
    is_devengada_flow,
)
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.transactions.enums import (
    BUSINESS_BEARING_STATES,
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...domain.transactions.models import Transaction
from .invoice_kind import invoice_kind_for_direction
from .source_mesh import CalculationSourceDiagnostic

#: Diagnostic ``source_kind`` for missing supplier evidence on deductible input
#: IVA whose cuota is positive or was never captured. Verification treats this
#: as filing-grade blocking.
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
    :class:`~cadrumo.domain.invoices.models.Invoice` record, which only exists behind
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


def iva_evidence_flow(
    *,
    lifecycle_state: TransactionLifecycleState,
    business_classification: BusinessClassification,
    direction: TransactionDirection,
    iva_category: IvaCategory | None,
) -> IvaFlowDirection | None:
    """Return the IVA settlement flow a ledger row answers for, or ``None``.

    ``None`` means the row bears no evidence duty at all: it is not ``ACTIVE``,
    not business-bearing, has no invoice kind (an internal transfer), or its
    category is in the published 0084 evidence-exempt projection. An absent
    category is an unclassified domestic row and takes the direction's flow.
    """
    if lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return None
    if business_classification not in BUSINESS_BEARING_STATES:
        return None
    invoice_kind = invoice_kind_for_direction(direction)
    if invoice_kind is None:
        return None
    if iva_category is None:
        return flow_direction_for_invoice_kind(invoice_kind)
    if iva_category in registry_category_projection("evidence_exempt"):
        return None
    return derive_flow_for_classification(category=iva_category, invoice_direction=invoice_kind)


def calculation_revision_claims_ledger_iva(
    revision: CalculationRevision,
    *,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether ``revision``'s registry revision declares IVA ledger bindings.

    This is the typed fact that says whether a calculation claims IVA at all:
    the registry revision the calculation is stamped with either declares
    ``ledger_iva_aggregation`` bindings (Modelo 303 and its kin) or does not
    (an IRPF return such as Modelo 130 or 100, which has no IVA claim).

    A registry revision that cannot be read answers ``True``. An unreadable
    authority cannot excuse an uncaptured cuota, and verification already
    blocks on the unresolved snapshot on its own account.
    """
    ref = revision.registry_snapshot_ref
    try:
        snapshot = operation.snapshot(
            ref.modelo,
            filing_year=ref.modelo_year,
            period=ref.period,
            revision_id=ref.revision_id,
        )
    except (FileNotFoundError, RegistrySnapshotError, RegistryValidationError):
        return True
    return any(binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION for binding in snapshot.revision.bindings)


def deductible_iva_evidence_gap(
    *,
    flow: IvaFlowDirection | None,
    iva_amount: Decimal | None,
    has_deduction_evidence: bool,
    revision_claims_ledger_iva: bool,
) -> bool:
    """Return whether a row claims deductible IVA that its evidence cannot support.

    An absent ``iva_amount`` on the deducible side is a gap only on a revision
    that claims IVA (``revision_claims_ledger_iva``). There the cuota was never
    captured, which is the missing-input state ``no-silent-under-declaration``
    keeps distinct from a proven zero. On a revision with no IVA claim, an
    absent cuota claims nothing. An explicit ``0.00`` deducts nothing and needs
    no documento justificativo on either. A positive cuota without evidence is
    a gap on every revision.
    """
    if flow is None or not is_deducible_flow(flow):
        return False
    if has_deduction_evidence:
        return False
    if iva_amount is None:
        return revision_claims_ledger_iva
    return iva_amount > Decimal("0")


def _transaction_missing_evidence_flow(
    transaction: Transaction,
    *,
    revision_claims_ledger_iva: bool,
) -> IvaFlowDirection | None:
    """Return the IVA flow requiring evidence, or ``None`` when out of scope.

    The evidence test is applied per settlement side rather than once up front,
    because the two sides answer to different standards. The deductible side is
    held to LIVA art. 97's closed list of documents that establish the right to
    deduct; the output side, which has no equivalent constitutive requirement and
    no CLI path that mints issued-invoice evidence, is satisfied by any linked
    document. That asymmetry mirrors the per-category severity split downstream,
    where only the deductible finding blocks.
    """
    flow = iva_evidence_flow(
        lifecycle_state=transaction.lifecycle_state,
        business_classification=transaction.business_classification,
        direction=transaction.direction,
        iva_category=transaction.iva_category,
    )
    if flow is None:
        return None
    if is_deducible_flow(flow):
        gap = deductible_iva_evidence_gap(
            flow=flow,
            iva_amount=transaction.iva_amount,
            has_deduction_evidence=_row_has_deduction_grade_evidence(transaction),
            revision_claims_ledger_iva=revision_claims_ledger_iva,
        )
        return flow if gap else None
    if not _positive_iva_quota(transaction):
        return None
    return None if _row_has_linked_evidence(transaction) else flow


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
    claim = "declares a positive IVA quota" if _positive_iva_quota(transaction) else "records no IVA quota"
    return CalculationSourceDiagnostic(
        reason="missing_transaction_evidence",
        source_kind=source_kind,
        binding_id=transaction.transaction_id,
        message=f"{role} transaction {transaction.transaction_id!r} {claim} but {gap}.",
    )


def missing_evidence_advisory_observations(
    transactions: Iterable[Transaction],
    *,
    revision_claims_ledger_iva: bool,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return missing-evidence diagnostics for IVA-bearing rows.

    A :class:`CalculationSourceDiagnostic` (reason
    ``missing_transaction_evidence``) is emitted for each ``ACTIVE``
    business/mixed row that lacks the evidence its settlement side requires:

    - a deductible input-IVA row whose cuota is positive, OR was never
      captured on a revision that claims IVA (``revision_claims_ledger_iva``),
      carrying no purchase-invoice evidence and no linked, validated
      reconciliation-catalogue invoice. A generic attachment does NOT satisfy
      this side: LIVA art. 97 enumerates the documents that establish the right
      to deduct and an attachment is not among them. This diagnostic blocks
      verification downstream, on the same evaluation export and local filing
      refuse.
    - an output-IVA row with a strictly-positive cuota whose IVA category is
      legally expected to bear a devengada cuota — i.e. not in the published
      0084 evidence-exempt projection — carrying no linked evidence of any kind
      (the issued-invoice evidence gap remains visible but advisory).

    Rows that legitimately bear no evidence requirement — non-business /
    personal, exempt / zero-rated / not-subject / sentinel IVA categories, an
    explicit zero cuota, an absent cuota on the output side or on a revision
    with no IVA claim, and non-ACTIVE lifecycle states — are excluded and never
    fire.

    Args:
        transactions: The revision's source transactions to inspect.
        revision_claims_ledger_iva: Whether the revision's registry revision
            declares IVA ledger bindings; see
            :func:`calculation_revision_claims_ledger_iva`.

    Returns:
        A tuple of non-blocking missing-evidence diagnostics, in input order.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for transaction in transactions:
        flow = _transaction_missing_evidence_flow(transaction, revision_claims_ledger_iva=revision_claims_ledger_iva)
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
                        "link it before filing, or record a 0.00 cuota when nothing "
                        "is deducted"
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
    "calculation_revision_claims_ledger_iva",
    "deductible_iva_evidence_gap",
    "iva_evidence_flow",
    "missing_evidence_advisory_observations",
]
