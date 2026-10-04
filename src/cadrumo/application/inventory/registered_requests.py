"""Canonical profile-bound inventory requests and operation identifiers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.filing_year import FilingYear
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingValuationBasis,
    PhysicalClosingEvidence,
    PhysicalClosingObservation,
    PriorClosingContinuityEvidence,
)
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAttributableCostComponent,
    InventoryAttributableCostKind,
    MovementKind,
)
from ...domain.filing_evidence import FilingEvidenceReference
from ..operations.public_scalar import PublicDecimal

if TYPE_CHECKING:
    from ...domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord

INVENTORY_LIST_OPERATION_DEFINITION_ID = "ledger.inventory.list"
INVENTORY_CREATE_OPERATION_DEFINITION_ID = "ledger.inventory.create"
INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID = "ledger.inventory.movement.add"
INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID = "ledger.inventory.valuation.preview"
INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID = "ledger.inventory.closing-authority.record"

INVENTORY_VALIDATION_REFUSAL_CODE = "REFUSED_PROFILE_INVENTORY_VALIDATION"
INVENTORY_SERVICE_INPUT_REFUSAL_CODE = "REFUSED_INVENTORY_SERVICE_INPUT"
INVENTORY_NOT_FOUND_REFUSAL_CODE = "REFUSED_INVENTORY_ACTIVIDAD_NOT_FOUND"
INVENTORY_CONFLICT_REFUSAL_CODE = "REFUSED_INVENTORY_ACTIVIDAD_CONFLICT"

type InventoryRefusalReason = Literal[
    "activity_conflict",
    "activity_not_found",
    "invalid_valuation_method",
    "duplicate_movement_id",
    "inventory_validation",
    "closing_authority_conflict",
    "closing_authority_invalid",
]
type InventoryRefusalCode = Literal[
    "REFUSED_PROFILE_INVENTORY_VALIDATION",
    "REFUSED_INVENTORY_SERVICE_INPUT",
    "REFUSED_INVENTORY_ACTIVIDAD_NOT_FOUND",
    "REFUSED_INVENTORY_ACTIVIDAD_CONFLICT",
]
type InventoryOperationId = Literal["list", "create", "movement.add", "valuation.preview", "closing-authority.record"]
type InventoryMutationOperationId = Literal["create", "movement.add", "valuation.preview", "closing-authority.record"]


class _InventoryRequest(BaseModel):
    """Common hidden-input policy for financial inventory operands."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class InventoryListRequest(_InventoryRequest):
    """List every activity ledger in one immutable profile."""


class InventoryCreateRequest(_InventoryRequest):
    """Create one inventory ledger for the exact profile and activity."""

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: str = Field(min_length=1)
    opening_stock: PublicDecimal = Field(default_factory=lambda: PublicDecimal(decimal="0"))


class InventoryAttributableCostComponentRequest(BaseModel):
    """Closed input row with decimal strings at the public operation boundary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    component_id: str = Field(min_length=1, max_length=128)
    kind: InventoryAttributableCostKind
    taxable_base: PublicDecimal
    iva_amount: PublicDecimal
    deductible_iva_ratio: PublicDecimal
    evidence_references: tuple[FilingEvidenceReference, ...] = Field(min_length=1)

    @classmethod
    def from_domain(
        cls,
        component: InventoryAttributableCostComponent,
    ) -> InventoryAttributableCostComponentRequest:
        """Project the established canonical stdin representation onto the worker DTO."""
        return cls(
            component_id=component.component_id,
            kind=component.kind,
            taxable_base=PublicDecimal(decimal=str(component.taxable_base)),
            iva_amount=PublicDecimal(decimal=str(component.iva_amount)),
            deductible_iva_ratio=PublicDecimal(decimal=str(component.deductible_iva_ratio)),
            evidence_references=component.evidence_references,
        )


class InventoryAcquisitionCostRequest(BaseModel):
    """Secure request DTO for sensitive purchase-cost evidence and amounts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    consideration_excluding_iva: PublicDecimal
    consideration_iva_amount: PublicDecimal
    consideration_deductible_iva_ratio: PublicDecimal
    attributable_cost_components: tuple[InventoryAttributableCostComponentRequest, ...]
    evidence: tuple[InventoryAcquisitionEvidence, ...] = Field(min_length=1)
    completeness: InventoryAcquisitionCompleteness
    directly_attributable_cost_total: PublicDecimal
    nonrecoverable_iva_included: PublicDecimal
    recoverable_iva_excluded: PublicDecimal
    total_acquisition_cost: PublicDecimal

    @classmethod
    def from_domain(cls, acquisition: InventoryAcquisitionCost) -> InventoryAcquisitionCostRequest:
        """Keep the operator's canonical JSON payload while storing typed scalars."""
        return cls(
            consideration_excluding_iva=PublicDecimal(decimal=str(acquisition.consideration_excluding_iva)),
            consideration_iva_amount=PublicDecimal(decimal=str(acquisition.consideration_iva_amount)),
            consideration_deductible_iva_ratio=PublicDecimal(
                decimal=str(acquisition.consideration_deductible_iva_ratio),
            ),
            attributable_cost_components=tuple(
                InventoryAttributableCostComponentRequest.from_domain(component)
                for component in acquisition.attributable_cost_components
            ),
            evidence=acquisition.evidence,
            completeness=acquisition.completeness,
            directly_attributable_cost_total=PublicDecimal(decimal=str(acquisition.directly_attributable_cost_total)),
            nonrecoverable_iva_included=PublicDecimal(decimal=str(acquisition.nonrecoverable_iva_included)),
            recoverable_iva_excluded=PublicDecimal(decimal=str(acquisition.recoverable_iva_excluded)),
            total_acquisition_cost=PublicDecimal(decimal=str(acquisition.total_acquisition_cost)),
        )

    def to_domain(self) -> InventoryAcquisitionCost:
        """Build the existing canonical domain operand inside worker custody."""
        return InventoryAcquisitionCost(
            consideration_excluding_iva=Decimal(self.consideration_excluding_iva.decimal),
            consideration_iva_amount=Decimal(self.consideration_iva_amount.decimal),
            consideration_deductible_iva_ratio=Decimal(self.consideration_deductible_iva_ratio.decimal),
            attributable_cost_components=tuple(
                InventoryAttributableCostComponent(
                    component_id=component.component_id,
                    kind=component.kind,
                    taxable_base=Decimal(component.taxable_base.decimal),
                    iva_amount=Decimal(component.iva_amount.decimal),
                    deductible_iva_ratio=Decimal(component.deductible_iva_ratio.decimal),
                    evidence_references=component.evidence_references,
                )
                for component in self.attributable_cost_components
            ),
            evidence=self.evidence,
            completeness=self.completeness,
            directly_attributable_cost_total=Decimal(self.directly_attributable_cost_total.decimal),
            nonrecoverable_iva_included=Decimal(self.nonrecoverable_iva_included.decimal),
            recoverable_iva_excluded=Decimal(self.recoverable_iva_excluded.decimal),
            total_acquisition_cost=Decimal(self.total_acquisition_cost.decimal),
        )


