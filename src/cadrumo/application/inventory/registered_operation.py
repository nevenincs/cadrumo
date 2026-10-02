"""Profile-bound registered operations for the canonical inventory service."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, ValidationError, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAttributableCostComponent,
    InventoryAttributableCostKind,
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingValuationBasis,
    InventoryLedger,
    InventoryLedgerError,
    MovementKind,
    PhysicalClosingEvidence,
    PhysicalClosingObservation,
    PriorClosingContinuityEvidence,
    ValuationMethod,
)
from ...domain.filing_evidence import FilingEvidenceReference
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from .ports import InventoryServicePortsFactory
from .service import (
    InventoryActividadSummary,
    InventoryLedgerResult,
    InventoryMovementCommand,
    InventoryService,
    InventoryValuationPreviewResult,
)

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

_MUTATING_IDS = frozenset(
    {
        INVENTORY_CREATE_OPERATION_DEFINITION_ID,
        INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
        INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
        INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    },
)
_SERVICE_INPUT_REASONS: dict[str, str] = {
    "application.inventory.service.errors.invalid_valuation_method": "invalid_valuation_method",
    "application.inventory.service.errors.duplicate_movement_id": "duplicate_movement_id",
    "application.inventory.service.errors.closing_authority_conflict": "closing_authority_conflict",
    "errors.refused.refused_profile_inventory_validation": "inventory_validation",
}

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


class _InventoryProfileScopedRequest(Protocol):
    profile_id: UUID


_OPERATION_IDS_BY_DEFINITION: dict[str, InventoryOperationId] = {
    INVENTORY_LIST_OPERATION_DEFINITION_ID: "list",
    INVENTORY_CREATE_OPERATION_DEFINITION_ID: "create",
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID: "movement.add",
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID: "valuation.preview",
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID: "closing-authority.record",
}


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


class InventoryListRowProjection(BaseModel):
    """Safe inventory-list facts; no acquisition or evidence detail is included."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    actividad_id: str
    year: int
    valuation_method: ValuationMethod
    opening_stock: PublicDecimal
    movement_count: NonNegativeInt


class InventoryStockLayerProjection(BaseModel):
    """One exact stock layer with no omitted or truncated numeric fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    sku: str
    quantity: PublicDecimal
    unit_cost: PublicDecimal
    source_movement_id: str


class InventoryAcquisitionCostProjection(BaseModel):
    """Safe totals and counts without component, evidence, or digest values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    consideration_excluding_iva: PublicDecimal
    directly_attributable_cost_total: PublicDecimal
    nonrecoverable_iva_included: PublicDecimal
    recoverable_iva_excluded: PublicDecimal
    total_acquisition_cost: PublicDecimal
    component_count: NonNegativeInt
    evidence_count: PositiveInt
    complete: Literal[True]


class InventoryMovementProjection(BaseModel):
    """One stored movement with sensitive acquisition evidence removed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    movement_id: str
    movement_date: date
    kind: MovementKind
    sku: str
    quantity: PublicDecimal
    unit_cost: PublicDecimal | None
    taxable_base: PublicDecimal | None
    iva_rate: PublicDecimal
    iva_amount: PublicDecimal | None
    deductible_iva_ratio: PublicDecimal
    acquisition_cost: InventoryAcquisitionCostProjection | None
    schema_version: str


class InventoryClosingAuthorityFingerprintsProjection(BaseModel):
    """Non-reversible source identities retained for closing authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    record: str
    decision: str
    physical_observation: str | None
    prior_closing_link: str


