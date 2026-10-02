"""Exact-profile registered worker bridge for human Google configuration leaves."""

from __future__ import annotations

from pathlib import Path
from typing import Never, cast

import typer
from pydantic import BaseModel, ValidationError

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.outbound.google.errors import GoogleAuthError, GoogleAuthValidationError
from ....adapters.outbound.google.google_configuration_refusal import google_configuration_refusal_error
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID,
    GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID,
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleConfigurationOutcome,
    GoogleCredentialSourceSetProjection,
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewProjection,
    GoogleCredentialSourceViewRequest,
    GoogleFolderSetProjection,
    GoogleFolderSetRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from ....application.user_profile.google_configuration_operation_refusal import (
    GOOGLE_CONFIGURATION_REFUSAL_CODE,
    GoogleConfigurationRefusalProjection,
)
from ....core.google_credential_source import GoogleCredentialSourceKind
from ....core.hashing import sha256_hex
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)
from .google_errors import google_refusal

_GOOGLE_CLIENT_SECRET_MAX_BYTES = 65_536
_REQUEST_OPERATIONS: dict[type[BaseModel], tuple[str, type[BaseModel]]] = {
    GoogleCredentialSourceSetRequest: (
        GOOGLE_CREDENTIAL_SOURCE_SET_OPERATION_DEFINITION_ID,
        GoogleCredentialSourceSetProjection,
    ),
    GoogleCredentialSourceViewRequest: (
        GOOGLE_CREDENTIAL_SOURCE_VIEW_OPERATION_DEFINITION_ID,
        GoogleCredentialSourceViewProjection,
    ),
    GoogleFolderSetRequest: (GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID, GoogleFolderSetProjection),
    GoogleFolderViewRequest: (GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID, GoogleFolderViewProjection),
    GoogleLoginRequest: (GOOGLE_LOGIN_OPERATION_DEFINITION_ID, GoogleLoginProjection),
    GoogleLogoutRequest: (GOOGLE_LOGOUT_OPERATION_DEFINITION_ID, GoogleLogoutProjection),
    GoogleProbeRequest: (GOOGLE_PROBE_OPERATION_DEFINITION_ID, GoogleProbeProjection),
    GoogleRegisterRequest: (GOOGLE_REGISTER_OPERATION_DEFINITION_ID, GoogleRegisterProjection),
    GoogleStatusRequest: (GOOGLE_STATUS_OPERATION_DEFINITION_ID, GoogleStatusProjection),
}


def run_google_register(ctx: typer.Context, source_path: Path) -> GoogleRegisterProjection:
    """Submit client JSON as one protected secret, with only path and digest public."""
    client = bound_profile_client(ctx)
    source = source_path.absolute()
    secret = bytearray(_GOOGLE_CLIENT_SECRET_MAX_BYTES + 1)
    try:
        with source.open("rb") as stream:
            byte_count = stream.readinto(secret)
    except OSError as error:
        _wipe(secret)
        raise google_refusal(
            GoogleAuthValidationError(
                translated_message="cli.config.google.detail.client_json_unreadable",
                context={"path": str(source), "error_type": type(error).__name__},
            ),
        ) from None
    if byte_count > _GOOGLE_CLIENT_SECRET_MAX_BYTES:
        _wipe(secret)
        raise google_refusal(
            GoogleAuthValidationError(
                translated_message="cli.config.google.detail.client_json_schema_invalid",
                context={"path": str(source), "error_type": "ValidationError"},
            ),
        ) from None
    del secret[byte_count:]
    if not secret:
        _wipe(secret)
        raise google_refusal(
            GoogleAuthValidationError(
                translated_message="cli.config.google.detail.client_json_invalid",
                context={"path": str(source), "error_type": "JSONDecodeError"},
            ),
        ) from None
    try:
        request = GoogleRegisterRequest(
            profile_id=client.profile_id,
            client_json_path=str(source),
            client_json_sha256=sha256_hex(bytes(secret)),
        )
    except ValidationError:
        _wipe(secret)
        raise submitted_operation_error(
            GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=None,
            effect=None,
        ) from None
    try:
        projection = run_google_configuration(ctx, request, result_type=GoogleRegisterProjection, secret=secret)
    finally:
        _wipe(secret)
    if type(projection) is not GoogleRegisterProjection:
        raise CliRefusedBoundaryError(RuntimeRefusalCode.INVALID_FRAME.value)
    return projection


