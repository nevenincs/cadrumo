"""Each export refusal names whose fault it is: the filer's value or decision, or a design fault.

Every refusal is raised by the real export code and read through the reader the
operation error detail uses.
"""

from __future__ import annotations

import pytest

from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ....domain.filing.errors import (
    FilingExportError,
    FilingExportRequiredRecordAbsentError,
    FilingExportValidationError,
    FilingExportValueOverflowError,
)
from ....domain.filing.software_identity import aeat_aux_version
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..export import _validate_envelope_identity_option
from ..export_refusal_doors import ExportRefusalReason, export_design_terminal, export_input_decision
from ..export_xml_dictionary_values import format_xml_dictionary_value
from ..record_field_renderer import format_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _outcome(error: BaseException) -> NoRecoveryOutcome | None:
    verdict = nested_terminal_precondition_verdict(error)
    assert isinstance(verdict, PreconditionVerdict)
    return verdict.no_recovery_outcome


def test_a_value_the_filer_stated_in_an_unreadable_form_is_the_filers_decision() -> None:
    with pytest.raises(FilingExportValidationError) as raised:
        format_xml_dictionary_value("P102", "abc")

    assert _outcome(raised.value) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_caller_option_the_layout_does_not_admit_is_terminal() -> None:
    with pytest.raises(FilingExportValidationError) as raised:
        _validate_envelope_identity_option(True, None)

    assert _outcome(raised.value) is NoRecoveryOutcome.TERMINAL


def test_a_value_wider_than_its_slot_is_the_filers_decision_and_keeps_the_door_in_its_record() -> None:
    field = ExportFieldDefinition(
        id="synthetic-field",
        offset=1,
        length=2,
        kind="casilla",
        casilla_id="synthetic-casilla",
        data_type=CasillaDataType.INTEGER,
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=("legal-ref",),
        source_refs=("source-ref",),
    )

    with pytest.raises(FilingExportValueOverflowError) as raised:
        format_field(field, 100000)

    assert _outcome(raised.value) is NoRecoveryOutcome.OPERATOR_DECISION
    assert _outcome(raised.value.in_record("synthetic-record")) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_required_record_with_no_occurrence_carries_the_door_it_was_given() -> None:
    error = FilingExportRequiredRecordAbsentError(
        export_record_id="synthetic-record",
        precondition_verdict=export_input_decision(ExportRefusalReason.REQUIRED_RECORD_ABSENT),
    )

    assert _outcome(error) is NoRecoveryOutcome.OPERATOR_DECISION


def test_an_export_refusal_without_a_door_reads_as_none() -> None:
    assert nested_terminal_precondition_verdict(FilingExportError("x")) is None


def test_a_design_fault_is_terminal_and_a_filer_input_is_a_decision() -> None:
    reason = ExportRefusalReason.RECORD_INCOMPLETE

    assert export_design_terminal(reason).no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert export_input_decision(reason).no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_package_version_without_an_aux_wire_form_is_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....domain.filing import software_identity

    monkeypatch.setattr(software_identity, "PACKAGE_VERSION", "not-a-release")

    with pytest.raises(FilingExportValidationError) as raised:
        aeat_aux_version()

    assert _outcome(raised.value) is NoRecoveryOutcome.TERMINAL
