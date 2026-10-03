"""Exact-profile CLI bridge for registered local auth teardown operations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import typer
from pydantic import BaseModel

from ....application.auth.catalogue import get_auth_provider
from ....application.auth.operation_definitions import (
    AUTH_LOGOUT_OPERATION_DEFINITION_ID,
    AUTH_RESET_OPERATION_DEFINITION_ID,
    AuthTeardownOperationRequest,
)
from ....application.auth.operator_results import AuthLogoutResult, AuthResetResult
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.auth_provider import AuthProviderKind
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)
from ._profile_support import resolve_active_profile_pointer


def _provider_kind(provider: str | None, *, all_providers: bool) -> AuthProviderKind | None:
    """Validate only public selector syntax before opening the worker."""
    if provider is not None and all_providers:
        raise CliRefusedBoundaryError(translated_message="application.auth.operator.errors.scope_conflict")
    if provider is None:
        return None
    try:
        return AuthProviderKind(get_auth_provider(provider).id)
    except KeyError:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider", context={"provider": provider}
        ) from None


def run_auth_teardown[ResultT: BaseModel](
    ctx: typer.Context,
    *,
    kind: Literal["logout", "reset"],
    provider: str | None,
    all_providers: bool,
    result_type: type[ResultT],
) -> RegisteredOperationCompletion[ResultT]:
    """Submit one teardown to the invocation's bound profile and verify its effect."""
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.auth.no_active_bucket")
    profile_id = UUID(str(pointer.bucket_id))
    provider_kind = _provider_kind(provider, all_providers=all_providers)
    try:
        client = require_profile_client(ctx, expected_profile_id=profile_id)
        completed = run_registered_operation(
            client,
            AuthTeardownOperationRequest(provider=provider_kind, all_providers=all_providers),
            definition_id=(
                AUTH_LOGOUT_OPERATION_DEFINITION_ID if kind == "logout" else AUTH_RESET_OPERATION_DEFINITION_ID
            ),
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=result_type,
            request_version=1,
            result_version=1,
            timeout=120,
        )
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason.value}) from None
    result = completed.projection
    if isinstance(result, AuthLogoutResult):
        changed = bool(result.removed_sessions or result.cleared_session_state)
        result_kind_ok = kind == "logout"
        bucket_id, providers = result.bucket_id, result.providers
    elif isinstance(result, AuthResetResult):
        changed = bool(
            result.removed_sessions
            or result.cleared_provider_configuration
            or result.cleared_locks
            or result.removed_certificate_sources
            or result.removed_certificate_secrets
        )
        result_kind_ok = kind == "reset"
        bucket_id, providers = result.bucket_id, result.providers
    else:
        changed = False
        result_kind_ok = False
        bucket_id, providers = None, ()
    if (
        not result_kind_ok
        or bucket_id != str(profile_id)
        or (provider_kind is not None and provider_kind.value not in providers)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not (OperationEffect.UPDATED if changed else OperationEffect.NONE)
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return completed


__all__ = ["run_auth_teardown"]