class InventoryLedgerProjection(BaseModel):
    """Closed operator projection of a canonical ledger with evidence redacted."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    actividad_id: str
    year: int
    valuation_method: ValuationMethod
    opening_stock: PublicDecimal
    opening_layers: tuple[InventoryStockLayerProjection, ...]
    closing_authority_fingerprints: InventoryClosingAuthorityFingerprintsProjection | None
    period_movements: tuple[InventoryMovementProjection, ...]
    schema_version: str
    bucket_event_ids: tuple[str, ...] = ()

    @classmethod
    def from_ledger(
        cls,
        ledger: InventoryLedger,
        *,
        bucket_event_ids: tuple[str, ...] = (),
    ) -> InventoryLedgerProjection:
        """Project every public ledger field while excluding evidence payloads."""
        record = ledger.closing_authority_record
        fingerprints = (
            InventoryClosingAuthorityFingerprintsProjection(
                record=record.fingerprint,
                decision=record.decision.fingerprint,
                physical_observation=(
                    record.physical_observation.fingerprint if record.physical_observation is not None else None
                ),
                prior_closing_link=record.prior_closing_link.fingerprint,
            )
            if record is not None
            else None
        )
        movements = tuple(
            InventoryMovementProjection(
                movement_id=movement.movement_id,
                movement_date=movement.movement_date,
                kind=movement.kind,
                sku=movement.sku,
                quantity=PublicDecimal(decimal=str(movement.quantity)),
                unit_cost=(PublicDecimal(decimal=str(movement.unit_cost)) if movement.unit_cost is not None else None),
                taxable_base=(
                    PublicDecimal(decimal=str(movement.taxable_base)) if movement.taxable_base is not None else None
                ),
                iva_rate=PublicDecimal(decimal=str(movement.iva_rate)),
                iva_amount=(
                    PublicDecimal(decimal=str(movement.iva_amount)) if movement.iva_amount is not None else None
                ),
                deductible_iva_ratio=PublicDecimal(decimal=str(movement.deductible_iva_ratio)),
                acquisition_cost=(
                    InventoryAcquisitionCostProjection(
                        consideration_excluding_iva=PublicDecimal(
                            decimal=str(movement.acquisition_cost.consideration_excluding_iva),
                        ),
                        directly_attributable_cost_total=PublicDecimal(
                            decimal=str(movement.acquisition_cost.directly_attributable_cost_total),
                        ),
                        nonrecoverable_iva_included=PublicDecimal(
                            decimal=str(movement.acquisition_cost.nonrecoverable_iva_included),
                        ),
                        recoverable_iva_excluded=PublicDecimal(
                            decimal=str(movement.acquisition_cost.recoverable_iva_excluded),
                        ),
                        total_acquisition_cost=PublicDecimal(
                            decimal=str(movement.acquisition_cost.total_acquisition_cost),
                        ),
                        component_count=len(movement.acquisition_cost.attributable_cost_components),
                        evidence_count=len(movement.acquisition_cost.evidence),
                        complete=True,
                    )
                    if movement.acquisition_cost is not None
                    else None
                ),
                schema_version=movement.schema_version,
            )
            for movement in ledger.period_movements
        )
        return cls(
            actividad_id=ledger.actividad_id,
            year=ledger.year,
            valuation_method=ledger.valuation_method,
            opening_stock=PublicDecimal(decimal=str(ledger.opening_stock)),
            opening_layers=tuple(
                InventoryStockLayerProjection(
                    sku=layer.sku,
                    quantity=PublicDecimal(decimal=str(layer.quantity)),
                    unit_cost=PublicDecimal(decimal=str(layer.unit_cost)),
                    source_movement_id=layer.source_movement_id,
                )
                for layer in ledger.opening_layers
            ),
            closing_authority_fingerprints=fingerprints,
            period_movements=movements,
            schema_version=ledger.schema_version,
            bucket_event_ids=bucket_event_ids,
        )


class InventoryValuationPreviewProjection(BaseModel):
    """Exact valuation amounts and the audit events produced by preview."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    actividad_id: str
    year: int
    valuation_method: ValuationMethod
    derived_closing_value: PublicDecimal
    cogs: PublicDecimal
    bucket_event_ids: tuple[str, ...] = Field(max_length=1)


class InventoryClosingAuthorityRecordProjection(BaseModel):
    """Only stable closing-authority fingerprints cross the result boundary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    actividad_id: str
    year: int
    authority_record_fingerprint: str
    decision_fingerprint: str
    physical_observation_fingerprint: str | None
    prior_closing_link_fingerprint: str
    changed: bool


class InventoryRefusalProjection(BaseModel):
    """Bounded safe explanation for a deterministic domain refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: InventoryRefusalCode
    reason: InventoryRefusalReason
    actividad_id: str | None = None
    year: int | None = None
    movement_id: str | None = None
    valuation_method: str | None = None


class InventoryListProjection(BaseModel):
    """Profile-correlated safe result of the inventory-list operation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: tuple[InventoryListRowProjection, ...]


class InventoryCreateProjection(BaseModel):
    """Successful create or registered validation refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["created", "refused"]
    profile_id: UUID
    ledger: InventoryLedgerProjection | None = None
    bucket_event_ids: tuple[str, ...] = ()
    refusal: InventoryRefusalProjection | None = None

    @model_validator(mode="after")
    def _outcome_is_complete(self) -> InventoryCreateProjection:
        if self.outcome == "created":
            if self.ledger is None or self.refusal is not None or len(self.bucket_event_ids) != 1:
                raise ValueError("inventory create projection is incomplete")
        elif self.ledger is not None or self.bucket_event_ids or self.refusal is None:
            raise ValueError("inventory create refusal projection is incomplete")
        return self


