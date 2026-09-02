"""Hardening checks for calc-sheets engine messages and locale-owned guide text."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.config import override_settings
from .....core.resources.bundled_data import bundled_path
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.relations import relation_requirement_index, relation_source_requirements
from .....domain.calculations.registry.schema import FormulaDefinition, RegistrySnapshot
from .....tests.registry_snapshot import build_snapshot
from .....tests.registry_tree import bundled_registry_tree
from ..engine import _rounding_rule_for, build_export_plan
from ..errors import CalcSheetsEngineError
from ..records import RelationValues

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_workbook_operator_labels_resolve_through_output_language() -> None:
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))

    with override_settings(cadrumo_output_language="en"):
        plan = build_export_plan(snapshot)

    label_values = {cell.value for cell in plan.value_cells if cell.role == "label"}
    protected_descriptions = {protected.description for protected in plan.protected_ranges}
    anchor_labels = {anchor.label for anchor in plan.anchors}

    assert {"Section", "Casilla", "Concept", "Value"}.issubset(label_values)
    assert "Derived calculations - protected to preserve parity" in protected_descriptions
    assert "Guide - protected" in protected_descriptions
    assert {"START: Entradas", "RESULT"}.issubset(anchor_labels)


def test_guide_paragraphs_resolve_through_output_language() -> None:
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))

    with override_settings(cadrumo_output_language="en"):
        plan = build_export_plan(snapshot)

    assert plan.guide.title == f"{snapshot.modelo.title} - 1T/2025"
    assert plan.guide.paragraphs[0] == f"{snapshot.modelo.title} - period 1T / 2025."
    assert "Edit only the cells in the 'Entradas' tab." in plan.guide.paragraphs[1]
    assert plan.guide.paragraphs[2] == (
        "To pull your edits into local storage, run 'aeat config google sync calc pull' from the CLI."
    )


def test_blank_relation_values_carry_registry_grounding() -> None:
    modelos, catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "180")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )

    plan = build_export_plan(snapshot, relation_values=RelationValues())

    assert plan.relation_provenance is not None
    relations_by_id = {relation.id: relation for relation in snapshot.revision.relations}
    requirements_by_relation = relation_requirement_index(
        relation_source_requirements(snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period),
    )
    relation_rows = plan.relation_provenance.values
    assert relation_rows
    for row in relation_rows:
        relation = relations_by_id[row.relation]
        assert row.value is None
        assert row.provenance == "operator_manual"
        assert row.source_modelo == relation.source_modelo
        assert row.source_casilla_ids == (relation.source_casilla_id,)
        assert row.dependency_treatment == requirements_by_relation[row.relation].dependency_treatment
        assert set(relation.legal_refs) <= set(row.legal_refs)
        assert set(relation.source_refs) <= set(row.source_refs)

    assert any(row.dependency_treatment for row in relation_rows), (
        "test precondition: the live snapshot declares treatment"
    )


def test_unsupported_rounding_error_omits_raw_rounding_token() -> None:
    formula = FormulaDefinition.model_construct(id="formula-sensitive", rounding="private-rounding-token")

    with pytest.raises(CalcSheetsEngineError) as raised:
        _rounding_rule_for(formula)

    error = raised.value
    # The refusal renders from its key alone now; the English sentence it used
    # to carry alongside was never the surfaced text.
    assert str(error) == "application.storage.calc_sheets.engine.errors.unsupported_rounding"
    assert "private-rounding-token" not in str(error)
    assert error.translated_message == "application.storage.calc_sheets.engine.errors.unsupported_rounding"
    assert error.context == {"formula_id": "formula-sensitive"}


def _m130_snapshot_with_scalar_tariff_values(*, values: tuple[object, ...]) -> RegistrySnapshot:
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T")
    parameter_id = "irpf.direct_estimation_fractional_payment_rate"
    revision = snapshot.revision.model_copy(
        update={
            "parameters": tuple(
                parameter.model_copy(update={"values": values}) if parameter.id == parameter_id else parameter
                for parameter in snapshot.revision.parameters
            ),
        },
    )
    return snapshot.model_copy(update={"revision": revision})


def test_missing_scalar_value_error_uses_translated_message_and_structured_context() -> None:
    snapshot = _m130_snapshot_with_scalar_tariff_values(values=())

    with pytest.raises(CalcSheetsEngineError) as raised:
        build_export_plan(snapshot)

    error = raised.value
    assert str(error) == "application.storage.calc_sheets.engine.errors.parameter_no_dated_value"
    assert error.translated_message == "application.storage.calc_sheets.engine.errors.parameter_no_dated_value"
    assert error.context == {
        "parameter_id": "irpf.direct_estimation_fractional_payment_rate",
        "valid_on": "2025-03-31",
    }


def test_overlapping_scalar_parameter_windows_refuse_export_through_engine_boundary() -> None:
    source = bundled_authority().snapshot("130", filing_year=2025, period="1T")
    parameter = next(
        item for item in source.revision.parameters if item.id == "irpf.direct_estimation_fractional_payment_rate"
    )
    assert len(parameter.values) == 1
    conflicting = parameter.values[0].model_copy(update={"value": parameter.values[0].value + 1})
    snapshot = _m130_snapshot_with_scalar_tariff_values(values=(parameter.values[0], conflicting))

    with pytest.raises(CalcSheetsEngineError) as raised:
        build_export_plan(snapshot)

    error = raised.value
    assert error.translated_message == "application.storage.calc_sheets.engine.errors.parameter_no_dated_value"
    assert error.context == {
        "parameter_id": "irpf.direct_estimation_fractional_payment_rate",
        "valid_on": "2025-03-31",
    }
    assert error.__cause__ is not None
    assert "expected exactly one dated value, found 2" in str(error.__cause__)
