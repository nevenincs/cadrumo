"""Hardening checks for calc-sheets engine messages and locale-owned guide text."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.config import override_settings
from .....core.resources import resources
from .....domain.calculations.registry import FormulaDefinition, ParameterDefinition
from .._engine import _resolve_scalar, _rounding_rule_for, build_export_plan
from .._errors import CalcSheetsEngineError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_workbook_operator_labels_resolve_through_output_language() -> None:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))

    with override_settings(aeat_output_language="en"):
        plan = build_export_plan(snapshot)

    label_values = {cell.value for cell in plan.value_cells if cell.role == "label"}
    protected_descriptions = {protected.description for protected in plan.protected_ranges}
    anchor_labels = {anchor.label for anchor in plan.anchors}

    assert {"Section", "Casilla", "Concept", "Value"}.issubset(label_values)
    assert "Derived calculations - protected to preserve parity" in protected_descriptions
    assert "Guide - protected" in protected_descriptions
    assert {"START: Entradas", "RESULT"}.issubset(anchor_labels)


def test_guide_paragraphs_resolve_through_output_language() -> None:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))

    with override_settings(aeat_output_language="en"):
        plan = build_export_plan(snapshot)

    assert plan.guide.title == f"{snapshot.modelo.title} - 1T/2025"
    assert plan.guide.paragraphs[0] == f"{snapshot.modelo.title} - period 1T / 2025."
    assert "Edit only the cells in the 'Entradas' tab." in plan.guide.paragraphs[1]
    assert plan.guide.paragraphs[2] == (
        "To pull your edits into local storage, run 'aeat config google sync calc pull' from the CLI."
    )


def test_unsupported_rounding_error_omits_raw_rounding_token() -> None:
    formula = FormulaDefinition.model_construct(id="formula-sensitive", rounding="private-rounding-token")

    with pytest.raises(CalcSheetsEngineError) as raised:
        _rounding_rule_for(formula)

    error = raised.value
    assert str(error) == "unsupported registry rounding code"
    assert "private-rounding-token" not in str(error)
    assert error.translated_message == "application.storage.calc_sheets.engine.errors.unsupported_rounding"
    assert error.context == {"formula_id": "formula-sensitive"}


def test_missing_scalar_value_error_uses_translated_message_and_structured_context() -> None:
    parameter = ParameterDefinition(
        id="parameter-without-current-value",
        data_type="money",
        unit="EUR",
        legal_refs=("boe-test",),
        source_refs=("source-test",),
    )

    with pytest.raises(CalcSheetsEngineError) as raised:
        _resolve_scalar(parameter, date(2025, 12, 31))

    error = raised.value
    assert str(error) == "parameter has no dated value valid for requested date"
    assert error.translated_message == "application.storage.calc_sheets.engine.errors.parameter_no_dated_value"
    assert error.context == {
        "parameter_id": "parameter-without-current-value",
        "valid_on": "2025-12-31",
    }
