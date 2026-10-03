"""Canonical Google request correlation contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_folder_correlation import correlate_folder_request
from .google_configuration_session_correlation import correlate_session_request
from .google_configuration_source_correlation import correlate_source_request
from .google_configuration_status_correlation import correlate_status_request


def correlate_google_request(
    request: BaseModel,
    result: BaseModel,
    client: RuntimeFrontendClient,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
) -> None:
    """Correlate each admitted request to the corresponding bounded result."""
    if correlate_source_request(request, result, completed):
        return
    if correlate_folder_request(request, result, completed):
        return
    if correlate_session_request(request, result, completed):
        return
    correlate_status_request(request, result, completed)
