"""Private acquisition detail released by an exact-profile inventory read."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidenceKind,
    InventoryAttributableCostKind,
)
from ..operations.public_scalar import PublicDecimal


class InventoryAttributableCostDetailProjection(BaseModel):
    """One directly attributable cost as the operator stated it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    component_id: str
    kind: InventoryAttributableCostKind
    taxable_base: PublicDecimal
    iva_amount: PublicDecimal
    deductible_iva_ratio: PublicDecimal
    evidence_references: tuple[str, ...]


class InventoryAcquisitionDocumentProjection(BaseModel):
    """One purchase document's identity; its bytes stay in custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    reference: str
    evidence_kind: InventoryAcquisitionEvidenceKind
    content_digest: str
    file_name: str | None = None


class InventoryAcquisitionDetailProjection(BaseModel):
    """The private facts of one purchase, released only by the exact-profile inspect read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    consideration_iva_amount: PublicDecimal
    consideration_deductible_iva_ratio: PublicDecimal
    components: tuple[InventoryAttributableCostDetailProjection, ...]
    documents: tuple[InventoryAcquisitionDocumentProjection, ...]
    consideration_evidence: str
    attributable_cost_review_evidence: str
    iva_recoverability_review_evidence: str

    @classmethod
    def from_acquisition(
        cls, acquisition: InventoryAcquisitionCost, *, document_file_names: Mapping[str, str]
    ) -> InventoryAcquisitionDetailProjection:
        """Project what correcting this purchase would otherwise ask for again."""
        return cls(
            consideration_iva_amount=PublicDecimal(decimal=str(acquisition.consideration_iva_amount)),
            consideration_deductible_iva_ratio=PublicDecimal(
                decimal=str(acquisition.consideration_deductible_iva_ratio)
            ),
            components=tuple(
                InventoryAttributableCostDetailProjection(
                    component_id=item.component_id,
                    kind=item.kind,
                    taxable_base=PublicDecimal(decimal=str(item.taxable_base)),
                    iva_amount=PublicDecimal(decimal=str(item.iva_amount)),
                    deductible_iva_ratio=PublicDecimal(decimal=str(item.deductible_iva_ratio)),
                    evidence_references=tuple(reference.reference for reference in item.evidence_references),
                )
                for item in acquisition.attributable_cost_components
            ),
            documents=tuple(
                InventoryAcquisitionDocumentProjection(
                    reference=item.reference.reference,
                    evidence_kind=item.evidence_kind,
                    content_digest=item.content_digest,
                    file_name=document_file_names.get(str(item.content_digest)),
                )
                for item in acquisition.evidence
            ),
            consideration_evidence=acquisition.completeness.consideration_evidence.reference,
            attributable_cost_review_evidence=acquisition.completeness.attributable_cost_review_evidence.reference,
            iva_recoverability_review_evidence=acquisition.completeness.iva_recoverability_review_evidence.reference,
        )
