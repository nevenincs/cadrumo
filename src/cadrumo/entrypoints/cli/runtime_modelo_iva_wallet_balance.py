"""CLI bridge for one exact-profile registered IVA-wallet balance read."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.modelo.iva_wallet_balance_operation import (
    MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletBalanceProjection,
    ModeloIvaWalletBalanceRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class ModeloIvaWalletBalanceRead:
    """Keep the operation receipt beside its bounded public projection."""

    completion: RegisteredOperationCompletion[ModeloIvaWalletBalanceProjection]
    projection: ModeloIvaWalletBalanceProjection


def read_modelo_iva_wallet_balance_for_cli(
    ctx: typer.Context,
    *,
    as_of_year: int,
) -> ModeloIvaWalletBalanceRead:
    """Submit one reference year to the runtime bound to the current profile."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ModeloIvaWalletBalanceRequest(profile_id=profile_id, as_of_year=as_of_year)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=ModeloIvaWalletBalanceProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ModeloIvaWalletBalanceProjection):
            raise ValueError("IVA wallet balance projection has an invalid type")
        if projection.profile_id != profile_id or projection.as_of_year != request.as_of_year:
            raise ValueError("IVA wallet balance result differs from its submitted profile and year")
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.NONE
        ):
            raise ValueError("IVA wallet balance result disagrees with its settled receipt")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return ModeloIvaWalletBalanceRead(completion=completed, projection=projection)


__all__ = ["ModeloIvaWalletBalanceRead", "read_modelo_iva_wallet_balance_for_cli"]