class InventoryMovementAddProjection(BaseModel):
    """Successful movement append or registered validation refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["added", "refused"]
    profile_id: UUID
    ledger: InventoryLedgerProjection | None = None
    bucket_event_ids: tuple[str, ...] = ()
    refusal: InventoryRefusalProjection | None = None

    @model_validator(mode="after")
    def _outcome_is_complete(self) -> InventoryMovementAddProjection:
        if self.outcome == "added":
            if self.ledger is None or self.refusal is not None or len(self.bucket_event_ids) != 1:
                raise ValueError("inventory movement projection is incomplete")
        elif self.ledger is not None or self.bucket_event_ids or self.refusal is None:
            raise ValueError("inventory movement refusal projection is incomplete")
        return self


class InventoryValuationOperationProjection(BaseModel):
    """Valuation result or a registered pre-event refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["previewed", "refused"]
    preview: InventoryValuationPreviewProjection | None = None
    refusal: InventoryRefusalProjection | None = None

    @model_validator(mode="after")
    def _outcome_is_complete(self) -> InventoryValuationOperationProjection:
        if self.outcome == "previewed":
            if self.preview is None or self.refusal is not None:
                raise ValueError("inventory valuation projection is incomplete")
        elif self.preview is not None or self.refusal is None:
            raise ValueError("inventory valuation refusal projection is incomplete")
        return self


class InventoryClosingAuthorityOperationProjection(BaseModel):
    """Closing-authority fingerprints or a registered refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["recorded", "refused"]
    record: InventoryClosingAuthorityRecordProjection | None = None
    refusal: InventoryRefusalProjection | None = None

    @model_validator(mode="after")
    def _outcome_is_complete(self) -> InventoryClosingAuthorityOperationProjection:
        if self.outcome == "recorded":
            if self.record is None or self.refusal is not None:
                raise ValueError("inventory closing-authority projection is incomplete")
        elif self.record is not None or self.refusal is None:
            raise ValueError("inventory closing-authority refusal projection is incomplete")
        return self


class InventoryOperationRefusalDetail(BaseModel):
    """Encrypted explanation details; never contains financial inputs or prose."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: InventoryRefusalCode
    reason: InventoryRefusalReason
    actividad_id: str | None = None
    year: int | None = None
    movement_id: str | None = None
    valuation_method: str | None = None


