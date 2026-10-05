"""Canonical Google status correlation contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
    GoogleStatusProjection,
    GoogleStatusRequest,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_refusals import google_invalid_frame


def status_session_details(result: GoogleStatusProjection) -> tuple[bool, bool]:
    """Status session details."""
    session_details_present = all(value is not None for value in (result.account_email, result.issued_at))
    session_details_absent = (
        all(value is None for value in (result.account_email, result.issued_at)) and not result.granted_scopes
    )
    return session_details_present, session_details_absent


def correlate_status(
    result: GoogleStatusProjection, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> None:
    """Correlate the status result to its submitted contract."""
    session_details_present, session_details_absent = status_session_details(result)
    if not (
        (result.session_present and session_details_present) or (not result.session_present and session_details_absent)
    ):
        google_invalid_frame(operation_id=completed.operation_id, completed=completed)


def correlate_status_request(
    request: BaseModel, result: BaseModel, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> bool:
    """Correlate a matching status request without changing branch order."""
    if isinstance(request, GoogleStatusRequest) and isinstance(result, GoogleStatusProjection):
        correlate_status(result, completed)
        return True
    return False
