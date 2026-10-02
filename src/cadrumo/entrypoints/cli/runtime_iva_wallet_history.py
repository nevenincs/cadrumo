"""CLI client for one exact-profile persisted IVA wallet history read."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.iva_wallet_history_operation import (
    IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
    IvaWalletHistoryProjection,
    IvaWalletHistoryRequest,
)
from ...application.live.remote_state_models import IvaCompensationHistoryReport
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
class IvaWalletHistoryRead:
    """Preserve the exact settled receipt through CLI presentation."""

    completion: RegisteredOperationCompletion[IvaWalletHistoryProjection]
    report: IvaCompensationHistoryReport


def read_iva_wallet_history_for_cli(ctx: typer.Context, *, as_of_year: int | None) -> IvaWalletHistoryRead:
    """Return only a matching, settled local result from the bound worker."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        IvaWalletHistoryRequest(profile_id=client.profile_id, as_of_year=as_of_year),
        definition_id=IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=IvaWalletHistoryProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or (as_of_year is not None and result.as_of_year != as_of_year)
        or completed.effect is not OperationEffect.NONE
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    try:
        report = result.to_report()
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return IvaWalletHistoryRead(completion=completed, report=report)
