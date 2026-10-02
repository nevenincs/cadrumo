"""Authenticated CLI bridge for protected apoderado configuration operations."""

from __future__ import annotations

from typing import Never

import typer
from pydantic import BaseModel, ValidationError

from ....application.auth.apoderado_operation import (
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
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    """Refuse a worker result that does not correlate with its operation receipt."""
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


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
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or str(projection.operation_id) != APODERADO_STATUS_OPERATION_DEFINITION_ID
        or projection.outcome != "completed"
        or projection.effect is not OperationEffect.NONE
        or projection.refusal_code is not None
        or projection.status is None
        or projection.configuration is not None
        or projection.cleared is not None
        or str(projection.status.bucket_id) != str(client.profile_id)
    ):
        _invalid(completed)
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
        _invalid(completed)
    if projection.outcome == "prewrite_refusal":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.effect is not OperationEffect.NONE
            or projection.effect is not OperationEffect.NONE
            or projection.refusal_code != completed.refusal_code
            or projection.status is not None
            or projection.configuration is not None
            or projection.cleared is not None
        ):
            _invalid(completed)
        if projection.refusal_code == "REFUSED_APODERADO_INVALID_REPRESENTED_NIF":
            raise ApoderadoRepresentedNifInvalidError(
                translated_message="errors.refused.refused_apoderado_invalid_represented_nif",
            )
        if projection.refusal_code == "REFUSED_APODERADO_UNKNOWN_SCOPE":
            raise UnknownScopeError(translated_message="errors.refused.refused_apoderado_unknown_scope")
        _invalid(completed)

    configuration = projection.configuration
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or projection.outcome != "completed"
        or configuration is None
        or projection.status is not None
        or projection.cleared is not None
        or str(configuration.bucket_id) != str(client.profile_id)
        or configuration.represented_nif != represented_nif
        or configuration.notes != notes
    ):
        _invalid(completed)
    return configuration


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
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or str(projection.operation_id) != APODERADO_CLEAR_OPERATION_DEFINITION_ID
        or projection.outcome != "completed"
        or projection.effect is not expected_effect
        or projection.refusal_code is not None
        or cleared is None
        or projection.status is not None
        or projection.configuration is not None
    ):
        _invalid(completed)
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
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != "REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE"
        or projection.profile_id != client.profile_id
        or str(projection.operation_id) != APODERADO_CHECK_OPERATION_DEFINITION_ID
        or projection.outcome != "prewrite_refusal"
        or projection.effect is not OperationEffect.NONE
        or projection.refusal_code != completed.refusal_code
        or projection.status is not None
        or projection.configuration is not None
        or projection.cleared is not None
    ):
        _invalid(completed)
    raise ApoderadoLiveCheckUnavailableError


__all__ = [
    "apoderado_catalogue",
    "check_apoderado",
    "clear_apoderado",
    "configure_apoderado",
    "read_apoderado_status",
]
