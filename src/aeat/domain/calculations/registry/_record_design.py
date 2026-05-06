"""Read-only extraction of official AEAT record-design rows."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pdfplumber
from openpyxl import load_workbook
from pydantic import ConfigDict

from ._schema import RegistryModel


class RecordDesignField(RegistryModel):
    """One fixed-width field described by an AEAT record-design sheet."""

    sheet: str
    row: int
    ordinal: int
    offset: int
    length: int
    type_code: str
    complementary: str | None = None
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignSheet(RegistryModel):
    """Parsed field rows and declared total length for one workbook sheet."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: tuple[RecordDesignField, ...]
    total_positions: int | None = None


def extract_record_design_workbook(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return the official fixed-width field rows described by ``path``."""

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return tuple(_extract_sheet(worksheet) for worksheet in workbook.worksheets)
    finally:
        workbook.close()


def extract_record_design_pdf(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return fixed-width field rows extracted from an official AEAT PDF."""

    if not path.is_file():
        raise FileNotFoundError(f"record-design PDF not found: {path}")
    with path.open("rb") as pdf_file:
        return _extract_record_design_pdf_stream(pdf_file, source_label=str(path))


def extract_record_design_pdf_bytes(
    pdf_bytes: bytes,
    *,
    source_label: str = "in-memory record-design PDF",
) -> tuple[RecordDesignSheet, ...]:
    """Return fixed-width field rows extracted from PDF bytes."""

    return _extract_record_design_pdf_stream(BytesIO(pdf_bytes), source_label=source_label)


def _extract_record_design_pdf_stream(
    stream: BinaryIO,
    *,
    source_label: str,
) -> tuple[RecordDesignSheet, ...]:
    try:
        with pdfplumber.open(stream) as pdf:
            pages = tuple(_snapshot_pdf_page(page) for page in pdf.pages)
    except Exception as exc:  # pragma: no cover - defensive; pdfplumber surface
        raise ValueError(f"pdfplumber could not open record-design PDF {source_label}: {exc}") from exc
    lines = tuple(line for page in pages for line in page.lines)
    if not any(line.strip() for line in lines):
        raise ValueError(f"no text extracted from record-design PDF {source_label}")
    try:
        return _extract_pdf_lines(lines, source_label=source_label)
    except ValueError as exc:
        if "did not contain parseable field rows" not in str(exc):
            raise
        legacy_chart = _extract_legacy_modelo_347_chart(pages, source_label=source_label)
        if legacy_chart:
            return legacy_chart
        raise


def _extract_sheet(worksheet) -> RecordDesignSheet:  # type: ignore[no-untyped-def]
    header_row, header = _find_header(worksheet)
    has_complementary_column = len(header) >= 5 and _clean(header[4]) == "Com"
    fields: list[RecordDesignField] = []
    total_positions: int | None = None
    for row_number, row in enumerate(
        worksheet.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        values = tuple(row)
        marker = values[0] if values else None
        if marker == "TOTAL":
            total_positions = _int_or_none(_cell(values, 2))
            continue
        ordinal = _int_or_none(marker)
        offset = _int_or_none(_cell(values, 1))
        length = _int_or_none(_cell(values, 2))
        if ordinal is None or offset is None or length is None:
            continue
        if has_complementary_column:
            type_code = _required_text(_cell(values, 3), worksheet.title, row_number, "type")
            complementary = _optional_text(_cell(values, 4))
            description = _required_text(_cell(values, 5), worksheet.title, row_number, "description")
            validation = _optional_text(_cell(values, 6))
            content = _optional_text(_cell(values, 7))
        else:
            type_code = _required_text(_cell(values, 3), worksheet.title, row_number, "type")
            complementary = None
            description = _required_text(_cell(values, 4), worksheet.title, row_number, "description")
            validation = _optional_text(_cell(values, 5))
            content = _optional_text(_cell(values, 6))
        fields.append(
            RecordDesignField(
                sheet=worksheet.title,
                row=row_number,
                ordinal=ordinal,
                offset=offset,
                length=length,
                type_code=type_code,
                complementary=complementary,
                description=description,
                validation=validation,
                content=content,
            )
        )
    return RecordDesignSheet(name=worksheet.title, fields=tuple(fields), total_positions=total_positions)


def _find_header(worksheet) -> tuple[int, tuple[object, ...]]:  # type: ignore[no-untyped-def]
    for row_number, row in enumerate(worksheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        values = tuple(row)
        if _clean(_cell(values, 0)) == "Nº" and _clean(_cell(values, 1)) == "Posic.":
            return row_number, values
    raise ValueError(f"{worksheet.title!r} has no record-design header")


def _cell(values: tuple[object, ...], index: int) -> object | None:
    return values[index] if index < len(values) else None


def _clean(value: object | None) -> str:
    return "" if value is None else str(value).strip()


def _optional_text(value: object | None) -> str | None:
    cleaned = _clean(value)
    return cleaned or None


def _required_text(value: object | None, sheet: str, row: int, field: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise ValueError(f"{sheet!r} row {row} missing {field}")
    return cleaned


def _int_or_none(value: object | None) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


_COMPACT_PDF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+(?P<type>An|Num|N|A)\s+(?P<text>.+)$",
    re.IGNORECASE,
)
_COMPACT_PDF_CRLF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<type>An|Num|N|A)\s+(?P<text>Salto de l[íi]nea\..*CRLF\.?)$",
    re.IGNORECASE,
)
_NARRATIVE_PDF_ROW_RE = re.compile(
    r"^\s*(?P<start>\d+)(?:\s*[-\u2013]\s*(?P<end>\d+))?\s+"
    r"(?P<type>Alfanum[eé]rico|Alfab[eé]tico|Num[eé]rico|[-\u2013]+)\s*"
    r"(?P<text>.*)$",
    re.IGNORECASE,
)
_PDF_PAGE_RECORD_RE = re.compile(r"^P[áa]g\s+(?P<page>\d+)\s+DISE[ÑN]O DE REGISTRO\b", re.IGNORECASE)
_PDF_RECORD_HEADING_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?(?:TIPO DE REGISTRO|Tipo de registro)\s+"
    r"(?P<record>\d+)\s*:\s*(?P<title>.+)$",
    re.IGNORECASE,
)


