"""Canonical Google source correlation contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
    GoogleCredentialSourceSetProjection,
    GoogleCredentialSourceSetRequest,
    GoogleCredentialSourceViewProjection,
    GoogleCredentialSourceViewRequest,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
)
from ....core.google_credential_source import GoogleCredentialSourceKind
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_refusals import google_invalid_frame


def source_optional_fields_match(
    request: GoogleCredentialSourceSetRequest, result: GoogleCredentialSourceSetProjection, fields_match: bool
) -> bool:
    """Source optional fields match."""
    if request.scopes:
        fields_match = fields_match and result.target_scopes == request.scopes
    if request.delegates:
        fields_match = fields_match and result.delegates == request.delegates
    if request.subject is not None:
        fields_match = fields_match and result.subject == request.subject
    if request.lifetime_seconds is not None:
        fields_match = fields_match and result.lifetime_s == request.lifetime_seconds
    return fields_match


def correlate_credential_source_set(
    request: GoogleCredentialSourceSetRequest,
    result: GoogleCredentialSourceSetProjection,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
) -> None:
    """Correlate the credentialsourceset result to its submitted contract."""
    fields_match = result.kind is request.kind
    if request.target_principal is not None:
        fields_match = fields_match and result.target_principal == request.target_principal.strip()
    fields_match = source_optional_fields_match(request, result, fields_match)
    if not fields_match:
        google_invalid_frame(operation_id=completed.operation_id, completed=completed)


def correlate_credential_source_view(
    result: GoogleCredentialSourceViewProjection, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> None:
    """Correlate the credentialsourceview result to its submitted contract."""
    if not result.configured and (
        result.kind is not GoogleCredentialSourceKind.OAUTH_DESKTOP
        or result.target_principal is not None
        or result.target_scopes
        or result.delegates
        or result.subject is not None
        or result.lifetime_s is not None
    ):
        google_invalid_frame(operation_id=completed.operation_id, completed=completed)


def correlate_register(
    result: GoogleRegisterProjection, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> None:
    """Correlate the register result to its submitted contract."""
    if not result.client_id or not result.project_id:
        google_invalid_frame(operation_id=completed.operation_id, completed=completed)


def correlate_source_request(
    request: BaseModel, result: BaseModel, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> bool:
    """Correlate a matching source request without changing branch order."""
    if isinstance(request, GoogleCredentialSourceSetRequest) and isinstance(
        result, GoogleCredentialSourceSetProjection
    ):
        correlate_credential_source_set(request, result, completed)
        return True
    elif isinstance(request, GoogleCredentialSourceViewRequest) and isinstance(
        result, GoogleCredentialSourceViewProjection
    ):
        correlate_credential_source_view(result, completed)
        return True
    elif isinstance(request, GoogleRegisterRequest) and isinstance(result, GoogleRegisterProjection):
        correlate_register(result, completed)
        return True
    return False
