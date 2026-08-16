"""Tests for read-only AEAT record-design PDF extraction."""

from __future__ import annotations

import inspect
import itertools
import subprocess
import sys
from pathlib import Path

import pytest

from .....core import DirectoryEntryKind, scan_directory
from .. import (
    RecordDesignCompositeRelativeClosing,
    RecordDesignRelativeSuffixMarker,
    RegistryValidationError,
    extract_record_design,
    resolve_record_design_binary,
)
from .. import _record_design as record_design_module
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

_WorkbookCell = str | int | None
_WorkbookRow = tuple[_WorkbookCell, ...]

_MODELO_303_DESIGNS = (
    ("aeat-dr-303-2023", 406),
    ("aeat-dr-303-2024-early", 406),
    ("aeat-dr-303-2024-late", 426),
    ("aeat-dr-303-2025", 429),
    ("aeat-dr-303-2026", 430),
)
_MODELO_220_DESIGNS = (
    ("aeat-dr-220-2023", 2023, "2023"),
    ("aeat-dr-220-2024", 2024, "2024"),
    ("aeat-dr-220-2025", 2025, "2025"),
)
_M220_COMPOSITE_CLOSING_ROWS: tuple[_WorkbookRow, ...] = (
    (15, "***", 3, "An", "Constante", None, "</T"),
    (16, "***", 3, "An", "Modelo", None, "220"),
    (17, "***", 1, "An", "Discriminente", None, "(*)[A|E|I|0]"),
    (18, "***", 4, "An", "Ejercicio de devengo", None, None),
    (19, "***", 2, "An", "Período", None, "0A"),
    (20, "***", 5, "An", "Constante", None, "0000>"),
)


def test_modelo_200_workbook_recovers_source_declared_totals_and_variable_envelope() -> None:
    """The pinned binary, rather than terminal inference, owns totals and composition."""
    _modelo, catalogues = _committed_registry_tree()
    source = catalogues.sources["aeat-dr-200-2025"]
    workbook_path = bundled_path() / source.corpus_path
    declared_totals, formula_anchors = _official_total_rows(workbook_path)

    assert declared_totals
    assert formula_anchors["DP200001"] == ("A119", "C119", "=SUM(C6:C118)", 627)
    assert formula_anchors["DP200DID"] == ("A49", "C49", "=SUM(C6:C48)", 774)

    parsed = {sheet.name: sheet for sheet in extract_record_design(workbook_path).accept_partial()}
    assert set(declared_totals) == {name for name, sheet in parsed.items() if sheet.total_positions is not None}
    for name, declared_total in declared_totals.items():
        sheet = parsed[name]
        terminal_extent = max(field.offset + field.length - 1 for field in sheet.fields)
        assert sheet.total_positions == declared_total == terminal_extent

    envelope_sheet = parsed["DP200000"]
    envelope = envelope_sheet.variable_envelope
    assert envelope_sheet.total_positions is None
    assert envelope is not None
    assert isinstance(envelope.closing, RecordDesignRelativeSuffixMarker)
    assert envelope.prefix_extent == 328
    assert max(field.offset + field.length - 1 for field in envelope.prefix_fields) == 328
    assert (envelope.body.row, envelope.body.offset, envelope.body.length) == (14, 329, "Variable")
    assert (
        envelope.closing.row,
        envelope.closing.offset,
        envelope.closing.length,
    ) == (15, "***", 18)
    assert (
        envelope.variable_total.row,
        envelope.variable_total.label,
        envelope.variable_total.length,
    ) == (16, "total", "Variable")


@pytest.mark.parametrize(("source_ref", "expected_field_count"), _MODELO_303_DESIGNS)
def test_modelo_303_workbooks_recognise_the_official_variable_envelope_shape(
    source_ref: str,
    expected_field_count: int,
) -> None:
    """Every pinned M303 binary owns the same explicit DP30300 composition."""
    _modelo, catalogues = _committed_registry_tree()
    source = catalogues.sources[source_ref]

    parsed = extract_record_design(bundled_path() / source.corpus_path).accept_partial()
    fixed = tuple(sheet for sheet in parsed if sheet.variable_envelope is None)
    envelopes = tuple(sheet.variable_envelope for sheet in parsed if sheet.variable_envelope is not None)

    assert len(parsed) == 7
    assert len(fixed) == 6
    assert sum(len(sheet.fields) for sheet in parsed) == expected_field_count
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope is not None
    assert isinstance(envelope.closing, RecordDesignRelativeSuffixMarker)
    assert envelope.name == "DP30300"
    assert envelope.prefix_extent == 328
    assert (envelope.body.row, envelope.body.ordinal, envelope.body.offset, envelope.body.length) == (
        19,
        14,
        329,
        "Variable",
    )
    assert (
        envelope.closing.row,
        envelope.closing.ordinal,
        envelope.closing.offset,
        envelope.closing.length,
    ) == (20, 15, "***", 18)
    assert (
        envelope.variable_total.row,
        envelope.variable_total.label,
        envelope.variable_total.length,
    ) == (21, "total", "Variable")


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch"), _MODELO_220_DESIGNS)
def test_modelo_220_workbooks_preserve_the_exact_composite_relative_closing(
    source_ref: str,
    filing_year: int,
    design_epoch: str,
) -> None:
    """Each SHA-bound M220 design retains all six official closing rows."""
    _modelo, catalogues = _committed_registry_tree()
    resolved = resolve_record_design_binary(
        bundled_path(),
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )

    parsed = extract_record_design(resolved.path).accept_partial()
    envelopes = tuple(sheet.variable_envelope for sheet in parsed if sheet.variable_envelope is not None)

    assert resolved.source.sha256 == catalogues.sources[source_ref].sha256
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope is not None
    assert envelope.name == "T220000000"
    assert envelope.prefix_extent == 328
    assert (envelope.body.row, envelope.body.ordinal, envelope.body.offset, envelope.body.length) == (
        19,
        14,
        329,
        "Variable",
    )
    assert isinstance(envelope.closing, RecordDesignCompositeRelativeClosing)
    assert tuple(
        (part.row, part.ordinal, part.offset, part.length, part.type_code, part.content)
        for part in envelope.closing.parts
    ) == (
        (20, 15, "***", 3, "An", "</T"),
        (21, 16, "***", 3, "An", "220"),
        (22, 17, "***", 1, "An", "(*)[A|E|I|0]"),
        (23, 18, "***", 4, "An", None),
        (24, 19, "***", 2, "An", "0A"),
        (25, 20, "***", 5, "An", "0000>"),
    )
    assert (envelope.variable_total.row, envelope.variable_total.length) == (26, "Variable")


