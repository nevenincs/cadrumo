"""The Declarations projection refusals serve the terminal stored-data integrity verdict."""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.external_constants import OutputLanguage
from ....core.operator_action_enums import NoRecoveryOutcome
from ...cli_exception_preconditions import CliExceptionPrecondition, nested_terminal_precondition_verdict
from ...operations.next_step import error_next_step
from ..declarations_calendar import DeclarationsCalendarProjectionError
from ..declarations_workspace_contracts import DeclarationsWorkspaceProjectionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("error_type", "code", "record"),
    [
        (
            DeclarationsCalendarProjectionError,
            "INTEGRITY_DECLARATIONS_CALENDAR_PROJECTION",
            "declarations_calendar_projection",
        ),
        (
            DeclarationsWorkspaceProjectionError,
            "INTEGRITY_DECLARATIONS_WORKSPACE_PROJECTION",
            "declarations_workspace_projection",
        ),
    ],
)
def test_projection_refusal_is_a_terminal_integrity_fault_without_an_invented_step(
    error_type: type[DeclarationsCalendarProjectionError | DeclarationsWorkspaceProjectionError],
    code: str,
    record: str,
) -> None:
    refusal = error_type("authorities disagree")

    registered = get_registered_error_code(refusal)
    assert (registered.code, registered.category) == (code, ErrorCategory.INTEGRITY)
    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert verdict.failed_condition_id == CliExceptionPrecondition.STORED_DATA_VALID.value
    assert verdict.action is None
    assert {(value, fact) for item in verdict.evidence for value, fact in item.values.items()} == {
        ("record", record),
        ("valid", False),
    }
    assert error_next_step(refusal, OutputLanguage.EN) is None
