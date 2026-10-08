"""Authenticated CLI bridge for protected apoderado configuration operations."""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import ValidationError

from ....application.auth.apoderado_contracts import (
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ApoderadoCheckRequest,
    ApoderadoClearRequest,
    ApoderadoConfigurationSnapshot,
    ApoderadoConfigureRequest,
    ApoderadoOperationProjection,
    ApoderadoStatusRequest,
    ApoderadoStatusSnapshot,
)
from ....application.auth.apoderado_service import (
    ApoderadoLiveCheckUnavailableError,
    ApoderadoRepresentedNifInvalidError,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.auth.apoderamientos.catalogue import (
    ApoderamientosCatalogue,
    UnknownScopeError,
    load_default_catalogue,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_errors import invalid_completion_error
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import run_registered_operation


def apoderado_catalogue(ctx: typer.Context) -> ApoderamientosCatalogue:
    """Load the public scope catalogue through the command's pinned authority."""
    from ..state_projection_support import authority_operation

    return load_default_catalogue(operation=authority_operation(ctx))


def read_apoderado_status(ctx: typer.Context) -> ApoderadoStatusSnapshot:
    """Read protected apoderado status for the exact authenticated profile."""
    client = bound_profile_client(ctx)
    request = ApoderadoStatusRequest(profile_id=client.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=APODERADO_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ApoderadoOperationProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        _apoderado_status_terminal_invalid(completed)
        or _apoderado_status_header_invalid(projection, client.profile_id)
        or projection.status is None
        or projection.configuration is not None
        or projection.cleared is not None
        or (str(projection.status.bucket_id) != str(client.profile_id))
    ):
        raise invalid_completion_error(completed)
    return projection.status


def configure_apoderado(
    ctx: typer.Context,
    *,
    represented_nif: str,
    scope_tokens: tuple[str, ...],
    notes: str = "",
) -> ApoderadoConfigurationSnapshot:
    """Configure exact-profile apoderado state with a one-use protected NIF."""
    client = bound_profile_client(ctx)
    try:
        request = ApoderadoConfigureRequest(
            profile_id=client.profile_id,
            scope_tokens=scope_tokens,
            notes=notes,
        )
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None

    secret = bytearray(represented_nif.encode("utf-8"))
    completed = run_registered_operation(
        client,
        request,
        definition_id=APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ApoderadoOperationProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
        secret=secret,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or str(projection.operation_id) != APODERADO_CONFIGURE_OPERATION_DEFINITION_ID
        or projection.effect is not completed.effect
    ):
        raise invalid_completion_error(completed)
    if projection.outcome == "prewrite_refusal":
        _raise_apoderado_prewrite_refusal(completed, projection)

    configuration = projection.configuration
    return _apoderado_configuration_result(
        completed, projection, configuration, client.profile_id, represented_nif, notes
    )


def clear_apoderado(ctx: typer.Context) -> bool:
    """Clear protected apoderado state for the exact authenticated profile."""
    client = bound_profile_client(ctx)
    request = ApoderadoClearRequest(profile_id=client.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=APODERADO_CLEAR_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ApoderadoOperationProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    cleared = projection.cleared
    expected_effect = OperationEffect.UPDATED if cleared else OperationEffect.NONE
    if (
        _apoderado_clear_terminal_invalid(completed, expected_effect)
        or _apoderado_clear_header_invalid(projection, client.profile_id, expected_effect)
        or cleared is None
        or projection.status is not None
        or projection.configuration is not None
    ):
        raise invalid_completion_error(completed)
    return cleared


def check_apoderado(ctx: typer.Context) -> None:
    """Run the registered live-check boundary and preserve its typed refusal."""
    client = bound_profile_client(ctx)
    request = ApoderadoCheckRequest(profile_id=client.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=APODERADO_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ApoderadoOperationProjection,
        request_version=1,
        result_version=1,
        timeout=60,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if (
        _apoderado_check_terminal_invalid(completed)
        or _apoderado_check_header_invalid(projection, client.profile_id, completed)
        or projection.status is not None
        or projection.configuration is not None
        or projection.cleared is not None
    ):
        raise invalid_completion_error(completed)
    raise ApoderadoLiveCheckUnavailableError


__all__ = [
    "apoderado_catalogue",
    "check_apoderado",
    "clear_apoderado",
    "configure_apoderado",
    "read_apoderado_status",
]


def _apoderado_status_header_invalid(projection: ApoderadoOperationProjection, profile_id: UUID) -> bool:
    """Correlate exact profile, operation kind, outcome, and projected receipt."""
    return (
        projection.profile_id != profile_id
        or str(projection.operation_id) != APODERADO_STATUS_OPERATION_DEFINITION_ID
        or projection.outcome != "completed"
        or (projection.effect is not OperationEffect.NONE)
        or (projection.refusal_code is not None)
    )


def _apoderado_status_terminal_invalid(completed: RegisteredOperationCompletion[ApoderadoOperationProjection]) -> bool:
    """Require the exact terminal condition, refusal code, and effect."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    )


def _apoderado_clear_header_invalid(
    projection: ApoderadoOperationProjection, profile_id: UUID, expected_effect: OperationEffect
) -> bool:
    """Correlate exact profile, operation kind, outcome, and projected receipt."""
    return (
        projection.profile_id != profile_id
        or str(projection.operation_id) != APODERADO_CLEAR_OPERATION_DEFINITION_ID
        or projection.outcome != "completed"
        or (projection.effect is not expected_effect)
        or (projection.refusal_code is not None)
    )


def _apoderado_clear_terminal_invalid(
    completed: RegisteredOperationCompletion[ApoderadoOperationProjection], expected_effect: OperationEffect
) -> bool:
    """Require the exact terminal condition, refusal code, and effect."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
    )


def _apoderado_check_header_invalid(
    projection: ApoderadoOperationProjection,
    profile_id: UUID,
    completed: RegisteredOperationCompletion[ApoderadoOperationProjection],
) -> bool:
    """Correlate exact profile, operation kind, outcome, and projected receipt."""
    return (
        projection.profile_id != profile_id
        or str(projection.operation_id) != APODERADO_CHECK_OPERATION_DEFINITION_ID
        or projection.outcome != "prewrite_refusal"
        or (projection.effect is not OperationEffect.NONE)
        or (projection.refusal_code != completed.refusal_code)
    )


def _apoderado_check_terminal_invalid(completed: RegisteredOperationCompletion[ApoderadoOperationProjection]) -> bool:
    """Require the exact terminal condition, refusal code, and effect."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != "REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE"
    )


def _raise_apoderado_prewrite_refusal(
    completed: RegisteredOperationCompletion[ApoderadoOperationProjection], projection: ApoderadoOperationProjection
) -> Never:
    """Translate only a correlated prewrite refusal without success payload."""
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or projection.effect is not OperationEffect.NONE
        or projection.refusal_code != completed.refusal_code
        or projection.status is not None
        or projection.configuration is not None
        or projection.cleared is not None
    ):
        raise invalid_completion_error(completed)
    if projection.refusal_code == "REFUSED_APODERADO_INVALID_REPRESENTED_NIF":
        raise ApoderadoRepresentedNifInvalidError(
            translated_message="errors.refused.refused_apoderado_invalid_represented_nif",
        )
    if projection.refusal_code == "REFUSED_APODERADO_UNKNOWN_SCOPE":
        raise UnknownScopeError(translated_message="errors.refused.refused_apoderado_unknown_scope")
    raise invalid_completion_error(completed)


def _apoderado_configure_terminal_invalid(
    completed: RegisteredOperationCompletion[ApoderadoOperationProjection],
) -> bool:
    """Require a successful updated configuration receipt without refusal."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    )


def _apoderado_configuration_result(
    completed: RegisteredOperationCompletion[ApoderadoOperationProjection],
    projection: ApoderadoOperationProjection,
    configuration: ApoderadoConfigurationSnapshot | None,
    profile_id: UUID,
    represented_nif: str,
    notes: str,
) -> ApoderadoConfigurationSnapshot:
    """Require the configured protected identity, metadata, and mutation receipt."""
    if (
        _apoderado_configure_terminal_invalid(completed)
        or projection.outcome != "completed"
        or configuration is None
        or projection.status is not None
        or (projection.cleared is not None)
        or (str(configuration.bucket_id) != str(profile_id))
        or (configuration.represented_nif != represented_nif)
        or (configuration.notes != notes)
    ):
        raise invalid_completion_error(completed)
    return configuration
