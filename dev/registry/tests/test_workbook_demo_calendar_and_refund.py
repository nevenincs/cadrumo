"""Real registry acceptance for the calendar and refund demonstration forms, using fictional data."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from cadrumo.adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan
from cadrumo.application.modelo.work_form_records import saved_form_records
from cadrumo.application.storage.calc_sheets.records import TabName
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.afiliado_contribution_bindings import AfiliadoContributionProvider
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormRepeatingGroupBlock,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_covering

from .. import workbook_demo
from ..compiler.authority import compiled_bundled_authority
from ..workbook_demo import build_demonstration_plan
from ..workbook_demo_cases import DEMO_CASES, newest_historical_year
from ..workbook_demo_inputs import demonstration_inputs
from .authored_edition_support import authored_revisions
from .workbook_demo_oracle_support import expected_result, numeric_inputs

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _assert_156_saved_member_rows(snapshot, saved) -> None:
    member = snapshot.revision.form_layouts[0].pages[1].sections[0].blocks[0]
    assert isinstance(member, FormRepeatingGroupBlock)
    known, rows = saved_form_records(
        snapshot=snapshot,
        revision=saved,
        block=member,
        column_casillas=tuple(column.casilla_id for column in member.columns),
    )
    assert known and len(rows) == 2
    first, second = [dict(zip((c.casilla_id for c in member.columns), row.values, strict=True)) for row in rows]
    assert first["cotizacion-enero"] == Decimal("100.25")
    assert first["cotizacion-enero-situacion"] == "S"
    assert first["cotizacion-abril"] == Decimal("0")
    assert first["cotizacion-abril-situacion"] == "N"
    assert second["cotizacion-enero"] == Decimal("75.50")
    assert second["cotizacion-diciembre"] is None
    assert second["cotizacion-diciembre-situacion"] is None


def _assert_156_form_shows_members_and_declarant(plan, values: dict[str, Decimal | str | bool | None]) -> None:
    assert "numero-justificante" not in values
    form_values = [cell.value for cell in plan.value_cells if cell.address.tab is TabName.FORM]
    assert values["declarante-razon-social"] == "Mutualidad ficticia Ejemplo"
    assert "Presentador ficticio" not in form_values
    mirrors = {str(cell.casilla_id) for cell in plan.formula_cells if cell.address.tab is TabName.FORM}
    assert "declarante-razon-social" in mirrors
    assert "Ejemplo Prueba Ana" in form_values and "Ejemplo Prueba Luis" in form_values
    assert "001234567890" in form_values and "001234567891" in form_values
    assert form_values.count("Enero") == 2 and form_values.count("Diciembre") == 2


def test_156_calendar_keeps_status_and_money_as_independent_facts() -> None:
    case = next(case for case in DEMO_CASES if case.modelo == "156")
    snapshot, plan = build_demonstration_plan(case)
    inputs, bindings = demonstration_inputs(snapshot, case)
    values = {str(value.casilla_id): value.value for value in inputs.values}
    assert bindings == {} and snapshot.revision.formulas == ()
    saved = workbook_demo.demonstration_records(snapshot)
    assert saved is not None and len(saved.detail_rows) == 2
    assert values["numero-total-afiliados"] == Decimal(len(saved.detail_rows))
    assert not any(key.startswith("cotizacion-") for key in values)
    _assert_156_saved_member_rows(snapshot, saved)
    _assert_156_form_shows_members_and_declarant(plan, values)
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    expected_headings = {
        binding.id: casillas[binding.provider.target_casilla_id].label
        for binding in snapshot.revision.bindings
        if isinstance(binding.provider, AfiliadoContributionProvider)
    }
    actual_headings = {column.binding: column.header_label for row_set in plan.row_sets for column in row_set.columns}
    assert len(expected_headings) == 27
    assert actual_headings == expected_headings


def test_156_amendment_marks_share_one_source_and_preserve_unknown() -> None:
    case = next(case for case in DEMO_CASES if case.modelo == "156")
    _snapshot, plan = build_demonstration_plan(case)
    marks = [
        c
        for c in plan.formula_cells
        if c.address.tab is TabName.FORM and c.casilla_id == "declaracion-complementaria-sustitutiva"
    ]
    assert len(marks) == 2
    source = next(
        c
        for c in plan.value_cells
        if c.role == "operator_input" and c.casilla_id == "declaracion-complementaria-sustitutiva"
    )
    assert source.value is None
    for mark in marks:
        assert f"ISBLANK({source.address.qualified()})" in mark.formula
        assert '"Sin dato"' in mark.formula and '"Valor no válido"' in mark.formula
        assert f'EXACT({source.address.qualified()},"C ")' in mark.formula
        assert f'EXACT({source.address.qualified()}," S")' in mark.formula
    book = load_workbook(BytesIO(materialize_export_plan(plan)), data_only=False)
    for mark in marks:
        assert book["Modelo"][mark.address.a1].value == "=" + mark.formula


def test_156_receipt_checks_are_derived_from_registered_predicates() -> None:
    case = next(case for case in DEMO_CASES if case.modelo == "156")
    snapshot, plan = build_demonstration_plan(case)
    checks = [c for c in plan.formula_cells if c.address.tab is TabName.FORM and '"Falta dato"' in c.formula]
    assert len(checks) == len(snapshot.revision.verification_predicates) == 3
    inputs = {str(c.casilla_id): c.address.qualified() for c in plan.value_cells if c.role == "operator_input"}
    for check in checks:
        assert check.casilla_id is None
        assert inputs["declaracion-complementaria-sustitutiva"] in check.formula
        assert inputs["numero-identificativo-anterior"] in check.formula
        assert "ISNUMBER(" in check.formula and '"Sin dato"' in check.formula
        assert '"No aplica"' in check.formula
        assert '"Dato aportado"' in check.formula or '"Cero indicado"' in check.formula
    book = load_workbook(BytesIO(materialize_export_plan(plan)), data_only=False)
    assert all(book["Modelo"][c.address.a1].value == "=" + c.formula for c in checks)


def test_308_refund_form_compiles_declared_quotas_and_preserves_unknown_branches() -> None:
    case = next(c for c in DEMO_CASES if c.modelo == "308")
    snapshot, plan = build_demonstration_plan(case)
    inputs, bindings = demonstration_inputs(snapshot, case)
    values = numeric_inputs(inputs)
    target = "decl.req-iva-devolver-17"
    assert target not in values
    assert expected_result(snapshot, values, bindings, target) == Decimal("250.35")
    assert expected_result(snapshot, {**values, "decl.req-cuota-16": Decimal("20")}, bindings, target) == Decimal(
        "270.35"
    )
    assert "decl.mtn-iva-devolver-eib" not in values
    assert any(str(cell.casilla_id) == target for cell in plan.formula_cells)
    form_values = [cell.value for cell in plan.value_cells if cell.address.tab is TabName.FORM]
    assert "12345678Z" in form_values
    assert next(v.value for v in inputs.values if v.casilla_id == "decl.nombre") == "Ana"
    assert "IVA a devolver por recargo de equivalencia" in form_values
    assert "Actividades exclusivamente en recargo de equivalencia" in form_values
    assert next(v.value for v in inputs.values if v.casilla_id == "decl.tipo-tributacion") == "2"
    assert not any("MTN -" in str(v) or "REQ -" in str(v) for v in form_values)
    assert plan.metadata.registry_sha not in "\n".join(str(v) for v in form_values)
    workbook = load_workbook(BytesIO(materialize_export_plan(plan)), data_only=False)
    assert any(cell.data_type == "f" for row in workbook["Modelo"] for cell in row)


def test_309_payment_copy_and_liquidation_share_one_live_result() -> None:
    case = next(c for c in DEMO_CASES if c.modelo == "309")
    snapshot, plan = build_demonstration_plan(case)
    inputs, bindings = demonstration_inputs(snapshot, case)
    values = numeric_inputs(inputs)
    target = "decl.resultado-24"
    assert target not in values
    assert expected_result(snapshot, values, bindings, target) == Decimal("210")
    assert expected_result(snapshot, {**values, "decl.rg-cuota-27": Decimal("20")}, bindings, target) == Decimal("230")
    repeated = [cell for cell in plan.formula_cells if cell.address.tab is TabName.FORM and cell.casilla_id == target]
    assert len(repeated) == 2
    assert repeated[0].formula == repeated[1].formula
    form_values = [cell.value for cell in plan.value_cells if cell.address.tab is TabName.FORM]
    assert "12345678Z" in form_values
    assert "00000000T" not in form_values
    assert "Forma de pago" in form_values
    assert "Firma (11)" in form_values
    assert "Persona física no empresario o profesional" in form_values
    assert not any("trigger" in str(value) for value in form_values)
    assert plan.metadata.registry_sha not in "\n".join(str(value) for value in form_values)
    book = load_workbook(BytesIO(materialize_export_plan(plan)), data_only=False)
    assert all(book["Modelo"][cell.address.a1].value == "=" + cell.formula for cell in repeated)


def test_309_historical_example_keeps_seven_rows_and_cannot_acquire_filing_authority() -> None:
    floor = filing_year_envelope().floor
    covering = str(revision_covering("309", floor).id)
    case = next(c for c in DEMO_CASES if c.modelo == "309" and c.revision == covering)
    snapshot, plan = build_demonstration_plan(case)
    inputs, bindings = demonstration_inputs(snapshot, case)
    values = numeric_inputs(inputs)
    assert snapshot.revision.authority_grade is RegistryAuthorityGrade.APPLICABILITY
    with pytest.raises(RegistryValidationError, match="authority"):
        compiled_bundled_authority().snapshot("309", filing_year=floor, period="0A", revision_id=covering)
    assert {value.casilla_id for value in inputs.values}.isdisjoint(
        {"decl.rg-base-25", "decl.rg-tipo-26", "decl.rg-cuota-27"}
    )
    assert expected_result(snapshot, values, bindings, "decl.resultado-24") == Decimal("210")
    assert expected_result(
        snapshot, {**values, "decl.rg-cuota-03": Decimal("20")}, bindings, "decl.resultado-24"
    ) == Decimal("230")
    form_values = [cell.value for cell in plan.value_cells if cell.address.tab is TabName.FORM]
    assert "12345678Z" in form_values
    assert "00000000T" not in form_values
    results = [
        cell
        for cell in plan.formula_cells
        if cell.address.tab is TabName.FORM and cell.casilla_id == "decl.resultado-24"
    ]
    assert len(results) == 2 and results[0].formula == results[1].formula


def test_309_2016_preview_uses_registry_layout_and_fictional_identity() -> None:
    from ..workbook_demo_nonperiodic_historical import build_historical_nonperiodic_plan

    newest = newest_historical_year("309")
    source, plan = build_historical_nonperiodic_plan()
    assert source.revision.id == revision_covering("309", newest).id
    assert plan.metadata.preview_year == newest
    assert plan.human_presentation
    values = [c.value for c in plan.value_cells if c.address.tab is TabName.FORM]
    assert "12345678Z" in values
    assert "00000000T" not in values
    assert "Ana Ejemplo" in values
    totals = [c for c in plan.formula_cells if c.address.tab is TabName.FORM and c.casilla_id == "decl.resultado-24"]
    assert len(totals) == 2
    assert totals[0].formula == totals[1].formula
    assert {c.casilla_id for c in plan.value_cells if c.value == "Ejemplo ficticio"} == {"papel-domicilio-via"}
    assert not any(c.value for c in plan.value_cells if str(c.casilla_id).startswith("papel-ccc-"))


def test_309_2015_preview_retains_original_mark_fields_and_paper_identity() -> None:
    from ..workbook_demo_nonperiodic_historical import build_historical_nonperiodic_plan

    oldest = authored_revisions("309")[0]
    assert oldest.valid_to is not None
    year = oldest.valid_to.year
    source, plan = build_historical_nonperiodic_plan(year=year)
    assert source.revision.id == oldest.id
    assert plan.metadata.preview_year == year
    values = [c.value for c in plan.value_cells if c.address.tab is TabName.FORM]
    assert "12345678Z" in values
    inputs = {str(c.casilla_id): c.value for c in plan.value_cells if c.role == "operator_input"}
    assert inputs["papel-nombre-completo"] == "Ana Ejemplo"
    assert inputs["papel-complementaria"] is False
    assert inputs["decl.hecho-imponible-medios-transporte-nuevos"] == "X"
    assert "decl.hecho-imponible" not in inputs
    assert "decl.situacion-tributaria" not in inputs
    totals = [c for c in plan.formula_cells if c.address.tab is TabName.FORM and c.casilla_id == "decl.resultado-24"]
    assert len(totals) == 2 and totals[0].formula == totals[1].formula
