"""CLI bridge for one exact-profile registered IVA filed-history capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import typer

from ...application.live.iva_wallet_history_capture_operation import (
    IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
    IvaWalletHistoryCapturePublicResultV1,
    IvaWalletHistoryCaptureRequest,
    iva_history_capture_base_effect,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_deadlines import provider_login_settlement_seconds
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


@dataclass(frozen=True, slots=True)
class IvaWalletHistoryCaptureRead:
    """Keep the settled worker receipt with its safe public report projection."""

    completion: RegisteredOperationCompletion[IvaWalletHistoryCapturePublicResultV1]
    projection: IvaWalletHistoryCapturePublicResultV1


def read_iva_wallet_history_capture_for_cli(
    ctx: typer.Context,
    *,
    year_from: int,
    year_to: int,
    output_root: Path,
) -> IvaWalletHistoryCaptureRead:
    """Submit one history sweep and accept only its exact-profile settled result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = IvaWalletHistoryCaptureRequest(
        profile_id=profile_id,
        output_root=output_root,
        year_from=year_from,
        year_to=year_to,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=IvaWalletHistoryCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
        settlement_timeout=provider_login_settlement_seconds(after_login=120),
    )
    try:
        projection = completed.projection
        if not isinstance(projection, IvaWalletHistoryCapturePublicResultV1):
            raise ValueError("IVA history capture projection has an invalid type")
        expected_effect = iva_history_capture_base_effect(
            projection.captured_count, projection.calculation_observation_count
        )
        if (
            projection.output_root != str(request.output_root)
            or projection.year_from != request.year_from
            or projection.year_to != request.year_to
        ):
            raise ValueError("IVA history capture result does not match its submitted scope")
        if _iva_history_receipt_invalid(completed, expected_effect):
            raise ValueError("IVA history capture result disagrees with its settled receipt")
    except Exception:
        raise invalid_completion_error(completed) from None
    return IvaWalletHistoryCaptureRead(completion=completed, projection=projection)


__all__ = ["IvaWalletHistoryCaptureRead", "read_iva_wallet_history_capture_for_cli"]


def _iva_history_receipt_invalid(
    completed: RegisteredOperationCompletion[IvaWalletHistoryCapturePublicResultV1], expected_effect: OperationEffect
) -> bool:
    """Accept the original idempotent updated receipt exception only after validating the capture scope."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or (
            completed.effect is not expected_effect
            and (not (expected_effect is OperationEffect.NONE and completed.effect is OperationEffect.UPDATED))
        )
    )
