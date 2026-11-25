"""A fault in the application's own export design is a terminal integrity refusal, worded in every locale.

The sites are reached through the real renderer functions. The export boundary
must keep the served words and the terminal door instead of the generic
"could not write the file" sentence, and the refusal must stay catchable as the
export validation failure it was before.
"""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.export_layout_format import ExportLayoutFormat
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition
from ....domain.filing.errors import (
    FilingExportDesignIntegrityError,
    FilingExportError,
    FilingExportIntegrityError,
    FilingExportValidationError,
)
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.export import export_layout_not_renderable_error
from ...filing.record_field_renderer import binding_field_value
from ..export import export_write_failure
from ..export_contracts import ModeloExportCommand, ModeloExportDesignIntegrityError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIELD_ID = "probe-record.dp-probe.f001"
_LOCALES = ("es", "ca", "en", "hu")


def _field_without_binding() -> ExportFieldDefinition:
    # The validated model refuses to be built this way, which is the point: the
    # renderer's own guard is what remains if a layout ever reaches it unchecked.
    return ExportFieldDefinition.model_construct(id=_FIELD_ID, kind="binding", binding=None)


def _design_refusal() -> FilingExportDesignIntegrityError:
    with pytest.raises(FilingExportDesignIntegrityError) as refused:
        binding_field_value(_field_without_binding(), {}, None)
    return refused.value


def _unclassified_layout_refusal() -> FilingExportIntegrityError:
    layout = ExportLayoutDefinition.model_construct(
        id="probe-layout", format=ExportLayoutFormat.FIXED_WIDTH, records=("probe-record",), dictionary_source_ref=None
    )
    with pytest.raises(FilingExportIntegrityError) as refused:
        raise export_layout_not_renderable_error("303", layout)
    return refused.value


def test_a_layout_field_without_its_binding_refuses_as_an_integrity_defect_with_a_terminal_door() -> None:
    refusal = _design_refusal()

    assert isinstance(refusal, FilingExportValidationError)
    assert refusal.context == {"field": _FIELD_ID}
    registered = get_registered_error_code(refusal)
    assert (registered.code, registered.category) == ("INTEGRITY_FILING_EXPORT_DESIGN", ErrorCategory.INTEGRITY)
    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_layout_with_no_reason_code_refuses_as_an_integrity_defect_that_is_not_a_validation_failure() -> None:
    refusal = _unclassified_layout_refusal()

    assert isinstance(refusal, FilingExportError)
    assert not isinstance(refusal, FilingExportValidationError)
    assert get_registered_error_code(refusal).code == "INTEGRITY_FILING_EXPORT"
    verdict = nested_terminal_precondition_verdict(refusal)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_export_boundary_keeps_the_served_words_and_the_terminal_door(locale: str) -> None:
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    failure = export_write_failure(command, _design_refusal())

    assert isinstance(failure, ModeloExportDesignIntegrityError)
    assert get_registered_error_code(failure).code == "INTEGRITY_MODELO_EXPORT_DESIGN"
    message = resolve_error_message(failure, locale=locale)
    assert _FIELD_ID in message
    assert "%{" not in message
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_base_export_integrity_refusal_names_the_modelo_in_every_locale(locale: str) -> None:
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    failure = export_write_failure(command, _unclassified_layout_refusal())

    assert isinstance(failure, ModeloExportDesignIntegrityError)
    message = resolve_error_message(failure, locale=locale)
    assert "303" in message
    assert "%{" not in message
