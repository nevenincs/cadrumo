"""Tests for read-only AEAT record-design workbook extraction."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import build_snapshot, load_registry_tree, resolve_export_layout
from ._record_design import extract_record_design_workbook

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_MODELO_131_WORKBOOK_ROOT = PROJECT_ROOT / "corpus" / "aeat_official" / "disenos_registro" / "modelo_131" / "files"
_MODELO_131_CURRENT = _MODELO_131_WORKBOOK_ROOT / "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx"


def test_modelo_131_current_record_design_exposes_dpa_and_did_records() -> None:
    sheets = {sheet.name: sheet for sheet in extract_record_design_workbook(_MODELO_131_CURRENT)}

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


@pytest.mark.parametrize(
    ("workbook_name", "expected_sheets"),
    (
        ("05-131-ejercicios-2019-a-2023-116-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1")),
        ("06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1", "DPA", "DID")),
        ("07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1", "DPA", "DID")),
        ("01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1", "DPA", "DID")),
    ),
)
def test_modelo_131_record_design_revision_shapes_are_read_from_official_workbooks(
    workbook_name: str,
    expected_sheets: tuple[str, ...],
) -> None:
    sheets = extract_record_design_workbook(Path(_MODELO_131_WORKBOOK_ROOT / workbook_name))

    assert tuple(sheet.name for sheet in sheets) == expected_sheets


@pytest.mark.parametrize(
    "workbook_name",
    (
        "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx",
        "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx",
    ),
)
def test_modelo_131_recent_record_designs_share_coordinates_but_not_source_text(workbook_name: str) -> None:
    current = {sheet.name: sheet for sheet in extract_record_design_workbook(_MODELO_131_CURRENT)}
    candidate = {
        sheet.name: sheet for sheet in extract_record_design_workbook(Path(_MODELO_131_WORKBOOK_ROOT / workbook_name))
    }

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
    )


@pytest.mark.parametrize(
    ("filing_year", "workbook_name", "source_ref"),
    (
        (2024, "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx", "aeat-dr-131-2024"),
        (2025, "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx", "aeat-dr-131-2025"),
        (2026, "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx", "aeat-dr-131-2026"),
    ),
)
def test_modelo_131_registry_bindings_cover_official_structured_records(
    filing_year: int,
    workbook_name: str,
    source_ref: str,
) -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=filing_year, period="1T")
    sheets = {sheet.name: sheet for sheet in extract_record_design_workbook(_MODELO_131_WORKBOOK_ROOT / workbook_name)}

    official_fields = {
        (sheet_name, field.offset, field.length, "integer" if field.type_code == "Num" else "text")
        for sheet_name in ("DPA", "DID")
        for field in sheets[sheet_name].fields
        if _is_structured_input_field(field.description)
    }
    registry_bindings = [
        binding for binding in snapshot.revision.bindings if binding.selector.get("record") in {"DPA", "DID"}
    ]
    registry_fields = {
        (
            str(binding.selector["record"]),
            _selector_int(binding.selector["offset"]),
            _selector_int(binding.selector["length"]),
            str(binding.selector["data_type"]),
        )
        for binding in registry_bindings
    }

    assert registry_fields == official_fields
    assert all(source_ref in binding.source_refs for binding in registry_bindings)
    assert all("rd-439-2007:art-110" in binding.legal_refs for binding in registry_bindings)


def test_modelo_131_2024_dpa_territorial_reduction_fields_carry_specific_legal_basis() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2024, period="4T")
    sheets = {
        sheet.name: sheet
        for sheet in extract_record_design_workbook(
            _MODELO_131_WORKBOOK_ROOT / "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx"
        )
    }
    bindings = {
        (_selector_int(binding.selector["offset"]), _selector_int(binding.selector["length"])): binding
        for binding in snapshot.revision.bindings
        if binding.selector.get("record") == "DPA"
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


@pytest.mark.parametrize(
    ("filing_year", "workbook_name"),
    (
        (2024, "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx"),
        (2025, "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx"),
        (2026, "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx"),
    ),
)
def test_modelo_131_registry_bindings_cover_official_page_one_structured_fields(
    filing_year: int,
    workbook_name: str,
) -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=filing_year, period="1T")
    page = next(
        sheet
        for sheet in extract_record_design_workbook(_MODELO_131_WORKBOOK_ROOT / workbook_name)
        if sheet.name == "Pág. 1"
    )

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
            _selector_int(binding.selector["offset"]),
            _selector_int(binding.selector["length"]),
            str(binding.selector["data_type"]),
        )
        for binding in snapshot.revision.bindings
        if binding.selector.get("record") == "page_1"
    }

    assert registry_fields == official_fields


@pytest.mark.parametrize(
    ("filing_year", "workbook_name", "palma_legal_ref"),
    (
        (
            2024,
            "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx",
            "real-decreto-ley-4-2024:art-3",
        ),
        (
            2025,
            "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx",
            "real-decreto-ley-13-2025:art-2",
        ),
    ),
)
def test_modelo_131_page_one_la_palma_fields_are_year_scoped(
    filing_year: int,
    workbook_name: str,
    palma_legal_ref: str,
) -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=filing_year, period="1T")
    page = next(
        sheet
        for sheet in extract_record_design_workbook(_MODELO_131_WORKBOOK_ROOT / workbook_name)
        if sheet.name == "Pág. 1"
    )
    bindings = {
        (_selector_int(binding.selector["offset"]), _selector_int(binding.selector["length"])): binding
        for binding in snapshot.revision.bindings
        if binding.selector.get("record") == "page_1"
    }

    for field in page.fields:
        if "Palma" not in field.description or not _is_page_one_structured_input_field(field.description):
            continue
        binding = bindings[(field.offset, field.length)]
        if "RENTAS OBTENIDAS" in field.description or "Deducción por rentas obtenidas" in field.description:
            assert "la-palma" in str(binding.selector["field"])
        assert palma_legal_ref in binding.legal_refs


def test_modelo_131_current_page_one_agrarian_fields_do_not_shadow_territorial_meaning() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="1T")
    page = next(sheet for sheet in extract_record_design_workbook(_MODELO_131_CURRENT) if sheet.name == "Pág. 1")
    descriptions = {(field.offset, field.length): field.description for field in page.fields}

    for binding in snapshot.revision.bindings:
        if binding.selector.get("record") != "page_1":
            continue
        offset = _selector_int(binding.selector["offset"])
        if offset not in {424, 434, 448, 458}:
            continue
        description = descriptions[(offset, _selector_int(binding.selector["length"]))]
        field_name = str(binding.selector["field"])
        if "RENTAS OBTENIDAS EN CEUTA" in description:
            assert "ceuta-melilla" in field_name
        else:
            assert "ceuta-melilla" not in field_name


@pytest.mark.parametrize("filing_year", [2024, 2025, 2026])
def test_modelo_131_export_records_derive_fields_from_reviewed_bindings(filing_year: int) -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=filing_year, period="1T")
    layout = resolve_export_layout(snapshot).layout
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for record in layout.records:
        if record.binding_record is None:
            continue
        expected = {
            binding.id: binding
            for binding in bindings.values()
            if binding.selector.get("record") == record.binding_record
        }
        derived = {field.binding: field for field in record.fields if field.kind == "binding"}

        assert expected
        assert set(derived) == set(expected)
        assert all(
            derived[binding_id].offset == _selector_int(binding.selector["offset"])
            for binding_id, binding in expected.items()
        )
        assert all(
            derived[binding_id].length == _selector_int(binding.selector["length"])
            for binding_id, binding in expected.items()
        )
        assert all(
            derived[binding_id].data_type == str(binding.selector["data_type"])
            for binding_id, binding in expected.items()
        )


@pytest.mark.parametrize("filing_year", [2023, 2024, 2025, 2026])
def test_modelo_131_submitted_file_profiles_target_exported_casillas(filing_year: int) -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=filing_year, period="1T")
    layout = resolve_export_layout(snapshot).layout
    profile = next(
        item
        for item in snapshot.revision.extraction_profiles
        if item.surface == "export_record" and "submitted_file" in item.accepted_artefact_kinds
    )

    exported_casillas = {
        field.casilla
        for record in layout.records
        for field in record.fields
        if field.kind == "casilla" and field.casilla is not None
    }

    assert set(profile.target_casillas) <= exported_casillas


def _is_structured_input_field(description: str) -> bool:
    if description in {
        "Inicio del identificador de modelo y página.",
        "Modelo.",
        "Página.",
        "Fin de identificador de modelo.",
        "Indicador de página complementaria.",
        "Indicador de fin de registro",
    }:
        return False
    return "RESERVADO" not in description.upper()


def _is_page_one_structured_input_field(description: str) -> bool:
    if description in {
        "Inicio del identificador de modelo y página.",
        "Modelo.",
        "Página.",
        "Fin de identificador de modelo.",
        "Indicador de página complementaria.",
        "Tipo de autoliquidación",
        "Declarante (1) - Nif",
        "Declarante (1) - Apellidos",
        "Declarante (1) - Nombre (solo personas físicas)",
        "Devengo (2) - Ejercicio",
        "Devengo (2) - Período",
        "Indicador de fin de registro",
    }:
        return False
    if "RESERVADO" in description.upper():
        return False
    return "[" not in description and "]" not in description


def _page_one_data_type(offset: int, type_code: str) -> str:
    if offset in {109, 613, 692}:
        return "boolean"
    if offset in {360, 374, 424, 434, 448, 458, 472, 614}:
        return "money"
    if type_code in {"N"}:
        return "money"
    if type_code == "An":
        return "text"
    if offset in {359, 556}:
        return "integer"
    return "decimal"


def _selector_int(value: str | int | Decimal | tuple[str, ...]) -> int:
    if isinstance(value, tuple):
        raise AssertionError(f"selector value {value!r} is not numeric")
    return int(value)
