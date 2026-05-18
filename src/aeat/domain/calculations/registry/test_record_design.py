"""Tests for read-only AEAT record-design workbook extraction."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from aeat.core.paths import PROJECT_ROOT
from aeat.core.resources import bundled_path

from . import build_snapshot, load_registry_tree, resolve_export_layout
from ._record_design import (
    extract_record_design,
    extract_record_design_pdf,
    extract_record_design_pdf_bytes,
    extract_record_design_workbook,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_MODELO_131_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_131", "files")
_MODELO_131_CURRENT = _MODELO_131_WORKBOOK_ROOT / "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx"
_RECORD_DESIGN_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")


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


def test_modelo_840_record_design_pdf_reuses_record_design_sheet_model() -> None:
    sheets = {sheet.name: sheet for sheet in extract_record_design_pdf(_record_design_pdf("modelo_840", "orden-hac"))}

    page_one = sheets["Pág. 1"]
    assert len(page_one.fields) == 106
    assert page_one.total_positions == 1132
    assert page_one.fields[0].offset == 1
    assert page_one.fields[0].length == 9
    assert page_one.fields[0].type_code == "An"
    assert page_one.fields[0].description.startswith("Inicio del identificador de modelo")
    assert page_one.fields[-1].offset == 1131
    assert page_one.fields[-1].length == 2
    assert page_one.fields[-1].description == "Salto de línea. Constante CRLF."


def test_generated_compact_record_design_pdf_round_trips_from_path_and_bytes(tmp_path: Path) -> None:
    pdf_path = tmp_path / "compact-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Pág 1 DISEÑO DE REGISTRO 01/12/2003",
            "Nº Posic. Lon Tipo Descripción Validación Contenido",
            "1 1 3 An Inicio del identificador de modelo.",
            "2 4 2 Num Ejercicio.",
            "3 6 5 An Nombre.",
            "4 11 An Salto de línea. Constante CRLF.",
        ),
    )

    from_path = extract_record_design_pdf(pdf_path)
    from_bytes = extract_record_design_pdf_bytes(pdf_path.read_bytes(), source_label=pdf_path.name)

    assert from_bytes == from_path
    sheet = from_path[0]
    assert sheet.name == "Pág. 1"
    assert sheet.total_positions == 12
    assert [(field.ordinal, field.offset, field.length, field.type_code) for field in sheet.fields] == [
        (1, 1, 3, "An"),
        (2, 4, 2, "Num"),
        (3, 6, 5, "An"),
        (4, 11, 2, "An"),
    ]


def test_generated_narrative_record_design_pdf_preserves_content_and_split_titles(tmp_path: Path) -> None:
    pdf_path = tmp_path / "narrative-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Tipo de registro 1: Registro de Declarante",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            "1 Numérico TIPO DE REGISTRO.",
            "Constante número '1'.",
            "2-4 Numérico MODELO DECLARACIÓN",
            "5-8 Numérico EJERCICIO",
            "9-17 Alfanumérico NIF DEL DECLARANTE",
            "18-57 Alfanumérico APELLIDOS Y NOMBRE,",
            "RAZÓN SOCIAL DEL DECLARANTE.",
            "Se consignará el primer apellido y nombre completo.",
            "58 Alfabético TIPO DE SOPORTE.",
            "59-107 Alfanumérico PERSONA CON QUIEN RELACIONARSE",
            "108-500 -------- BLANCOS",
        ),
    )

    sheet = extract_record_design_pdf(pdf_path)[0]

    assert sheet.name == "Tipo 1 - Registro De Declarante"
    assert sheet.total_positions == 500
    assert len(sheet.fields) == 8
    name_field = next(field for field in sheet.fields if field.offset == 18)
    assert name_field.length == 40
    assert name_field.description == "APELLIDOS Y NOMBRE, RAZÓN SOCIAL DEL DECLARANTE."
    assert name_field.content == "Se consignará el primer apellido y nombre completo."
    assert sheet.fields[-1].type_code == "Blancos"
    assert sheet.fields[-1].length == 393


def test_generated_record_design_pdf_rejects_inverted_position_ranges(tmp_path: Path) -> None:
    pdf_path = tmp_path / "bad-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Tipo de registro 1: Registro de Declarante",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            "1 Numérico TIPO DE REGISTRO.",
            "4-3 Numérico MODELO DECLARACIÓN",
        ),
    )

    with pytest.raises(ValueError, match="inverted position range 4-3"):
        extract_record_design_pdf(pdf_path)


def test_modelo_190_record_design_pdf_extracts_narrative_type_one_and_two_records() -> None:
    sheets = {
        sheet.name: sheet for sheet in extract_record_design_pdf(_record_design_pdf("modelo_190", "orden-hac-1431"))
    }

    declarante = sheets["Tipo 1 - Registro De Declarante"]
    perceptor = sheets["Tipo 2 - Registro De Perceptor"]
    assert declarante.total_positions == 500
    assert perceptor.total_positions == 500
    assert [(field.offset, field.length, field.type_code) for field in declarante.fields[:4]] == [
        (1, 1, "Numérico"),
        (2, 3, "Numérico"),
        (5, 4, "Numérico"),
        (9, 9, "Alfanumérico"),
    ]
    assert declarante.fields[4].offset == 18
    assert declarante.fields[4].length == 40
    assert "SOCIAL DEL DECLARANTE" in declarante.fields[4].description
    assert declarante.fields[-2].offset == 226
    assert declarante.fields[-2].length == 262
    assert declarante.fields[-2].type_code == "Blancos"
    assert declarante.fields[-1].offset == 488
    assert declarante.fields[-1].length == 13
    assert perceptor.fields[0].description == "TIPO DE REGISTRO."


def test_modelo_193_record_design_pdf_preserves_split_field_titles_across_lines() -> None:
    sheets = {
        sheet.name: sheet for sheet in extract_record_design_pdf(_record_design_pdf("modelo_193", "orden-hac-1430"))
    }
    declarante = sheets["Tipo 1 - Registro De Declarante"]

    name_field = next(field for field in declarante.fields if field.offset == 18)
    assert name_field.length == 40
    assert name_field.description == "APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL DECLARANTE."
    assert name_field.content is not None
    assert "persona física" in name_field.content


def test_modelo_347_record_design_pdf_keeps_distinct_type_two_layouts() -> None:
    sheets = extract_record_design_pdf(_record_design_pdf("modelo_347", "orden-hac-1431"))

    assert [sheet.name for sheet in sheets] == [
        "Tipo 1 - Registro De Declarante",
        "Tipo 2 - Registro De Declarado",
        "Tipo 2 - Registro De Inmueble",
    ]
    assert [sheet.total_positions for sheet in sheets] == [500, 500, 500]
    declarado, inmueble = sheets[1], sheets[2]
    assert declarado.fields[4].description == "NIF DEL DECLARADO"
    assert inmueble.fields[4].description == "NIF DEL ARRENDATARIO"
    assert declarado.fields[-1].offset == 306
    assert inmueble.fields[-1].offset == 334


def test_modelo_347_positional_chart_pdf_extracts_reviewable_record_data() -> None:
    sheets = extract_record_design_pdf(_record_design_pdf("modelo_347", "2008-y-2009"))

    assert [sheet.name for sheet in sheets] == [
        "Tipo 1 - Registro De Declarante",
        "Tipo 2 - Registro De Declarado",
        "Tipo 2 - Registro De Inmueble",
    ]
    assert [sheet.total_positions for sheet in sheets] == [500, 500, 500]
    declarante, declarado, inmueble = sheets
    assert len(declarante.fields) == 20
    assert declarante.fields[17].offset == 391
    assert declarante.fields[17].description == "NIF. DEL REPRESENTANTE LEGAL"
    assert declarante.fields[17].type_code == "No consta en gráfico"
    assert declarado.fields[4].description == "N.I.F. DECLARADO"
    assert declarado.fields[-1].offset == 130
    assert declarado.fields[-1].length == 371
    assert inmueble.fields[12].offset == 116
    assert inmueble.fields[12].length == 25
    assert inmueble.fields[12].description == "REFERENCIA CATASTRAL"
    assert inmueble.fields[27].description == "CODIGO POSTAL"
    assert all(
        field.content == "Extracted from visual record-design chart geometry."
        for sheet in sheets
        for field in sheet.fields
    )


def test_generated_non_table_pdf_does_not_activate_visual_chart_fallback(tmp_path: Path) -> None:
    pdf_path = tmp_path / "non-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "MODELO 347 REGISTRO DE TIPO 1 REGISTRO DE DECLARANTE",
            "This page names one record heading but has no position ruler or record field geometry.",
        ),
    )

    with pytest.raises(ValueError, match="did not contain parseable field rows"):
        extract_record_design_pdf(pdf_path)


def test_record_design_pdf_corpus_is_discovered_and_parseable() -> None:
    pdfs = _record_design_pdf_files()

    parsed = {path.relative_to(_RECORD_DESIGN_ROOT): extract_record_design_pdf(path) for path in pdfs}

    assert pdfs
    assert all(parsed.values())
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(pdfs)


def test_registered_record_design_sources_are_discovered_and_parseable() -> None:
    _, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    sources = {
        source_id: bundled_path() / source.corpus_path
        for source_id, source in catalogues.sources.items()
        if source.kind == "record_design"
    }

    parsed = {source_id: extract_record_design(path) for source_id, path in sorted(sources.items())}

    assert sources
    assert all(parsed.values())
    assert {path.suffix.lower() for path in sources.values()} >= {".pdf", ".xls", ".xlsx"}
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(sources)


def test_modelo_registry_tests_use_public_record_design_dispatcher() -> None:
    registry_tests = sorted(Path(__file__).parent.glob("test_modelo_*_registry.py"))

    private_imports = [
        path.name for path in registry_tests if "._record_design import" in path.read_text(encoding="utf-8")
    ]

    assert private_imports == []


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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period="1T")
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="4T")
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period="1T")
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period="1T")
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


def test_modelo_131_current_page_one_agrarian_fields_preserve_territorial_meaning() -> None:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2026, period="1T")
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period="1T")
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period="1T")
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


def _record_design_pdf_files() -> tuple[Path, ...]:
    return tuple(sorted(_RECORD_DESIGN_ROOT.glob("modelo_*/files/*.pdf")))


def _record_design_pdf(*path_parts: str) -> Path:
    matches = [path for path in _record_design_pdf_files() if all(part in path.as_posix() for part in path_parts)]
    assert len(matches) == 1, f"expected one record-design PDF for {path_parts!r}, found {matches!r}"
    return matches[0]


def _write_pdf_lines(path: Path, lines: tuple[str, ...]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica", 8)
    y = A4[1] - 36
    for line in lines:
        if y < 36:
            pdf.showPage()
            pdf.setFont("Helvetica", 8)
            y = A4[1] - 36
        pdf.drawString(36, y, line)
        y -= 12
    pdf.save()
