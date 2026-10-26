"""Closed source rows must not turn an incomplete spreadsheet into a zero."""

from decimal import Decimal

import pytest

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.record_row_membership import ClosedRecordRowSet, RecordRowMembership
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormFieldBlock,
    FormLayoutDefinition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormSectionDefinition,
)
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from .._translator import translate_formula
from ..engine import build_export_plan
from ..errors import CalcSheetsEngineError
from ..form_workbook import add_form_workbook
from ..formula_guards import conditional_missing_input_guard
from ..layout import plan_layout
from ..records import TabName

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PREFIX = "modelo-369-exterior-fichero.3-prestaciones-de-servicios-"
_COUNTRY = _PREFIX + "codigo-de-pais-em-de-consumo-1"
_QUOTA = _PREFIX + "cuota-iva-1"
_BASE = _PREFIX + "base-imponible-1"


def _unused():
    return FormulaExpression(op="record_row_unused", args=(FormulaExpression(binding=_COUNTRY),))


@pytest.fixture
def row_source():
    snapshot = published_snapshot("369", filing_year=2025, period="EXT-3T")
    expression = FormulaExpression(
        op="if_then_else",
        args=(_unused(), FormulaExpression(literal=Decimal(0)), FormulaExpression(binding=_QUOTA)),
    )
    formula = snapshot.revision.formulas[0].model_copy(update={"expression": expression})
    # Use a deliberately synthetic form to test compiler contracts, not
    # official-form fidelity. Preserve other declared formula dependencies.
    form = FormLayoutDefinition(
        id="row-test",
        revision_id=snapshot.revision.id,
        seed_source="authored",
        generator_version=1,
        source_state_digest="d" * 64,
        pages=(
            FormPageDefinition(
                id="page",
                heading_key="test.page",
                sections=(
                    FormSectionDefinition(
                        id="section",
                        heading_key="test.section",
                        official_heading="Operaciones",
                        blocks=(
                            *(
                                FormFieldBlock(id=f"field-{i}", casilla_id=casilla.id)
                                for i, casilla in enumerate(snapshot.revision.casillas)
                            ),
                            FormBindingInputsBlock(id="detail", binding_ids=(_COUNTRY, _QUOTA, _BASE)),
                        ),
                    ),
                ),
            ),
        ),
        placements=tuple(
            FormPlacementDefinition(casilla_id=casilla.id, kind="on_form") for casilla in snapshot.revision.casillas
        ),
    )
    snapshot = snapshot.model_copy(
        update={
            "revision": snapshot.revision.model_copy(
                update={
                    "formulas": tuple(
                        formula if item.id == formula.id else item for item in snapshot.revision.formulas
                    ),
                    "form_layouts": (form,),
                }
            )
        }
    )
    row = RecordRowMembership(row_index=1, binding_ids=(_COUNTRY, _QUOTA, _BASE), occupied=False)
    evidence = ClosedRecordRowSet(
        record_id="modelo-369-exterior-t36901",
        bucket_id="fictional-profile",
        work_unit_id="a" * 64,
        registry_snapshot_ref=snapshot.snapshot_ref,
        authority_generation="b" * 64,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        source_ref="fictional-source",
        source_fingerprint="c" * 64,
        rows=(row,),
    )
    return snapshot, evidence, formula


def test_unknown_row_uses_a_visible_missing_guard_even_without_a_conditional(row_source):
    snapshot, _, _ = row_source
    layout = plan_layout(snapshot.revision)
    reference = layout.address_for_binding(_COUNTRY).qualified()
    predicate = translate_formula(_unused(), layout=layout)
    assert predicate == f'IF(LEN({reference}&"")=0,NA(),0)'
    assert conditional_missing_input_guard(_unused(), formulas={}, layout=layout) == f"ISERROR({predicate})"


def test_unused_row_predicate_observes_every_member_including_nonformula_fields(row_source):
    snapshot, evidence, _ = row_source
    row = evidence.rows[0]
    layout = plan_layout(snapshot.revision).model_copy(update={"record_rows": dict.fromkeys(row.binding_ids, row)})
    predicate = translate_formula(_unused(), layout=layout)
    for binding in (_COUNTRY, _QUOTA, _BASE):
        assert f'LEN({layout.address_for_binding(binding).qualified()}&"")=0' in predicate
    assert predicate.startswith("IF(AND(") and predicate.endswith("),1,0)")
    assert "record_rows" not in layout.model_dump()


@pytest.mark.parametrize("occupied", [False, True])
def test_source_membership_reaches_formula_and_human_form_guards(row_source, occupied):
    snapshot, evidence, formula = row_source
    evidence = evidence.model_copy(update={"rows": (evidence.rows[0].model_copy(update={"occupied": occupied}),)})
    plan = build_export_plan(snapshot, closed_record_row_sets=(evidence,))
    compiled = next(cell for cell in plan.formula_cells if cell.casilla_id == formula.target_casilla_id)
    layout = plan_layout(snapshot.revision)
    required_amount = f"ISBLANK({layout.address_for_binding(_QUOTA).qualified()})"
    assert compiled.missing_input_condition is not None
    assert required_amount in compiled.missing_input_condition
    if occupied:
        assert "IF((0)<>0,FALSE," in compiled.missing_input_condition
    else:
        for binding in evidence.rows[0].binding_ids:
            assert layout.address_for_binding(binding).qualified() in compiled.formula
    rendered = add_form_workbook(plan, snapshot)
    visible = next(
        cell
        for cell in rendered.formula_cells
        if cell.address.tab is TabName.FORM and cell.casilla_id == formula.target_casilla_id
    )
    assert compiled.missing_input_condition in visible.formula
    assert "Sin dato" in visible.formula
    assert not any(
        value in str(cell.value)
        for cell in rendered.value_cells
        for value in (evidence.source_fingerprint, evidence.work_unit_id, evidence.source_ref)
    )


@pytest.mark.parametrize("mismatch", ["period", "record", "overlap"])
def test_workbook_refuses_membership_from_a_different_scope(row_source, mismatch):
    snapshot, evidence, _ = row_source
    rows = (evidence,)
    if mismatch == "period":
        rows = (
            evidence.model_copy(
                update={"registry_snapshot_ref": evidence.registry_snapshot_ref.model_copy(update={"period": "EXT-2T"})}
            ),
        )
    elif mismatch == "record":
        rows = (evidence.model_copy(update={"record_id": "corrections"}),)
    else:
        rows = (evidence, evidence)
    with pytest.raises(RegistryValidationError):
        build_export_plan(snapshot, closed_record_row_sets=rows)


def test_unused_row_cannot_skip_a_member_that_has_no_editable_cell(row_source):
    snapshot, evidence, _ = row_source
    row = evidence.rows[0]
    layout = plan_layout(snapshot.revision)
    layout = layout.model_copy(
        update={
            "binding_cells": {key: value for key, value in layout.binding_cells.items() if key != _BASE},
            "record_rows": dict.fromkeys(row.binding_ids, row),
        }
    )
    with pytest.raises(CalcSheetsEngineError, match="no resolved cell"):
        translate_formula(_unused(), layout=layout)
