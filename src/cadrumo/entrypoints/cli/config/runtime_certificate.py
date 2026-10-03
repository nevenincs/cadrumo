"""Exact-profile CLI bridge for named certificate sources and passphrase custody."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import UUID

import typer
from pydantic import BaseModel

from ....application.auth.certificate_secret_operation import (
    CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID,
    CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID,
    CertificateSecretMutationProjection,
    CertificateSecretMutationRequest,
)
from ....application.auth.certificate_source_contracts import (
    CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
    CertificateSourceCheckProjection,
    CertificateSourceCheckRequest,
    CertificateSourceListProjection,
    CertificateSourceListRequest,
    CertificateSourceRegisterProjection,
    CertificateSourceRegisterRequest,
    CertificateSourceRemoveProjection,
    CertificateSourceRemoveRequest,
    CertificateSourceSelectProjection,
    CertificateSourceSelectRequest,
)
from ....application.auth.operator_results import (
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
    CertificateSourceSecretMutationResult,
)
from ....application.runtime.contracts import RuntimeRefusalError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_errors import invalid_completion_error
from ..runtime_profile_binding import require_profile_client
from ..runtime_registered_operation import run_registered_operation
from ._profile_support import resolve_active_profile_pointer


def _profile_id() -> UUID:
    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.auth.no_active_bucket")
    return UUID(str(pointer.bucket_id))


def _run[ProjectionT: BaseModel](
    ctx: typer.Context,
    *,
    profile_id: UUID,
    definition_id: str,
    payload: BaseModel,
    projection_type: type[ProjectionT],
    expected_effect: OperationEffect | Callable[[ProjectionT], OperationEffect],
    validate: Callable[[ProjectionT], bool] | None = None,
    secret: bytearray | None = None,
) -> ProjectionT:
    try:
        client = require_profile_client(ctx, expected_profile_id=profile_id)
        completed = run_registered_operation(
            client,
            payload,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
            result_type=projection_type,
            request_version=1,
            result_version=1,
            timeout=120,
            secret=secret,
        )
    except CliRefusedBoundaryError as error:
        if error.context is not None and error.context.get("reason") == "REFUSED_AUTH_CERTIFICATE_SOURCE_NOT_FOUND":
            raise CliRefusedBoundaryError(
                translated_message="errors.refused.refused_auth_certificate_source_not_found",
                context=error.context,
            ) from None
        raise
    except RuntimeRefusalError as error:
        raise CliRefusedBoundaryError(context={"reason": error.reason.value}) from None
    projection = completed.projection
    resolved_effect = expected_effect(projection) if callable(expected_effect) else expected_effect
    if _certificate_receipt_invalid(completed, projection, projection_type, profile_id, resolved_effect, validate):
        raise invalid_completion_error(completed) from None
    return projection


def register_source(
    ctx: typer.Context, *, name: str, file: Path, friendly_name: str | None
) -> CertificateSourceMutationResult:
    """Preserve caller-relative path meaning before crossing into a worker cwd."""
    profile_id = _profile_id()
    absolute_file = file.expanduser().resolve(strict=False)
    projection = _run(
        ctx,
        profile_id=profile_id,
        definition_id=CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
        payload=CertificateSourceRegisterRequest(
            profile_id=profile_id, name=name, certificate_path=absolute_file, friendly_name=friendly_name
        ),
        projection_type=CertificateSourceRegisterProjection,
        expected_effect=OperationEffect.UPDATED,
        validate=lambda row: row.result.name == name.strip() and row.result.certificate_path == str(absolute_file),
    )
    return projection.result


def list_sources(ctx: typer.Context) -> CertificateSourceListResult:
    """Read the exact profile's named source inventory through its worker."""
    profile_id = _profile_id()
    projection = _run(
        ctx,
        profile_id=profile_id,
        definition_id=CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
        payload=CertificateSourceListRequest(profile_id=profile_id),
        projection_type=CertificateSourceListProjection,
        expected_effect=OperationEffect.NONE,
    )
    return projection.result


