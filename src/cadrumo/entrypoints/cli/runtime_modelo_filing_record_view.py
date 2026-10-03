"""CLI bridge for worker-owned, exact-profile filing-record views."""

from __future__ import annotations

import typer

from ...application.modelo.filing_record_view_operation import (
    MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
    ModeloFilingObservationLayerProjection,
    ModeloFilingObservationLayersProjection,
    ModeloFilingObservationOverrideProjection,
    ModeloFilingRecordViewProjection,
    ModeloFilingRecordViewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ._filing_chain_payloads import (
    ObservationLayerPayload,
    ObservationLayersPayload,
    ObservationOverridePayload,
)
from ._modelo_payloads import ModeloRecordPayload
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def _layer_payload(layer: ModeloFilingObservationLayerProjection | None) -> ObservationLayerPayload | None:
    if layer is None:
        return None
    return ObservationLayerPayload(
        source_kind=layer.source_kind,
        official_evidence=layer.official_evidence,
        captured_at=layer.captured_at,
        stamped_revision_id=layer.stamped_revision_id,
        casilla_values={casilla_id: str(value) for casilla_id, value in layer.casilla_values},
    )


def _override_payload(
    override: ModeloFilingObservationOverrideProjection | None,
) -> ObservationOverridePayload | None:
    if override is None:
        return None
    return ObservationOverridePayload(
        actor=override.actor,
        reason=override.reason,
        recorded_at=override.recorded_at,
        replaced_source_kind=override.replaced_source_kind,
        replaced_values=dict(override.replaced_values),
    )


def _observation_layers_payload(layers: ModeloFilingObservationLayersProjection) -> ObservationLayersPayload:
    """Restore the payload used by the existing CLI renderer."""
    return ObservationLayersPayload(
        official=_layer_payload(layers.official),
        pending_local=_layer_payload(layers.pending_local),
        effective_source_kind=layers.effective_source_kind,
        override=_override_payload(layers.override),
    )


def read_modelo_filing_record_view(
    ctx: typer.Context,
    *,
    filing_record_id: str,
) -> tuple[ModeloRecordPayload, ObservationLayersPayload]:
    """Return only established CLI fields and renderer-ready observation layers."""
    client = bound_profile_client(ctx)
    request = ModeloFilingRecordViewRequest(
        profile_id=client.profile_id,
        filing_record_id=filing_record_id,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloFilingRecordViewProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if not isinstance(projection, ModeloFilingRecordViewProjection):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    try:
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.NONE
            or projection.profile_id != client.profile_id
            or projection.filing_record_id != request.filing_record_id
        ):
            raise ValueError("filing view receipt or profile does not match its request")
        snapshot = projection.record
        record = ModeloRecordPayload.model_validate(
            snapshot.model_dump(mode="python")
            | {"period": Period.from_year_and_code(snapshot.filing_year, snapshot.period)}
        )
        layers = projection.observation_layers
        if (
            record.bucket_id != str(client.profile_id)
            or record.filing_record_id != request.filing_record_id
            or layers.modelo != str(record.modelo)
            or layers.filing_year != record.filing_year
            or layers.period != record.period.registry_token
            or layers.member_nif != record.member_nif
        ):
            raise ValueError("filing view record or observation layers exceed the submitted scope")
        payload = _observation_layers_payload(layers)
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return record, payload


__all__ = ["read_modelo_filing_record_view"]