def run_google_configuration[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    result_type: type[ProjectionT],
    secret: bytearray | None = None,
) -> ProjectionT:
    """Run one typed request and correlate its complete projection to the actual receipt."""
    client = bound_profile_client(ctx)
    request_contract = _REQUEST_OPERATIONS.get(type(request))
    if (
        request_contract is None
        or request_contract[1] is not result_type
        or getattr(request, "profile_id", None) != client.profile_id
    ):
        _invalid(operation_id="config.google.invalid")
    definition_id, expected_projection_type = request_contract
    if (definition_id == GOOGLE_REGISTER_OPERATION_DEFINITION_ID) is not (secret is not None):
        _invalid(operation_id=definition_id)
    if secret is not None and type(secret) is not bytearray:
        _invalid(operation_id=definition_id)

    if isinstance(request, GoogleLoginRequest) and not request.refresh_only:
        from .runtime_google_consent import login_google_with_runtime

        try:
            completed = login_google_with_runtime(client, request, timeout=420)
        except GoogleAuthError as error:
            raise google_refusal(error) from None
    else:
        completed = run_registered_operation(
            client,
            request,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=GoogleConfigurationOutcome,
            request_version=1,
            result_version=1,
            timeout=120,
            allow_refusal_detail=True,
            secret=secret,
        )
    _correlate_completion(
        client,
        request,
        completed,
        definition_id=definition_id,
        expected_projection_type=expected_projection_type,
    )
    outcome = completed.projection
    if outcome.outcome == "refused":
        refusal = outcome.refusal
        if refusal is None:
            _invalid(operation_id=definition_id, completed=completed)
        if not isinstance(refusal, GoogleConfigurationRefusalProjection):
            _invalid(operation_id=definition_id, completed=completed)
        raise google_configuration_refusal_error(
            refusal,
            operation_id=completed.operation_id,
            effect=completed.effect,
            terminal_condition=completed.terminal_condition,
            refusal_code=completed.refusal_code or "",
        ) from None
    result = outcome.result
    if result is None or type(result) is not expected_projection_type:
        _invalid(operation_id=definition_id, completed=completed)
    return cast("ProjectionT", result)


def _correlate_completion(
    client: RuntimeFrontendClient,
    request: BaseModel,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
    *,
    definition_id: str,
    expected_projection_type: type[BaseModel],
) -> None:
    """Require exact profile, request class, registered operation, and truthful effect."""
    outcome = completed.projection
    if (
        completed.terminal_condition not in {OperationTerminalCondition.SUCCEEDED, OperationTerminalCondition.REFUSED}
        or outcome.profile_id != client.profile_id
        or client.frontend is not OperationFrontendProjection.CLI
    ):
        _invalid(operation_id=definition_id, completed=completed)
    if outcome.outcome == "refused":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != GOOGLE_CONFIGURATION_REFUSAL_CODE
            or outcome.result is not None
            or outcome.refusal is None
            or outcome.refusal.profile_id != client.profile_id
            or completed.effect not in {OperationEffect.NONE, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
        ):
            _invalid(operation_id=definition_id, completed=completed)
        return
    result = outcome.result
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or outcome.refusal is not None
        or result is None
        or type(result) is not expected_projection_type
        or result.profile_id != client.profile_id
        or completed.effect not in _success_effects(request, result)
    ):
        _invalid(operation_id=definition_id, completed=completed)
    _correlate_request(request, result, client, completed)


