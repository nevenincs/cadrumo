"""Refusals that state a fault in stored or computed data serve the terminal integrity verdict.

The workspace projection ports and the persisted row provenance are written by
the application itself, and a filing record's cross-field invariants are ones
its builder never violates, so no operator input at the refusal corrects them.
The verdict is read through the same readers the operation boundary uses.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.external_constants import OutputLanguage
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.filing.errors import FilingValidationError
from ....domain.filing.schema import ModeloValue, ModeloValueKind
from ...cli_exception_preconditions import CliExceptionPrecondition, nested_terminal_precondition_verdict
from ...operations.next_step import error_next_step
from ..workspace import ModeloWorkspaceAbsentReadinessProjectionError, ModeloWorkspaceAbsentRegistryProjectionError
from ..workspace_graded import ModeloWorkspaceMaterializationProvenanceMissingError, _require_graded_readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _record_of(error: BaseException) -> str:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert verdict.failed_condition_id == CliExceptionPrecondition.STORED_DATA_VALID.value
    assert verdict.action is None
    facts = {(value, fact) for item in verdict.evidence for value, fact in item.values.items()}
    assert ("valid", False) in facts
    (record,) = (fact for value, fact in facts if value == "record")
    assert isinstance(record, str)
    return record


@pytest.mark.parametrize(
    ("error_type", "record"),
    [
        (ModeloWorkspaceAbsentRegistryProjectionError, "workspace_registry_projection"),
        (ModeloWorkspaceAbsentReadinessProjectionError, "workspace_readiness_projection"),
        (ModeloWorkspaceMaterializationProvenanceMissingError, "calculation_revision_row_provenance"),
    ],
)
def test_a_workspace_integrity_class_is_a_terminal_fault_without_an_invented_step(
    error_type: type[
        ModeloWorkspaceAbsentRegistryProjectionError
        | ModeloWorkspaceAbsentReadinessProjectionError
        | ModeloWorkspaceMaterializationProvenanceMissingError
    ],
    record: str,
) -> None:
    refusal = error_type("the port answered without its projection")

    assert get_registered_error_code(refusal).category is ErrorCategory.INTEGRITY
    assert _record_of(refusal) == record
    assert error_next_step(refusal, OutputLanguage.EN) is None


def test_a_missing_readiness_report_raised_by_the_graded_reader_is_terminal() -> None:
    with pytest.raises(ModeloWorkspaceAbsentReadinessProjectionError) as refused:
        _require_graded_readiness(())

    assert _record_of(refused.value) == "workspace_readiness_projection"


def test_a_filing_record_that_contradicts_itself_is_a_terminal_fault_through_pydantic() -> None:
    with pytest.raises(ValidationError) as refused:
        ModeloValue(casilla_id="03", value=Decimal("1"), kind=ModeloValueKind.EMPTY, source="registry schema")

    assert _record_of(refused.value) == "filing_draft"


def test_a_filing_validation_error_raised_directly_is_terminal() -> None:
    refusal = FilingValidationError("draft values claim a casilla more than once: '03'")

    assert get_registered_error_code(refusal).category is ErrorCategory.INTEGRITY
    assert _record_of(refusal) == "filing_draft"
    assert error_next_step(refusal, OutputLanguage.EN) is None
