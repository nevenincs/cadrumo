"""Canonical redacted public inventory operation projections."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.contribuyente.inventory.records import (
    InventoryCorrectionReason,
    InventoryHistoryKind,
    InventoryLedger,
    InventoryLedgerDescriptor,
    InventoryLedgerHistoryEntry,
    InventoryRetirementReason,
    MovementKind,
    MovementRecord,
    ValuationMethod,
)
from ..operations.public_scalar import PublicDecimal

if TYPE_CHECKING:
    pass

from .acquisition_detail_projection import InventoryAcquisitionDetailProjection
from .registered_requests import InventoryRefusalCode, InventoryRefusalReason
from .stock_projection import InventoryAcquisitionCostProjection, InventoryStockLayerProjection

_RETIRED_BOOK_UNRESOLVED_LOCALE_KEY = "application.inventory.advisories.retired_book_leaves_year_unresolved"


class InventoryAdvisoryProjection(BaseModel):
    """Something the operator should know about a book, as a stable code and its sentence's key."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["retired_book_leaves_year_unresolved"]
    key: str
    year: int


def inventory_advisories(*, year: int, leaves_year_unresolved: bool) -> tuple[InventoryAdvisoryProjection, ...]:
    """Say so when a retired book holding entries keeps its year's Anexo D unresolved."""
    if not leaves_year_unresolved:
        return ()
    return (
        InventoryAdvisoryProjection(
            code="retired_book_leaves_year_unresolved",
            key=_RETIRED_BOOK_UNRESOLVED_LOCALE_KEY,
            year=year,
        ),
    )


class InventoryListRowProjection(BaseModel):
    """Safe inventory-list facts; no acquisition or evidence detail is included."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    actividad_id: str
    year: int
    valuation_method: ValuationMethod
    opening_stock: PublicDecimal
    movement_count: NonNegativeInt
    label: str | None = None
    retired: bool = False
    retirement_reason: InventoryRetirementReason | None = None
    correction_count: NonNegativeInt = 0
    advisories: tuple[InventoryAdvisoryProjection, ...] = ()


class InventoryMovementProjection(BaseModel):
    """One stored movement; acquisition detail stays out unless a caller asks for it by name."""

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
    acquisition_detail: InventoryAcquisitionDetailProjection | None = None

    @classmethod
    def from_movement(
        cls,
        movement: MovementRecord,
        *,
        with_acquisition_detail: bool = False,
        document_file_names: Mapping[str, str] | None = None,
    ) -> InventoryMovementProjection:
        """Project one movement; its evidence payloads are excluded unless asked for by name."""
        acquisition = movement.acquisition_cost
        return cls(
            movement_id=movement.movement_id,
            movement_date=movement.movement_date,
            kind=movement.kind,
            sku=movement.sku,
            quantity=PublicDecimal(decimal=str(movement.quantity)),
            unit_cost=PublicDecimal(decimal=str(movement.unit_cost)) if movement.unit_cost is not None else None,
            taxable_base=(
                PublicDecimal(decimal=str(movement.taxable_base)) if movement.taxable_base is not None else None
            ),
            iva_rate=PublicDecimal(decimal=str(movement.iva_rate)),
            iva_amount=PublicDecimal(decimal=str(movement.iva_amount)) if movement.iva_amount is not None else None,
            deductible_iva_ratio=PublicDecimal(decimal=str(movement.deductible_iva_ratio)),
            acquisition_cost=(
                InventoryAcquisitionCostProjection(
                    consideration_excluding_iva=PublicDecimal(decimal=str(acquisition.consideration_excluding_iva)),
                    directly_attributable_cost_total=PublicDecimal(
                        decimal=str(acquisition.directly_attributable_cost_total),
                    ),
                    nonrecoverable_iva_included=PublicDecimal(decimal=str(acquisition.nonrecoverable_iva_included)),
                    recoverable_iva_excluded=PublicDecimal(decimal=str(acquisition.recoverable_iva_excluded)),
                    total_acquisition_cost=PublicDecimal(decimal=str(acquisition.total_acquisition_cost)),
                    component_count=len(acquisition.attributable_cost_components),
                    evidence_count=len(acquisition.evidence),
                    complete=True,
                )
                if acquisition is not None
                else None
            ),
            schema_version=movement.schema_version,
            acquisition_detail=(
                InventoryAcquisitionDetailProjection.from_acquisition(
                    acquisition, document_file_names=document_file_names or {}
                )
                if with_acquisition_detail and acquisition is not None
                else None
            ),
        )


class InventoryDescriptorProjection(BaseModel):
    """The descriptive facts of an inventory."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    label: str
    description: str | None

    @classmethod
    def from_descriptor(cls, descriptor: InventoryLedgerDescriptor) -> InventoryDescriptorProjection:
        """Project one stored descriptor."""
        return cls(label=descriptor.label, description=descriptor.description)