class InventoryMovementAddRequest(_InventoryRequest):
    """Append one typed movement without putting source evidence on argv."""

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    movement_id: str = Field(min_length=1, max_length=64)
    movement_date: date
    kind: MovementKind
    quantity: PublicDecimal
    unit_cost: PublicDecimal | None = None
    taxable_base: PublicDecimal | None = None
    acquisition_cost: InventoryAcquisitionCostRequest | None = None


class InventoryValuationPreviewRequest(_InventoryRequest):
    """Run and audit a valuation preview for one exact activity ledger."""

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)


class InventoryClosingAuthorityDecisionRequest(BaseModel):
    """Strict wire DTO for an inventory closing-authority decision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    decision_id: str = Field(min_length=1, max_length=128)
    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    authority: InventoryClosingAuthority
    physical_observation_id: str | None = Field(default=None, min_length=1, max_length=128)
    physical_observation_fingerprint: ContentDigest | None = None
    reason: str = Field(min_length=1, max_length=512)
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    decided_at: datetime
    evidence: tuple[InventoryClosingDecisionEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _decision_timestamp_is_utc(self) -> InventoryClosingAuthorityDecisionRequest:
        validate_utc_aware(self.decided_at)
        return self


class InventoryPriorClosingLinkRequest(BaseModel):
    """Strict wire DTO for one immediately prior authoritative closing link."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    actividad_id: str = Field(min_length=1)
    current_filing_year: int = Field(ge=2001, le=2100)
    prior_filing_year: int = Field(ge=2000, le=2099)
    prior_authoritative_closing_value: PublicDecimal
    current_opening_value: PublicDecimal
    prior_authoritative_source_fingerprint: ContentDigest
    prior_authoritative_closing_fingerprint: ContentDigest
    evidence: tuple[PriorClosingContinuityEvidence, ...] = Field(min_length=1)


