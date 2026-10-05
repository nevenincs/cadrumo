"""CLI bridge for one exact-profile registered IVA wallet capture."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.iva_wallet_capture_operation import (
    IVA_WALLET_CAPTURE_DEFINITION_ID,
    IvaWalletCapturePublicResultV1,
    IvaWalletCaptureRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_deadlines import provider_login_settlement_seconds
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


@dataclass(frozen=True, slots=True)
class IvaWalletCaptureRead:
    """Keep the settled worker receipt with its safe public report projection."""

    completion: RegisteredOperationCompletion[IvaWalletCapturePublicResultV1]
    projection: IvaWalletCapturePublicResultV1


def read_iva_wallet_capture_for_cli(
    ctx: typer.Context,
    *,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None,
) -> IvaWalletCaptureRead:
    """Submit the parsed filing period and accept only its exact-profile result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = IvaWalletCaptureRequest(
        profile_id=profile_id,
        target_year=target_year,
        target_period=target_period.registry_token,
        taxpayer_nif=taxpayer_nif,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=IVA_WALLET_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=IvaWalletCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
        settlement_timeout=provider_login_settlement_seconds(after_login=120),
    )
    try:
        projection = completed.projection
        if not isinstance(projection, IvaWalletCapturePublicResultV1):
            raise ValueError("IVA wallet capture projection has an invalid type")
        if projection.target_year != request.target_year or projection.target_period != request.target_period:
            raise ValueError("IVA wallet capture result does not match its submitted period")
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.UPDATED
        ):
            raise ValueError("IVA wallet capture result disagrees with its settled receipt")
    except Exception:
        raise invalid_completion_error(completed) from None
    return IvaWalletCaptureRead(completion=completed, projection=projection)


__all__ = ["IvaWalletCaptureRead", "read_iva_wallet_capture_for_cli"]