def test_variable_envelope_recognition_has_no_record_name_selector() -> None:
    """The parser recognises official composition markers, never a known tab name."""
    source = inspect.getsource(record_design_module._extract_sheet_rows)

    assert "DP200000" not in source
    assert "DP30300" not in source
    assert "T220000000" not in source


def test_workbook_declared_total_must_equal_terminal_parsed_extent(tmp_path: Path) -> None:
    """A cached official total that disagrees with parsed geometry refuses the sheet."""
    from openpyxl import Workbook

    path = tmp_path / "mismatched-total.xlsx"
    workbook = Workbook()
    worksheet = workbook.worksheets[0]
    worksheet.title = "Fixed"
    worksheet.append(("Nº", "Posic.", "Lon", "Tipo", "Descripción"))
    worksheet.append((1, 1, 2, "An", "First"))
    worksheet.append(("Total:", None, 3, None, None))
    workbook.save(path)
    workbook.close()

    with pytest.raises(RegistryValidationError, match="declares 3 total positions but parsed fields fill 2"):
        extract_record_design(path)


def test_workbook_total_recovery_accepts_only_official_labels_and_positive_integers(tmp_path: Path) -> None:
    """Punctuation variants and non-positive values do not become declared totals."""
    from openpyxl import Workbook

    path = tmp_path / "total-labels.xlsx"
    workbook = Workbook()
    labels = (
        ("Total", " Total ", 2),
        ("TotalColon", "Total:", 2),
        ("SpacedColon", "Total :", 2),
        ("NonPositive", "Total:", 0),
    )
    for index, (sheet_name, label, declared) in enumerate(labels):
        worksheet = workbook.worksheets[0] if index == 0 else workbook.create_sheet()
        worksheet.title = sheet_name
        worksheet.append(("Nº", "Posic.", "Lon", "Tipo", "Descripción"))
        worksheet.append((1, 1, 2, "An", "First"))
        worksheet.append((label, None, declared, None, None))
    workbook.save(path)
    workbook.close()

    parsed = {sheet.name: sheet.total_positions for sheet in extract_record_design(path).accept_partial()}
    assert parsed == {
        "Total": 2,
        "TotalColon": 2,
        "SpacedColon": None,
        "NonPositive": None,
    }


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, 330, "Variable", "An", "Second body", None, None),
                (4, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "duplicate variable-body markers",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
                (4, "***", 2, "An", "Second suffix", None, "CRLF"),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "incomplete or ambiguous relative closing",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
                ("Total", None, "Variable", None, None, None, None),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "duplicate variable totals",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                ("Total", None, 328, None, None, None, None),
                ("Total", None, 328, None, None, None, None),
            ),
            "duplicate fixed totals",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
                ("Total", 328, "Variable", None, None, None, None),
            ),
            "mixes fixed and variable totals",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                ("Total", 328, "Variable", None, None, None, None),
            ),
            "mixes fixed and variable totals",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                ("Total:", 328, "Variable", None, None, None, None),
            ),
            "mixes fixed and variable totals",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
                ("Total", None, 328, None, None, None, None),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "mixes fixed-total and variable-envelope geometry",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "incomplete variable-envelope composition",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
            ),
            "incomplete variable-envelope composition",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (None, 329, "Variable", "An", "Malformed variable body", None, None),
            ),
            "malformed variable-envelope marker in row 3",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, "***", 17, "An", "Wrong-length closing suffix", None, '"</T200"'),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "incomplete or ambiguous relative closing",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 329, "Variable", "An", "Variable body", None, None),
                (3, "***", 17, "An", "Wrong-length closing suffix", None, '"</T200"'),
                ("Total", None, 328, None, None, None, None),
            ),
            "incomplete variable-envelope composition",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (2, 330, "Variable", "An", "Variable body", None, None),
                (3, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "variable body starts at 330 after fixed prefix extent 328",
        ),
        (
            (
                (1, 1, 328, "An", "Fixed prefix", None, None),
                (3, "***", 18, "An", "Closing suffix", None, '"</T200>"'),
                (2, 329, "Variable", "An", "Variable body", None, None),
                ("Total", None, "Variable", None, None, None, None),
            ),
            "misordered variable-envelope composition markers",
        ),
    ),
)
def test_variable_envelope_rejects_malformed_composition(
    tmp_path: Path,
    rows: tuple[_WorkbookRow, ...],
    message: str,
) -> None:
    """Malformed composition markers refuse through the production workbook parser."""
    from openpyxl import Workbook

    path = tmp_path / "malformed-envelope.xlsx"
    workbook = Workbook()
    worksheet = workbook.worksheets[0]
    worksheet.title = "VARIABLE-ENVELOPE"
    worksheet.append(("Nº", "Posic.", "Lon", "Tipo", "Descripción", "Validación", "Contenido"))
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()

    with pytest.raises(RegistryValidationError, match=message):
        extract_record_design(path)