class InventoryPhysicalClosingObservationRequest(BaseModel):
    """Strict wire DTO for a physical closing observation and its evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    observation_id: str = Field(min_length=1, max_length=128)
    observed_on: date
    as_of_date: date
    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    closing_value: PublicDecimal
    valuation_basis: InventoryClosingValuationBasis
    evidence: tuple[PhysicalClosingEvidence, ...] = Field(min_length=2)


class InventoryClosingAuthorityRecordInput(BaseModel):
    """Full bounded private request for a closing-authority record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    decision: InventoryClosingAuthorityDecisionRequest
    physical_observation: InventoryPhysicalClosingObservationRequest | None = None
    prior_closing_link: InventoryPriorClosingLinkRequest

    @classmethod
    def from_domain(cls, record: InventoryClosingAuthorityRecord) -> InventoryClosingAuthorityRecordInput:
        """Convert the established canonical JSON record into the closed worker DTO."""
        decision = record.decision
        physical = record.physical_observation
        prior = record.prior_closing_link
        return cls(
            decision=InventoryClosingAuthorityDecisionRequest(
                decision_id=decision.decision_id,
                actividad_id=decision.actividad_id,
                filing_year=decision.filing_year,
                authority=decision.authority,
                physical_observation_id=decision.physical_observation_id,
                physical_observation_fingerprint=decision.physical_observation_fingerprint,
                reason=decision.reason,
                actor=decision.actor,
                source_command=decision.source_command,
                decided_at=decision.decided_at,
                evidence=decision.evidence,
            ),
            physical_observation=(
                InventoryPhysicalClosingObservationRequest(
                    observation_id=physical.observation_id,
                    observed_on=physical.observed_on,
                    as_of_date=physical.as_of_date,
                    actividad_id=physical.actividad_id,
                    filing_year=physical.filing_year,
                    closing_value=PublicDecimal(decimal=str(physical.closing_value)),
                    valuation_basis=physical.valuation_basis,
                    evidence=physical.evidence,
                )
                if physical is not None
                else None
            ),
            prior_closing_link=InventoryPriorClosingLinkRequest(
                actividad_id=prior.actividad_id,
                current_filing_year=prior.current_filing_year,
                prior_filing_year=prior.prior_filing_year,
                prior_authoritative_closing_value=PublicDecimal(
                    decimal=str(prior.prior_authoritative_closing_value),
                ),
                current_opening_value=PublicDecimal(decimal=str(prior.current_opening_value)),
                prior_authoritative_source_fingerprint=prior.prior_authoritative_source_fingerprint,
                prior_authoritative_closing_fingerprint=prior.prior_authoritative_closing_fingerprint,
                evidence=prior.evidence,
            ),
        )

    def to_domain(self) -> InventoryClosingAuthorityRecord:
        """Build the canonical evidenced authority bundle inside worker custody."""
        from ...domain.contribuyente.inventory.closing_authority_records import (
            InventoryClosingAuthorityDecision,
            InventoryClosingAuthorityRecord,
            PriorAuthoritativeClosingLink,
        )

        decision = InventoryClosingAuthorityDecision(
            decision_id=self.decision.decision_id,
            actividad_id=self.decision.actividad_id,
            filing_year=self.decision.filing_year,
            authority=self.decision.authority,
            physical_observation_id=self.decision.physical_observation_id,
            physical_observation_fingerprint=self.decision.physical_observation_fingerprint,
            reason=self.decision.reason,
            actor=self.decision.actor,
            source_command=self.decision.source_command,
            decided_at=validate_utc_aware(self.decision.decided_at),
            evidence=self.decision.evidence,
        )
        physical = self.physical_observation
        physical_observation = (
            PhysicalClosingObservation(
                observation_id=physical.observation_id,
                observed_on=physical.observed_on,
                as_of_date=physical.as_of_date,
                actividad_id=physical.actividad_id,
                filing_year=physical.filing_year,
                closing_value=Decimal(physical.closing_value.decimal),
                valuation_basis=physical.valuation_basis,
                evidence=physical.evidence,
            )
            if physical is not None
            else None
        )
        prior = self.prior_closing_link
        prior_closing_link = PriorAuthoritativeClosingLink(
            actividad_id=prior.actividad_id,
            current_filing_year=prior.current_filing_year,
            prior_filing_year=prior.prior_filing_year,
            prior_authoritative_closing_value=Decimal(prior.prior_authoritative_closing_value.decimal),
            current_opening_value=Decimal(prior.current_opening_value.decimal),
            prior_authoritative_source_fingerprint=prior.prior_authoritative_source_fingerprint,
            prior_authoritative_closing_fingerprint=prior.prior_authoritative_closing_fingerprint,
            evidence=prior.evidence,
        )
        return InventoryClosingAuthorityRecord(
            decision=decision,
            physical_observation=physical_observation,
            prior_closing_link=prior_closing_link,
        )


class InventoryClosingAuthorityRecordRequest(_InventoryRequest):
    """Record one complete typed closing-authority source in the profile."""

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    authority_record: InventoryClosingAuthorityRecordInput


__all__ = [
    "INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID",
    "INVENTORY_CONFLICT_REFUSAL_CODE",
    "INVENTORY_CREATE_OPERATION_DEFINITION_ID",
    "INVENTORY_LIST_OPERATION_DEFINITION_ID",
    "INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID",
    "INVENTORY_NOT_FOUND_REFUSAL_CODE",
    "INVENTORY_SERVICE_INPUT_REFUSAL_CODE",
    "INVENTORY_VALIDATION_REFUSAL_CODE",
    "INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID",
    "InventoryAcquisitionCostRequest",
    "InventoryAttributableCostComponentRequest",
    "InventoryClosingAuthorityDecisionRequest",
    "InventoryClosingAuthorityRecordInput",
    "InventoryClosingAuthorityRecordRequest",
    "InventoryCreateRequest",
    "InventoryListRequest",
    "InventoryMovementAddRequest",
    "InventoryMutationOperationId",
    "InventoryOperationId",
    "InventoryPhysicalClosingObservationRequest",
    "InventoryPriorClosingLinkRequest",
    "InventoryRefusalCode",
    "InventoryRefusalReason",
    "InventoryValuationPreviewRequest",
]
