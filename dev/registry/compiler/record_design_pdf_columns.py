"""Development-only column geometry for PDF record-design tables.

Most PDF record designs print their rows as a table whose header names separate
``Descripción``, ``Validación`` and ``Contenido`` columns. The text layer the line
parser reads flattens every row into one string, so on a line the three cells
are indistinguishable: ``1 1 9 An Inicio del identificador de modelo y página
obligatorio <T360010>`` carries a description, a validation and a constant with
nothing separating them. The page itself does separate them -- each cell sits at
its own horizontal position under its own header -- and this module reads that
geometry so a field's cells can be taken from the columns AEAT printed them in.

The geometry is never trusted on its own. :func:`apply_pdf_column_cells` accepts
a row's cells only when their text, read in page order, is exactly the text the
line parser already attributed to the same field (see there), so this module
can redistribute a field's own words between its columns and trim prose printed
below the table, but it can never invent, move or drop a word of the table.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from typing import TYPE_CHECKING, Final

from cadrumo.core.text_fold import fold_diacritics
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev.registry.compiler.record_design_schema import RecordDesignField, RecordDesignSheet

from .record_design_pdf_rows import (
    clean_pdf_line,
    is_pdf_footer,
    is_pdf_page_heading,
    join_pdf_parts,
    pdf_page_name,
)

if TYPE_CHECKING:
    from pdfplumber.page import Page

#: A header line that declares a separate Contenido column. Checked on the flat
#: text first so only designs that print such a table pay for word geometry.
_COLUMN_HEADER_TEXT_RE: Final = re.compile(r"Descripci[oó]n\b.*\bContenido\b", re.IGNORECASE)

#: Words closer vertically than this belong to one printed line.
_LINE_TOLERANCE: Final = 2.0
#: How far right of its column boundary a left-aligned cell may begin. Cells in
#: the bundled designs start 0-5 points inside their boundary; a first word much
#: further right means the boundary was not read from this table's geometry.
_CELL_INDENT_LIMIT: Final = 12.0
#: A vertical rule must be at least this tall to be a column border.
_MIN_RULE_HEIGHT: Final = 4.0
_MAX_RULE_WIDTH: Final = 2.0

_ROW_KEY_TOKEN_RE: Final = re.compile(r"\d+")
#: The labels a record-design table header opens with: ``Nº Posic.``, ``NºPosic.``.
_TABLE_HEADER_LEAD_RE: Final = re.compile(r"^n[º°o]\s*posic")


@dataclass(frozen=True, slots=True)
class _Word:
    text: str
    x0: float
    x1: float
    top: float

    @property
    def centre(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass(frozen=True, slots=True)
class _ColumnLayout:
    """Where one table's description, validation and content columns begin."""

    description: float
    validation: float | None
    content: float

    def boundaries(self) -> tuple[float, ...]:
        return tuple(edge for edge in (self.description, self.validation, self.content) if edge is not None)


@dataclass(frozen=True, slots=True)
class PdfColumnRow:
    """One table row read from page geometry, keyed by the numbers that open it.

    ``key`` holds the leading integers of the row's first line -- ordinal,
    position and, where the design prints one, length. ``lead`` is any text left
    of the description column after the row's type token (a ``Com`` column, for
    instance), kept because the line parser has always read it as the start of
    the description. ``ended_by_table_end`` is set when prose printed below the
    table, not the next row, ended this row's cells.
    """

    key: tuple[int, ...]
    lead: tuple[str, ...]
    description: tuple[str, ...]
    validation: tuple[str, ...]
    content: tuple[str, ...]
    ended_by_table_end: bool
    reading_order: tuple[str, ...]


