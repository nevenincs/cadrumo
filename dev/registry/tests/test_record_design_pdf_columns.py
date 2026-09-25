"""Record-design PDF tables read Descripción, Validación and Contenido as columns."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ..compiler.record_design import extract_record_design_pdf
from ..compiler.record_design_pdf_orchestration import extract_record_design_pdf_stream
from ..compiler.record_design_schema import RecordDesignField
from ._record_design_support import _record_design_pdf

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Column starts of the synthetic table: ordinal, position, length, type,
#: description, validation, content.
_COLUMNS = (40.0, 60.0, 90.0, 112.0, 135.0, 410.0, 455.0)
_HEADER = ("Nº", "Posic.", "Lon", "Tipo", "Descripción", "Validación", "Contenido")


def _write_table(path: Path, lines: tuple[tuple[tuple[float, str], ...], ...]) -> None:
    """Draw each line as cells at explicit horizontal positions, like AEAT's tables."""
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica", 8)
    y = A4[1] - 36
    for cells in lines:
        for x, text in cells:
            pdf.drawString(x, y, text)
        y -= 10
    pdf.save()


def _row(*cells: str) -> tuple[tuple[float, str], ...]:
    return tuple((x, text) for x, text in zip(_COLUMNS, cells, strict=False) if text)


def _cells(fields: tuple[RecordDesignField, ...]) -> list[tuple[str, str | None, str | None]]:
    return [(field.description, field.validation, field.content) for field in fields]


def _read(path: Path) -> tuple[RecordDesignField, ...]:
    extraction = extract_record_design_pdf_stream(BytesIO(path.read_bytes()), source_label=path.name)
    (sheet,) = extraction.accept_partial()
    return sheet.fields


_HEADING = ((40.0, "Pág. 1 DISEÑO DE REGISTRO 25/03/2021"),)
_TABLE_HEADER = tuple(zip(_COLUMNS, _HEADER, strict=True))


def test_validation_and_content_columns_are_read_apart_from_the_description(tmp_path: Path) -> None:
    pdf_path = tmp_path / "columns.pdf"
    _write_table(
        pdf_path,
        (
            _HEADING,
            _TABLE_HEADER,
            _row("1", "1", "9", "An", "Inicio del identificador de modelo y página", "obligatorio", "<T999010>"),
            _row("2", "10", "1", "A", "Indicador de página complementaria", "", "blanco"),
            _row("3", "11", "2", "An", "Tipo de operación.", "obligatorio", '"P" Adquisición de'),
            _row("", "", "", "", "", "", "Bienes"),
            _row("4", "13", "5", "Num", "Reservado AEAT"),
            _row("5", "18", "10", "An", "Identificador de fin de registro.", "obligatorio", "</T999010>"),
        ),
    )

    assert _cells(_read(pdf_path)) == [
        ("Inicio del identificador de modelo y página", "obligatorio", "<T999010>"),
        ("Indicador de página complementaria", None, "blanco"),
        ("Tipo de operación.", "obligatorio", '"P" Adquisición de Bienes'),
        ("Reservado AEAT", None, None),
        ("Identificador de fin de registro.", "obligatorio", "</T999010>"),
    ]


def test_note_prose_below_the_table_is_not_the_closing_tag_rows_content(tmp_path: Path) -> None:
    pdf_path = tmp_path / "closing-notes.pdf"
    _write_table(
        pdf_path,
        (
            _HEADING,
            _TABLE_HEADER,
            _row("1", "1", "9", "An", "Inicio del identificador de modelo y página", "obligatorio", "<T999010>"),
            _row("2", "10", "10", "An", "Identificador de fin de registro.", "obligatorio", "</T999010>"),
            ((40.0, "TOTAL"), (90.0, "19 Posiciones")),
            ((34.0, "Nota 1"), (90.0, "Página 1, Campo 4. Se admitirán los siguientes valores: '0' normal.")),
            ((90.0, "'1' Presentación realizada en pruebas."),),
        ),
    )

    closing = _read(pdf_path)[-1]

    assert (closing.description, closing.validation, closing.content) == (
        "Identificador de fin de registro.",
        "obligatorio",
        "</T999010>",
    )


def test_a_row_interrupted_inside_the_table_keeps_its_parsed_text(tmp_path: Path) -> None:
    """Prose between two rows of one table does not end the table, so nothing is trimmed."""
    pdf_path = tmp_path / "interrupted.pdf"
    _write_table(
        pdf_path,
        (
            _HEADING,
            _TABLE_HEADER,
            _row("1", "1", "9", "An", "Inicio del identificador de modelo y página", "obligatorio", "<T999010>"),
            _row("2", "10", "1", "A", "Indicador de página complementaria", "", "blanco"),
            ((34.0, "Aviso"), (135.0, "texto intercalado")),
            _row("3", "11", "1", "A", "Tipo", "", '"C"'),
        ),
    )

    interrupted = _read(pdf_path)[1]

    assert interrupted.validation is None
    assert interrupted.content is not None
    assert "texto intercalado" in f"{interrupted.description} {interrupted.content}"


def test_prose_naming_a_description_and_its_content_is_not_a_table_header(tmp_path: Path) -> None:
    pdf_path = tmp_path / "prose.pdf"
    _write_table(
        pdf_path,
        (
            _HEADING,
            _TABLE_HEADER,
            _row("1", "1", "9", "An", "Inicio del identificador de modelo y página", "obligatorio", "<T999010>"),
            _row("2", "10", "10", "An", "Identificador de fin de registro.", "obligatorio", "</T999010>"),
            ((40.0, "TOTAL"), (90.0, "19 Posiciones")),
            ((34.0, "Nota 1"), (90.0, "Se deberá identificar la descripción del contenido del campo")),
        ),
    )

    closing = _read(pdf_path)[-1]

    assert closing.content == "</T999010>"


def test_modelo_360_constants_come_from_the_contenido_column() -> None:
    fields = {
        (sheet.name, field.ordinal): field
        for sheet in extract_record_design_pdf(_record_design_pdf("modelo_360", "orden-eha-789-2010")).accept_partial()
        for field in sheet.fields
    }

    assert _cells((fields["Pág. 1", "1"], fields["Pág. 1", "160"], fields["Pág. 2", "102"])) == [
        ("Inicio del identificador de modelo y página", "obligatorio", "<T360010>"),
        ("Identificador de fin de registro.", "obligatorio", "</T360010>"),
        ("Identificador de fin de registro.", "obligatorio", "</T360020>"),
    ]
    assert fields["Pág. 1", "3"].content == "000100"
    assert fields["Pág. 1", "114"].content == '"A" Solicitante "R" Representante'
    assert not [key for key, field in fields.items() if "obligatorio" in field.description]
