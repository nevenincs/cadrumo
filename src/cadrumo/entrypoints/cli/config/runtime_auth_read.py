"""CLI binding to one admitted profile-worker auth read."""

from __future__ import annotations

from uuid import UUID

import typer

from ....application.auth.catalogue import get_auth_provider
from ....application.auth.read_operation import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadKind,
    AuthReadProjection,
    AuthReadRequest,
    AuthReadResult,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..common import activate_subcommand_output_language
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import run_registered_operation, submitted_operation_error
from ._profile_support import require_active_profile_pointer
from .runtime_profile_view import resolve_runtime_profile_output_language


def cli_auth_read(
    ctx: typer.Context,
    *,
    kind: AuthReadKind,
    provider: str | None = None,
    diagnostic_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> AuthReadResult:
    """Use only the invocation's exact authenticated profile connection."""
    pointer = require_active_profile_pointer()
    profile_id = UUID(str(pointer.bucket_id))
    try:
        if provider is not None:
            try:
                get_auth_provider(provider)
            except KeyError as error:
                raise CliRefusedBoundaryError(
                    translated_message="cli.config.auth.unknown_provider", context={"provider": provider}
                ) from error
        client = require_profile_client(ctx, expected_profile_id=profile_id)
        language = resolve_runtime_profile_output_language(client, requested=output_language)
        activate_subcommand_output_language(ctx, language)
        request = AuthReadRequest(
            profile_id=profile_id,
            kind=kind,
            provider=provider,
            diagnostic_id=diagnostic_id,
        )
        completed = run_registered_operation(
            client,
            request,
            definition_id=AUTH_READ_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=AuthReadProjection,
            request_version=1,
            result_version=1,
            timeout=60,
        )
        projected = completed.projection
        try:
            result = projected.to_result()
        except ValueError:
            result = None
        if (
            projected.profile_id != profile_id
            or projected.kind != kind
            or result is None
            or (
                kind == "diagnostics_view"
                and result.diagnostics_view is not None
                and result.diagnostics_view.diagnostic_id != diagnostic_id
            )
            or completed.effect is not OperationEffect.NONE
        ):
            raise submitted_operation_error(
                completed.operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=OperationTerminalCondition.SUCCEEDED,
                effect=completed.effect,
            )
        return result
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason.value}) from error
