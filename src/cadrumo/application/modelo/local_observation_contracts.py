"""Exact local-observation request, persisted-layer and bounded-result contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.filing_text import ModeloActorLabel, OperatorReason
from ..calculations.observations_repository import ObservationSourceKind
from ..operations.public_period import PublicPeriod
from .filing_record_view_operation import ModeloFilingObservationLayersProjection
from .local_observation_actions import (
    LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL,
)

MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID = "modelo.observation.local"


MAX_MODELO_LOCAL_OBSERVATION_CASILLAS = 4_096


_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]


class ModeloLocalObservationCasillaValue(BaseModel):
    """One canonical casilla and decimal-text pair on the operation wire."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_id: CasillaId
    value: _DecimalText

    @field_validator("value")
    @classmethod
    def _canonical_decimal_text(cls, value: str) -> str:
        """Keep the operation schema textual while matching the CLI decimal grammar."""
        if try_parse_canonical_decimal(value, max_fraction_digits=2) is None:
            raise ValueError("local observation values must be canonical decimal text")
        return value


_CasillaValues = Annotated[
    tuple[ModeloLocalObservationCasillaValue, ...],
    Field(max_length=MAX_MODELO_LOCAL_OBSERVATION_CASILLAS),
]


class ModeloLocalObservationMutationRequest(BaseModel):
    """One profile-bound record or clear request with securely stored values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    action: Literal["record", "clear"]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    casilla_values: _CasillaValues = ()
    actor: ModeloActorLabel | None = None
    reason: OperatorReason

    @model_validator(mode="after")
    def _action_values(self) -> Self:
        """Require the exact input shape for the selected mutation."""
        keys = tuple(row.casilla_id for row in self.casilla_values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("local observation casilla values must be unique and sorted")
        if self.action == "record" and not self.casilla_values:
            raise ValueError("recording a local observation requires at least one casilla value")
        if self.action == "clear" and self.casilla_values:
            raise ValueError("clearing a local observation cannot carry casilla values")
        return self


class ModeloLocalObservationMutationProjection(BaseModel):
    """Allowlisted command result with string decimals and both observation layers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    action: Literal["recorded", "cleared"]
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    revision_id: RevisionId | None = None
    observation_key: Annotated[str, Field(min_length=1, max_length=256)]
    source_kind: ObservationSourceKind | None = None
    casilla_values: _CasillaValues = ()
    captured_at: datetime
    captured_by: ModeloActorLabel
    reason: OperatorReason
    observation_layers: ModeloFilingObservationLayersProjection
    official_evidence: Literal[False] = False
    filing_record_created: Literal[False] = False
    aeat_accepted: Literal[False] = False

    @field_validator("captured_at")
    @classmethod
    @pydantic_validation_boundary
    def _captured_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _coherent_projection(self) -> Self:
        """Prove record/clear shape and the persisted layers describe one coordinate."""
        carries_detail = LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL[self.action]
        details = (self.revision_id is not None, self.source_kind is not None, bool(self.casilla_values))
        if any(value is not carries_detail for value in details):
            raise ValueError("local observation result fields do not match its action")

        keys = tuple(row.casilla_id for row in self.casilla_values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("local observation result casilla values must be unique and sorted")

        layers = self.observation_layers
        if (
            layers.modelo != self.modelo
            or layers.filing_year != self.period.filing_year
            or layers.period != self.period.code
            or layers.member_nif is not None
        ):
            raise ValueError("local observation result layers do not match its coordinate")

        if self.action == "recorded":
            _require_recorded_pending_layer(self, layers)
            _require_recorded_override(self, layers)
        else:
            _require_cleared_layers(layers)
        return self


class ModeloLocalObservationMutationReport(BaseModel):
    """Encrypted operation result before the receipt-bound public projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloLocalObservationMutationProjection
    local_write_performed: Literal[True]


def _require_recorded_pending_layer(
    self: ModeloLocalObservationMutationProjection, layers: ModeloFilingObservationLayersProjection
) -> None:
    """Require exact persisted manual values, revision, capture time and effective source."""
    pending = layers.pending_local
    if (
        self.source_kind is not ObservationSourceKind.OPERATOR_MANUAL
        or pending is None
        or pending.source_kind is not ObservationSourceKind.OPERATOR_MANUAL
        or pending.stamped_revision_id != self.revision_id
        or pending.captured_at != self.captured_at
        or pending.casilla_values != tuple((row.casilla_id, row.value) for row in self.casilla_values)
        or layers.effective_source_kind is not ObservationSourceKind.OPERATOR_MANUAL
    ):
        raise ValueError("recorded local observation differs from its persisted pending layer")


def _require_recorded_override(
    self: ModeloLocalObservationMutationProjection, layers: ModeloFilingObservationLayersProjection
) -> None:
    """Require the override audit metadata for the same recorded mutation."""
    override = layers.override
    if (
        override is None
        or override.actor != self.captured_by
        or override.reason != self.reason
        or override.recorded_at != self.captured_at
    ):
        raise ValueError("recorded local observation differs from its persisted pending layer")


def _require_cleared_layers(layers: ModeloFilingObservationLayersProjection) -> None:
    """Require cleared pending and override layers with the official fallback source."""
    if (
        layers.pending_local is not None
        or layers.override is not None
        or layers.effective_source_kind != (layers.official.source_kind if layers.official is not None else None)
    ):
        raise ValueError("cleared local observation still exposes a pending override")