class InventoryOperationExecutionResult(BaseModel):
    """Private typed result arm persisted under secure operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: InventoryOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    rows: tuple[InventoryActividadSummary, ...] = ()
    ledger_result: InventoryLedgerResult | None = None
    valuation_result: InventoryValuationPreviewResult | None = None
    closing_changed: bool | None = None
    refusal: InventoryOperationRefusalDetail | None = None

    @model_validator(mode="after")
    def _result_arm_is_closed(self) -> InventoryOperationExecutionResult:
        if self.outcome == "refused":
            if self.refusal is None or self.rows or self.ledger_result is not None or self.valuation_result is not None:
                raise ValueError("inventory refusal result contains an incompatible payload")
            if self.closing_changed is not None:
                raise ValueError("inventory refusal result contains a mutation status")
            return self
        if self.refusal is not None:
            raise ValueError("inventory success result contains refusal detail")
        if self.operation_id != "list" and self.rows:
            raise ValueError("non-list inventory result contains list rows")
        if self.operation_id == "list":
            if self.ledger_result is not None or self.valuation_result is not None or self.closing_changed is not None:
                raise ValueError("inventory list result contains a mutation payload")
        elif self.operation_id in {"create", "movement.add"}:
            if self.ledger_result is None or self.valuation_result is not None or self.closing_changed is not None:
                raise ValueError("inventory ledger result arm is incomplete")
        elif self.operation_id == "valuation.preview":
            if self.valuation_result is None or self.ledger_result is not None or self.closing_changed is not None:
                raise ValueError("inventory valuation result arm is incomplete")
        else:
            if self.ledger_result is None or self.valuation_result is not None or self.closing_changed is None:
                raise ValueError("inventory closing-authority result arm is incomplete")
        return self


@dataclass(frozen=True, slots=True)
class _OperationShape:
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    refusal_codes: frozenset[str]


_SHAPES: dict[str, _OperationShape] = {
    INVENTORY_LIST_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=InventoryListRequest,
        projection_type=InventoryListProjection,
        refusal_codes=frozenset(),
    ),
    INVENTORY_CREATE_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=InventoryCreateRequest,
        projection_type=InventoryCreateProjection,
        refusal_codes=frozenset(
            {INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_CONFLICT_REFUSAL_CODE}
        ),
    ),
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=InventoryMovementAddRequest,
        projection_type=InventoryMovementAddProjection,
        refusal_codes=frozenset(
            {INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}
        ),
    ),
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=InventoryValuationPreviewRequest,
        projection_type=InventoryValuationOperationProjection,
        refusal_codes=frozenset({INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}),
    ),
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=InventoryClosingAuthorityRecordRequest,
        projection_type=InventoryClosingAuthorityOperationProjection,
        refusal_codes=frozenset(
            {INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}
        ),
    ),
}


class InventoryOperationExecutor:
    """Run one inventory service call under the supervisor's profile custody."""

    def __init__(self, ports_factory: InventoryServicePortsFactory, *, definition_id: str) -> None:
        """Bind the exact operation type to the bucket service factory."""
        self._ports_factory = ports_factory
        self._definition_id = definition_id

    def _service(self, profile_id: UUID) -> InventoryService:
        profile = str(profile_id)
        return InventoryService(ports=self._ports_factory(bucket_id=profile))

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run one validated request and retain only its typed safe outcome."""
        shape = _SHAPES.get(self._definition_id)
        if shape is None or type(request.payload) is not shape.request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        profile_id = cast(_InventoryProfileScopedRequest, payload).profile_id
        profile = str(profile_id)
        if (
            request.definition_id != self._definition_id
            or request.subject_ref != profile_operation_subject(profile)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(self._definition_id)

        if self._definition_id == INVENTORY_LIST_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryListRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

            async def read() -> str:
                rows = await asyncio.to_thread(lambda: self._service(profile_id).list_all(bucket_id=profile))
                result = InventoryOperationExecutionResult(
                    operation_id="list",
                    outcome="success",
                    profile_id=profile_id,
                    rows=rows,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.NONE)
                return reference

            return await await_cancellation_complete(read(), task_name="inventory-list")

        if self._definition_id == INVENTORY_CREATE_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryCreateRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            create_request = payload

            def create() -> InventoryLedgerResult:
                return self._service(profile_id).create(
                    bucket_id=profile,
                    actividad_id=create_request.actividad_id,
                    year=create_request.year,
                    valuation_method=create_request.valuation_method,
                    opening_stock=Decimal(create_request.opening_stock.decimal),
                    actor="runtime",
                )

            return await self._mutate(
                context,
                operation_id="create",
                profile_id=profile_id,
                request=create_request,
                work=create,
            )

        if self._definition_id == INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryMovementAddRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            movement_request = payload

            try:
                movement = InventoryMovementCommand(
                    movement_id=movement_request.movement_id,
                    movement_date=movement_request.movement_date,
                    kind=movement_request.kind,
                    quantity=Decimal(movement_request.quantity.decimal),
                    unit_cost=(
                        Decimal(movement_request.unit_cost.decimal) if movement_request.unit_cost is not None else None
                    ),
                    taxable_base=(
                        Decimal(movement_request.taxable_base.decimal)
                        if movement_request.taxable_base is not None
                        else None
                    ),
                    acquisition_cost=(
                        movement_request.acquisition_cost.to_domain()
                        if movement_request.acquisition_cost is not None
                        else None
                    ),
                )
            except (ValidationError, InventoryLedgerError):
                return await _record_precommit_validation_refusal(
                    context,
                    operation_id="movement.add",
                    profile_id=profile_id,
                    request=movement_request,
                )

            def add_movement() -> InventoryLedgerResult:
                with validating_governed_facts(context.authority_operation):
                    return self._service(profile_id).movement_add(
                        bucket_id=profile,
                        actividad_id=movement_request.actividad_id,
                        year=movement_request.year,
                        movement=movement,
                        actor="runtime",
                    )

            return await self._mutate(
                context,
                operation_id="movement.add",
                profile_id=profile_id,
                request=movement_request,
                work=add_movement,
            )

        if self._definition_id == INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryValuationPreviewRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            valuation_request = payload

            def preview() -> InventoryValuationPreviewResult:
                return self._service(profile_id).valuation_preview(
                    bucket_id=profile,
                    actividad_id=valuation_request.actividad_id,
                    year=valuation_request.year,
                    actor="runtime",
                )

            return await self._mutate(
                context,
                operation_id="valuation.preview",
                profile_id=profile_id,
                request=valuation_request,
                work=preview,
            )

        if not isinstance(payload, InventoryClosingAuthorityRecordRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        closing_request = payload

        try:
            authority_record = closing_request.authority_record.to_domain()
        except (ValidationError, InventoryLedgerError):
            return await _record_precommit_validation_refusal(
                context,
                operation_id="closing-authority.record",
                profile_id=profile_id,
                request=closing_request,
            )

        def record_closing_authority() -> InventoryLedgerResult:
            return self._service(profile_id).closing_authority_record(
                bucket_id=profile,
                actividad_id=closing_request.actividad_id,
                year=closing_request.year,
                authority_record=authority_record,
            )

        return await self._mutate(
            context,
            operation_id="closing-authority.record",
            profile_id=profile_id,
            request=closing_request,
            work=record_closing_authority,
        )

    async def _mutate(
        self,
        context: OperationExecutorContext,
        *,
        operation_id: InventoryMutationOperationId,
        profile_id: UUID,
        request: BaseModel,
        work: Callable[[], object],
    ) -> str | OperationRefusalEvidence:
        """Hold cancellation ownership from UNKNOWN through actual commit receipt."""

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(work)
                except Exception as error:
                    refusal = _refusal_for_error(request=request, error=error)
                    if refusal is None:
                        raise
                    execution = InventoryOperationExecutionResult(
                        operation_id=operation_id,
                        outcome="refused",
                        profile_id=profile_id,
                        refusal=refusal,
                    )
                    detail_ref = await context.operands.put(execution, written_at=now())
                    await context.events.effect(OperationEffect.NONE)
                    return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)

                execution = _success_execution(operation_id=operation_id, profile_id=profile_id, result=result)
                await context.events.effect(_effect_for_success(execution))
                return await context.operands.put(execution, written_at=now())

        return await await_cancellation_complete(commit(), task_name=f"inventory-{operation_id}")


def _refusal_for_error(
    *,
    request: BaseModel,
    error: Exception,
) -> InventoryOperationRefusalDetail | None:
    reason: InventoryRefusalReason | None = None
    code: InventoryRefusalCode | None = None
    if isinstance(error, InventoryActividadConflictError):
        reason, code = "activity_conflict", INVENTORY_CONFLICT_REFUSAL_CODE
    elif isinstance(error, InventoryActividadNotFoundError):
        reason, code = "activity_not_found", INVENTORY_NOT_FOUND_REFUSAL_CODE
    elif isinstance(error, InventoryServiceInputError):
        service_reason = _SERVICE_INPUT_REASONS.get(error.translated_message or "")
        if service_reason is not None:
            reason = cast(InventoryRefusalReason, service_reason)
            code = (
                INVENTORY_VALIDATION_REFUSAL_CODE
                if service_reason == "inventory_validation"
                else INVENTORY_SERVICE_INPUT_REFUSAL_CODE
            )
    if reason is None or code is None:
        return None
    actividad_id = getattr(request, "actividad_id", None)
    year = getattr(request, "year", None)
    movement_id = getattr(request, "movement_id", None)
    valuation_method = getattr(request, "valuation_method", None)
    return InventoryOperationRefusalDetail(
        code=code,
        reason=reason,
        actividad_id=actividad_id if isinstance(actividad_id, str) else None,
        year=year if isinstance(year, int) else None,
        movement_id=movement_id if isinstance(movement_id, str) else None,
        valuation_method=valuation_method if isinstance(valuation_method, str) else None,
    )


async def _record_precommit_validation_refusal(
    context: OperationExecutorContext,
    *,
    operation_id: InventoryOperationId,
    profile_id: UUID,
    request: BaseModel,
) -> OperationRefusalEvidence:
    """Persist a typed NONE-effect refusal after validation known to precede writes."""
    reason: InventoryRefusalReason = (
        "closing_authority_invalid" if operation_id == "closing-authority.record" else "inventory_validation"
    )
    refusal = InventoryOperationRefusalDetail(
        code=INVENTORY_VALIDATION_REFUSAL_CODE,
        reason=reason,
        actividad_id=getattr(request, "actividad_id", None),
        year=getattr(request, "year", None),
        movement_id=getattr(request, "movement_id", None),
    )

    async def persist_refusal() -> OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            execution = InventoryOperationExecutionResult(
                operation_id=operation_id,
                outcome="refused",
                profile_id=profile_id,
                refusal=refusal,
            )
            detail_ref = await context.operands.put(execution, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)

    return await await_cancellation_complete(persist_refusal(), task_name=f"inventory-{operation_id}-refusal")


def _success_execution(
    *,
    operation_id: InventoryMutationOperationId,
    profile_id: UUID,
    result: object,
) -> InventoryOperationExecutionResult:
    if operation_id in {"create", "movement.add"} and isinstance(result, InventoryLedgerResult):
        return InventoryOperationExecutionResult(
            operation_id=operation_id,
            outcome="success",
            profile_id=profile_id,
            ledger_result=result,
        )
    if operation_id == "valuation.preview" and isinstance(result, InventoryValuationPreviewResult):
        return InventoryOperationExecutionResult(
            operation_id=operation_id,
            outcome="success",
            profile_id=profile_id,
            valuation_result=result,
        )
    if operation_id == "closing-authority.record" and isinstance(result, InventoryLedgerResult):
        return InventoryOperationExecutionResult(
            operation_id=operation_id,
            outcome="success",
            profile_id=profile_id,
            ledger_result=result,
            closing_changed=result.changed,
        )
    raise TypeError("inventory service returned an incompatible canonical result")


def _effect_for_success(result: InventoryOperationExecutionResult) -> OperationEffect:
    if result.operation_id == "list":
        return OperationEffect.NONE
    if result.operation_id == "closing-authority.record":
        return OperationEffect.UPDATED if result.closing_changed else OperationEffect.NONE
    if result.operation_id == "valuation.preview":
        if result.valuation_result is None:
            raise ValueError("inventory valuation result is missing")
        return OperationEffect.UPDATED if result.valuation_result.bucket_event_ids else OperationEffect.NONE
    if result.ledger_result is None:
        raise ValueError("inventory ledger result is missing")
    return OperationEffect.UPDATED if result.ledger_result.bucket_event_ids else OperationEffect.NONE


def _profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if receipt.identity.definition_id != definition_id:
        raise ValueError("inventory result definition differs from its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("inventory result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("inventory result has an invalid profile subject")
    return profile_id


def _execution_result(result: BaseModel) -> InventoryOperationExecutionResult:
    if type(result) is not InventoryOperationExecutionResult:
        raise ValueError("inventory execution result has an incompatible type")
    return InventoryOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def project_inventory_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> InventoryListProjection:
    """Release only a safe list projection correlated with its exact receipt."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_LIST_OPERATION_DEFINITION_ID)
    if (
        private.operation_id != "list"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("inventory list result contradicts its terminal receipt")
    return InventoryListProjection(
        profile_id=profile_id,
        rows=tuple(
            InventoryListRowProjection(
                actividad_id=row.actividad_id,
                year=row.year,
                valuation_method=row.valuation_method,
                opening_stock=PublicDecimal(decimal=str(row.opening_stock)),
                movement_count=row.movement_count,
            )
            for row in private.rows
        ),
    )


def _validate_refusal_receipt(
    *,
    private: InventoryOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
    definition_id: str,
    operation_id: InventoryOperationId,
) -> InventoryRefusalProjection:
    refusal = private.refusal
    if (
        private.outcome != "refused"
        or private.operation_id != operation_id
        or private.profile_id != profile_id
        or refusal is None
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref != refusal.code
        or definition_id not in _SHAPES
        or refusal.code not in _SHAPES[definition_id].refusal_codes
        or _OPERATION_IDS_BY_DEFINITION[definition_id] != operation_id
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.identity.definition_id != definition_id
    ):
        raise ValueError("inventory refusal detail contradicts its terminal receipt")
    return InventoryRefusalProjection(
        code=refusal.code,
        reason=refusal.reason,
        actividad_id=refusal.actividad_id,
        year=refusal.year,
        movement_id=refusal.movement_id,
        valuation_method=refusal.valuation_method,
    )


def _validate_ledger_success(
    *,
    private: InventoryOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
    operation_id: Literal["create", "movement.add", "closing-authority.record"],
    definition_id: str,
) -> InventoryLedgerResult:
    result = private.ledger_result
    expected_effect = (
        OperationEffect.UPDATED if result is not None and result.bucket_event_ids else OperationEffect.NONE
    )
    if operation_id == "closing-authority.record":
        expected_effect = OperationEffect.UPDATED if private.closing_changed else OperationEffect.NONE
    if (
        private.operation_id != operation_id
        or private.outcome != "success"
        or private.profile_id != profile_id
        or result is None
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not expected_effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.identity.definition_id != definition_id
        or (operation_id == "closing-authority.record" and result.bucket_event_ids)
        or (operation_id in {"create", "movement.add"} and len(result.bucket_event_ids) != 1)
    ):
        raise ValueError("inventory ledger result contradicts its terminal receipt")
    return result


def project_inventory_create_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryCreateProjection:
    """Release redacted ledger data or a typed create refusal."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            operation_id="create",
        )
        return InventoryCreateProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = _validate_ledger_success(
        private=private,
        receipt=receipt,
        profile_id=profile_id,
        operation_id="create",
        definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    )
    if not ledger_result.changed:
        raise ValueError("inventory create result reports no change")
    ledger = InventoryLedgerProjection.from_ledger(
        ledger_result.ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )
    return InventoryCreateProjection(
        outcome="created",
        profile_id=profile_id,
        ledger=ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )


def project_inventory_movement_add_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryMovementAddProjection:
    """Release redacted movement data or a typed movement refusal."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
            operation_id="movement.add",
        )
        return InventoryMovementAddProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = _validate_ledger_success(
        private=private,
        receipt=receipt,
        profile_id=profile_id,
        operation_id="movement.add",
        definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    )
    if not ledger_result.changed:
        raise ValueError("inventory movement result reports no change")
    ledger = InventoryLedgerProjection.from_ledger(
        ledger_result.ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )
    return InventoryMovementAddProjection(
        outcome="added",
        profile_id=profile_id,
        ledger=ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )


def project_inventory_valuation_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryValuationOperationProjection:
    """Release valuation facts only after the exact audited effect settles."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
            operation_id="valuation.preview",
        )
        return InventoryValuationOperationProjection(outcome="refused", refusal=refusal)
    preview_result = private.valuation_result
    if (
        private.operation_id != "valuation.preview"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or preview_result is None
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not (OperationEffect.UPDATED if preview_result.bucket_event_ids else OperationEffect.NONE)
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or len(preview_result.bucket_event_ids) != 1
        or receipt.identity.definition_id != INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID
    ):
        raise ValueError("inventory valuation result contradicts its terminal receipt")
    preview = preview_result.preview
    return InventoryValuationOperationProjection(
        outcome="previewed",
        preview=InventoryValuationPreviewProjection(
            profile_id=profile_id,
            actividad_id=preview.actividad_id,
            year=preview.year,
            valuation_method=preview.valuation_method,
            derived_closing_value=PublicDecimal(decimal=str(preview.derived_closing_value)),
            cogs=PublicDecimal(decimal=str(preview.cogs)),
            bucket_event_ids=preview_result.bucket_event_ids,
        ),
    )


def project_inventory_closing_authority_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryClosingAuthorityOperationProjection:
    """Release only closing fingerprints and the repository's actual changed flag."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(
        receipt,
        definition_id=INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    )
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
            operation_id="closing-authority.record",
        )
        return InventoryClosingAuthorityOperationProjection(outcome="refused", refusal=refusal)
    result_value = _validate_ledger_success(
        private=private,
        receipt=receipt,
        profile_id=profile_id,
        operation_id="closing-authority.record",
        definition_id=INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    )
    record = result_value.ledger.closing_authority_record
    if record is None:
        raise ValueError("inventory closing-authority result contains no persisted authority")
    return InventoryClosingAuthorityOperationProjection(
        outcome="recorded",
        record=InventoryClosingAuthorityRecordProjection(
            profile_id=profile_id,
            actividad_id=result_value.ledger.actividad_id,
            year=result_value.ledger.year,
            authority_record_fingerprint=record.fingerprint,
            decision_fingerprint=record.decision.fingerprint,
            physical_observation_fingerprint=(
                record.physical_observation.fingerprint if record.physical_observation is not None else None
            ),
            prior_closing_link_fingerprint=record.prior_closing_link.fingerprint,
            changed=bool(private.closing_changed),
        ),
    )