@dataclass
class _PdfFieldDraft:
    sheet: str
    row: int
    ordinal: int
    offset: int
    length: int
    type_code: str
    description_parts: list[str] = field(default_factory=list)
    content_parts: list[str] = field(default_factory=list)

    def append_continuation(self, line: str) -> None:
        if not self.description_parts or (not self.content_parts and _looks_like_title_continuation(line)):
            self.description_parts.append(line)
            return
        self.content_parts.append(line)

    def finish(self) -> RecordDesignField:
        description = _join_pdf_parts(self.description_parts)
        if not description:
            raise ValueError(f"{self.sheet!r} PDF row {self.row} missing description")
        content = _join_pdf_parts(self.content_parts) or None
        return RecordDesignField(
            sheet=self.sheet,
            row=self.row,
            ordinal=self.ordinal,
            offset=self.offset,
            length=self.length,
            type_code=self.type_code,
            complementary=None,
            description=description,
            validation=None,
            content=content,
        )


@dataclass
class _PdfSheetDraft:
    name: str
    fields: list[RecordDesignField] = field(default_factory=list)
    current: _PdfFieldDraft | None = None

    def start_field(self, row: _PdfRow) -> None:
        self.finish_current()
        ordinal = row.ordinal or len(self.fields) + 1
        self.current = _PdfFieldDraft(
            sheet=self.name,
            row=row.source_row,
            ordinal=ordinal,
            offset=row.offset,
            length=row.length,
            type_code=row.type_code,
            description_parts=[row.description] if row.description else [],
        )

    def finish_current(self) -> None:
        if self.current is None:
            return
        self.fields.append(self.current.finish())
        self.current = None

    def finish(self, *, source_label: str) -> RecordDesignSheet:
        self.finish_current()
        total_positions = max((field.offset + field.length - 1 for field in self.fields), default=None)
        sheet = RecordDesignSheet(name=self.name, fields=tuple(self.fields), total_positions=total_positions)
        _validate_pdf_sheet(sheet, source_label=source_label)
        return sheet