class InventoryHistoryEntryProjection(BaseModel):
    """One retained change with the fact it displaced, evidence payloads removed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    correction_id: str
    kind: InventoryHistoryKind
    recorded_at: datetime
    actor: str
    correction_reason: InventoryCorrectionReason | None
    retirement_reason: InventoryRetirementReason | None
    superseded_movement: InventoryMovementProjection | None
    replacement_movement_id: str | None
    prior_opening_stock: PublicDecimal | None
    prior_valuation_method: ValuationMethod | None
    prior_descriptor: InventoryDescriptorProjection | None

    @classmethod
    def from_entry(cls, entry: InventoryLedgerHistoryEntry) -> InventoryHistoryEntryProjection:
        """Project one stored history entry."""
        return cls(
            correction_id=entry.correction_id,
            kind=entry.kind,
            recorded_at=entry.recorded_at,
            actor=entry.actor,
            correction_reason=entry.correction_reason,
            retirement_reason=entry.retirement_reason,
            superseded_movement=(
                InventoryMovementProjection.from_movement(entry.superseded_movement)
                if entry.superseded_movement is not None
                else None
            ),
            replacement_movement_id=entry.replacement_movement_id,
            prior_opening_stock=(
                PublicDecimal(decimal=str(entry.prior_opening_stock)) if entry.prior_opening_stock is not None else None
            ),
            prior_valuation_method=entry.prior_valuation_method,
            prior_descriptor=(
                InventoryDescriptorProjection.from_descriptor(entry.prior_descriptor)
                if entry.prior_descriptor is not None
                else None
            ),
        )


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
    descriptor: InventoryDescriptorProjection | None = None
    retired: bool = False
    retirement_reason: InventoryRetirementReason | None = None
    history: tuple[InventoryHistoryEntryProjection, ...] = ()
    advisories: tuple[InventoryAdvisoryProjection, ...] = ()

    @classmethod
    def from_ledger(
        cls,
        ledger: InventoryLedger,
        *,
        bucket_event_ids: tuple[str, ...] = (),
        with_acquisition_detail: bool = False,
        document_file_names: Mapping[str, str] | None = None,
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
            period_movements=tuple(
                InventoryMovementProjection.from_movement(
                    item,
                    with_acquisition_detail=with_acquisition_detail,
                    document_file_names=document_file_names,
                )
                for item in ledger.period_movements
            ),
            schema_version=ledger.schema_version,
            bucket_event_ids=bucket_event_ids,
            descriptor=(
                InventoryDescriptorProjection.from_descriptor(ledger.descriptor)
                if ledger.descriptor is not None
                else None
            ),
            retired=ledger.is_retired,
            retirement_reason=ledger.retirement_reason,
            history=tuple(InventoryHistoryEntryProjection.from_entry(entry) for entry in ledger.history),
            advisories=inventory_advisories(year=ledger.year, leaves_year_unresolved=ledger.leaves_year_unresolved),
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


class InventoryReasonFact(BaseModel):
    """One immutable fact used to render an inventory refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str
    value: str


class InventoryRefusalProjection(BaseModel):
    """Bounded safe explanation for a deterministic domain refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: InventoryRefusalCode
    reason: InventoryRefusalReason
    actividad_id: str | None = None
    year: int | None = None
    movement_id: str | None = None
    valuation_method: str | None = None
    reason_key: str | None = None
    reason_facts: tuple[InventoryReasonFact, ...] = ()


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


class InventoryInspectProjection(BaseModel):
    """One ledger with its movements and history, or a registered refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["found", "refused"]
    profile_id: UUID
    ledger: InventoryLedgerProjection | None = None
    refusal: InventoryRefusalProjection | None = None

    @model_validator(mode="after")
    def _outcome_is_complete(self) -> InventoryInspectProjection:
        if (self.outcome == "found") != (self.ledger is not None) or (self.outcome == "refused") != (
            self.refusal is not None
        ):
            raise ValueError("inventory inspect projection is incomplete")
        return self


class InventoryLedgerChangeProjection(BaseModel):
    """A settled edit, rectification, retirement or restoration, or a registered refusal.

    ``applied`` wrote one history entry and emitted one event; ``replayed`` found
    the exact request already applied and changed nothing.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["applied", "replayed", "refused"]
    profile_id: UUID
    ledger: InventoryLedgerProjection | None = None
    bucket_event_ids: tuple[str, ...] = ()
    refusal: InventoryRefusalProjection | None = None

    @model_validator(mode="after")
    def _outcome_is_complete(self) -> InventoryLedgerChangeProjection:
        expected_events = 1 if self.outcome == "applied" else 0
        if (
            (self.outcome == "refused") == (self.ledger is not None)
            or (self.outcome == "refused") != (self.refusal is not None)
            or len(self.bucket_event_ids) != expected_events
        ):
            raise ValueError("inventory change projection is incomplete")
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
    "InventoryClosingAuthorityFingerprintsProjection",
    "InventoryClosingAuthorityOperationProjection",
    "InventoryClosingAuthorityRecordProjection",
    "InventoryCreateProjection",
    "InventoryDescriptorProjection",
    "InventoryHistoryEntryProjection",
    "InventoryInspectProjection",
    "InventoryLedgerChangeProjection",
    "InventoryLedgerProjection",
    "InventoryListProjection",
    "InventoryListRowProjection",
    "InventoryMovementAddProjection",
    "InventoryMovementProjection",
    "InventoryReasonFact",
    "InventoryRefusalProjection",
    "InventoryValuationOperationProjection",
    "InventoryValuationPreviewProjection",
]
