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
from ....application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from ....application.runtime.contracts import RuntimeRefusalError
from ....core.auth_provider import AuthProviderKind
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_errors import invalid_completion_error
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import run_registered_operation
from ._profile_support import resolve_active_profile_pointer


def run_auth_configure(
    ctx: typer.Context,
    *,
    provider: str,
    certificate_path: Path | None = None,
    clave_movil_route: str | None = None,
) -> AuthConfigurePublicResultV2:
    """Configure auth through this invocation's exact authenticated profile.

    Parsing is the CLI schema boundary: an invalid choice exposes the field and
    rule, never echoing the supplied value into a refusal envelope.
    """
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
        # The deferred certificate reference will be read in a worker whose
        # cwd is the storage root, rather than this CLI invocation's directory.
        absolute_certificate = certificate_path.expanduser().resolve(strict=False) if certificate_path else None
        completed = run_registered_operation(
            client,
            AuthConfigureOperationRequest.model_validate(
                {
                    "provider": provider_kind,
                    "certificate_path": absolute_certificate,
                    "clave_movil_route": clave_movil_route,
                },
                strict=False,
            ),
            definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=AuthConfigurePublicResultV2,
            request_version=1,
            result_version=2,
            timeout=120,
        )
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason.value}) from None

    projection = completed.projection
    try:
        if type(projection) is not AuthConfigurePublicResultV2:
            raise ValueError("provider configure returned a different projection")
    except (AttributeError, TypeError, ValueError):
        raise invalid_completion_error(completed) from None

    if _auth_configure_receipt_invalid(completed, projection, profile_id, provider_kind):
        raise invalid_completion_error(completed) from None
    return projection


__all__ = ["run_auth_configure"]


def _auth_configure_receipt_invalid(
    completed: RegisteredOperationCompletion[AuthConfigurePublicResultV2],
    projection: AuthConfigurePublicResultV2,
    profile_id: UUID,
    provider_kind: AuthProviderKind,
) -> bool:
    """Correlate provider configuration and its exact changed-or-unchanged effect."""
    return (
        projection.profile_id != profile_id
        or projection.provider is not provider_kind
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or (completed.refusal_code is not None)
        or (completed.effect is not (OperationEffect.UPDATED if projection.changed else OperationEffect.NONE))
    )
