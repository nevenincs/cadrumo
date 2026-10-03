"""Canonical Google projection contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....adapters.outbound.google.google_configuration_refusal import google_configuration_refusal_error
from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
)
from ....application.user_profile.google_configuration_operation_refusal import (
    GoogleConfigurationRefusalProjection,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from .google_configuration_refusals import google_invalid_frame


def google_success_projection(
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome],
    definition_id: str,
    expected_projection_type: type[BaseModel],
) -> BaseModel:
    """Google success projection."""
    outcome = completed.projection
    if outcome.outcome == "refused":
        refusal = outcome.refusal
        if refusal is None:
            google_invalid_frame(operation_id=definition_id, completed=completed)
        if not isinstance(refusal, GoogleConfigurationRefusalProjection):
            google_invalid_frame(operation_id=definition_id, completed=completed)
        raise google_configuration_refusal_error(
            refusal,
            operation_id=completed.operation_id,
            effect=completed.effect,
            terminal_condition=completed.terminal_condition,
            refusal_code=completed.refusal_code or "",
        ) from None
    result = outcome.result
    if result is None or type(result) is not expected_projection_type:
        google_invalid_frame(operation_id=definition_id, completed=completed)
    return result
