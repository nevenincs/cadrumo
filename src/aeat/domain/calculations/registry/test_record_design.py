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


def test_modelo_131_current_registry_bindings_cover_official_structured_records() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="1T")
    sheets = {sheet.name: sheet for sheet in extract_record_design_workbook(_MODELO_131_CURRENT)}

    official_fields = {
        (sheet_name, field.offset, field.length, "integer" if field.type_code == "Num" else "text")
        for sheet_name in ("DPA", "DID")
        for field in sheets[sheet_name].fields
        if _is_structured_input_field(field.description)
    }
    registry_fields = {
        (
            str(binding.selector["record"]),
            _selector_int(binding.selector["offset"]),
            _selector_int(binding.selector["length"]),
            str(binding.selector["data_type"]),
        )
        for binding in snapshot.revision.bindings
        if binding.selector.get("record") in {"DPA", "DID"}
    }

    assert registry_fields == official_fields
    assert all("aeat-dr-131-2026" in binding.source_refs for binding in snapshot.revision.bindings)
    assert all("rd-439-2007:art-110" in binding.legal_refs for binding in snapshot.revision.bindings)


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


def _selector_int(value: str | int | Decimal | tuple[str, ...]) -> int:
    if isinstance(value, tuple):
        raise AssertionError(f"selector value {value!r} is not numeric")
    return int(value)
