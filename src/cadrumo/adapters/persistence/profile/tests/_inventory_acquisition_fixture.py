"""Build the complete acquisition cost a purchase movement requires.

``MovementRecord`` refuses a purchase whose ``acquisition_cost`` is absent or
whose consideration, IVA and recoverability ratio do not agree with the
movement's own value, rate and ratio. Composing that record correctly takes
three evidence rows and a completeness attestation, so the construction lives
here once rather than in each test module that needs a valid purchase.
"""

from __future__ import annotations

from decimal import Decimal

from .....domain.contribuyente.inventory import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
)
from .....domain.filing_evidence import FilingEvidenceReference

PURCHASE_INVOICE_REFERENCE = "INVENTORY-PURCHASE-INVOICE"
COST_REVIEW_REFERENCE = "INVENTORY-ATTRIBUTABLE-COST-REVIEW"
IVA_REVIEW_REFERENCE = "INVENTORY-IVA-RECOVERABILITY-REVIEW"


def evidence_reference(value: str) -> FilingEvidenceReference:
    """Wrap a raw reference string as a filing-evidence reference."""
    return FilingEvidenceReference(reference=value)


def acquisition_for(value: Decimal, *, iva_rate: Decimal, ratio: Decimal) -> InventoryAcquisitionCost:
    """Return the complete acquisition cost a purchase movement now requires.

    A purchase must carry consideration equal to its own value, IVA equal to its
    own rate applied to that value, and a matching recoverability ratio -- the
    record refuses any other combination. Every completeness attestation must
    also resolve to a real evidence entry, so the two review references have
    evidence rows of their own rather than naming documents that do not exist.

    Args:
        value: The purchase consideration excluding IVA.
        iva_rate: The IVA rate percentage applied to that consideration.
        ratio: The fraction of input IVA the contribuyente may recover.

    Returns:
        An acquisition cost consistent with those three inputs.
    """
    iva = (value * iva_rate / Decimal("100")).quantize(Decimal("0.01"))
    return InventoryAcquisitionCost(
        consideration_excluding_iva=value,
        consideration_iva_amount=iva,
        consideration_deductible_iva_ratio=ratio,
        attributable_cost_components=(),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=evidence_reference(PURCHASE_INVOICE_REFERENCE),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a1" * 32,
            ),
            InventoryAcquisitionEvidence(
                reference=evidence_reference(COST_REVIEW_REFERENCE),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="a2" * 32,
            ),
            InventoryAcquisitionEvidence(
                reference=evidence_reference(IVA_REVIEW_REFERENCE),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="a3" * 32,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=evidence_reference(PURCHASE_INVOICE_REFERENCE),
            attributable_cost_review_evidence=evidence_reference(COST_REVIEW_REFERENCE),
            iva_recoverability_review_evidence=evidence_reference(IVA_REVIEW_REFERENCE),
        ),
        directly_attributable_cost_total=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        recoverable_iva_excluded=iva,
        total_acquisition_cost=value,
    )