@dataclass(frozen=True)
class _PdfRow:
    source_row: int
    ordinal: int | None
    offset: int
    length: int
    type_code: str
    description: str


@dataclass(frozen=True)
class _PdfWord:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass(frozen=True)
class _PdfRect:
    x0: float
    x1: float
    top: float
    bottom: float
    width: float
    height: float
    fill: object | None


@dataclass(frozen=True)
class _PdfPageSnapshot:
    lines: tuple[str, ...]
    words: tuple[_PdfWord, ...]
    rects: tuple[_PdfRect, ...]


@dataclass(frozen=True)
class _LegacyVisualFragment:
    start: int
    end: int
    description: str


def _snapshot_pdf_page(page) -> _PdfPageSnapshot:  # type: ignore[no-untyped-def]
    text = page.extract_text() or ""
    return _PdfPageSnapshot(
        lines=tuple(text.splitlines()),
        words=tuple(
            _PdfWord(
                text=str(word["text"]),
                x0=float(word["x0"]),
                x1=float(word["x1"]),
                top=float(word["top"]),
                bottom=float(word["bottom"]),
            )
            for word in page.extract_words()
        ),
        rects=tuple(
            _PdfRect(
                x0=float(rect["x0"]),
                x1=float(rect["x1"]),
                top=float(rect["top"]),
                bottom=float(rect["bottom"]),
                width=float(rect["width"]),
                height=float(rect["height"]),
                fill=rect.get("non_stroking_color"),
            )
            for rect in page.rects
        ),
    )


def _extract_pdf_lines(lines: tuple[str, ...], *, source_label: str) -> tuple[RecordDesignSheet, ...]:
    sheets: list[RecordDesignSheet] = []
    current: _PdfSheetDraft | None = None
    in_table = False
    pending_name: str | None = None

    for row_number, raw_line in enumerate(lines, start=1):
        line = _clean_pdf_line(raw_line)
        if not line or _is_pdf_footer(line):
            continue

        page_name = _pdf_page_name(line)
        if page_name is not None:
            pending_name = page_name
            if current is not None and current.name != page_name:
                sheets.append(current.finish(source_label=source_label))
                current = _PdfSheetDraft(page_name)
            continue

        heading_name = _pdf_record_heading_name(line)
        if heading_name is not None:
            if current is not None:
                sheets.append(current.finish(source_label=source_label))
            current = _PdfSheetDraft(heading_name)
            in_table = False
            continue

        if _is_pdf_header(line):
            if current is None:
                current = _PdfSheetDraft(pending_name or "PDF record design")
            in_table = True
            continue

        if not in_table and current is not None and not current.fields and _looks_like_title_continuation(line):
            current.name = _normalise_pdf_sheet_name(_join_pdf_parts([current.name, line]))
            continue

        if _is_pdf_page_heading(line):
            continue

        row = _parse_pdf_row(line, row_number)
        if row is not None:
            if current is None:
                current = _PdfSheetDraft(pending_name or "PDF record design")
            current.start_field(row)
            in_table = True
            continue

        if in_table and current is not None and current.current is not None:
            current.current.append_continuation(line)

    if current is not None:
        sheets.append(current.finish(source_label=source_label))

    non_empty = tuple(sheet for sheet in sheets if sheet.fields)
    if not non_empty:
        raise ValueError("record-design PDF did not contain parseable field rows")
    return non_empty


