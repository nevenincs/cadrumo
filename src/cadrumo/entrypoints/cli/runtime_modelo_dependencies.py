"""Authenticated CLI transport for cross-period dependency inspection."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.modelo.dependency_operation import (
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
    ModeloDependencyProjection,
    ModeloDependencyRequest,
    ModeloDependencySnapshot,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class ModeloDependenciesRead:
    """Keep the exact result receipt beside its correlated snapshot."""

    completion: RegisteredOperationCompletion[ModeloDependencyProjection]
    snapshot: ModeloDependencySnapshot


def read_modelo_dependencies(
    ctx: typer.Context, *, filing_year: int, modelo: str | None, period: Period | None
) -> ModeloDependenciesRead:
    """Capture dependency facts only in the selected profile's worker."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    requested_period = PublicPeriod.from_period(period) if period is not None else None
    completed = run_registered_operation(
        client,
        ModeloDependencyRequest(
            profile_id=client.profile_id, filing_year=filing_year, modelo=modelo, period=requested_period
        ),
        definition_id=MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloDependencyProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    snapshot = projection.snapshot
    if (
        projection.profile_id != client.profile_id
        or snapshot.filing_year != filing_year
        or snapshot.modelo_filter != modelo
        or snapshot.period_filter != requested_period
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return ModeloDependenciesRead(completion=completed, snapshot=snapshot)


__all__ = ["ModeloDependenciesRead", "read_modelo_dependencies"]
