"""CLI bridge for one exact-profile registered IVA-wallet override."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import typer

from ...application.modelo.iva_wallet_override_operation import (
    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletOverrideProjection,
    ModeloIvaWalletOverrideRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .runtime_profile_binding import require_profile_client
from .runtime_profile_operation import settled_projection, submit_profile_operation


@dataclass(frozen=True, slots=True)
class ModeloIvaWalletOverrideRead:
    """Keep the operation receipt beside its bounded public projection."""

    completion: RegisteredOperationCompletion[ModeloIvaWalletOverrideProjection]
    projection: ModeloIvaWalletOverrideProjection


def read_modelo_iva_wallet_override_for_cli(
    ctx: typer.Context,
    *,
    period: Period,
    amount: str,
    reason: str,
    evidence_locator: str,
) -> ModeloIvaWalletOverrideRead:
    """Submit one canonical period to the runtime bound to the current profile."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ModeloIvaWalletOverrideRequest(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        amount=amount,
        reason=reason,
        evidence_locator=evidence_locator,
    )
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
        result_type=ModeloIvaWalletOverrideProjection,
        timeout=60,
    )

    def correlate(projection: ModeloIvaWalletOverrideProjection) -> None:
        if (
            projection.profile_id != profile_id
            or projection.period != PublicPeriod.from_period(period)
            or Decimal(projection.amount) != Decimal(request.amount)
            or projection.reason != request.reason
            or projection.evidence_locator != request.evidence_locator
            or projection.selected_authority != "taxpayer_override"
            or projection.divergence != "override"
        ):
            raise ValueError("IVA wallet override result differs from its submitted profile and request")

    projection = settled_projection(
        completed, ModeloIvaWalletOverrideProjection, correlate, effect=OperationEffect.UPDATED
    )
    return ModeloIvaWalletOverrideRead(completion=completed, projection=projection)


__all__ = ["ModeloIvaWalletOverrideRead", "read_modelo_iva_wallet_override_for_cli"]
