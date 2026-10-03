"""CLI bridge for one exact-profile registered IVA-wallet seed."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import typer

from ...application.modelo.iva_wallet_seed_operation import (
    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
    ModeloIvaWalletSeedProjection,
    ModeloIvaWalletSeedRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class ModeloIvaWalletSeedRead:
    """Keep the operation receipt beside its bounded public projection."""

    completion: RegisteredOperationCompletion[ModeloIvaWalletSeedProjection]
    projection: ModeloIvaWalletSeedProjection


def read_modelo_iva_wallet_seed_for_cli(
    ctx: typer.Context,
    *,
    period: Period,
    amount: str,
) -> ModeloIvaWalletSeedRead:
    """Submit one canonical period to the runtime bound to the current profile."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ModeloIvaWalletSeedRequest(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        amount=amount,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=ModeloIvaWalletSeedProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ModeloIvaWalletSeedProjection):
            raise ValueError("IVA wallet seed projection has an invalid type")
        if (
            projection.profile_id != profile_id
            or projection.period != PublicPeriod.from_period(period)
            or Decimal(projection.amount) != Decimal(request.amount)
            or projection.provenance is not IvaCompensationStateProvenance.OPERATOR_SEED
            or projection.register_status is not None
        ):
            raise ValueError("IVA wallet seed result differs from its submitted profile and request")
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.UPDATED
        ):
            raise ValueError("IVA wallet seed result disagrees with its settled receipt")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return ModeloIvaWalletSeedRead(completion=completed, projection=projection)


__all__ = ["ModeloIvaWalletSeedRead", "read_modelo_iva_wallet_seed_for_cli"]