def _validate_pdf_sheet(sheet: RecordDesignSheet, *, source_label: str) -> None:
    if not sheet.fields:
        return
    first_field = sheet.fields[0]
    if first_field.offset != 1:
        raise ValueError(
            f"{source_label} {sheet.name!r} first field starts at position {first_field.offset}; expected 1"
        )
    for parsed_field in sheet.fields:
        if parsed_field.offset < 1:
            raise ValueError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"position {parsed_field.offset}"
            )
        if parsed_field.length < 1:
            raise ValueError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"length {parsed_field.length}"
            )
    terminal_position = max(parsed_field.offset + parsed_field.length - 1 for parsed_field in sheet.fields)
    if sheet.total_positions is not None and terminal_position != sheet.total_positions:
        raise ValueError(
            f"{source_label} {sheet.name!r} declares {sheet.total_positions} total positions "
            f"but parsed fields fill {terminal_position}"
        )


def _parse_pdf_row(line: str, source_row: int) -> _PdfRow | None:
    compact = _COMPACT_PDF_ROW_RE.match(line)
    if compact is not None:
        return _PdfRow(
            source_row=source_row,
            ordinal=int(compact.group("ordinal")),
            offset=int(compact.group("offset")),
            length=int(compact.group("length")),
            type_code=compact.group("type"),
            description=compact.group("text").strip(),
        )

    crlf = _COMPACT_PDF_CRLF_ROW_RE.match(line)
    if crlf is not None:
        return _PdfRow(
            source_row=source_row,
            ordinal=int(crlf.group("ordinal")),
            offset=int(crlf.group("offset")),
            length=2,
            type_code=crlf.group("type"),
            description=crlf.group("text").strip(),
        )

    narrative = _NARRATIVE_PDF_ROW_RE.match(line)
    if narrative is None:
        return None

    start = int(narrative.group("start"))
    end_group = narrative.group("end")
    end = int(end_group) if end_group is not None else start
    if end < start:
        raise ValueError(f"PDF row {source_row} has inverted position range {start}-{end}")
    type_code = _normalise_pdf_type_code(narrative.group("type"))
    return _PdfRow(
        source_row=source_row,
        ordinal=None,
        offset=start,
        length=end - start + 1,
        type_code=type_code,
        description=narrative.group("text").strip(),
    )


def _normalise_pdf_type_code(value: str) -> str:
    normalised = value.strip(" .").lower()
    if set(normalised) <= {"-", "\u2013"}:
        return "Blancos"
    if normalised.startswith("num"):
        return "Numérico"
    if normalised.startswith("alfanum"):
        return "Alfanumérico"
    if normalised.startswith("alfab"):
        return "Alfabético"
    return value.strip()


def _pdf_page_name(line: str) -> str | None:
    match = _PDF_PAGE_RECORD_RE.match(line)
    if match is None:
        return None
    return f"Pág. {match.group('page')}"


def _pdf_record_heading_name(line: str) -> str | None:
    match = _PDF_RECORD_HEADING_RE.match(line)
    if match is None:
        return None
    title = _normalise_pdf_sheet_name(match.group("title"))
    return f"Tipo {match.group('record')} - {title}"


def _is_pdf_header(line: str) -> bool:
    normalised = line.upper()
    return (
        ("POSICIONES" in normalised or "POSICIÓN" in normalised)
        and "NATURALEZA" in normalised
        and "DESCRIPCI" in normalised
    ) or ("Nº POSIC" in normalised and "LON" in normalised and "TIPO" in normalised and "DESCRIPCI" in normalised)


def _is_pdf_footer(line: str) -> bool:
    return bool(
        re.match(r"^P[áa]gina\s+\d+\s+de\s+\d+$", line, re.IGNORECASE)
        or re.match(r"^Ejercicio\s+\d{4}(?:\s+\d+)?$", line, re.IGNORECASE)
        or re.match(r"^\d+$", line)
    )