def resolve_inventory_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind inventory disclosure and mutation authority to the exact profile."""
    shape = _SHAPES.get(request.definition_id)
    payload = request.payload
    if shape is None or type(payload) is not shape.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = cast(_InventoryProfileScopedRequest, payload).profile_id
    resolved = resolve_ledger_read_access(request, context, profile_id=profile_id, periods=frozenset())
    if request.definition_id not in _MUTATING_IDS:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}},
    )
    return replace(resolved, policy=policy)


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    ports_factory: InventoryServicePortsFactory,
) -> OperationDefinition:
    shape = _SHAPES[definition_id]
    if shape.request_type is not request_type:
        raise ValueError("inventory operation builder request type does not match its registration")
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=InventoryOperationExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=InventoryOperationExecutor,
            build=lambda: InventoryOperationExecutor(ports_factory, definition_id=definition_id),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP},
        ),
        refusal_detail_codes=shape.refusal_codes,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    projection_type: type[BaseModel],
    projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    shape = _SHAPES[definition.definition_id]
    if shape.request_type is not request_type or shape.projection_type is not projection_type:
        raise ValueError("inventory operation registration does not match its canonical schema")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=projection_type,
        ),
        access_resolver=resolve_inventory_operation_access,
        result_projector=projector,
    )


def build_inventory_list_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the exact-profile inventory-list worker definition."""
    return _definition(INVENTORY_LIST_OPERATION_DEFINITION_ID, InventoryListRequest, ports_factory)


