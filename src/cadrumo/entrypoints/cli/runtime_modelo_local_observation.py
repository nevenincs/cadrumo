"""CLI bridge for worker-owned local modelo observation mutations."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import typer
from pydantic import ValidationError

from ...application.modelo.filing_record_view_operation import (
    ModeloFilingObservationLayerProjection,
    ModeloFilingObservationLayersProjection,
)
from ...application.modelo.local_observation_operation import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationCasillaValue,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.casilla_id import CasillaId
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ._filing_chain_payloads import (
    ObservationLayerPayload,
    ObservationLayersPayload,
    ObservationOverridePayload,
)
from ._modelo_payloads import FilingRecordLocalObservationResult
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid_frame(
    completed: RegisteredOperationCompletion[ModeloLocalObservationMutationProjection],
) -> CliRefusedBoundaryError:
    """Retain the exact operation identity when its result exceeds the CLI adapter."""
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _observation_layers_payload(
    layers: ModeloFilingObservationLayersProjection,
) -> ObservationLayersPayload:
    """Adapt the worker's allowlisted projection to the established CLI payload."""

    def layer_payload(layer: ModeloFilingObservationLayerProjection | None) -> ObservationLayerPayload | None:
        if layer is None:
            return None
        return ObservationLayerPayload(
            source_kind=layer.source_kind,
            official_evidence=layer.official_evidence,
            captured_at=layer.captured_at,
            stamped_revision_id=layer.stamped_revision_id,
            casilla_values={casilla_id: value for casilla_id, value in layer.casilla_values},
        )

    override_projection = layers.override
    override = (
        ObservationOverridePayload(
            actor=override_projection.actor,
            reason=override_projection.reason,
            recorded_at=override_projection.recorded_at,
            replaced_source_kind=override_projection.replaced_source_kind,
            replaced_values=dict(override_projection.replaced_values),
        )
        if override_projection is not None
        else None
    )
    return ObservationLayersPayload(
        official=layer_payload(layers.official),
        pending_local=layer_payload(layers.pending_local),
        effective_source_kind=layers.effective_source_kind,
        override=override,
    )


def _mutate_modelo_local_observation(
    ctx: typer.Context,
    *,
    action: Literal["record", "clear"],
    modelo: str,
    period: Period,
    actor: str | None,
    reason: str,
    casilla_values: dict[CasillaId, Decimal] | None,
) -> FilingRecordLocalObservationResult:
    """Submit one period-scoped request and restore only the existing CLI result."""
    client = bound_profile_client(ctx)
    values = tuple(
        ModeloLocalObservationCasillaValue(casilla_id=casilla_id, value=str(value))
        for casilla_id, value in sorted((casilla_values or {}).items())
    )
    try:
        request = ModeloLocalObservationMutationRequest(
            profile_id=client.profile_id,
            action=action,
            modelo=modelo,
            period=PublicPeriod.from_period(period),
            casilla_values=values,
            actor=actor,
            reason=reason,
        )
    except ValidationError:
        raise typer.BadParameter("local observation request is invalid") from None
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloLocalObservationMutationProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    expected_action = "recorded" if action == "record" else "cleared"
    expected_actor = actor or f"profile:{client.profile_id}"
    try:
        if (
            not isinstance(projection, ModeloLocalObservationMutationProjection)
            or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.UPDATED
            or projection.profile_id != client.profile_id
            or projection.action != expected_action
            or projection.modelo != modelo
            or projection.period.to_period() != period
            or projection.captured_by != expected_actor
            or projection.reason != reason.strip()
        ):
            raise ValueError("local observation result differs from its exact request")
        output_values = {row.casilla_id: row.value for row in projection.casilla_values}
        if action == "record" and output_values != {
            casilla_id: str(value) for casilla_id, value in sorted((casilla_values or {}).items())
        }:
            raise ValueError("recorded local observation values differ from the submitted values")
        if action == "clear" and output_values:
            raise ValueError("cleared local observation unexpectedly returned values")

        result = FilingRecordLocalObservationResult(
            action=projection.action,
            modelo=projection.modelo,
            filing_year=projection.period.filing_year,
            period=projection.period.to_period(),
            revision_id=projection.revision_id,
            observation_key=projection.observation_key,
            source_kind=projection.source_kind,
            casilla_values=output_values,
            casilla_count=len(output_values),
            captured_at=projection.captured_at,
            captured_by=projection.captured_by,
            reason=projection.reason,
            observation_layers=_observation_layers_payload(projection.observation_layers),
        )
    except Exception:
        raise _invalid_frame(completed) from None
    return result


def record_modelo_local_observation(
    ctx: typer.Context,
    *,
    modelo: str,
    period: Period,
    casilla_values: dict[CasillaId, Decimal],
    actor: str | None,
    reason: str,
) -> FilingRecordLocalObservationResult:
    """Persist operator-supplied values through the registered profile worker."""
    return _mutate_modelo_local_observation(
        ctx,
        action="record",
        modelo=modelo,
        period=period,
        actor=actor,
        reason=reason,
        casilla_values=casilla_values,
    )


def clear_modelo_local_observation(
    ctx: typer.Context,
    *,
    modelo: str,
    period: Period,
    actor: str | None,
    reason: str,
) -> FilingRecordLocalObservationResult:
    """Clear the pending local layer through the registered profile worker."""
    return _mutate_modelo_local_observation(
        ctx,
        action="clear",
        modelo=modelo,
        period=period,
        actor=actor,
        reason=reason,
        casilla_values=None,
    )


__all__ = ["clear_modelo_local_observation", "record_modelo_local_observation"]
