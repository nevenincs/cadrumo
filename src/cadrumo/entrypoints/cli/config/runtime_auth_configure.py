"""Exact-profile CLI bridge for the registered auth provider configure operation."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer

from ....application.auth.catalogue import get_auth_provider
from ....application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AuthConfigureOperationRequest,
)
from ....application.auth.operator_results import AuthConfigureResult
from ....application.auth.provider_configure_operation_access import (
    AuthConfigureOperationProjection,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.auth_provider import AuthProviderKind
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import run_registered_operation, submitted_operation_error
from ._profile_support import resolve_active_profile_pointer


def run_auth_configure(
    ctx: typer.Context,
    *,
    provider: str,
    certificate_path: Path | None = None,
) -> AuthConfigureResult:
    """Configure auth through this invocation's exact authenticated profile."""
    try:
        provider_kind = AuthProviderKind(get_auth_provider(provider).id)
    except KeyError:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.auth.unknown_provider",
            context={"provider": provider},
        ) from None

    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.auth.no_active_bucket")
    profile_id = UUID(str(pointer.bucket_id))

    try:
        client = require_profile_client(ctx, expected_profile_id=profile_id)
        completed = run_registered_operation(
            client,
            AuthConfigureOperationRequest(provider=provider_kind, certificate_path=certificate_path),
            definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=AuthConfigureOperationProjection,
            request_version=1,
            result_version=1,
            timeout=120,
        )
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason.value}) from None

    projection = completed.projection
    try:
        if type(projection) is not AuthConfigureOperationProjection:
            raise ValueError("provider configure returned a different projection")
        result = projection.result.to_result()
    except (AttributeError, TypeError, ValueError):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None

    if (
        projection.profile_id != profile_id
        or result.provider != provider_kind.value
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return result


__all__ = ["run_auth_configure"]
