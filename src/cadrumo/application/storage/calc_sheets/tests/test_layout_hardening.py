"""Hardening checks for calc-sheets layout error surfaces."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import resources
from cadrumo.domain.calculations.registry.schema import FormulaDefinition, FormulaExpression, ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from ..errors import CalcSheetsEngineError
from .._layout import plan_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _modelo_130_revision() -> ModeloRevision:
    return resources().modelos.get("130").revisions["2019-y-siguientes"]


def test_missing_layout_address_raises_typed_error_without_raw_identifier() -> None:
    layout = plan_layout(_modelo_130_revision(), bracket_filter_date=date(2025, 12, 31))

    with pytest.raises(CalcSheetsEngineError) as raised:
        layout.address_for("private-casilla-token")

    error = raised.value
    assert str(error) == "layout reference has no resolved cell"
    assert "private-casilla-token" not in str(error)
    assert error.context == {"reference_kind": "casilla"}
    assert error.translated_message == "application.storage.calc_sheets.layout.errors.unresolved_reference"


@pytest.mark.parametrize(
    ("reference_kind", "expression"),
    [
        ("binding", FormulaExpression(binding="private-binding-token")),
        ("date_binding", FormulaExpression(date_binding="private-date-binding-token")),
        ("parameter", FormulaExpression(parameter="private-parameter-token")),
        ("relation", FormulaExpression(relation="private-relation-token")),
    ],
)
def test_referenced_undeclared_layout_inputs_are_not_silently_skipped(
    reference_kind: str,
    expression: FormulaExpression,
) -> None:
    revision = _modelo_130_revision()
    computed_casilla = revision.casillas[0].model_copy(
        update={"input_kind": InputKind.COMPUTED, "formula": "missing-reference-formula"},
    )
    formula = FormulaDefinition.model_construct(
        id="missing-reference-formula",
        target=computed_casilla.id,
        expression=expression,
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-source-test",),
    )
    malformed_revision = revision.model_copy(
        update={
            "casillas": (computed_casilla,),
            "formulas": (formula,),
            "bindings": (),
            "parameters": (),
            "relations": (),
        },
    )

    with pytest.raises(CalcSheetsEngineError) as raised:
        plan_layout(malformed_revision, bracket_filter_date=date(2025, 12, 31))

    error = raised.value
    assert str(error) == "layout reference is not declared by the revision"
    assert "private-" not in str(error)
    assert error.context == {"reference_kind": reference_kind}
    assert error.translated_message == "application.storage.calc_sheets.layout.errors.undeclared_reference"
