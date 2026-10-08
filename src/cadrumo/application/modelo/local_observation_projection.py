"""Receipt-bound public projection of committed local observations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.public_period import PublicPeriod
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .filing_record_view_operation import ModeloFilingObservationLayersProjection
from .local_observation_actions import (
    ModeloLocalObservationClearResult,
    ModeloLocalObservationResult,
)
from .local_observation_contracts import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationCasillaValue,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationReport,
)


def project_modelo_local_observation_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release only a result whose exact receipt proves the local write."""
    if type(result) is not ModeloLocalObservationMutationReport:
        raise ValueError("invalid local observation operation result")
    report = ModeloLocalObservationMutationReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    require_terminal_receipt_match(
        receipt,
        definition_id=MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        message="local observation result contradicts its terminal receipt",
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ValueError("local observation result exceeds the projection document limit")
    return projection


def project_recorded_observation(
    *,
    profile_id: UUID,
    result: ModeloLocalObservationResult,
    layers: ModeloFilingObservationLayersProjection,
) -> ModeloLocalObservationMutationProjection:
    """Project a canonical record result without exposing an unbounded domain object."""
    return ModeloLocalObservationMutationProjection(
        profile_id=profile_id,
        action="recorded",
        modelo=result.modelo,
        period=PublicPeriod.from_period(result.period),
        revision_id=result.revision_id,
        observation_key=result.observation_key,
        source_kind=result.source_kind,
        casilla_values=tuple(
            ModeloLocalObservationCasillaValue(casilla_id=str(casilla_id), value=str(value))
            for casilla_id, value in sorted(result.casilla_values.items())
        ),
        captured_at=result.captured_at,
        captured_by=result.captured_by,
        reason=result.override.reason,
        observation_layers=layers,
    )


def project_cleared_observation(
    *,
    profile_id: UUID,
    result: ModeloLocalObservationClearResult,
    layers: ModeloFilingObservationLayersProjection,
) -> ModeloLocalObservationMutationProjection:
    """Project a clear result without releasing the removed override's old values."""
    return ModeloLocalObservationMutationProjection(
        profile_id=profile_id,
        action="cleared",
        modelo=result.modelo,
        period=PublicPeriod.from_period(result.period),
        observation_key=result.observation_key,
        captured_at=result.cleared_at,
        captured_by=result.cleared_by,
        reason=result.reason,
        observation_layers=layers,
    )
