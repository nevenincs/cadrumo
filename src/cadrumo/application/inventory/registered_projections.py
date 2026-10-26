"""Canonical redacted public inventory operation projections."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.contribuyente.inventory.records import (
    InventoryLedger,
    MovementKind,
    ValuationMethod,
)
from ..operations.public_scalar import PublicDecimal

if TYPE_CHECKING:
    pass

from .registered_requests import InventoryRefusalCode, InventoryRefusalReason


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


__all__ = [
    "InventoryAcquisitionCostProjection",
    "InventoryClosingAuthorityFingerprintsProjection",
    "InventoryClosingAuthorityOperationProjection",
    "InventoryClosingAuthorityRecordProjection",
    "InventoryCreateProjection",
    "InventoryLedgerProjection",
    "InventoryListProjection",
    "InventoryListRowProjection",
    "InventoryMovementAddProjection",
    "InventoryMovementProjection",
    "InventoryRefusalProjection",
    "InventoryStockLayerProjection",
    "InventoryValuationOperationProjection",
    "InventoryValuationPreviewProjection",
]