def build_inventory_create_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the guarded exact-profile ledger-creation definition."""
    return _definition(INVENTORY_CREATE_OPERATION_DEFINITION_ID, InventoryCreateRequest, ports_factory)


def build_inventory_movement_add_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the guarded exact-profile movement append definition."""
    return _definition(INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID, InventoryMovementAddRequest, ports_factory)


def build_inventory_valuation_preview_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the audited exact-profile valuation preview definition."""
    return _definition(
        INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
        InventoryValuationPreviewRequest,
        ports_factory,
    )


def build_inventory_closing_authority_record_definition(
    ports_factory: InventoryServicePortsFactory,
) -> OperationDefinition:
    """Build the guarded exact-profile closing-authority write definition."""
    return _definition(
        INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
        InventoryClosingAuthorityRecordRequest,
        ports_factory,
    )


def build_inventory_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the safe inventory-list projection and profile disclosure policy."""
    return _registration(
        definition,
        request_type=InventoryListRequest,
        projection_type=InventoryListProjection,
        projector=project_inventory_list_result,
    )


def build_inventory_create_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind redacted ledger-create results and typed refusal explanations."""
    return _registration(
        definition,
        request_type=InventoryCreateRequest,
        projection_type=InventoryCreateProjection,
        projector=project_inventory_create_result,
    )


def build_inventory_movement_add_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind redacted movement results and typed refusal explanations."""
    return _registration(
        definition,
        request_type=InventoryMovementAddRequest,
        projection_type=InventoryMovementAddProjection,
        projector=project_inventory_movement_add_result,
    )