@dataclass(slots=True)
class _RowBuilder:
    key: tuple[int, ...]
    lead: list[str]
    layout: _ColumnLayout
    description: list[str] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)
    reading_order: list[str] = field(default_factory=list)
    valid: bool = True
    interrupted: bool = False

    def add_cells(self, words: Sequence[_Word]) -> None:
        for word in words:
            if _straddles(word, self.layout):
                self.valid = False
            self.reading_order.append(word.text)
            column = _column_of(word, self.layout)
            if column == "description":
                self.description.append(word.text)
            elif column == "validation":
                self.validation.append(word.text)
            else:
                self.content.append(word.text)
        for column in ("description", "content"):
            leftmost = min((word.x0 for word in words if _column_of(word, self.layout) == column), default=None)
            edge = self.layout.description if column == "description" else self.layout.content
            if leftmost is not None and not -1.0 <= leftmost - edge <= _CELL_INDENT_LIMIT:
                self.valid = False

    def finish(self, *, ended_by_table_end: bool) -> PdfColumnRow | None:
        if not self.valid:
            return None
        return PdfColumnRow(
            key=self.key,
            lead=tuple(self.lead),
            description=tuple(self.description),
            validation=tuple(self.validation),
            content=tuple(self.content),
            ended_by_table_end=ended_by_table_end,
            reading_order=(*self.lead, *self.reading_order),
        )


def _column_of(word: _Word, layout: _ColumnLayout) -> str:
    if word.centre >= layout.content:
        return "content"
    if layout.validation is not None and word.centre >= layout.validation:
        return "validation"
    return "description"


def _straddles(word: _Word, layout: _ColumnLayout) -> bool:
    """Whether a word crosses a column border, which no cell of a real table does."""
    return any(word.x0 < edge - 0.5 < word.x1 - 1.0 for edge in layout.boundaries())


def document_declares_column_table(lines: Iterable[str]) -> bool:
    """Whether any flat text line is a table header naming a Contenido column."""
    return any(_COLUMN_HEADER_TEXT_RE.search(line) for line in lines)


def extract_pdf_column_rows(pdf_bytes: bytes, *, source_label: str) -> tuple[PdfColumnRow, ...]:
    """Read every table row of a column-table record design from word geometry."""
    import pdfplumber

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages = tuple(_page_geometry(page) for page in pdf.pages)
    except Exception as exc:  # pragma: no cover - defensive; pdfplumber surface
        raise RegistryValidationError(
            f"pdfplumber could not open record-design PDF {source_label}: {exc}",
        ) from exc
    return _read_column_rows(pages)


def _page_geometry(page: Page) -> tuple[tuple[_Word, ...], tuple[tuple[float, float, float], ...]]:
    words = tuple(
        _Word(text=str(word["text"]), x0=float(word["x0"]), x1=float(word["x1"]), top=float(word["top"]))
        for word in page.extract_words()
    )
    rules = tuple(
        (float(shape["x0"]), float(shape["top"]), float(shape["bottom"]))
        for shape in (*page.rects, *page.lines, *page.curves)
        if float(shape["width"]) <= _MAX_RULE_WIDTH and float(shape["height"]) >= _MIN_RULE_HEIGHT
    )
    return words, rules


def _printed_lines(words: Sequence[_Word]) -> list[list[_Word]]:
    lines: list[list[_Word]] = []
    for word in sorted(words, key=lambda item: (item.top, item.x0)):
        if lines and word.top - lines[-1][0].top <= _LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda item: item.x0) for line in lines]


_HEADER_ABSENT: Final = "absent"
_HEADER_UNSUPPORTED: Final = "unsupported"


