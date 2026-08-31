"""Tests for read-only AEAT record-design PDF extraction and corpus coverage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ..errors import RegistryValidationError
from ..record_design import (
    extract_record_design,
    extract_record_design_pdf,
    extract_record_design_pdf_bytes,
)
from ._record_design_support import (
    _RECORD_DESIGN_ROOT,
    _committed_registry_tree,
    _official_record_design_sheets,
    _official_record_designs,
    _record_design_pdf,
    _record_design_pdf_files,
    _write_pdf_lines,
    bundled_path,
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

    from_path = extract_record_design_pdf(pdf_path).accept_partial()
    from_bytes = extract_record_design_pdf_bytes(pdf_path.read_bytes(), source_label=pdf_path.name).accept_partial()

    assert from_bytes == from_path
    sheet = from_path[0]
    assert sheet.name == "Pág. 1"
    assert sheet.total_positions == 12
    assert [(field.ordinal, field.offset, field.length, field.type_code) for field in sheet.fields] == [
        ("1", 1, 3, "An"),
        ("2", 4, 2, "Num"),
        ("3", 6, 5, "An"),
        ("4", 11, 2, "An"),
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

    sheet = extract_record_design_pdf(pdf_path).accept_partial()[0]

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


# Two bundled record-design PDFs ship as reference corpus but are NOT tabular
# field-row designs the extractor can parse, and neither is wired as a
# registry-consumed ``record_design`` source (the consumed set is covered by
# ``test_registered_record_design_sources_are_discovered_and_parseable``):
#   - modelo_038 (28-06-2024) is a visual positional-CHART layout — a position
#     ruler with scattered visual field labels, not a field-row table — and the
#     geometric chart extractor cannot reconstruct its field geometry.
#   - modelo_604 ``atf-en-ingles`` is a redundant ENGLISH-language translation of
#     the authoritative Spanish ATF design (``atf-en-espanol``, which parses);
#     the Spanish original is the field-row authority and the parser is
#     Spanish-stem by design.
# They stay discovered (asserted below) but are excluded from the field-row parse
# gate; drop an entry here if the extractor is later extended to read it.
_NON_FIELD_ROW_CORPUS_PDFS = frozenset(
    {
        Path("modelo_038/files/01-038-diseno-de-registro-actualizado-28-06-2024.pdf"),
        Path("modelo_604/files/02-604-diseno-de-registro-atf-en-ingles.pdf"),
    },
)


def test_record_design_pdf_corpus_is_discovered_and_parseable() -> None:
    pdfs = _record_design_pdf_files()
    discovered = {path.relative_to(_RECORD_DESIGN_ROOT) for path in pdfs}
    assert pdfs
    # Both known non-field-row artefacts must remain present in discovery, so a
    # rename/removal trips this gate rather than silently shrinking the corpus.
    assert discovered >= _NON_FIELD_ROW_CORPUS_PDFS

    # A design the catalogue declares `provenance_only` is corpus evidence, not a
    # machine-readable authority, so it is discovered above but never parsed here.
    # Read from the declaration rather than from a parse failure: a failure cannot
    # tell provenance from a broken design.
    _, catalogues = _committed_registry_tree()
    provenance_only = {
        Path(*source.corpus_path.split("/")[3:])
        for source in catalogues.sources.values()
        if source.kind == "record_design" and source.design_authority == "provenance_only"
    }
    field_row_pdfs = tuple(
        path
        for path in pdfs
        if path.relative_to(_RECORD_DESIGN_ROOT) not in _NON_FIELD_ROW_CORPUS_PDFS
        and path.relative_to(_RECORD_DESIGN_ROOT) not in provenance_only
    )
    parsed = {
        path.relative_to(_RECORD_DESIGN_ROOT): sheets
        for path, sheets in _official_record_designs(field_row_pdfs).items()
    }

    assert field_row_pdfs
    # Every design either yields sheets or SAYS why it could not. A design whose
    # rows leave holes in its own declared extent is recorded as skipped rather
    # than handed over as whole, so an empty sheet set is a legitimate -- and
    # loudly stated -- outcome, not a silent one. Asserting universal
    # parseability instead would force the reader to keep returning
    # partially-read records as if they were complete, which is the false green
    # the skip exists to remove.
    unexplained = sorted(
        str(path)
        for path, sheets in parsed.items()
        if not sheets and not extract_record_design(_RECORD_DESIGN_ROOT / path).skipped
    )
    assert not unexplained, f"designs yielding no sheets and recording no reason: {unexplained}"
    assert any(parsed.values()), "no bundled PDF design parsed at all"
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(field_row_pdfs)


def test_every_provenance_only_design_still_refuses_to_parse() -> None:
    """The declaration's teeth: a provenance stamp must stay earned.

    ``design_authority = "provenance_only"`` takes a design out of the
    parseability sweeps, so on its own it is an exemption anyone could hand out.
    This is the cross-check against physical evidence that keeps it honest: every
    stamped design must ACTUALLY still refuse to parse. The day one parses
    cleanly, this gate reds and forces the promotion reconsideration the modelo
    184 regression already asks for -- "reconsider promotion only when strict
    parsing produces complete records starting at position 1".

    Mis-stamping a genuinely authoritative design would otherwise drop it from
    parse coverage in silence, which is the one way this field can do harm.
    """
    _, catalogues = _committed_registry_tree()
    stamped = sorted(
        (source.id, bundled_path() / source.corpus_path)
        for source in catalogues.sources.values()
        if source.kind == "record_design" and source.design_authority == "provenance_only"
    )

    assert stamped, "no design is stamped provenance_only; this gate would pass vacuously"

    parsed_anyway = []
    for source_id, path in stamped:
        try:
            extract_record_design(path)
        except RegistryValidationError:
            continue
        parsed_anyway.append(source_id)

    assert not parsed_anyway, (
        "these designs are stamped provenance_only but parse cleanly, so the stamp is no longer "
        f"earned -- promote them or correct the stamp: {parsed_anyway}"
    )


def test_registered_record_design_sources_are_discovered_and_parseable() -> None:
    _, catalogues = _committed_registry_tree()
    sources = {
        source_id: bundled_path() / source.corpus_path
        for source_id, source in catalogues.sources.items()
        if source.kind == "record_design" and source.design_authority == "authoritative"
    }

    source_items = tuple(sorted(sources.items()))
    parsed_by_path = _official_record_designs(tuple(path for _source_id, path in source_items))
    parsed = {source_id: parsed_by_path[path] for source_id, path in source_items}

    assert sources
    # Same invariant as the corpus sweep above: a registered design either
    # yields sheets or records why it could not. Modelo 156, 280 and 349's
    # designs each leave holes in their own declared extent, which the reader
    # now reports as skipped sheets instead of returning as whole records.
    unexplained = sorted(
        source_id
        for source_id, sheets in parsed.items()
        if not sheets and not extract_record_design(sources[source_id]).skipped
    )
    assert not unexplained, f"registered designs yielding no sheets and recording no reason: {unexplained}"
    assert any(parsed.values()), "no registered record design parsed at all"
    assert {path.suffix.lower() for path in sources.values()} >= {".pdf", ".xls", ".xlsx"}
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(sources)


# Run out-of-process: any sibling test that parses a workbook or PDF imports these
# backends into the shared session, so an in-process check cannot observe absence.
_PARSER_BACKEND_IMPORT_PROBE = """
import sys