def build_inventory_valuation_preview_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind valuation facts with their audit-effect receipt."""
    return _registration(
        definition,
        request_type=InventoryValuationPreviewRequest,
        projection_type=InventoryValuationOperationProjection,
        projector=project_inventory_valuation_result,
    )


def build_inventory_closing_authority_record_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind fingerprint-only closing-authority results and typed refusals."""
    return _registration(
        definition,
        request_type=InventoryClosingAuthorityRecordRequest,
        projection_type=InventoryClosingAuthorityOperationProjection,
        projector=project_inventory_closing_authority_result,
    )


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
    "InventoryAcquisitionCostProjection",
    "InventoryClosingAuthorityFingerprintsProjection",
    "InventoryClosingAuthorityOperationProjection",
    "InventoryClosingAuthorityRecordProjection",
    "InventoryClosingAuthorityRecordRequest",
    "InventoryCreateProjection",
    "InventoryCreateRequest",
    "InventoryLedgerProjection",
    "InventoryListProjection",
    "InventoryListRequest",
    "InventoryListRowProjection",
    "InventoryMovementAddProjection",
    "InventoryMovementAddRequest",
    "InventoryMovementProjection",
    "InventoryOperationExecutionResult",
    "InventoryOperationExecutor",
    "InventoryOperationRefusalDetail",
    "InventoryRefusalProjection",
    "InventoryStockLayerProjection",
    "InventoryValuationOperationProjection",
    "InventoryValuationPreviewProjection",
    "InventoryValuationPreviewRequest",
    "build_inventory_closing_authority_record_definition",
    "build_inventory_closing_authority_record_registration",
    "build_inventory_create_definition",
    "build_inventory_create_registration",
    "build_inventory_list_definition",
    "build_inventory_list_registration",
    "build_inventory_movement_add_definition",
    "build_inventory_movement_add_registration",
    "build_inventory_valuation_preview_definition",
    "build_inventory_valuation_preview_registration",
    "project_inventory_closing_authority_result",
    "project_inventory_create_result",
    "project_inventory_list_result",
    "project_inventory_movement_add_result",
    "project_inventory_valuation_result",
    "resolve_inventory_operation_access",
]
