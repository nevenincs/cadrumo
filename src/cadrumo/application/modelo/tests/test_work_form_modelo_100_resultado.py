"""The form serves box 0700 of the 2025 Modelo 100 as a calculated result, never as an optional value left at zero."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_input_kind import InputKind
from ..work_form_field_vocabulary import (
    ModeloFormEditability,
    ModeloFormOrigin,
)
from ..work_review import build_modelo_work_review_casillas
from .work_form_fixture import built_form, form_casilla, form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BOX = "0700"


def _typed_boxes(operation: PinnedAuthorityOperation) -> set[str]:
    snapshot = form_snapshot(operation, "100", 2025, "0A")
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    return {
        str(row.casilla_id) for row in rows if row.declared_input_kind is InputKind.MANUAL and not row.absent_by_design
    }


def test_the_box_is_no_typed_value_for_the_calculation_to_hold_at_zero(operation: PinnedAuthorityOperation) -> None:
    typed = _typed_boxes(operation)

    assert _BOX not in typed
    assert {"0693", "0694"} <= typed


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_before_any_calculation_the_box_waits_for_the_calculation(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    field = form_casilla(built_form(operation, "100", 2025, "0A", language=language), _BOX)

    assert field.editability is ModeloFormEditability.CALCULATED
    assert field.origin is ModeloFormOrigin.NOT_CALCULATED_YET
    assert field.formula_id == "renta-resultado-ingresar-o-devolver"
    assert sorted(field.formula_operands) == ["0670", "0693", "0694", "0695"]
    assert not field.takes_typed_value
    assert not field.clearable
    assert field.value is None


def test_once_calculated_the_box_shows_its_amount_as_calculated_and_not_as_a_held_zero(
    operation: PinnedAuthorityOperation,
) -> None:
    typed = _typed_boxes(operation)
    held = {item: Decimal("0") for item in typed} | {"0003": Decimal("24000"), _BOX: Decimal("-250.00")}

    field = form_casilla(built_form(operation, "100", 2025, "0A", held=held, entered=None), _BOX)

    assert field.origin is ModeloFormOrigin.CALCULATED
    assert field.editability is ModeloFormEditability.CALCULATED
    assert not field.held_zero
    assert not field.takes_typed_value
    assert not field.unattributed
    assert str(field.value) == "-250.00"


def test_a_calculation_that_left_the_box_without_a_value_serves_it_as_could_not_calculate(
    operation: PinnedAuthorityOperation,
) -> None:
    """A waived refund leaves only this box unresolved: its neighbours keep their figures and it is never a zero."""
    form = built_form(
        operation,
        "100",
        2025,
        "0A",
        held={"0003": Decimal("30000.00"), "0670": Decimal("-19000.00")},
        calculated=True,
    )
    result = form_casilla(form, "0670")
    field = form_casilla(form, _BOX)

    assert result.origin is ModeloFormOrigin.CALCULATED
    assert str(result.value) == "-19000.00"
    assert field.origin is ModeloFormOrigin.CALCULATION_FAILED
    assert field.value is None
    assert not field.held_zero
    assert form.counts.could_not_calculate >= 1
    assert sum(group.counts.could_not_calculate for group in form.outline) == form.counts.could_not_calculate
    group = next(
        group for group in form.outline if "datoseconomicos-resultados.ingresodevolucionres" in group.section_ids
    )
    assert group.counts.could_not_calculate >= 1