import cadrumo.domain.calculations.registry  # noqa: F401

deferred = [name for name in ("openpyxl", "pdfplumber", "pypdfium2", "xlrd") if name in sys.modules]
print(",".join(deferred) if deferred else "clean")
"""


def test_registry_import_does_not_load_the_pdf_and_xls_parser_backends() -> None:
    """Importing the registry must not drag in the spreadsheet/PDF parser stack.

    ``_record_design`` and ``_workbook_parity`` are both imported eagerly by the
    registry facade, so a module-scope ``import openpyxl`` / ``pdfplumber`` /
    ``pypdfium2`` / ``xlrd`` in either makes every registry consumer -- every
    taxpayer calculation -- pay for a parser stack it never calls. They are
    deferred into the functions that call them; hoisting any one back to module
    scope reds this test.

    All four are asserted together because they mask each other: openpyxl had
    TWO eager importers, so deferring only one of them freed nothing. A partial
    fix here is indistinguishable from no fix unless every importer is covered.
    """
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv with in-test script.
        [sys.executable, "-c", _PARSER_BACKEND_IMPORT_PROBE],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "clean", (
        f"importing the registry loaded deferred parser backends: {completed.stdout.strip()}; "
        "keep these imports inside the extraction functions that call them"
    )


def test_a_design_yielding_no_fields_is_never_reported_complete() -> None:
    """A design the reader emptied must say so, not pass as a clean read.

    The blind spot this closes: an EMPTY sheet set is trivially contiguous and
    trivially free of overlaps, so every structural check written against holes
    and overlaps reports such a design clean. Modelo 100's five 2009-2013
    editions and Modelo 185 sat at zero sheets and zero fields for exactly that
    reason -- their record bodies open but no heading names them, so every row
    is discarded and nothing downstream could tell that from a design with
    nothing to read.

    The same blind spot has a sibling worth naming here: once a sheet is
    recorded as SKIPPED it leaves the returned sheet list, so a checker walking
    returned sheets alone stops seeing the very defect that moved it there.
    Both halves need ``is_complete`` and the skip reasons read in the SAME pass,
    which is what this asserts -- a design that yielded nothing must carry a
    recorded reason, so its silence is always accounted for.
    """
    empty: list[str] = []
    for path in _record_design_pdf_files():
        relative = path.relative_to(_RECORD_DESIGN_ROOT)
        if relative in _NON_FIELD_ROW_CORPUS_PDFS:
            continue
        try:
            extraction = extract_record_design(path)
        except Exception:  # noqa: S112 - an unreadable design is the sibling gate's subject, not this one's
            continue
        if sum(len(sheet.fields) for sheet in extraction.sheets):
            continue
        if extraction.is_complete or not extraction.skipped:
            empty.append(str(relative))
    assert not empty, (
        "designs yielding no fields while reporting a complete read: "
        + ", ".join(empty)
        + " -- an empty read is trivially contiguous, so nothing else can catch it"
    )