@pytest.mark.parametrize(
    ("closing_rows", "message"),
    (
        (_M220_COMPOSITE_CLOSING_ROWS[:-1], "incomplete or ambiguous relative closing"),
        (
            (*_M220_COMPOSITE_CLOSING_ROWS, (21, "***", 1, "An", "Duplicate", None, "!")),
            "incomplete or ambiguous relative closing",
        ),
        (
            (
                _M220_COMPOSITE_CLOSING_ROWS[0],
                _M220_COMPOSITE_CLOSING_ROWS[2],
                _M220_COMPOSITE_CLOSING_ROWS[1],
                *_M220_COMPOSITE_CLOSING_ROWS[3:],
            ),
            "malformed composite relative closing",
        ),
        (
            (
                *_M220_COMPOSITE_CLOSING_ROWS[:4],
                (19, "***", 2, "An", "Período", None, "1T"),
                _M220_COMPOSITE_CLOSING_ROWS[5],
            ),
            "malformed composite relative closing",
        ),
    ),
)
def test_modelo_220_composite_relative_closing_refuses_incomplete_duplicate_reordered_or_ambiguous_rows(
    tmp_path: Path,
    closing_rows: tuple[_WorkbookRow, ...],
    message: str,
) -> None:
    """The six-row contract fails closed without joining or defaulting parts."""
    from openpyxl import Workbook

    path = tmp_path / "malformed-m220-composite.xlsx"
    workbook = Workbook()
    worksheet = workbook.worksheets[0]
    worksheet.title = "OFFICIAL-SHAPE"
    worksheet.append(("Nº", "Posic.", "Lon", "Tipo", "Descripción", "Validación", "Contenido"))
    worksheet.append((13, 1, 328, "An", "Fixed prefix", None, None))
    worksheet.append((14, 329, "Variable", "An", "Variable body", None, None))
    for row in closing_rows:
        worksheet.append(row)
    worksheet.append(("Total", None, "Variable", None, None, None, None))
    workbook.save(path)
    workbook.close()

    with pytest.raises(RegistryValidationError, match=message):
        extract_record_design(path)


def test_closing_and_variable_total_without_a_body_do_not_reclassify_a_fixed_record(tmp_path: Path) -> None:
    """Partial marker facts remain non-envelope facts unless a body or mixed total is present."""
    from openpyxl import Workbook

    path = tmp_path / "partial-marker-fixed-record.xlsx"
    workbook = Workbook()
    worksheet = workbook.worksheets[0]
    worksheet.title = "FIXED"
    worksheet.append(("Nº", "Posic.", "Lon", "Tipo", "Descripción", "Validación", "Contenido"))
    worksheet.append((1, 1, 328, "An", "Fixed record", None, None))
    worksheet.append((2, "***", 18, "An", "Relative marker", None, "</T200020250A0000>"))
    worksheet.append(("Total", None, "Variable", None, None, None, None))
    worksheet.append(("Total", None, 328, None, None, None, None))
    workbook.save(path)
    workbook.close()

    parsed = extract_record_design(path).accept_partial()

    assert len(parsed) == 1
    assert parsed[0].total_positions == 328
    assert parsed[0].variable_envelope is None


@pytest.mark.parametrize(
    ("sheet_name", "rows", "message"),
    (
        (
            "FixedStartsLate",
            ((1, 2, 2, "An", "First"), ("Total", None, 3, None, None)),
            "has a gap before field at row 2: expected offset 1, got 2",
        ),
        (
            "FixedGap",
            ((1, 1, 2, "An", "First"), (2, 4, 2, "An", "Second"), ("Total", None, 5, None, None)),
            "has a gap before field at row 3: expected offset 3, got 4",
        ),
        (
            "FixedOverlap",
            ((1, 1, 3, "An", "First"), (2, 3, 2, "An", "Second"), ("Total", None, 4, None, None)),
            "has an overlap before field at row 3: expected offset 4, got 3",
        ),
        (
            "VariableOverlap",
            (
                (1, 1, 200, "An", "Prefix one"),
                (2, 200, 129, "An", "Overlapping prefix"),
                (3, 329, "Variable", "An", "Variable body"),
                (4, "***", 18, "An", "Closing suffix"),
                ("Total", None, "Variable", None, None),
            ),
            "has an overlap before field at row 3: expected offset 201, got 200",
        ),
        (
            "VariableGap",
            (
                (1, 1, 199, "An", "Prefix one"),
                (2, 201, 128, "An", "Discontinuous prefix"),
                (3, 329, "Variable", "An", "Variable body"),
                (4, "***", 18, "An", "Closing suffix"),
                ("Total", None, "Variable", None, None),
            ),
            "has a gap before field at row 3: expected offset 200, got 201",
        ),
    ),
)
def test_workbook_refuses_noncontiguous_fixed_and_variable_prefix_geometry(
    tmp_path: Path,
    sheet_name: str,
    rows: tuple[_WorkbookRow, ...],
    message: str,
) -> None:
    """Fixed sheets and envelope prefixes require exact source-order geometry."""
    from openpyxl import Workbook

    path = tmp_path / f"{sheet_name}.xlsx"
    workbook = Workbook()
    worksheet = workbook.worksheets[0]
    worksheet.title = sheet_name
    worksheet.append(("Nº", "Posic.", "Lon", "Tipo", "Descripción"))
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()

    with pytest.raises(RegistryValidationError, match=message):
        extract_record_design(path)


