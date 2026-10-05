"""Canonical Google folder correlation contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_refusals import google_invalid_frame


def correlate_folder_view(
    result: GoogleFolderViewProjection, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> None:
    """Correlate the folderview result to its submitted contract."""
    if result.configured is not (result.root_folder_id is not None):
        google_invalid_frame(operation_id=completed.operation_id, completed=completed)


def correlate_folder_request(
    request: BaseModel, result: BaseModel, completed: RegisteredOperationCompletion[GoogleConfigurationOutcome]
) -> bool:
    """Correlate a matching folder request without changing branch order."""
    if isinstance(request, GoogleFolderViewRequest) and isinstance(result, GoogleFolderViewProjection):
        correlate_folder_view(result, completed)
        return True
    return False