def _is_pdf_page_heading(line: str) -> bool:
    return bool(
        line.startswith("Modelo ")
        or line.startswith("Agencia Tributaria")
        or line.startswith("Declaración Informativa")
        or line.startswith("Declaración informativa")
        or line.startswith("determinados ")
        or line.startswith("determinadas ")
        or line == "Resumen anual"
        or line == "MODELO 193"
        or line == "MODELO 190"
        or line == "DISEÑOS DE REGISTRO"
    )


def _looks_like_title_continuation(line: str) -> bool:
    letters = [char for char in line if char.isalpha()]
    if not letters:
        return False
    return not any(char.islower() for char in letters)


def _clean_pdf_line(line: str) -> str:
    return " ".join(line.strip().split())


def _join_pdf_parts(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part.strip())


def _normalise_pdf_sheet_name(value: str) -> str:
    return _join_pdf_parts([value.replace(".", " ").strip()]).strip(". ").title()


def _extract_legacy_modelo_347_chart(
    pages: tuple[_PdfPageSnapshot, ...],
    *,
    source_label: str,
) -> tuple[RecordDesignSheet, ...]:
    text = "\n".join(_clean_pdf_line(line).upper() for page in pages for line in page.lines)
    if not all(marker in text for marker in _LEGACY_MODELO_347_REQUIRED_MARKERS):
        return ()

    pages_by_sheet: dict[str, list[_PdfPageSnapshot]] = {sheet_name: [] for sheet_name in _LEGACY_MODELO_347_SHEETS}
    for page in pages:
        page_text = "\n".join(_clean_pdf_line(line).upper() for line in page.lines)
        for marker, sheet_name in _LEGACY_MODELO_347_PAGE_MARKERS.items():
            if marker in page_text:
                pages_by_sheet[sheet_name].append(page)
                break

    if any(not sheet_pages for sheet_pages in pages_by_sheet.values()):
        return ()

    return tuple(
        _extract_legacy_visual_sheet(sheet_name, tuple(pages_by_sheet[sheet_name]), source_label=source_label)
        for sheet_name in _LEGACY_MODELO_347_SHEETS
    )


def _extract_legacy_visual_sheet(
    name: str,
    pages: tuple[_PdfPageSnapshot, ...],
    *,
    source_label: str,
) -> RecordDesignSheet:
    fragments: list[_LegacyVisualFragment] = []
    for page in pages:
        fragments.extend(_extract_legacy_visual_fragments(page))

    merged = _merge_legacy_visual_fragments(sorted(fragments, key=lambda fragment: fragment.start))
    fields = tuple(
        RecordDesignField(
            sheet=name,
            row=ordinal,
            ordinal=ordinal,
            offset=fragment.start,
            length=fragment.end - fragment.start + 1,
            type_code=_LEGACY_VISUAL_CHART_TYPE_CODE,
            description=fragment.description,
            content="Extracted from legacy Modelo 347 visual chart geometry.",
        )
        for ordinal, fragment in enumerate(merged, start=1)
    )
    sheet = RecordDesignSheet(name=name, fields=fields, total_positions=500)
    _validate_pdf_sheet(sheet, source_label=source_label)
    return sheet


def _extract_legacy_visual_fragments(page: _PdfPageSnapshot) -> list[_LegacyVisualFragment]:
    grid = _legacy_visual_grid(page)
    if grid is None:
        return []
    left, cell_width, horizontal_rules = grid
    fragments: list[_LegacyVisualFragment] = []
    number_rows = _legacy_visual_number_rows(page)
    for index, (number_top, first_position) in enumerate(number_rows):
        row_rules = _legacy_visual_rules_for_number_row(horizontal_rules, number_top)
        if not row_rules:
            continue
        region_top = number_rows[index - 1][0] + 8 if index else 20
        for rule in row_rules:
            start = first_position - 1 + round((rule.x0 - left) / cell_width) + 1
            end = first_position - 1 + round((rule.x1 - left) / cell_width)
            if start > end:
                continue
            fragments.append(
                _LegacyVisualFragment(
                    start=start,
                    end=end,
                    description=_legacy_visual_description(page, rule, region_top=region_top),
                )
            )
    return fragments