def _official_total_rows(
    workbook_path: Path,
) -> tuple[dict[str, int], dict[str, tuple[str, str, str, int]]]:
    """Read formula and cached views to retain the binary's exact total-row evidence."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    formula_book = load_workbook(workbook_path, read_only=True, data_only=False)
    cached_book = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        totals: dict[str, int] = {}
        anchors: dict[str, tuple[str, str, str, int]] = {}
        for formula_sheet in formula_book.worksheets:
            cached_sheet = cached_book[formula_sheet.title]
            for row_number, (formula_row, cached_row) in enumerate(
                zip(formula_sheet.iter_rows(values_only=True), cached_sheet.iter_rows(values_only=True), strict=True),
                start=1,
            ):
                if formula_row[0] != "Total:":
                    continue
                cached_index, cached_total = next(
                    (index, value)
                    for index, value in enumerate(cached_row[1:], start=1)
                    if isinstance(value, int) and not isinstance(value, bool) and value > 0
                )
                formula_value = formula_row[cached_index]
                assert isinstance(formula_value, str) and formula_value.startswith("=")
                totals[formula_sheet.title.strip()] = cached_total
                anchors[formula_sheet.title.strip()] = (
                    f"A{row_number}",
                    f"{get_column_letter(cached_index + 1)}{row_number}",
                    formula_value,
                    cached_total,
                )

        variable_formula = formula_book["DP200000"]
        variable_cached = cached_book["DP200000"]
        assert variable_formula["A16"].value == "Total"
        assert variable_cached["C16"].value == "Variable"
        return totals, anchors
    finally:
        formula_book.close()
        cached_book.close()


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

    field_row_pdfs = tuple(
        path for path in pdfs if path.relative_to(_RECORD_DESIGN_ROOT) not in _NON_FIELD_ROW_CORPUS_PDFS
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


def test_header_matching_ignores_an_abbreviating_full_stop_on_either_side() -> None:
    """A header token means the same thing with or without AEAT's trailing stop.

    Pinned as a PROPERTY rather than as the accepted string set, because the set
    is what went wrong: ``posic.`` and ``oblig.`` were enrolled with their stop
    and ``lon`` without, so Modelo 115 -- which writes ``Lon`` on one sheet and
    ``Lon.`` on the next, inside ONE workbook -- matched the first and missed the
    second. A test naming the literal spellings would have been satisfied by the
    broken set. This one fails for any token whose two spellings disagree.
    """
    for token in ("lon", "posic", "tipo", "descripcion", "oblig", "validacion", "contenido"):
        with_stop = record_design_module._optional_header_index((f"{token}.",), token)
        without_stop = record_design_module._optional_header_index((token,), token)
        assert with_stop == without_stop == 0, token
        # And the expected side may carry the stop just as the cell may.
        assert record_design_module._optional_header_index((token,), f"{token}.") == 0, token


def test_a_workbook_mixing_both_header_spellings_yields_every_sheet() -> None:
    """The real Modelo 115 binary: ``Lon`` on one sheet, ``Lon.`` on the other.

    The regression this locks is not a parse error -- it is a SILENT one. The
    body sheet was skipped for its header spelling, the remaining 13-field sheet
    was classified as an auxiliary envelope, and a healthy 1422-row design
    presented as carrying no record sheets at all.
    """
    design = scan_directory(
        _RECORD_DESIGN_ROOT / "modelo_115" / "files", pattern="*.xlsx", select=DirectoryEntryKind.FILES
    )[0]
    sheets = extract_record_design(design).accept_partial()

    assert len(sheets) == 2, [sheet.name for sheet in sheets]
    assert all(sheet.fields for sheet in sheets), {sheet.name: len(sheet.fields) for sheet in sheets}


def test_a_design_with_a_dropped_sheet_reports_the_read_as_partial() -> None:
    """A partial read must SAY it is partial -- the first half of the bite proof.

    Modelo 232 is the live case: its ``TABLAS`` tab is a legend -- two lookup
    tables of relationship-type and valuation-method codes (LIS art. 18.3/18.4)
    -- carrying no ``Posic.``/``Lon``/``Tipo``/``Contenido`` columns anywhere, so
    the header probe correctly finds nothing to parse there while the sheet's
    three genuine record pages (``DR23200``-``DR23202``) read cleanly. Modelo
    151's own nine header-shape-variant sheets were this test's specimen until
    the parser learned that second AEAT header shape (see
    ``test_a_second_recognised_header_shape_is_read_and_a_non_matching_sheet_still_skips``);
    now they parse, so this specimen moved to a sheet that is genuinely never
    going to become a record -- not a temporarily-unread one.

    Asserted on the PROPERTY -- some sheets read, some named as skipped, and the
    two disjoint -- rather than on the counts, which move whenever the header
    vocabulary widens or AEAT republishes.
    """
    design = (
        _RECORD_DESIGN_ROOT
        / "modelo_232"
        / "files"
        / "01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx"
    )
    assert design.is_file(), f"corpus anchor moved: {design}"

    extraction = extract_record_design(design)

    assert extraction.skipped, "Modelo 232 drops its TABLAS tab; a read that reports none is not seeing it"
    assert extraction.sheets, "some sheets do parse, so this must be a PARTIAL read rather than a refusal"
    assert extraction.is_complete is False
    assert not {sheet.name for sheet in extraction.sheets} & {item.name for item in extraction.skipped}
    assert all(item.reason for item in extraction.skipped), "a skipped sheet must say WHY it was skipped"

    with pytest.raises(RegistryValidationError, match="PARTIAL design"):
        extraction.require_complete()


def test_a_second_recognised_header_shape_is_read_and_a_non_matching_sheet_still_skips() -> None:
    """AEAT's real second header shape is read; a sheet matching neither shape still refuses.

    Modelo 151's nine annex sheets (``M15100000``, ``M15102000``-``M15109000``)
    title their description column with the sheet's own topical caption instead
    of the literal ``Descripción``, and carry no ``Validación`` column at all --
    a real published AEAT shape, not a parser defect. Resilience to it is
    permitted precisely because it is matched as specifically as the ordinary
    shape (``Com.`` present by its own recognised alias AND the very next
    column non-blank), never by relaxing the ordinary shape's own token match.

    Both directions are asserted: the nine sheets read with correct geometry
    (spot-checked against the raw workbook, not just "it parsed"), AND a sheet
    matching NEITHER shape -- no ``Descripción``, no ``Com.`` -- still skips.
    """
    design = _RECORD_DESIGN_ROOT / "modelo_151" / "files" / "01-151-ejercicio-2023-y-siguientes.xls"
    assert design.is_file(), f"corpus anchor moved: {design}"
    extraction = extract_record_design(design)

    annex_sheet_names = {f"M1510{n}000" for n in range(2, 10)} | {"M15100000"}
    read_names = {sheet.name for sheet in extraction.sheets}
    assert annex_sheet_names <= read_names, f"still skipped: {annex_sheet_names - read_names}"

    # Spot-check exact geometry against the raw workbook (row 6, sheet M15102000):
    # ``38.0, 480.0, 1.0, 'Num', 'Datos Adicionales...Situación [13]'`` verified directly.
    m15102000 = next(sheet for sheet in extraction.sheets if sheet.name == "M15102000")
    first = m15102000.fields[0]
    assert (first.ordinal, first.offset, first.length, first.type_code) == ("1", 1, 2, "An")
    assert "Inicio del identificador de modelo y p" in (first.description or "")
    last = m15102000.fields[-1]
    assert (last.offset, last.length, last.type_code) == (1089, 12, "An")
    assert last.description == "Indicador de fin de registro"

    # Negative case: a header row with NEITHER "Descripcion" NOR "Com." must still refuse,
    # proving Shape B did not widen the match rather than add a second one.
    no_shape_match = record_design_module._probe_header_row(
        ("Nº", "Posic.", "Lon", "Tipo", "Contenido"),
        1,
        label="test",
        sheet_name="test",
        header_corrections={},
    )
    assert no_shape_match is None, "a header with no description column and no 'Com.' column must not match"

    # Negative case: "Com." present but the following column is blank -- no caption to
    # treat as the description -- must also still refuse.
    blank_caption = record_design_module._probe_header_row(
        ("Nº", "Posic.", "Lon", "Tipo", "Com.", None, "Contenido"),
        1,
        label="test",
        sheet_name="test",
        header_corrections={},
    )
    assert blank_caption is None, "a 'Com.' column followed by a blank cell must not match Shape B"


def test_a_declared_header_cell_correction_is_read_and_an_undeclared_blank_column_still_refuses() -> None:
    """A declared header correction recovers a design; an undeclared one still skips.

    Modelo 100's ``100-03`` sheet (2015 and 2016 editions, both containers) is
    the live case: AEAT's own length-column header cell is a whitespace-only
    string, not the literal word ``Long.``/``Lon`` -- confirmed by cross-year
    comparison against the 2017 edition's identical cell. The correction fires
    ONLY because a sidecar declares it for this exact sheet, row and column;
    without one, the same blank cell must still refuse (proven with a
    synthetic row carrying no declared correction).
    """
    design = _RECORD_DESIGN_ROOT / "modelo_100" / "files" / "20-100-ejercicio-2015-1-75-mb-xls.xlsx"
    assert design.is_file(), f"corpus anchor moved: {design}"
    extraction = extract_record_design(design)

    assert not extraction.skipped, f"still skipped: {[item.name for item in extraction.skipped]}"
    header_corrections = [c for c in extraction.corrections if c.kind == "header_cell"]
    assert len(header_corrections) == 1
    correction = header_corrections[0]
    assert (correction.sheet, correction.header_row, correction.column_index, correction.column_role) == (
        "100-03",
        5,
        2,
        "length",
    )

    # Spot-check exact geometry against the raw workbook, sheet 100-03:
    sheet = next(item for item in extraction.sheets if item.name == "100-03")
    assert len(sheet.fields) == 54
    first = sheet.fields[0]
    assert (first.ordinal, first.offset, first.length, first.type_code) == ("1", 1, 2, "An")
    assert first.description == "Inicio del identificador de modelo y página."
    last = sheet.fields[-1]
    assert (last.ordinal, last.offset, last.length, last.type_code) == ("54", 630, 2, "An")

    # Negative case: the identical blank-length-column shape with NO declared correction
    # must still refuse -- proving the sidecar is load-bearing, not a fallback default.
    undeclared = record_design_module._probe_header_row(
        ("Nº", "Posic.", "", "Tipo", "Descripción", "Validación", "Contenido"),
        5,
        label="test",
        sheet_name="100-03",
        header_corrections={},
    )
    assert undeclared is None, "a blank length-column cell with no declared correction must not match"


def test_a_design_read_in_full_reports_complete_and_hands_over_its_sheets() -> None:
    """The other half, and the one that matters more.

    2,458 of the corpus's 2,803 workbook sheets read cleanly today. If completeness
    reporting were wrong in the permissive direction it would be caught by the test
    above; wrong in the strict direction it would make every complete design refuse,
    which is the more expensive failure and the easier one to ship unnoticed.
    """
    design = scan_directory(
        _RECORD_DESIGN_ROOT / "modelo_115" / "files", pattern="*.xlsx", select=DirectoryEntryKind.FILES
    )[0]
    extraction = extract_record_design(design)

    assert extraction.skipped == ()
    assert extraction.is_complete is True
    assert extraction.require_complete() == extraction.sheets
    assert extraction.require_complete() == extraction.accept_partial()


def test_every_sheet_of_a_source_is_either_read_or_named_as_skipped() -> None:
    """Nothing may fall between the two lists -- the anti-vacuity guard.

    A completeness notion that under-counts the container is worse than none: it
    reports ``is_complete`` on a design whose sheets it never enumerated. This
    reads the container's OWN sheet listing, independently of the extractor, and
    requires every sheet to appear on exactly one side of the result.
    """
    from openpyxl import load_workbook

    design = scan_directory(
        _RECORD_DESIGN_ROOT / "modelo_232" / "files", pattern="*.xlsx", select=DirectoryEntryKind.FILES
    )[0]
    workbook = load_workbook(design, read_only=True, data_only=True)
    try:
        present = {worksheet.title.strip() for worksheet in workbook.worksheets}
    finally:
        workbook.close()

    extraction = extract_record_design(design)
    accounted = {sheet.name for sheet in extraction.sheets} | {item.name for item in extraction.skipped}

    assert accounted == present, (
        "every sheet the container holds must be either read or named as skipped; "
        f"unaccounted: {sorted(present - accounted)}, invented: {sorted(accounted - present)}"
    )


def test_a_truncated_header_spelling_names_the_same_column() -> None:
    """``Lon``, ``Lon.``, ``Long.`` and ``Longitud`` are one column, not four.

    The unit half of the truncation rule. Pinned on the RELATION rather than on a
    list of accepted spellings: a test naming the spellings would be satisfied by
    an enrolled set, which is the design this replaced and which went silent again
    the moment AEAT wrote a spelling nobody had enrolled.
    """
    for spelling in ("lon", "lon.", "long", "long.", "longitud"):
        assert record_design_module._optional_header_index((spelling,), "lon") == 0, spelling

    # The floor: a token under three characters may not prefix-match a column.
    assert record_design_module._optional_header_index(("n",), "no") is None
    assert record_design_module._optional_header_index(("lo",), "lon") is None
    # And an unrelated column is still not matched, however long it is.
    assert record_design_module._optional_header_index(("contenido",), "lon") is None
    assert record_design_module._optional_header_index(("descripcion",), "tipo") is None


def test_the_truncation_rule_recovers_a_sheet_that_was_silently_dropped() -> None:
    """Modelo 714 spells its length column two ways and lost a sheet to it.

    The corpus half. Eleven body sheets head the column ``Lon`` and the twelfth
    heads it ``Long.``, so that sheet failed header detection and was dropped --
    silently, because eleven others survived. This asserts the design now reads
    COMPLETE, which is the property; the sheet count is checked as "more than the
    survivors" rather than pinned, so a republished design cannot make it vacuous.
    """
    design = _RECORD_DESIGN_ROOT / "modelo_714" / "files" / "DR714_2025.xls"
    assert design.is_file(), f"corpus anchor moved: {design}"

    extraction = extract_record_design(design)

    assert extraction.is_complete, (
        f"Modelo 714 still drops {[item.name for item in extraction.skipped]}; the length column "
        "on its header sheet is spelled 'Long.' where its body sheets spell it 'Lon'"
    )
    assert len(extraction.sheets) > 11


def test_a_declared_end_of_record_terminator_is_separated_and_kept() -> None:
    """The closing identifies the record; the CRLF row ends the line.

    Thirty bundled designs across eight modelos declare both as adjacent
    relative-offset rows, and the closing recogniser -- which accepted one suffix of
    length 18 or exactly six -- refused every one. They were not exotic: each is the
    ordinary 18-byte identifier followed by a row AEAT labels ``Fin de Registro.
    Constante CRLF``.

    The assertion that matters is the second one. Separating the terminator makes
    them parse; KEEPING it is what stops that being a clean-looking wrong answer,
    because those two bytes are part of the record and a parse that drops them
    understates every record built from it.
    """
    design = _RECORD_DESIGN_ROOT / "modelo_100" / "files" / "20-100-ejercicio-2015-1-75-mb-xls.xlsx"
    assert design.is_file(), f"corpus anchor moved: {design}"

    envelopes = [sheet.variable_envelope for sheet in extract_record_design(design).accept_partial()]
    envelope = next(item for item in envelopes if item is not None)

    assert envelope.closing.length == 18, "the closing identifier must remain the closing identifier"
    assert envelope.terminator is not None, (
        "the end-of-record row was consumed instead of kept; its two bytes are part of the record"
    )
    assert envelope.terminator.length == 2
    assert "fin de registro" in envelope.terminator.description.casefold()


def test_a_two_byte_closing_part_that_is_not_a_terminator_is_not_peeled() -> None:
    """The split matches the declared MEANING, never the length alone.

    A two-byte relative suffix is not automatically a line terminator -- the Modelo
    220 composite closing carries a two-byte ``0A`` part that is genuinely part of
    the record identifier. Peeling on width would silently truncate that closing and
    reclassify a real identifier component as physical padding.
    """
    from .._record_design import _split_record_terminator
    from .._record_design_schema import RecordDesignRelativeSuffixMarker

    def suffix(length: int, description: str, ordinal: int) -> RecordDesignRelativeSuffixMarker:
        return RecordDesignRelativeSuffixMarker(
            sheet="S",
            row=ordinal,
            ordinal=ordinal,
            offset="***",
            length=length,
            type_code="An",
            description=description,
        )

    identifier_part = suffix(2, "Periodo. Constante 0A", 2)
    kept, terminator = _split_record_terminator([suffix(18, "Constante. </T...>", 1), identifier_part])
    assert terminator is None, "a two-byte identifier component was mistaken for a line terminator"
    assert len(kept) == 2

    real = suffix(2, "Fin de Registro. Constante CRLF (Hexadecimal 0D0A)", 2)
    kept, terminator = _split_record_terminator([suffix(18, "Constante. </T...>", 1), real])
    assert terminator is real
    assert len(kept) == 1


def test_a_terminator_that_does_not_come_last_is_refused() -> None:
    """A terminator that is not last is not a terminator.

    Without this the split would accept a line-terminator row appearing anywhere in
    the closing and quietly reorder the record's tail. Refusing is right: a design
    declaring it early is either malformed or has been misread, and rearranging it
    would hide both.
    """
    from .._record_design import _require_terminator_closes_the_record
    from .._record_design_schema import RecordDesignRelativeSuffixMarker

    def suffix(ordinal: int, length: int, description: str) -> RecordDesignRelativeSuffixMarker:
        return RecordDesignRelativeSuffixMarker(
            sheet="S",
            row=ordinal,
            ordinal=ordinal,
            offset="***",
            length=length,
            type_code="An",
            description=description,
        )

    closing = (suffix(9, 18, "Constante. </T...>"),)
    _require_terminator_closes_the_record("S", closing, suffix(10, 2, "Fin de Registro. CRLF"))
    with pytest.raises(RegistryValidationError, match="not last is not a terminator"):
        _require_terminator_closes_the_record("S", closing, suffix(8, 2, "Fin de Registro. CRLF"))


def test_a_design_declaring_no_terminator_does_not_acquire_one() -> None:
    """THE INVERSE FALSE GREEN: peeling is conditional on the row being declared.

    A design closing with a bare 18-byte identifier and no CRLF row must parse with
    no terminator and an unchanged record tail. If the split ever fired on the
    closing merely LOOKING like it wants a terminator, every such design would
    silently gain two bytes it does not have -- the same defect as dropping two
    bytes, with the sign reversed, and equally invisible.

    Modelo 303's current design is the anchor: it declares the same DP30300
    variable envelope as the older editions that DO carry a terminator, so the two
    differ in exactly the thing under test.
    """
    design = (
        _RECORD_DESIGN_ROOT
        / "modelo_303"
        / "files"
        / "01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx"
    )
    assert design.is_file(), f"corpus anchor moved: {design}"

    extraction = extract_record_design(design)
    assert extraction.is_complete
    envelope = next(sheet.variable_envelope for sheet in extraction.sheets if sheet.variable_envelope is not None)

    assert envelope.terminator is None, (
        "a design that declares no end-of-record row acquired one; peeling must be conditional "
        "on the row being present, never inferred from the closing's shape"
    )
    assert envelope.closing.length == 18


def test_the_workbook_and_pdf_parsers_share_one_notion_of_a_crlf_row() -> None:
    """One concept, one home -- the two parsers may not drift on the same fact.

    They already had. The PDF compact-row recogniser has known the end-of-record row
    since it was written; the workbook closing recogniser refused thirty designs
    across eight modelos for declaring one. Two private spellings of a single domain
    fact is what let that divergence stand, so the PDF pattern now composes the
    shared phrase rather than restating it.

    Asserted by composition, not by equality of behaviour: this fails if either side
    grows its own copy.
    """
    assert record_design_module._RECORD_TERMINATOR_PHRASE in record_design_module._COMPACT_PDF_CRLF_ROW_RE.pattern
    assert record_design_module._RECORD_TERMINATOR.pattern == record_design_module._RECORD_TERMINATOR_PHRASE

    # Every wording the shared phrase claims to cover must actually match, so a
    # dead alternative cannot hide behind a live one. The bare-CRLF spelling was
    # dead for exactly this reason before this test existed.
    for wording in ("Fin de Registro. Constante CRLF", "Salto de linea. CRLF", "Salto de línea. CRLF"):
        assert record_design_module._RECORD_TERMINATOR.search(wording), wording
    assert not record_design_module._RECORD_TERMINATOR.search("Periodo. Constante 0A")


def test_envelope_composition_order_is_checked_by_source_position_not_by_ordinal() -> None:
    """Removing the ordinal comparison must not remove the coverage it appeared to give.

    The envelope-order check asserted composition order twice, on source row and on
    ordinal, and the ordinal half asserted nothing the row half did not. Deleting a
    redundant assertion is only safe if the survivor still bites, so every
    misordering the pair used to catch is exercised here against the row check
    alone.

    Why the ordinal half had to go rather than be made string-safe: AEAT's ordinal
    is a PRINTED LABEL, not an arithmetic value -- it publishes ``14bis`` to insert
    a field between 14 and 15 without renumbering. Ordering by it assumes a density
    the authority never promised, and a string ordering would place ``2`` after
    ``10`` by construction.
    """
    from .._record_design import _require_ordered_variable_envelope
    from .._record_design_schema import (
        RecordDesignField,
        RecordDesignRelativeSuffixMarker,
        RecordDesignVariableBodyMarker,
        RecordDesignVariableTotalMarker,
    )

    def field(row: int) -> RecordDesignField:
        return RecordDesignField(sheet="S", row=row, ordinal="1", offset=1, length=1, type_code="An", description="d")

    def body(row: int) -> RecordDesignVariableBodyMarker:
        return RecordDesignVariableBodyMarker(
            sheet="S", row=row, ordinal=2, offset=2, length="Variable", type_code="An", description="d"
        )

    def closing(row: int) -> RecordDesignRelativeSuffixMarker:
        return RecordDesignRelativeSuffixMarker(
            sheet="S", row=row, ordinal=3, offset="***", length=18, type_code="An", description="d"
        )

    def total(row: int) -> RecordDesignVariableTotalMarker:
        return RecordDesignVariableTotalMarker(sheet="S", row=row, label="total", length="Variable")

    _require_ordered_variable_envelope("S", [field(10)], body(11), (closing(12),), total(13))

    for label, args in (
        ("body before the fixed prefix", ([field(11)], body(10), (closing(12),), total(13))),
        ("closing before the body", ([field(10)], body(12), (closing(11),), total(13))),
        ("total before the closing", ([field(10)], body(11), (closing(12),), total(11))),
    ):
        with pytest.raises(RegistryValidationError, match="misordered variable-envelope"):
            _require_ordered_variable_envelope("S", *args)
            pytest.fail(f"{label} was accepted; the row check does not cover it")


def test_an_unnumbered_row_is_admitted_and_a_printed_label_is_admitted_verbatim() -> None:
    """The ordinal CELL decides, not the parse result -- both directions.

    AEAT leaves the ordinal blank for rows it declines to number: Modelo 036 writes
    one `Fecha de constitución` as three unnumbered rows for día, mes and año,
    sharing casilla ``[C71]``. Dropping them put their eight bytes into a downstream
    geometry gap whose message blamed the design.

    THE OTHER DIRECTION IS THE POINT THIS TEST NOW COVERS. ``ordinal`` is
    ``str | None`` precisely because AEAT's ordinal is a PRINTED LABEL, not an
    arithmetic value: Modelo 303 prints ``14bis`` beside its ``14`` to insert a
    field without renumbering. A ``14bis`` row is now admitted VERBATIM as its
    own peer field -- not absorbed into anything, not discarding the label -- and
    representable exactly as AEAT printed it, closing the gap the earlier,
    ``int``-typed ordinal could not represent.
    """
    root = _RECORD_DESIGN_ROOT
    unnumbered = (
        root / "modelo_036" / "files" / "04-036-ejercicio-2021-y-siguientes-actualizado-11-04-2023-106-kb-xlsx.xlsx"
    )
    printed_label = (
        root / "modelo_303" / "files" / "12-303-orden-hap-2373-2014-de-9-de-diciembre-ejercicio-2018-292-kb-xlsx.xlsx"
    )
    for path in (unnumbered, printed_label):
        assert path.is_file(), f"corpus anchor moved: {path}"

    extraction = extract_record_design(unnumbered)
    sheet = next(item for item in extraction.sheets if item.name == "Pag. 2C")
    unnumbered_fields = [item for item in sheet.fields if item.ordinal is None]
    assert unnumbered_fields, "the unnumbered rows are still being dropped"
    assert all("[C71]" in item.description for item in unnumbered_fields), (
        "the admitted unnumbered fields are not the shared-casilla group this covers"
    )
    # Their bytes are now part of the record rather than a phantom gap.
    assert {item.offset for item in unnumbered_fields} == {1294, 1296, 1298}

    # The other half: a row whose ordinal cell is NON-EMPTY is admitted verbatim as
    # its own peer field, `14bis` included -- no longer refused, and not absorbed
    # into `14` or `15` either (it is contiguous with, never nested inside, either).
    printed_extraction = extract_record_design(printed_label)
    printed_sheets = printed_extraction.require_complete()
    dp30303 = next(item for item in printed_sheets if item.name == "DP30303")
    fourteen = next(item for item in dp30303.fields if item.ordinal == "14")
    fourteen_bis = next(item for item in dp30303.fields if item.ordinal == "14bis")
    fifteen = next(item for item in dp30303.fields if item.ordinal == "15")
    assert fourteen_bis.components == ()
    assert "Reservado" in fourteen_bis.description
    # Contiguous with its neighbours, a genuine peer rather than a nested detail.
    assert fourteen.offset + fourteen.length == fourteen_bis.offset
    assert fourteen_bis.offset + fourteen_bis.length == fifteen.offset


def test_a_dotted_ordinal_is_absorbed_as_a_component_not_a_peer() -> None:
    """Modelo 576's ``19.1``..``19.8`` desglosa (break out) their parent's own span.

    THE DISCRIMINATOR IS CONJUNCTIVE, both conditions required together: a
    dotted ordinal's integer prefix must match the IMMEDIATELY PRECEDING field's
    own ordinal, AND its byte span must fall entirely inside that field's own
    already-declared offset/length. Neither condition alone is enough -- a
    coincidental prefix match elsewhere in the sheet must not absorb an
    unrelated field, and an in-span row with a non-matching prefix must not be
    silently swallowed either.

    ADDITIVE, NOT REPLACING: the parent's own ``offset``/``length`` continue to
    span the whole 40-byte group exactly as before components existed, so a
    consumer reading only ``offset``/``length`` -- the contiguity check, the IR
    projection -- sees exactly what it saw when these rows were still invisible.
    """
    root = _RECORD_DESIGN_ROOT
    path = root / "modelo_576" / "files" / "01-576-diseno-de-registro-vigente.xlsx"
    assert path.is_file(), f"corpus anchor moved: {path}"

    extraction = extract_record_design(path)
    sheets = extraction.require_complete()
    parent = next(item for sheet in sheets for item in sheet.fields if item.ordinal == "19")

    assert parent.offset == 514
    assert parent.length == 40
    assert [component.ordinal for component in parent.components] == [f"19.{n}" for n in range(1, 9)]
    # Zero remainder: the eight components exactly tile the parent's own span.
    assert parent.components[0].offset == parent.offset
    assert parent.components[-1].offset + parent.components[-1].length == parent.offset + parent.length
    for left, right in itertools.pairwise(parent.components):
        assert left.offset + left.length == right.offset, "components must themselves be contiguous"

    # A component is never counted as a top-level peer -- the outer sheet sees
    # only the parent at this position, exactly as before components existed.
    all_ordinals = [item.ordinal for sheet in sheets for item in sheet.fields]
    assert "19.1" not in all_ordinals


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