def select_source(ctx: typer.Context, *, name: str) -> CertificateSourceMutationResult:
    """Select one named source through a guarded worker operation."""
    profile_id = _profile_id()
    projection = _run(
        ctx,
        profile_id=profile_id,
        definition_id=CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
        payload=CertificateSourceSelectRequest(profile_id=profile_id, name=name),
        projection_type=CertificateSourceSelectProjection,
        expected_effect=OperationEffect.UPDATED,
        validate=lambda row: row.result.name == name.strip() and row.result.active,
    )
    return projection.result


def remove_source(ctx: typer.Context, *, name: str) -> CertificateSourceMutationResult:
    """Remove one named source and verify its recorded no-op or update."""
    profile_id = _profile_id()
    projection = _run(
        ctx,
        profile_id=profile_id,
        definition_id=CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
        payload=CertificateSourceRemoveRequest(profile_id=profile_id, name=name),
        projection_type=CertificateSourceRemoveProjection,
        expected_effect=lambda row: OperationEffect.UPDATED if row.result.removed else OperationEffect.NONE,
        validate=lambda row: row.result.name == name.strip(),
    )
    return projection.result


def check_sources(ctx: typer.Context) -> CertificateSourceCheckReport:
    """Probe named source health within the bound profile worker."""
    profile_id = _profile_id()
    projection = _run(
        ctx,
        profile_id=profile_id,
        definition_id=CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
        payload=CertificateSourceCheckRequest(profile_id=profile_id),
        projection_type=CertificateSourceCheckProjection,
        expected_effect=OperationEffect.NONE,
    )
    return projection.result


def set_source_passphrase(ctx: typer.Context, *, name: str, secret: bytearray) -> CertificateSourceSecretMutationResult:
    """Transmit only a one-shot protected frame, clearing bytes on every failure."""
    try:
        profile_id = _profile_id()
        projection = _run(
            ctx,
            profile_id=profile_id,
            definition_id=CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID,
            payload=CertificateSecretMutationRequest(profile_id=profile_id, name=name),
            projection_type=CertificateSecretMutationProjection,
            expected_effect=OperationEffect.UPDATED,
            secret=secret,
            validate=lambda row: row.result.name == name.strip() and row.result.has_secret and not row.result.removed,
        )
        return projection.result
    finally:
        secret[:] = bytes(len(secret))


def remove_source_passphrase(ctx: typer.Context, *, name: str) -> CertificateSourceSecretMutationResult:
    """Remove one named passphrase through fresh human commit authority."""
    profile_id = _profile_id()
    projection = _run(
        ctx,
        profile_id=profile_id,
        definition_id=CERTIFICATE_CREDENTIAL_REMOVE_OPERATION_DEFINITION_ID,
        payload=CertificateSecretMutationRequest(profile_id=profile_id, name=name),
        projection_type=CertificateSecretMutationProjection,
        expected_effect=lambda row: OperationEffect.UPDATED if row.result.removed else OperationEffect.NONE,
        validate=lambda row: row.result.name == name.strip() and not row.result.has_secret and not row.result.rotated,
    )
    return projection.result


__all__ = [
    "check_sources",
    "list_sources",
    "register_source",
    "remove_source",
    "remove_source_passphrase",
    "select_source",
    "set_source_passphrase",
]


def _certificate_receipt_invalid[ProjectionT: BaseModel](
    completed: RegisteredOperationCompletion[ProjectionT],
    projection: ProjectionT,
    projection_type: type[ProjectionT],
    profile_id: UUID,
    resolved_effect: OperationEffect,
    validate: Callable[[ProjectionT], bool] | None,
) -> bool:
    """Validate the exact typed certificate result before any optional content check."""
    return (
        type(projection) is not projection_type
        or cast(object, getattr(projection, "profile_id", None)) != profile_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or (completed.refusal_code is not None)
        or (completed.effect is not resolved_effect)
        or (validate is not None and (not validate(projection)))
    )