def _header_layout(
    line: Sequence[_Word],
    rules: Sequence[tuple[float, float, float]],
) -> _ColumnLayout | str:
    """Read a table header's column starts, or say the line is not a supported header.

    A header is supported only when Contenido is its LAST column. Designs that
    print a further column after it (``Uso``) have no field slot for that
    column's text, and their Contenido cells visibly overflow into it, so their
    rows are left to the line parser rather than split on an uncertain border.
    """
    texts = [fold_diacritics(word.text).lower() for word in line]
    description = next((index for index, text in enumerate(texts) if text.startswith("descripci")), None)
    content = next((index for index, text in enumerate(texts) if text == "contenido"), None)
    if description is None or content is None or not _TABLE_HEADER_LEAD_RE.match(" ".join(texts[:description])):
        # Prose mentions both words too ("la descripcion del contenido del
        # campo"); a table header opens with its ordinal and position labels.
        return _HEADER_ABSENT
    validation = next(
        (index for index, text in enumerate(texts) if text in {"validacion", "oblig.", "oblig"}),
        None,
    )
    if (
        content != len(line) - 1
        or content < description
        or (validation is not None and not description < validation < content)
    ):
        return _HEADER_UNSUPPORTED
    middle = line[0].top + 3.0
    borders = sorted(x for x, top, bottom in rules if top <= middle <= bottom)

    def column_start(label: _Word, floor: float) -> float:
        # A header label may be centred over its column, so the column's own
        # border, where the page draws one, is where its cells begin.
        drawn = [x for x in borders if floor < x <= label.x0 + 1.0]
        return drawn[-1] if drawn else label.x0 - 1.0

    description_start = column_start(line[description], line[description - 1].x1 if description else 0.0)
    validation_start = column_start(line[validation], line[validation - 1].x1) if validation is not None else None
    content_start = column_start(line[content], line[content - 1].x1)
    return _ColumnLayout(description=description_start, validation=validation_start, content=content_start)


def _row_key(lead: Sequence[_Word]) -> tuple[tuple[int, ...], tuple[str, ...]] | None:
    """Split a row-opening line's left cells into its numeric key and any extra lead text."""
    numbers: list[int] = []
    for word in lead:
        if len(numbers) == 3 or not _ROW_KEY_TOKEN_RE.fullmatch(word.text):
            break
        numbers.append(int(word.text))
    if len(numbers) < 2:
        return None
    rest = [word.text for word in lead[len(numbers) :]]
    # The first remaining token is the type cell; anything after it is text the
    # line parser has always read as the start of the description.
    return tuple(numbers), tuple(rest[1:])


def _is_page_furniture(line: Sequence[_Word]) -> bool:
    text = clean_pdf_line(" ".join(word.text for word in line))
    return is_pdf_footer(text) or is_pdf_page_heading(text) or pdf_page_name(text) is not None


def _read_column_rows(
    pages: Sequence[tuple[Sequence[_Word], Sequence[tuple[float, float, float]]]],
) -> tuple[PdfColumnRow, ...]:
    """Walk the pages' printed lines and return every row a column table defines.

    A row runs from the line that opens it (ordinal and position left of the
    description column) to the next such line. A line with text left of the
    description column that does NOT open a row -- ``TOTAL 3400 Posiciones``,
    ``Nota 1`` -- is prose below the table: the open row stops collecting there.
    Whether that stop was the table's real end is settled by what follows. If
    another row opens with no new header in between, the stop was not the end,
    so the stopped row is discarded; if text reaches the next header's table
    before any row opens, it may be the stopped row's continuation, so the
    stopped row is discarded too. Discarded rows are simply left to the line
    parser.
    """
    rows: list[PdfColumnRow] = []
    open_row: _RowBuilder | None = None
    closed_at_table_end: PdfColumnRow | None = None

    def close(builder: _RowBuilder, *, ended_by_table_end: bool) -> PdfColumnRow | None:
        finished = builder.finish(ended_by_table_end=ended_by_table_end)
        if finished is not None:
            rows.append(finished)
        return finished

    for words, rules in pages:
        layout: _ColumnLayout | None = None
        for line in _printed_lines(words):
            header = _header_layout(line, rules)
            if header != _HEADER_ABSENT:
                layout = header if isinstance(header, _ColumnLayout) else None
                if open_row is not None and layout is not None and not open_row.interrupted:
                    open_row.layout = layout
                elif open_row is not None:
                    ended = close(open_row, ended_by_table_end=open_row.interrupted and layout is not None)
                    closed_at_table_end = ended if open_row.interrupted else None
                    open_row = None
                continue
            if layout is None or _is_page_furniture(line):
                continue
            lead = [word for word in line if word.centre < layout.description]
            cells = [word for word in line if word.centre >= layout.description]
            if lead:
                opened = _row_key(lead)
                if opened is None:
                    if open_row is not None:
                        open_row.interrupted = True
                    continue
                if open_row is not None:
                    if open_row.interrupted:
                        open_row.valid = False
                    close(open_row, ended_by_table_end=False)
                closed_at_table_end = None
                key, extra = opened
                open_row = _RowBuilder(key=key, lead=list(extra), layout=layout)
                open_row.valid = not any(_straddles(word, layout) for word in lead)
                open_row.add_cells(cells)
                continue
            if open_row is not None and not open_row.interrupted:
                open_row.add_cells(cells)
            elif open_row is None and closed_at_table_end is not None:
                # Text inside a new table before its first row may continue the
                # row that was closed at the previous table's end.
                rows[:] = [row for row in rows if row is not closed_at_table_end]
                closed_at_table_end = None
    if open_row is not None:
        close(open_row, ended_by_table_end=open_row.interrupted)
    return tuple(rows)


