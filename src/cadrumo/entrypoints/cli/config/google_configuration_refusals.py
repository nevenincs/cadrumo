"""Canonical Google refusals contracts."""

from __future__ import annotations

from typing import Never

from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.user_profile.google_configuration_operation_contracts import (
    GoogleConfigurationOutcome,
)
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_errors import invalid_completion_error, submitted_operation_error


def google_invalid_frame(
    *,
    operation_id: str,
    completed: RegisteredOperationCompletion[GoogleConfigurationOutcome] | None = None,
) -> Never:
    """Refuse an invalid frame using its actual receipt when submission occurred."""
    if completed is None:
        raise submitted_operation_error(
            operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=None,
            effect=None,
        )
    raise invalid_completion_error(completed)
