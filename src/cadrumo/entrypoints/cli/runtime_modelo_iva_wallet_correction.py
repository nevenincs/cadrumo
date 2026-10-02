"""CLI bridge for one exact-profile registered IVA-wallet correction."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import typer

from ...application.modelo.iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionProjection,
    ModeloIvaWalletCorrectionRequest,
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
class ModeloIvaWalletCorrectionRead:
    """Keep the operation receipt beside its bounded public projection."""

    completion: RegisteredOperationCompletion[ModeloIvaWalletCorrectionProjection]
    projection: ModeloIvaWalletCorrectionProjection


def read_modelo_iva_wallet_correction_for_cli(
    ctx: typer.Context,
    *,
    period: Period,
    amount: str,
    reason: str,
) -> ModeloIvaWalletCorrectionRead:
    """Submit one canonical period to the runtime bound to the current profile."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ModeloIvaWalletCorrectionRequest(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        amount=amount,
        reason=reason,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=ModeloIvaWalletCorrectionProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ModeloIvaWalletCorrectionProjection):
            raise ValueError("IVA wallet correction projection has an invalid type")
        if (
            projection.profile_id != profile_id
            or projection.period != PublicPeriod.from_period(period)
            or Decimal(projection.amount) != Decimal(request.amount)
            or projection.provenance is not IvaCompensationStateProvenance.OPERATOR_CORRECTION
            or projection.register_status is not None
            or projection.reason != request.reason
        ):
            raise ValueError("IVA wallet correction result differs from its submitted profile and request")
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.UPDATED
        ):
            raise ValueError("IVA wallet correction result disagrees with its settled receipt")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return ModeloIvaWalletCorrectionRead(completion=completed, projection=projection)


__all__ = ["ModeloIvaWalletCorrectionRead", "read_modelo_iva_wallet_correction_for_cli"]
