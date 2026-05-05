"""Tests for read-only AEAT record-design workbook extraction."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import build_snapshot, load_registry_tree
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


def test_modelo_131_current_registry_bindings_cover_official_page_one_structured_fields() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="1T")
    page = next(sheet for sheet in extract_record_design_workbook(_MODELO_131_CURRENT) if sheet.name == "Pág. 1")

    official_fields = {
        (field.offset, field.length) for field in page.fields if _is_page_one_structured_input_field(field.description)
    }
    registry_fields = {
        (_selector_int(binding.selector["offset"]), _selector_int(binding.selector["length"]))
        for binding in snapshot.revision.bindings
        if binding.selector.get("record") == "page_1"
    }

    assert registry_fields == official_fields


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


def _selector_int(value: str | int | Decimal | tuple[str, ...]) -> int:
    if isinstance(value, tuple):
        raise AssertionError(f"selector value {value!r} is not numeric")
    return int(value)
