"""CLI recovery enrollment inspection through immutable worker custody."""

from __future__ import annotations

from uuid import UUID

import typer

from ....application.runtime.contracts import RuntimeRefusalError
from ....application.user_profile.recovery_status_operation import (
    RECOVERY_STATUS_OPERATION_DEFINITION_ID,
    RecoveryStatusProjection,
    RecoveryStatusRequest,
    RecoveryStatusResult,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..registered_operation_errors import invalid_completion_error
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import run_registered_operation
from ._profile_support import resolve_active_profile_pointer


def read_recovery_status(ctx: typer.Context) -> RecoveryStatusResult:
    """Release only the successful enrollment projection for the selected profile."""
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.profile.recovery.no_active_profile")
    profile_id = UUID(str(pointer.bucket_id))
    try:
        client = require_profile_client(ctx, expected_profile_id=profile_id)
        completed = run_registered_operation(
            client,
            RecoveryStatusRequest(profile_id=profile_id),
            definition_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=RecoveryStatusProjection,
            request_version=1,
            result_version=1,
            timeout=60,
        )
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason.value}) from None
    result = completed.projection
    if (
        type(result) is not RecoveryStatusProjection
        or result.profile_id != profile_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise invalid_completion_error(completed) from None
    return result
