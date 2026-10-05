"""Canonical Google session correlation contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_refusals import google_invalid_frame


def correlate_probe(
    request: GoogleProbeRequest,
    result: GoogleProbeProjection,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
) -> None:
    """Correlate the probe result to its submitted contract."""
    if result.read_only is not request.read_only or result.provider_kind != "google_drive":
        google_invalid_frame(operation_id=completed.operation_id, completed=completed)


def correlate_session_request(
    request: BaseModel, result: BaseModel, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> bool:
    """Correlate a matching session request without changing branch order."""
    if isinstance(request, GoogleLoginRequest) and isinstance(result, GoogleLoginProjection):
        # A sign-in result names the account and scopes; neither is derivable from the request.
        return True
    elif isinstance(request, GoogleProbeRequest) and isinstance(result, GoogleProbeProjection):
        correlate_probe(request, result, completed)
        return True
    elif isinstance(request, GoogleLogoutRequest) and isinstance(result, GoogleLogoutProjection):
        # Logout carries two independent removal flags that the receipt's effect already binds.
        return True
    return False
