"""Modelo 131 record-design workbook and export binding tests."""

from __future__ import annotations

from functools import lru_cache

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.export import resolve_export_layout
from cadrumo.domain.calculations.registry.tests._record_design_support import (
    _MODELO_131_CURRENT,
    _MODELO_131_WORKBOOK_ROOT,
    _fixed_export_selectors,
    _is_page_one_structured_input_field,
    _is_structured_input_field,
    _modelo_131_snapshot,
    _official_record_design_sheets,
    _page_one_data_type,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WORKBOOK_2019_2023 = "05-131-ejercicios-2019-a-2023-116-kb-xlsx.xlsx"
_WORKBOOK_2024 = "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx"
_WORKBOOK_2025 = "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx"
_WORKBOOK_2026 = "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx"

_RECORD_DESIGN_REVISION_SHAPES = (
    (_WORKBOOK_2019_2023, ("Pág. 0", "Pág. 1")),
    (_WORKBOOK_2024, ("Pág. 0", "Pág. 1", "DPA", "DID")),
    (_WORKBOOK_2025, ("Pág. 0", "Pág. 1", "DPA", "DID")),
    (_WORKBOOK_2026, ("Pág. 0", "Pág. 1", "DPA", "DID")),
)
_RECENT_RECORD_DESIGN_WORKBOOKS = (_WORKBOOK_2024, _WORKBOOK_2025)
_STRUCTURED_RECORD_CASES = (
    (2024, _WORKBOOK_2024, "aeat-dr-131-2024"),
    (2025, _WORKBOOK_2025, "aeat-dr-131-2025"),
    (2026, _WORKBOOK_2026, "aeat-dr-131-2026"),
)
_PAGE_ONE_STRUCTURED_CASES = tuple(
    (filing_year, workbook_name) for filing_year, workbook_name, _ in _STRUCTURED_RECORD_CASES
)
_LA_PALMA_LEGAL_REF_CASES = (
    (2024, _WORKBOOK_2024, "real-decreto-ley-4-2024:art-3"),
    (2025, _WORKBOOK_2025, "real-decreto-ley-13-2025:art-2"),
)
_EXPORT_BINDING_YEARS = (2024, 2025, 2026)
_SUBMITTED_FILE_PROFILE_YEARS = (2023, 2024, 2025, 2026)


@lru_cache
def _record_design_sheets_by_name(workbook_name: str):
    return {sheet.name: sheet for sheet in _official_record_design_sheets(_MODELO_131_WORKBOOK_ROOT / workbook_name)}


@lru_cache
def _current_record_design_sheets_by_name():
    return {sheet.name: sheet for sheet in _official_record_design_sheets(_MODELO_131_CURRENT)}


@lru_cache
def _modelo_131_snapshot_for(filing_year: int, period: str = "1T"):
    return _modelo_131_snapshot(filing_year=filing_year, period=period)


def test_modelo_131_current_record_design_exposes_dpa_and_did_records() -> None:
    sheets = _current_record_design_sheets_by_name()

    assert tuple(sheets) == ("Pág. 0", "Pág. 1", "DPA", "DID")
    assert len(sheets["Pág. 1"].fields) == 71
    assert sheets["Pág. 1"].total_positions == 831
    assert len(sheets["DPA"].fields) == 69
    assert sheets["DPA"].total_positions == 598
    assert len(sheets["DID"].fields) == 7
    assert sheets["DID"].total_positions == 257

    dpa_activity = sheets["DPA"].fields[5]
    assert dpa_activity.offset == 13
    assert dpa_activity.length == 4
    assert "Epigrafe IAE" in dpa_activity.description

    direct_debit_iban = sheets["DID"].fields[4]
    assert direct_debit_iban.offset == 12
    assert direct_debit_iban.length == 34
    assert direct_debit_iban.description == "Domiciliación - IBAN"


def test_modelo_131_record_design_revision_shapes_are_read_from_official_workbooks() -> None:
    for workbook_name, expected_sheets in _RECORD_DESIGN_REVISION_SHAPES:
        sheets = _official_record_design_sheets(_MODELO_131_WORKBOOK_ROOT / workbook_name)

        assert tuple(sheet.name for sheet in sheets) == expected_sheets, workbook_name


def test_modelo_131_recent_record_designs_share_coordinates_but_not_source_text() -> None:
    current = _current_record_design_sheets_by_name()

    for workbook_name in _RECENT_RECORD_DESIGN_WORKBOOKS:
        candidate = _record_design_sheets_by_name(workbook_name)

        for sheet_name in ("Pág. 1", "DPA", "DID"):
            current_fields = current[sheet_name].fields
            candidate_fields = candidate[sheet_name].fields

            assert candidate[sheet_name].total_positions == current[sheet_name].total_positions
            assert [(field.offset, field.length) for field in candidate_fields] == [
                (field.offset, field.length) for field in current_fields
            ]

        assert any(
            candidate_field.description != current_field.description
            for sheet_name in ("Pág. 1", "DPA")
            for candidate_field, current_field in zip(
                candidate[sheet_name].fields,
                current[sheet_name].fields,
                strict=True,
            )
        ), workbook_name


def test_modelo_131_registry_bindings_cover_official_structured_records() -> None:
    for filing_year, workbook_name, source_ref in _STRUCTURED_RECORD_CASES:
        snapshot = _modelo_131_snapshot_for(filing_year)
        sheets = _record_design_sheets_by_name(workbook_name)

        official_fields = {
            (sheet_name, field.offset, field.length, "integer" if field.type_code == "Num" else "text")
            for sheet_name in ("DPA", "DID")
            for field in sheets[sheet_name].fields
            if _is_structured_input_field(field.description)
        }
        registry_bindings = [
            (binding, selector)
            for binding, selector in _fixed_export_selectors(snapshot.revision.bindings, revision=snapshot.revision)
            if selector.record in {"DPA", "DID"}
        ]
        registry_fields = {
            (
                selector.record,
                selector.offset,
                selector.length,
                selector.data_type,
            )
            for _binding, selector in registry_bindings
        }

        assert registry_fields == official_fields, filing_year
        assert all(source_ref in binding.source_refs for binding, _selector in registry_bindings)
        assert all("rd-439-2007:art-110" in binding.legal_refs for binding, _selector in registry_bindings)


def test_modelo_131_2024_dpa_territorial_reduction_fields_carry_specific_legal_basis() -> None:
    snapshot = _modelo_131_snapshot_for(2024, "4T")
    sheets = _record_design_sheets_by_name(_WORKBOOK_2024)
    bindings = {
        (selector.offset, selector.length): binding
        for binding, selector in _fixed_export_selectors(snapshot.revision.bindings, revision=snapshot.revision)
        if selector.record == "DPA"
    }

    for field in sheets["DPA"].fields:
        binding = bindings.get((field.offset, field.length))
        if binding is None:
            continue
        if "Lorca" in field.description:
            assert "orden-hfp-1359-2023:da-5" in binding.legal_refs
        if "Reducción" in field.description and "Palma" in field.description:
            assert "orden-hfp-1359-2023:da-6" in binding.legal_refs
        if "DANA" in field.description:
            assert "real-decreto-ley-7-2024:art-11" in binding.legal_refs


def test_modelo_131_registry_bindings_cover_official_page_one_structured_fields() -> None:
    for filing_year, workbook_name in _PAGE_ONE_STRUCTURED_CASES:
        snapshot = _modelo_131_snapshot_for(filing_year)
        page = _record_design_sheets_by_name(workbook_name)["Pág. 1"]

        official_fields = {
            (
                field.offset,
                field.length,
                _page_one_data_type(field.offset, field.type_code),
            )
            for field in page.fields
            if _is_page_one_structured_input_field(field.description)
        }
        registry_fields = {
            (
                selector.offset,
                selector.length,
                selector.data_type,
            )
            for _binding, selector in _fixed_export_selectors(snapshot.revision.bindings, revision=snapshot.revision)
            if selector.record == "page_1"
        }

        assert registry_fields == official_fields, filing_year


def test_modelo_131_page_one_la_palma_fields_are_year_scoped() -> None:
    for filing_year, workbook_name, palma_legal_ref in _LA_PALMA_LEGAL_REF_CASES:
        snapshot = _modelo_131_snapshot_for(filing_year)
        page = _record_design_sheets_by_name(workbook_name)["Pág. 1"]
        bindings = {
            (selector.offset, selector.length): (binding, selector)
            for binding, selector in _fixed_export_selectors(snapshot.revision.bindings, revision=snapshot.revision)
            if selector.record == "page_1"
        }

        for field in page.fields:
            if "Palma" not in field.description or not _is_page_one_structured_input_field(field.description):
                continue
            binding, selector = bindings[(field.offset, field.length)]
            if "RENTAS OBTENIDAS" in field.description or "Deducción por rentas obtenidas" in field.description:
                assert selector.field is not None
                assert "la-palma" in selector.field
            assert palma_legal_ref in binding.legal_refs


def test_modelo_131_current_page_one_agrarian_fields_preserve_territorial_meaning() -> None:
    snapshot = _modelo_131_snapshot_for(2026)
    page = _current_record_design_sheets_by_name()["Pág. 1"]
    descriptions = {(field.offset, field.length): field.description for field in page.fields}

    for _binding, selector in _fixed_export_selectors(snapshot.revision.bindings, revision=snapshot.revision):
        if selector.record != "page_1":
            continue
        offset = selector.offset
        if offset not in {424, 434, 448, 458}:
            continue
        description = descriptions[(offset, selector.length)]
        assert selector.field is not None
        field_name = selector.field
        if "RENTAS OBTENIDAS EN CEUTA" in description:
            assert "ceuta-melilla" in field_name
        else:
            assert "ceuta-melilla" not in field_name


def test_modelo_131_export_records_derive_fields_from_reviewed_bindings() -> None:
    for filing_year in _EXPORT_BINDING_YEARS:
        snapshot = _modelo_131_snapshot_for(filing_year)
        layout = resolve_export_layout(snapshot).layout
        bindings = {binding.id: binding for binding in snapshot.revision.bindings}

        for record in layout.records:
            if record.binding_record is None:
                continue
            expected = {
                binding.id: selector
                for binding, selector in _fixed_export_selectors(bindings.values(), revision=snapshot.revision)
                if selector.record == record.binding_record
            }
            derived = {field.binding: field for field in record.fields if field.kind is CasillaFieldKind.BINDING}

            assert expected
            assert set(derived) == set(expected)
            assert all(derived[binding_id].offset == selector.offset for binding_id, selector in expected.items())
            assert all(derived[binding_id].length == selector.length for binding_id, selector in expected.items())
            assert all(derived[binding_id].data_type == selector.data_type for binding_id, selector in expected.items())


def test_modelo_131_submitted_file_profiles_target_exported_casillas() -> None:
    for filing_year in _SUBMITTED_FILE_PROFILE_YEARS:
        snapshot = _modelo_131_snapshot_for(filing_year)
        layout = resolve_export_layout(snapshot).layout
        profile = next(
            item
            for item in snapshot.revision.extraction_profiles
            if item.surface == "export_record" and "submitted_file" in item.accepted_artefact_kinds
        )

        exported_casillas = {
            field.casilla_id
            for record in layout.records
            for field in record.fields
            if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
        }

        assert {t.casilla_id for t in profile.target_casillas} <= exported_casillas
