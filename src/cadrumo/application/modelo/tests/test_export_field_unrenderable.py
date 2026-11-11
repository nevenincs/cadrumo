"""A value the record design cannot render refuses the export as a design defect, naming the field.

The integer slot given a fractional amount is rendered through the real codec;
the refusal must name the field and casilla, say nothing was written, and carry
a terminal no-recovery verdict because no filer action repairs the design.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ....domain.filing.errors import FilingExportFieldUnrenderableError
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.record_field_renderer import format_field
from ..export import export_write_failure
from ..export_contracts import ModeloExportCommand, ModeloExportFieldUnrenderableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIELD_ID = "probe-record.dp-probe.f032"
_CASILLA_ID = "32"


def _integer_field(casilla_id: str | None) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=_FIELD_ID,
        offset=1,
        length=5,
        kind="casilla" if casilla_id is not None else "binding",
        casilla_id=casilla_id,
        binding=None if casilla_id is not None else "probe-binding",
        data_type=CasillaDataType.INTEGER,
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=("orden-eha-3786-2008:art-1",),
        source_refs=("aeat-dr-303-2025",),
    )


def test_a_fractional_value_in_an_integer_slot_is_a_typed_terminal_refusal() -> None:
    field = _integer_field(_CASILLA_ID)

    with pytest.raises(FilingExportFieldUnrenderableError) as refused:
        format_field(field, Decimal("1.5"))

    error = refused.value
    assert (error.field_id, error.casilla_id, error.data_type) == (_FIELD_ID, _CASILLA_ID, "integer")
    assert "fractional" in error.reason
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


@pytest.mark.parametrize("locale", ["es", "ca", "en", "hu"])
def test_the_export_maps_it_to_an_integrity_refusal_naming_field_and_casilla(locale: str) -> None:
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")
    with pytest.raises(FilingExportFieldUnrenderableError) as refused:
        format_field(_integer_field(_CASILLA_ID), Decimal("1.5"))

    failure = export_write_failure(command, refused.value)

    assert isinstance(failure, ModeloExportFieldUnrenderableError)
    registered = get_registered_error_code(failure)
    assert (registered.code, registered.category) == (
        "INTEGRITY_MODELO_EXPORT_FIELD_UNRENDERABLE",
        ErrorCategory.INTEGRITY,
    )
    message = resolve_error_message(failure, locale=locale)
    assert _FIELD_ID in message
    assert f"{_CASILLA_ID}" in message
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_field_without_a_casilla_is_named_by_its_field_alone() -> None:
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")
    with pytest.raises(FilingExportFieldUnrenderableError) as refused:
        format_field(_integer_field(None), Decimal("1.5"))
    assert refused.value.casilla_id is None

    failure = export_write_failure(command, refused.value)

    assert isinstance(failure, ModeloExportFieldUnrenderableError)
    message = resolve_error_message(failure, locale="en")
    assert _FIELD_ID in message
    assert "casilla" not in message
