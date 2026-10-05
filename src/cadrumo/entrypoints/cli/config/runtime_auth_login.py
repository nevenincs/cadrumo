"""Exact-profile CLI submission of provider authentication to its worker."""

from __future__ import annotations

from uuid import UUID

import typer

from ....application.auth.catalogue import get_auth_provider
from ....application.auth.operation_definitions import (
    AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
    AuthSessionAcquireOperationRequest,
)
from ....application.auth.operator_results import AuthLoginResult
from ....application.auth.session_acquire_operation_access import AuthSessionAcquireOperationProjection
from ....application.runtime.contracts import RuntimeRefusalError
from ....core.auth_provider import AuthProviderKind
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRecordedOperationError, CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_deadlines import provider_login_settlement_seconds
from ..registered_operation_errors import invalid_completion_error
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import run_registered_operation
from ._profile_support import resolve_active_profile_pointer


def run_auth_login(
    ctx: typer.Context,
    *,
    provider: str | None,
    fresh: bool,
    reset_lock: bool,
) -> AuthLoginResult:
    """Keep browser work and provider state inside the authenticated profile worker."""
    try:
        provider_kind = AuthProviderKind(get_auth_provider(provider).id) if provider is not None else None
    except KeyError:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider", context={"provider": provider or ""}
        ) from None
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.auth.no_active_bucket")
    profile_id = UUID(str(pointer.bucket_id))
    try:
        client = require_profile_client(ctx, expected_profile_id=profile_id)
        completed = run_registered_operation(
            client,
            AuthSessionAcquireOperationRequest(provider=provider_kind, fresh=fresh, reset_lock=reset_lock),
            definition_id=AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=AuthSessionAcquireOperationProjection,
            request_version=1,
            result_version=1,
            timeout=120,
            settlement_timeout=provider_login_settlement_seconds(),
        )
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason.value}) from None
    except CliRecordedOperationError as error:
        raise _with_diagnostic_follow_up(error) from None
    projection = completed.projection
    if type(projection) is not AuthSessionAcquireOperationProjection or _auth_login_receipt_invalid(
        completed, projection, profile_id, fresh, provider_kind
    ):
        raise invalid_completion_error(completed) from None
    return projection.result


def _with_diagnostic_follow_up(error: CliRecordedOperationError) -> CliRecordedOperationError:
    """Name the encrypted diagnostic a failed provider attempt captured as the next action."""
    from ....application.auth.diagnostics import auth_diagnostic_view_verdict
    from ..common import attach_cli_policy_verdict

    diagnostic_id = (error.context or {}).get("diagnostic_id")
    if error.terminal_precondition_verdict is not None or not isinstance(diagnostic_id, str):
        return error
    # A capture that failed is recorded as an absent id, which the context renders as "null".
    if not 1 <= len(diagnostic_id) <= 128 or diagnostic_id == "null":
        return error
    return attach_cli_policy_verdict(error, verdict=auth_diagnostic_view_verdict(diagnostic_id))


def _auth_login_receipt_invalid(
    completed: RegisteredOperationCompletion[AuthSessionAcquireOperationProjection],
    projection: AuthSessionAcquireOperationProjection,
    profile_id: UUID,
    fresh: bool,
    provider_kind: AuthProviderKind | None,
) -> bool:
    """Require authenticated provider facts and the exact successful profile receipt."""
    return (
        projection.profile_id != profile_id
        or not projection.result.authenticated
        or projection.result.removed_sessions < 0
        or (projection.result.fresh != fresh)
        or (provider_kind is not None and projection.result.provider != provider_kind.value)
        or (completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED)
        or (completed.refusal_code is not None)
        or (completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED})
    )
