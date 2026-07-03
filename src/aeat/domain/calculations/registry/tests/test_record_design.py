"""Tests for read-only AEAT record-design PDF extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._record_design_support import (
    _RECORD_DESIGN_ROOT,
    _committed_registry_tree,
    _official_record_design_sheets,
    _official_record_designs,
    _record_design_pdf,
    _record_design_pdf_files,
    _write_pdf_lines,
    bundled_path,
    extract_record_design_pdf,
    extract_record_design_pdf_bytes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_840_record_design_pdf_reuses_record_design_sheet_model() -> None:
    sheets = {
        sheet.name: sheet for sheet in _official_record_design_sheets(_record_design_pdf("modelo_840", "orden-hac"))
    }

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
        sheet.name: sheet
        for sheet in _official_record_design_sheets(_record_design_pdf("modelo_190", "orden-hac-1431"))
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
        sheet.name: sheet
        for sheet in _official_record_design_sheets(_record_design_pdf("modelo_193", "orden-hac-1430"))
    }
    declarante = sheets["Tipo 1 - Registro De Declarante"]

    name_field = next(field for field in declarante.fields if field.offset == 18)
    assert name_field.length == 40
    assert name_field.description == "APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL DECLARANTE."
    assert name_field.content is not None
    assert "persona física" in name_field.content


def test_modelo_347_record_design_pdf_keeps_distinct_type_two_layouts() -> None:
    sheets = _official_record_design_sheets(_record_design_pdf("modelo_347", "orden-hac-1431"))

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
    sheets = _official_record_design_sheets(_record_design_pdf("modelo_347", "2008-y-2009"))

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

    parsed = {path.relative_to(_RECORD_DESIGN_ROOT): sheets for path, sheets in _official_record_designs(pdfs).items()}

    assert pdfs
    assert all(parsed.values())
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(pdfs)


def test_registered_record_design_sources_are_discovered_and_parseable() -> None:
    _, catalogues = _committed_registry_tree()
    sources = {
        source_id: bundled_path() / source.corpus_path
        for source_id, source in catalogues.sources.items()
        if source.kind == "record_design"
    }

    source_items = tuple(sorted(sources.items()))
    parsed_by_path = _official_record_designs(tuple(path for _source_id, path in source_items))
    parsed = {source_id: parsed_by_path[path] for source_id, path in source_items}

    assert sources
    assert all(parsed.values())
    assert {path.suffix.lower() for path in sources.values()} >= {".pdf", ".xls", ".xlsx"}
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(sources)