def _legacy_visual_grid(page: _PdfPageSnapshot) -> tuple[float, float, tuple[_PdfRect, ...]] | None:
    horizontal_rules = tuple(
        rect
        for rect in page.rects
        if rect.fill == 0.0 and rect.height <= 2.0 and rect.width >= 8.0
    )
    full_width_rules = tuple(rect for rect in horizontal_rules if rect.width > 700.0)
    if not full_width_rules:
        return None
    left = min(rect.x0 for rect in full_width_rules)
    right = max(rect.x1 for rect in full_width_rules)
    return left, (right - left) / 65, horizontal_rules


def _legacy_visual_number_rows(page: _PdfPageSnapshot) -> list[tuple[float, int]]:
    grouped_words: dict[float, list[_PdfWord]] = {}
    for word in page.words:
        if _legacy_visual_number_values(word.text):
            grouped_words.setdefault(round(word.top, 1), []).append(word)

    rows: list[tuple[float, int]] = []
    for top, words in grouped_words.items():
        values = [
            value
            for word in sorted(words, key=lambda current: current.x0)
            for value in _legacy_visual_number_values(word.text)
        ]
        if len(values) >= 20 and max(values) - min(values) >= 30:
            rows.append((top, min(values)))
    return sorted(rows)


def _legacy_visual_number_values(text: str) -> tuple[int, ...]:
    if not text.isdigit():
        return ()
    if len(text) <= 3:
        return (int(text),)
    if len(text) % 3 == 0:
        return tuple(int(text[index : index + 3]) for index in range(0, len(text), 3))
    return ()


def _legacy_visual_rules_for_number_row(
    horizontal_rules: tuple[_PdfRect, ...],
    number_top: float,
) -> tuple[_PdfRect, ...]:
    grouped_rules: dict[float, list[_PdfRect]] = {}
    for rule in horizontal_rules:
        if 0 < number_top - rule.top <= 30:
            grouped_rules.setdefault(round(rule.top, 1), []).append(rule)
    if not grouped_rules:
        return ()
    rule_top = max(grouped_rules)
    return tuple(sorted(grouped_rules[rule_top], key=lambda rule: rule.x0))


def _legacy_visual_description(
    page: _PdfPageSnapshot,
    rule: _PdfRect,
    *,
    region_top: float,
) -> str:
    words = [
        word
        for word in page.words
        if rule.x0 - 2 <= (word.x0 + word.x1) / 2 <= rule.x1 + 2
        and region_top <= word.top <= rule.top - 1
        and not _is_legacy_visual_number_text(word.text)
    ]
    description = _normalise_legacy_visual_description(words)
    return description or "BLANCOS."


def _normalise_legacy_visual_description(words: list[_PdfWord]) -> str:
    tokens = [word.text for word in sorted(words, key=lambda word: (word.top, word.x0))]
    tokens = [
        _LEGACY_REVERSED_VISUAL_TOKENS.get(visual_word, visual_word)
        for visual_word in tokens
        if visual_word != "D"
    ]
    if not tokens:
        return ""
    if any(token.strip(".").upper() in _LEGACY_REVERSED_VISUAL_WORDS for token in tokens):
        tokens = [token[::-1] for token in reversed(tokens)]
    return _clean_legacy_visual_description(_dedupe_legacy_visual_tokens(tokens))


def _dedupe_legacy_visual_tokens(tokens: list[str]) -> str:
    deduped: list[str] = []
    for token in tokens:
        if not deduped or deduped[-1] != token:
            deduped.append(token)
    return " ".join(deduped).strip()