def _success_effects(request: BaseModel, result: BaseModel) -> frozenset[OperationEffect]:
    if isinstance(request, (GoogleCredentialSourceSetRequest, GoogleFolderSetRequest, GoogleRegisterRequest)):
        return frozenset({OperationEffect.UPDATED})
    if isinstance(request, (GoogleCredentialSourceViewRequest, GoogleFolderViewRequest, GoogleStatusRequest)):
        return frozenset({OperationEffect.NONE})
    if isinstance(request, GoogleLoginRequest):
        return frozenset({OperationEffect.NONE if request.refresh_only else OperationEffect.UPDATED})
    if isinstance(request, GoogleLogoutRequest) and isinstance(result, GoogleLogoutProjection):
        return frozenset(
            {OperationEffect.UPDATED if result.token_removed or result.metadata_removed else OperationEffect.NONE}
        )
    if isinstance(request, GoogleProbeRequest) and isinstance(result, GoogleProbeProjection):
        return frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN})
    return frozenset[OperationEffect]()


def _correlate_request(
    request: BaseModel,
    result: BaseModel,
    client: RuntimeFrontendClient,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
) -> None:
    if isinstance(request, GoogleCredentialSourceSetRequest) and isinstance(
        result, GoogleCredentialSourceSetProjection
    ):
        fields_match = result.kind is request.kind
        if request.target_principal is not None:
            fields_match = fields_match and result.target_principal == request.target_principal.strip()
        if request.scopes:
            fields_match = fields_match and result.target_scopes == request.scopes
        if request.delegates:
            fields_match = fields_match and result.delegates == request.delegates
        if request.subject is not None:
            fields_match = fields_match and result.subject == request.subject
        if request.lifetime_seconds is not None:
            fields_match = fields_match and result.lifetime_s == request.lifetime_seconds
        if not fields_match:
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleCredentialSourceViewRequest) and isinstance(
        result, GoogleCredentialSourceViewProjection
    ):
        if not result.configured and (
            result.kind is not GoogleCredentialSourceKind.OAUTH_DESKTOP
            or result.target_principal is not None
            or result.target_scopes
            or result.delegates
            or result.subject is not None
            or result.lifetime_s is not None
        ):
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleFolderSetRequest) and isinstance(result, GoogleFolderSetProjection):
        if result.root_folder_id != request.folder_id.strip():
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleFolderViewRequest) and isinstance(result, GoogleFolderViewProjection):
        if result.configured is not (result.root_folder_id is not None):
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleLoginRequest) and isinstance(result, GoogleLoginProjection):
        expected_mode = "refresh-only" if request.refresh_only else "consent"
        if result.mode != expected_mode:
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleProbeRequest) and isinstance(result, GoogleProbeProjection):
        if result.read_only is not request.read_only or result.provider_kind != "google_drive":
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleLogoutRequest) and isinstance(result, GoogleLogoutProjection):
        if result.client_preserved is not True:
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleRegisterRequest) and isinstance(result, GoogleRegisterProjection):
        if not result.client_id or not result.project_id:
            _invalid(operation_id=completed.operation_id, completed=completed)
    elif isinstance(request, GoogleStatusRequest) and isinstance(result, GoogleStatusProjection):
        session_details_present = all(
            value is not None
            for value in (result.account_email, result.issued_at, result.last_refresh_at, result.reauth_required)
        )
        session_details_absent = (
            all(
                value is None
                for value in (result.account_email, result.issued_at, result.last_refresh_at, result.reauth_required)
            )
            and not result.granted_scopes
        )
        client_details_match = (result.client_registered and bool(result.client_id)) or (
            not result.client_registered and result.client_id is None
        )
        if not client_details_match or not (
            (result.session_present and session_details_present)
            or (not result.session_present and session_details_absent)
        ):
            _invalid(operation_id=completed.operation_id, completed=completed)


def _invalid(
    *,
    operation_id: str,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome] | None = None,
) -> Never:
    if completed is None:
        raise submitted_operation_error(
            operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=None,
            effect=None,
        )
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _wipe(secret: bytearray) -> None:
    secret[:] = bytes(len(secret))


__all__ = ["run_google_configuration", "run_google_register"]