def _compact(parts: Iterable[str]) -> str:
    return "".join("".join(parts).split())


def _field_text(design_field: RecordDesignField) -> str:
    return _compact((design_field.description, design_field.content or ""))


def _accepts(design_field: RecordDesignField, row: PdfColumnRow) -> bool:
    """Whether ``row``'s cells are exactly the text the line parser gave this field.

    The row's words, in page reading order, must spell the field's parsed
    description-plus-content from its first character. They may stop short of
    it only when the table ended the row, which is where the line parser went
    on reading note prose into the last field. Anything else -- a different
    word, a different order, text the parser has and the row does not in the
    middle of a table -- refuses the row and the field keeps its parsed text.
    """
    if not row.description and not row.lead:
        return False
    parsed = _field_text(design_field)
    printed = _compact(row.reading_order)
    if not printed or not parsed.startswith(printed):
        return False
    return parsed == printed or row.ended_by_table_end


def _row_matches(design_field: RecordDesignField, row: PdfColumnRow) -> bool:
    if design_field.ordinal is None or not design_field.ordinal.isdigit():
        return False
    expected = (int(design_field.ordinal), design_field.offset, design_field.length)
    return row.key == expected[: len(row.key)]


def apply_pdf_column_cells(
    sheets: tuple[RecordDesignSheet, ...],
    rows: Sequence[PdfColumnRow],
) -> tuple[RecordDesignSheet, ...]:
    """Return ``sheets`` with each matched field's cells taken from its printed columns.

    Fields and rows are walked in document order and paired on the row's own
    numbers (ordinal, position and length). A field no accepted row matches keeps
    what the line parser read.
    """
    if not rows:
        return sheets
    cursor = 0
    updated: list[RecordDesignSheet] = []
    for sheet in sheets:
        replacements: dict[int, RecordDesignField] = {}
        for index, design_field in sorted(enumerate(sheet.fields), key=lambda item: item[1].row):
            match = next(
                (position for position in range(cursor, len(rows)) if _row_matches(design_field, rows[position])),
                None,
            )
            if match is None:
                continue
            cursor = match + 1
            row = rows[match]
            if not _accepts(design_field, row):
                continue
            replacements[index] = design_field.model_copy(
                update={
                    "description": join_pdf_parts([*row.lead, *row.description]),
                    "validation": join_pdf_parts(list(row.validation)) or None,
                    "content": join_pdf_parts(list(row.content)) or None,
                    "content_in_contenido_column": bool(row.content),
                },
            )
        if replacements:
            fields = tuple(replacements.get(index, original) for index, original in enumerate(sheet.fields))
            sheet = sheet.model_copy(update={"fields": fields})
        updated.append(sheet)
    return tuple(updated)
