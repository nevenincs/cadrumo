"""A Modelo validation that guards a record Cadrumo built or stored refuses with a terminal verdict naming it."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import get_registered_error_code
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import open_ended_revision
from ....domain.filing.errors import FilingValidationError
from ....domain.modelos.errors import ModeloValidatedRecord, ModeloValidationError
from ....domain.modelos.filing_record import IvaCreditSnapshot
from ....domain.modelos.participation_index import derive_participation_index_id
from ....domain.modelos.work_unit import derive_work_unit_id
from ...cli_exception_preconditions import CliExceptionPrecondition, nested_terminal_precondition_verdict
from ..verification_required_fields import missing_required_casilla_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION = open_ended_revision("303")
_YEAR = _REVISION.valid_from.year


def _registered(error: BaseException) -> ModeloValidationError:
    """Return the registered refusal a real validator raised, through Pydantic's wrapping when present."""
    if isinstance(error, ValidationError):
        cause = error.errors()[0]["ctx"]["error"]
        assert isinstance(cause, ValueError)
        registered = cause.__cause__
        assert isinstance(registered, ModeloValidationError)
        return registered
    assert isinstance(error, ModeloValidationError)
    return error


def _credit_snapshot_applied_beyond_its_credit() -> BaseException:
    with pytest.raises(ValidationError) as refused:
        IvaCreditSnapshot(
            opening_amount=Decimal("0"),
            generated_amount=Decimal("0"),
            applied_amount=Decimal("1"),
            remaining_amount=Decimal("0"),
        )
    return refused.value


def _work_unit_id_across_two_years() -> BaseException:
    with pytest.raises(ModeloValidationError) as refused:
        derive_work_unit_id(
            bucket_id="bucket",
            modelo="303",
            filing_year=_YEAR + 1,
            period=Period.from_year_and_code(_YEAR, "1T"),
            revision_id=_REVISION.id,
        )
    return refused.value


def _blank_participation_transaction() -> BaseException:
    with pytest.raises(ModeloValidationError) as refused:
        derive_participation_index_id("   ")
    return refused.value


def _finding_without_casilla_provenance() -> BaseException:
    with pytest.raises(ModeloValidationError) as refused:
        missing_required_casilla_finding("0001")
    return refused.value


@pytest.mark.parametrize(
    ("refuse", "record"),
    [
        (_credit_snapshot_applied_beyond_its_credit, ModeloValidatedRecord.FILING_RECORD),
        (_work_unit_id_across_two_years, ModeloValidatedRecord.WORK_UNIT),
        (_blank_participation_transaction, ModeloValidatedRecord.PARTICIPATION_INDEX),
        (_finding_without_casilla_provenance, ModeloValidatedRecord.REGISTRY_DECLARATION),
    ],
    ids=["filing_record", "work_unit", "participation_index", "registry_declaration"],
)
def test_a_broken_record_invariant_is_terminal_and_names_the_record(
    refuse: Callable[[], BaseException], record: ModeloValidatedRecord
) -> None:
    raised = refuse()
    refusal = _registered(raised)

    verdict = nested_terminal_precondition_verdict(raised)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert verdict.failed_condition_id == CliExceptionPrecondition.STORED_DATA_VALID.value
    assert verdict.evidence[0].values == {"record": record.value, "valid": False}
    assert get_registered_error_code(refusal).code == "ERROR_MODELOS_VALIDATION"


def test_a_validation_that_states_no_outcome_carries_no_door() -> None:
    assert nested_terminal_precondition_verdict(ModeloValidationError("unclassified")) is None


def test_a_terminal_record_refusal_defers_to_the_verdict_of_its_cause() -> None:
    cause = FilingValidationError("draft broken")
    refusal = ModeloValidationError(
        "fact did not resolve",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
        record=ModeloValidatedRecord.REGISTRY_DECLARATION,
    )
    refusal.__cause__ = cause

    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict == nested_terminal_precondition_verdict(cause)
    assert verdict.evidence[0].values == {"record": "filing_draft", "valid": False}