def _clean_legacy_visual_description(description: str) -> str:
    replacements = {
        "DEL DECLARANTE N.I.F. DEL DECLARANTE": "N.I.F. DEL DECLARANTE",
        "DECLARANTE N.I.F. DECLARANTE": "N.I.F. DECLARANTE",
        "PROVINCIA AICNIVORP OGIDOC": "CODIGO PROVINCIA",
        "CODIGO PAIS SIAP": "CODIGO PAIS",
        "DECIMAL ED": "DECIMAL",
        "I TIPO DE HOJA": "TIPO DE HOJA",
        "REFERENCIA CATASTRAL REFERENCIA CATASTRAL": "REFERENCIA CATASTRAL",
    }
    for before, after in replacements.items():
        description = description.replace(before, after)
    return description


def _is_legacy_visual_number_text(text: str) -> bool:
    return bool(re.fullmatch(r"\d+", text) or re.fullmatch(r"\d{3}(?:\d{3})+", text))


def _merge_legacy_visual_fragments(
    fragments: list[_LegacyVisualFragment],
) -> tuple[_LegacyVisualFragment, ...]:
    merged: list[_LegacyVisualFragment] = []
    for fragment in fragments:
        if (
            merged
            and fragment.start == merged[-1].end + 1
            and merged[-1].end % 65 == 0
            and _legacy_visual_fragments_should_merge(merged[-1], fragment)
        ):
            previous = merged[-1]
            description = _merge_legacy_visual_descriptions(previous.description, fragment.description)
            merged[-1] = _LegacyVisualFragment(start=previous.start, end=fragment.end, description=description)
            continue
        merged.append(fragment)
    return tuple(merged)


def _legacy_visual_fragments_should_merge(
    previous: _LegacyVisualFragment,
    current: _LegacyVisualFragment,
) -> bool:
    return not (previous.description == "BLANCOS." and current.description != "BLANCOS.")


def _merge_legacy_visual_descriptions(previous: str, current: str) -> str:
    parts = [description for description in (previous, current) if description != "BLANCOS."]
    return _clean_legacy_visual_description(_join_pdf_parts(parts)) or "BLANCOS."


_LEGACY_MODELO_347_REQUIRED_MARKERS = (
    "MODELO 347 REGISTRO DE TIPO 1 REGISTRO DE DECLARANTE",
    "MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE DECLARADO",
    "MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE INMUEBLE",
    "SELLO ELECTRÓNICO",
    "REFERENCIA CATASTRAL",
)
_LEGACY_MODELO_347_SHEETS = (
    "Tipo 1 - Registro De Declarante",
    "Tipo 2 - Registro De Declarado",
    "Tipo 2 - Registro De Inmueble",
)
_LEGACY_MODELO_347_PAGE_MARKERS = {
    "MODELO 347 REGISTRO DE TIPO 1 REGISTRO DE DECLARANTE": "Tipo 1 - Registro De Declarante",
    "MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE DECLARADO": "Tipo 2 - Registro De Declarado",
    "MODELO 347 REGISTRO DE TIPO 2 REGISTRO DE INMUEBLE": "Tipo 2 - Registro De Inmueble",
}
_LEGACY_VISUAL_CHART_TYPE_CODE = "No consta en gráfico"
_LEGACY_REVERSED_VISUAL_WORDS = {
    "AICNIVORP",
    "AJOH",
    "DNERRA",
    "EVALC",
    "ETROPOS",
    "LACOL",
    "LAMICED",
    "NÓICAREPO",
    "OPIT",
    "ORTSIGER",
}
_LEGACY_REVERSED_VISUAL_TOKENS = {
    "AIRATNEMELPMOC.CED": "DEC. COMPLEMENTARIA",
    "AVITUTITSUS.CED": "DEC. SUSTITUTIVA",
    ".REPO": "OPER.",
    "ORUGES": "SEGURO",
    "ELBEUMNI": "INMUEBLE",
    ".CAUTIS": "SITUAC.",
    "ARELACSE": "ESCALERA",
    "IMNUEBLE": "INMUEBLE",
}


__all__ = [
    "RecordDesignField",
    "RecordDesignSheet",
    "extract_record_design_pdf",
    "extract_record_design_pdf_bytes",
    "extract_record_design_workbook",
]
