"""Canonical Google client registration correlation contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_refusals import google_invalid_frame


def correlate_register(
    result: GoogleRegisterProjection, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> None:
    """Correlate the register result to its submitted contract."""
    if not result.client_id or not result.project_id:
        google_invalid_frame(operation_id=completed.operation_id, completed=completed)


def correlate_source_request(
    request: BaseModel, result: BaseModel, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> bool:
    """Correlate a matching client-source request without changing branch order."""
    if isinstance(request, GoogleRegisterRequest) and isinstance(result, GoogleRegisterProjection):
        correlate_register(result, completed)
        return True
    return False
