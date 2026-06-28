"""Read-only extraction of official AEAT record-design rows.

Parses official AEAT record-design workbooks (PDF or XLS/XLSX) and derives
coverage casillas from a :class:`ModeloRevision` so that the extracted layout
can be compared against the registry declarations.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from io import BufferedReader, BytesIO
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
import xlrd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from pdfplumber.page import Page
from xlrd.sheet import Sheet as XlrdSheet

from ....core.external_constants import PDF_EXTENSION as _PDF_EXTENSION
from ....core.external_constants import XLS_EXTENSION as _XLS_EXTENSION
from ....core.external_constants import XLSM_EXTENSION as _XLSM_EXTENSION
from ....core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from ....core.logging import get_logger
from ._errors import RegistryValidationError
from ._record_design_coverage import (
    DerivedDisenoCasilla,
    DisenoCoverageReport,
    build_diseno_coverage_report,
    calculation_closure_casilla_ids,
    calculation_closure_legal_refs,
    calculation_closure_record_design_metadata,
    derive_calculation_completeness_casillas,
    derive_diseno_coverage_casillas,
)
from ._record_design_schema import RecordDesignField, RecordDesignSheet

_log = get_logger(__name__)

_OPENPYXL_HEADER_FOOTER_WARNING = "Cannot parse header or footer so it will be ignored"
_OPENPYXL_PRINT_AREA_WARNING = r"Print area cannot be set to Defined name: .*"


@dataclass(frozen=True)
class _WorkbookHeader:
    row_number: int
    ordinal_index: int
    offset_index: int
    length_index: int
    type_index: int
    complementary_index: int | None
    description_index: int
    validation_index: int | None
    content_index: int | None


def extract_record_design(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return fixed-width field rows from a supported official record-design source.

    Returns:
        Tuple of :class:`RecordDesignSheet` objects parsed from the source file.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design source not found: {path}")
    stat = resolved.stat()
    return _extract_record_design_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _extract_record_design_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> tuple[RecordDesignSheet, ...]:
    del byte_count, modified_ns
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == _PDF_EXTENSION:
        return extract_record_design_pdf(source_path)
    if suffix in {_XLSX_EXTENSION, _XLSM_EXTENSION}:
        return extract_record_design_workbook(source_path)
    if suffix == _XLS_EXTENSION:
        return extract_record_design_xls_workbook(source_path)
    raise RegistryValidationError(f"unsupported record-design source extension: {source_path.suffix}")


def extract_record_design_workbook(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return :class:`RecordDesignSheet` rows described by workbook ``path``."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design workbook not found: {path}")
    stat = resolved.stat()
    return _extract_record_design_workbook_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


def extract_record_design_xls_workbook(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return official fixed-width field rows from a legacy binary XLS workbook.

    Returns:
        Tuple of :class:`RecordDesignSheet` objects parsed from the XLS workbook.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design XLS workbook not found: {path}")
    stat = resolved.stat()
    return _extract_record_design_xls_workbook_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _extract_record_design_workbook_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> tuple[RecordDesignSheet, ...]:
    del byte_count, modified_ns
    source_path = Path(path)
    with _ignore_openpyxl_header_footer_metadata_warnings():
        workbook = load_workbook(source_path, read_only=True, data_only=True)
        try:
            sheets: list[RecordDesignSheet] = []
            skipped: list[str] = []
            for worksheet in workbook.worksheets:
                try:
                    sheets.append(_extract_sheet(worksheet))
                except ValueError as exc:
                    if "has no record-design header" not in str(exc):
                        raise
                    skipped.append(worksheet.title)
            if not sheets:
                skipped_sheets = ", ".join(skipped) if skipped else "none"
                raise RegistryValidationError(
                    f"{source_path}: no record-design sheets found; skipped sheets: {skipped_sheets}",
                )
            return tuple(sheets)
        finally:
            workbook.close()


@lru_cache(maxsize=128)
def _extract_record_design_xls_workbook_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> tuple[RecordDesignSheet, ...]:
    del byte_count, modified_ns
    source_path = Path(path)
    workbook = xlrd.open_workbook(str(source_path), on_demand=True)
    try:
        sheets: list[RecordDesignSheet] = []
        skipped: list[str] = []
        for sheet_name in workbook.sheet_names():
            worksheet = workbook.sheet_by_name(sheet_name)
            try:
                sheets.append(_extract_xls_sheet(worksheet))
            except ValueError as exc:
                if "has no record-design header" not in str(exc):
                    raise
                skipped.append(sheet_name)
        if not sheets:
            skipped_sheets = ", ".join(skipped) if skipped else "none"
            raise RegistryValidationError(
                f"{source_path}: no record-design sheets found; skipped sheets: {skipped_sheets}",
            )
        return tuple(sheets)
    finally:
        workbook.release_resources()


@contextmanager
def _ignore_openpyxl_header_footer_metadata_warnings() -> Iterator[None]:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=_OPENPYXL_HEADER_FOOTER_WARNING,
            category=UserWarning,
            module=r"openpyxl\.worksheet\.header_footer",
        )
        warnings.filterwarnings(
            "ignore",
            message=_OPENPYXL_PRINT_AREA_WARNING,
            category=UserWarning,
            module=r"openpyxl\.reader\.workbook",
        )
        yield


def extract_record_design_pdf(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return :class:`RecordDesignSheet` rows extracted from an official AEAT PDF."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design PDF not found: {path}")
    stat = resolved.stat()
    return _extract_record_design_pdf_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _extract_record_design_pdf_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> tuple[RecordDesignSheet, ...]:
    del byte_count, modified_ns
    source_path = Path(path)
    with source_path.open("rb") as pdf_file:
        return _extract_record_design_pdf_stream(pdf_file, source_label=str(source_path))


def extract_record_design_pdf_bytes(
    pdf_bytes: bytes,
    *,
    source_label: str = "in-memory record-design PDF",
) -> tuple[RecordDesignSheet, ...]:
    """Return fixed-width field rows extracted from PDF bytes.

    Returns:
        Tuple of :class:`RecordDesignSheet` objects extracted from the PDF content.
    """
    return _extract_record_design_pdf_stream(BytesIO(pdf_bytes), source_label=source_label)


def _extract_record_design_pdf_stream(
    stream: BufferedReader | BytesIO,
    *,
    source_label: str,
) -> tuple[RecordDesignSheet, ...]:
    pdf_bytes = stream.read()
    lines = _extract_pdf_text_lines(pdf_bytes, source_label=source_label)
    if _uses_page_record_layout(lines):
        lines = _extract_pdfplumber_text_lines(pdf_bytes, source_label=source_label)
    if not any(line.strip() for line in lines):
        raise RegistryValidationError(f"no text extracted from record-design PDF {source_label}")
    try:
        return _extract_pdf_lines(lines, source_label=source_label)
    except ValueError as pdfium_exc:
        text_fallback_error = pdfium_exc
        try:
            fallback_lines = _extract_pdfplumber_text_lines(pdf_bytes, source_label=source_label)
            return _extract_pdf_lines(fallback_lines, source_label=source_label)
        except ValueError as fallback_exc:
            text_fallback_error = fallback_exc
        if "did not contain parseable field rows" not in str(text_fallback_error):
            raise text_fallback_error from pdfium_exc
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                pages = tuple(_snapshot_pdf_page(page) for page in pdf.pages)
        except Exception as pdf_exc:  # pragma: no cover - defensive; pdfplumber surface
            raise RegistryValidationError(
                f"pdfplumber could not open record-design PDF {source_label}: {pdf_exc}",
            ) from pdf_exc
        visual_chart = _extract_visual_record_design_chart(pages, source_label=source_label)
        if visual_chart:
            return visual_chart
        raise


def _extract_sheet(worksheet: Worksheet) -> RecordDesignSheet:
    header = _find_header(worksheet)
    return _extract_sheet_rows(
        worksheet.title,
        header,
        enumerate(
            worksheet.iter_rows(min_row=header.row_number + 1, values_only=True),
            start=header.row_number + 1,
        ),
    )


def _extract_xls_sheet(worksheet: XlrdSheet) -> RecordDesignSheet:
    header = _find_xls_header(worksheet)
    return _extract_sheet_rows(
        worksheet.name,
        header,
        ((rowx + 1, tuple(worksheet.row_values(rowx))) for rowx in range(header.row_number, worksheet.nrows)),
    )


def _extract_sheet_rows(
    sheet_name: str,
    header: _WorkbookHeader,
    rows: Iterator[tuple[int, tuple[object, ...]]],
) -> RecordDesignSheet:
    # AEAT Diseño workbooks occasionally carry surrounding whitespace on a
    # sheet tab (e.g. 'DP200026 '). The sheet name is the record-segment
    # identity that segment-qualified casillas and the calculation-
    # completeness derivation match against, so the raw tab whitespace
    # must not leak into that identity.
    sheet_name = sheet_name.strip()
    fields: list[RecordDesignField] = []
    total_positions: int | None = None
    trailing_blank_rows = 0
    for row_number, row in rows:
        values = tuple(row)
        if _is_blank_row(values):
            if fields:
                trailing_blank_rows += 1
                if trailing_blank_rows >= 25:
                    break
            continue
        trailing_blank_rows = 0
        row_total = _total_positions_from_row(values)
        if row_total is not None:
            total_positions = row_total
            continue
        ordinal = _int_or_none(_cell(values, header.ordinal_index))
        offset = _int_or_none(_cell(values, header.offset_index))
        length = _int_or_none(_cell(values, header.length_index))
        if ordinal is None or offset is None or length is None:
            continue
        type_code = _required_text(_cell(values, header.type_index), sheet_name, row_number, "type")
        complementary = _optional_header_text(values, header.complementary_index)
        validation = _optional_header_text(values, header.validation_index)
        content = _optional_header_text(values, header.content_index)
        description = _field_description_text(
            values,
            header=header,
            content=content,
            sheet=sheet_name,
            row=row_number,
        )
        fields.append(
            RecordDesignField(
                sheet=sheet_name,
                row=row_number,
                ordinal=ordinal,
                offset=offset,
                length=length,
                type_code=type_code,
                complementary=complementary,
                description=description,
                validation=validation,
                content=content,
            ),
        )
    return RecordDesignSheet(name=sheet_name, fields=tuple(fields), total_positions=total_positions)


def _is_blank_row(values: tuple[object, ...]) -> bool:
    return all(value is None or str(value).strip() == "" for value in values)


def _find_header(worksheet: Worksheet) -> _WorkbookHeader:
    for row_number, row in enumerate(worksheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        values = tuple(row)
        if _normalise_header_cell(_cell(values, 0)) not in {"no", "n"}:
            continue
        try:
            offset_index = _required_header_index(values, "posic.")
            length_index = _required_header_index(values, "lon")
            type_index = _required_header_index(values, "tipo")
            description_index = _required_header_index(values, "descripcion")
        except ValueError as header_exc:
            _log.debug(
                "record-design header probe (xlsx %s): row %d missing required columns (%s); trying next",
                worksheet.title,
                row_number,
                header_exc,
            )
            continue
        return _WorkbookHeader(
            row_number=row_number,
            ordinal_index=0,
            offset_index=offset_index,
            length_index=length_index,
            type_index=type_index,
            complementary_index=_optional_header_index(values, "com", "comp"),
            description_index=description_index,
            validation_index=_optional_header_index(values, "validacion", "oblig."),
            content_index=_optional_header_index(values, "contenido"),
        )
    raise RegistryValidationError(f"{worksheet.title!r} has no record-design header")


def _find_xls_header(worksheet: XlrdSheet) -> _WorkbookHeader:
    for rowx in range(min(10, worksheet.nrows)):
        values = tuple(worksheet.row_values(rowx))
        if _normalise_header_cell(_cell(values, 0)) not in {"no", "n"}:
            continue
        try:
            offset_index = _required_header_index(values, "posic.")
            length_index = _required_header_index(values, "lon")
            type_index = _required_header_index(values, "tipo")
            description_index = _required_header_index(values, "descripcion")
        except ValueError as header_exc:
            _log.debug(
                "record-design header probe (xls): row %d missing required columns (%s); trying next",
                rowx + 1,
                header_exc,
            )
            continue
        return _WorkbookHeader(
            row_number=rowx + 1,
            ordinal_index=0,
            offset_index=offset_index,
            length_index=length_index,
            type_index=type_index,
            complementary_index=_optional_header_index(values, "com", "comp"),
            description_index=description_index,
            validation_index=_optional_header_index(values, "validacion", "oblig."),
            content_index=_optional_header_index(values, "contenido"),
        )
    raise RegistryValidationError(f"{worksheet.name!r} has no record-design header")


def _cell(values: tuple[object, ...], index: int) -> object | None:
    return values[index] if index < len(values) else None


def _clean(value: object | None) -> str:
    return "" if value is None else str(value).strip()


def _optional_text(value: object | None) -> str | None:
    cleaned = _clean(value)
    return cleaned or None


def _optional_header_text(values: tuple[object, ...], index: int | None) -> str | None:
    if index is None:
        return None
    return _optional_text(_cell(values, index))


def _required_text(value: object | None, sheet: str, row: int, field: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise RegistryValidationError(f"{sheet!r} row {row} missing {field}")
    return cleaned


def _field_description_text(
    values: tuple[object, ...],
    *,
    header: _WorkbookHeader,
    content: str | None,
    sheet: str,
    row: int,
) -> str:
    description = _optional_text(_cell(values, header.description_index))
    if description is not None:
        return description
    if content is not None:
        return content
    raise RegistryValidationError(f"{sheet!r} row {row} missing description")


def _int_or_none(value: object | None) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _normalise_header_cell(value: object | None) -> str:
    return (
        _clean(value)
        .casefold()
        .replace("º", "o")
        .replace("ó", "o")
        .replace("í", "i")
        .replace("á", "a")
        .replace("é", "e")
        .replace("ú", "u")
    )


def _required_header_index(values: tuple[object, ...], header_name: str) -> int:
    index = _optional_header_index(values, header_name)
    if index is None:
        raise RegistryValidationError(f"missing workbook header {header_name!r}")
    return index


def _optional_header_index(values: tuple[object, ...], *header_names: str) -> int | None:
    expected = set(header_names)
    for index, value in enumerate(values):
        if _normalise_header_cell(value) in expected:
            return index
    return None


def _total_positions_from_row(values: tuple[object, ...]) -> int | None:
    for index, value in enumerate(values):
        if _normalise_header_cell(value) != "total":
            continue
        for candidate in values[index + 1 :]:
            total = _int_or_none(candidate)
            if total is not None:
                return total
        return None
    return None


_COMPACT_PDF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+(?P<type>An|Num|N|A)\s+(?P<text>.+)$",
    re.IGNORECASE,
)
_COMPACT_PDF_CRLF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<type>An|Num|N|A)\s+"
    r"(?P<text>Salto de l[íi]nea\..*CRLF\.?)$",
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
            raise RegistryValidationError(f"{self.sheet!r} PDF row {self.row} missing description")
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
            content=_join_pdf_parts(self.content_parts) or None,
        )


@dataclass
class _PdfSheetDraft:
    name: str
    fields: list[RecordDesignField] = field(default_factory=list)
    current: _PdfFieldDraft | None = None

    def start_field(self, row: _PdfRow) -> None:
        self.finish_current()
        self.current = _PdfFieldDraft(
            sheet=self.name,
            row=row.source_row,
            ordinal=row.ordinal or len(self.fields) + 1,
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
class _VisualChartFragment:
    start: int
    end: int
    description: str


def _extract_pdf_text_lines(pdf_bytes: bytes, *, source_label: str) -> tuple[str, ...]:
    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:  # pragma: no cover - pdfium parser surface
        raise RegistryValidationError(f"pypdfium2 could not open record-design PDF {source_label}: {exc}") from exc
    try:
        lines: list[str] = []
        for page in document:
            text_page = page.get_textpage()
            try:
                lines.extend(text_page.get_text_range().splitlines())
            finally:
                text_page.close()
                page.close()
        return tuple(lines)
    finally:
        document.close()


def _extract_pdfplumber_text_lines(pdf_bytes: bytes, *, source_label: str) -> tuple[str, ...]:
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            return tuple(line for page in pdf.pages for line in _extract_pdf_page_lines(page))
    except Exception as exc:  # pragma: no cover - defensive; pdfplumber surface
        raise RegistryValidationError(f"pdfplumber could not open record-design PDF {source_label}: {exc}") from exc


def _uses_page_record_layout(lines: tuple[str, ...]) -> bool:
    return any(_pdf_page_name(_clean_pdf_line(line)) is not None for line in lines)


def _snapshot_pdf_page(page: Page) -> _PdfPageSnapshot:
    return _PdfPageSnapshot(
        lines=_extract_pdf_page_lines(page),
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


def _extract_pdf_page_lines(page: Page) -> tuple[str, ...]:
    text = page.extract_text() or ""
    return tuple(text.splitlines())


class _PdfParseState:
    """Mutable state for the PDF record-design line parser.

    Encapsulates the three locals (``current`` draft sheet,
    ``in_table`` flag, ``pending_name`` carried across page-name
    boundaries) so the per-line dispatch can mutate them without
    threading three out-parameters through every helper.
    """

    __slots__ = ("current", "in_table", "pending_name", "sheets", "source_label")

    def __init__(self, *, source_label: str) -> None:
        self.sheets: list[RecordDesignSheet] = []
        self.current: _PdfSheetDraft | None = None
        self.in_table: bool = False
        self.pending_name: str | None = None
        self.source_label = source_label

    def finalise(self) -> tuple[RecordDesignSheet, ...]:
        if self.current is not None:
            self.sheets.append(self.current.finish(source_label=self.source_label))
        non_empty = tuple(sheet for sheet in self.sheets if sheet.fields)
        if not non_empty:
            raise RegistryValidationError("record-design PDF did not contain parseable field rows")
        return non_empty

    def feed(self, line: str, row_number: int) -> None:
        if not line or _is_pdf_footer(line):
            return
        if self._consume_page_name(line):
            return
        if self._consume_record_heading(line):
            return
        if self._consume_table_header(line):
            return
        if self._consume_title_continuation(line):
            return
        if _is_pdf_page_heading(line):
            return
        if self._consume_field_row(line, row_number):
            return
        self._consume_field_continuation(line)

    def _consume_page_name(self, line: str) -> bool:
        page_name = _pdf_page_name(line)
        if page_name is None:
            return False
        self.pending_name = page_name
        if self.current is not None and self.current.name != page_name:
            self.sheets.append(self.current.finish(source_label=self.source_label))
            self.current = _PdfSheetDraft(page_name)
        return True

    def _consume_record_heading(self, line: str) -> bool:
        heading_name = _pdf_record_heading_name(line)
        if heading_name is None:
            return False
        if self.current is not None:
            self.sheets.append(self.current.finish(source_label=self.source_label))
        self.current = _PdfSheetDraft(heading_name)
        self.in_table = False
        return True

    def _consume_table_header(self, line: str) -> bool:
        if not _is_pdf_header(line):
            return False
        if self.current is None:
            self.current = _PdfSheetDraft(self.pending_name or "PDF record design")
        self.in_table = True
        return True

    def _consume_title_continuation(self, line: str) -> bool:
        if self.in_table or self.current is None or self.current.fields:
            return False
        if not _looks_like_title_continuation(line):
            return False
        self.current.name = _normalise_pdf_sheet_name(_join_pdf_parts([self.current.name, line]))
        return True

    def _consume_field_row(self, line: str, row_number: int) -> bool:
        row = _parse_pdf_row(line, row_number)
        if row is None:
            return False
        if self.current is None:
            self.current = _PdfSheetDraft(self.pending_name or "PDF record design")
        self.current.start_field(row)
        self.in_table = True
        return True

    def _consume_field_continuation(self, line: str) -> None:
        if self.in_table and self.current is not None and self.current.current is not None:
            self.current.current.append_continuation(line)


def _extract_pdf_lines(lines: tuple[str, ...], *, source_label: str) -> tuple[RecordDesignSheet, ...]:
    state = _PdfParseState(source_label=source_label)
    for row_number, raw_line in enumerate(lines, start=1):
        state.feed(_clean_pdf_line(raw_line), row_number)
    return state.finalise()


def _validate_pdf_sheet(sheet: RecordDesignSheet, *, source_label: str) -> None:
    if not sheet.fields:
        return
    first_field = sheet.fields[0]
    if first_field.offset != 1:
        raise RegistryValidationError(
            f"{source_label} {sheet.name!r} first field starts at position {first_field.offset}; expected 1",
        )
    for parsed_field in sheet.fields:
        if parsed_field.offset < 1:
            raise RegistryValidationError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"position {parsed_field.offset}",
            )
        if parsed_field.length < 1:
            raise RegistryValidationError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"length {parsed_field.length}",
            )
    terminal_position = max(parsed_field.offset + parsed_field.length - 1 for parsed_field in sheet.fields)
    if sheet.total_positions is not None and terminal_position != sheet.total_positions:
        raise RegistryValidationError(
            f"{source_label} {sheet.name!r} declares {sheet.total_positions} total positions "
            f"but parsed fields fill {terminal_position}",
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
        raise RegistryValidationError(f"PDF row {source_row} has inverted position range {start}-{end}")
    return _PdfRow(
        source_row=source_row,
        ordinal=None,
        offset=start,
        length=end - start + 1,
        type_code=_normalise_pdf_type_code(narrative.group("type")),
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
        or re.match(r"^\d+$", line),
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
        or line == "DISEÑOS DE REGISTRO",
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


def _extract_visual_record_design_chart(
    pages: tuple[_PdfPageSnapshot, ...],
    *,
    source_label: str,
) -> tuple[RecordDesignSheet, ...]:
    pages_by_sheet: dict[str, list[_PdfPageSnapshot]] = {}
    for page in pages:
        sheet_name = _visual_chart_page_sheet_name(page)
        if sheet_name is not None:
            pages_by_sheet.setdefault(sheet_name, []).append(page)
    if not pages_by_sheet:
        return ()

    sheets = tuple(
        _extract_visual_chart_sheet(sheet_name, tuple(sheet_pages), source_label=source_label)
        for sheet_name, sheet_pages in pages_by_sheet.items()
    )
    return sheets if all(sheet.fields for sheet in sheets) else ()


def _visual_chart_page_sheet_name(page: _PdfPageSnapshot) -> str | None:
    for line in page.lines:
        match = _VISUAL_CHART_HEADER_RE.match(_clean_pdf_line(line))
        if match is not None:
            title = _normalise_pdf_sheet_name(match.group("title"))
            return f"Tipo {match.group('record')} - {title}"
    return None


def _extract_visual_chart_sheet(
    name: str,
    pages: tuple[_PdfPageSnapshot, ...],
    *,
    source_label: str,
) -> RecordDesignSheet:
    fragments: list[_VisualChartFragment] = []
    for page in pages:
        fragments.extend(_extract_visual_chart_fragments(page))

    merged = _merge_visual_chart_fragments(sorted(fragments, key=lambda fragment: fragment.start))
    fields = tuple(
        RecordDesignField(
            sheet=name,
            row=ordinal,
            ordinal=ordinal,
            offset=fragment.start,
            length=fragment.end - fragment.start + 1,
            type_code=_VISUAL_CHART_TYPE_CODE,
            description=fragment.description,
            content="Extracted from visual record-design chart geometry.",
        )
        for ordinal, fragment in enumerate(merged, start=1)
    )
    total_positions = max((field.offset + field.length - 1 for field in fields), default=None)
    sheet = RecordDesignSheet(name=name, fields=fields, total_positions=total_positions)
    _validate_pdf_sheet(sheet, source_label=source_label)
    return sheet


def _extract_visual_chart_fragments(page: _PdfPageSnapshot) -> list[_VisualChartFragment]:
    grid = _visual_chart_grid(page)
    if grid is None:
        return []
    left, cell_width, horizontal_rules = grid
    fragments: list[_VisualChartFragment] = []
    number_rows = _visual_chart_number_rows(page)
    for index, (number_top, first_position) in enumerate(number_rows):
        row_rules = _visual_chart_rules_for_number_row(horizontal_rules, number_top)
        if not row_rules:
            continue
        region_top = number_rows[index - 1][0] + 8 if index else 20
        for rule in row_rules:
            start = first_position - 1 + round((rule.x0 - left) / cell_width) + 1
            end = first_position - 1 + round((rule.x1 - left) / cell_width)
            if start > end:
                continue
            fragments.append(
                _VisualChartFragment(
                    start=start,
                    end=end,
                    description=_visual_chart_description(page, rule, region_top=region_top),
                ),
            )
    return fragments


def _visual_chart_grid(page: _PdfPageSnapshot) -> tuple[float, float, tuple[_PdfRect, ...]] | None:
    horizontal_rules = tuple(
        rect for rect in page.rects if rect.fill == 0.0 and rect.height <= 2.0 and rect.width >= 8.0
    )
    full_width_rules = tuple(rect for rect in horizontal_rules if rect.width > 700.0)
    if not full_width_rules:
        return None
    left = min(rect.x0 for rect in full_width_rules)
    right = max(rect.x1 for rect in full_width_rules)
    return left, (right - left) / 65, horizontal_rules


def _visual_chart_number_rows(page: _PdfPageSnapshot) -> list[tuple[float, int]]:
    grouped_words: dict[float, list[_PdfWord]] = {}
    for word in page.words:
        if _visual_chart_number_values(word.text):
            grouped_words.setdefault(round(word.top, 1), []).append(word)

    rows: list[tuple[float, int]] = []
    for top, words in grouped_words.items():
        values = [
            value
            for word in sorted(words, key=lambda current: current.x0)
            for value in _visual_chart_number_values(word.text)
        ]
        if len(values) >= 20 and max(values) - min(values) >= 30:
            rows.append((top, min(values)))
    return sorted(rows)


def _visual_chart_number_values(text: str) -> tuple[int, ...]:
    if not text.isdigit():
        return ()
    if len(text) <= 3:
        return (int(text),)
    if len(text) % 3 == 0:
        return tuple(int(text[index : index + 3]) for index in range(0, len(text), 3))
    return ()


def _visual_chart_rules_for_number_row(
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


def _visual_chart_description(
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
        and not _is_visual_chart_number_text(word.text)
    ]
    description = _normalise_visual_chart_description(words)
    return description or "BLANCOS."


def _normalise_visual_chart_description(words: list[_PdfWord]) -> str:
    tokens = [word.text for word in sorted(words, key=lambda word: (word.top, word.x0))]
    tokens = [
        _REVERSED_VISUAL_CHART_TOKENS.get(visual_word, visual_word) for visual_word in tokens if visual_word != "D"
    ]
    if not tokens:
        return ""
    if any(token.strip(".").upper() in _REVERSED_VISUAL_CHART_WORDS for token in tokens):
        tokens = [token[::-1] for token in reversed(tokens)]
    return _clean_visual_chart_description(_dedupe_visual_chart_tokens(tokens))


def _dedupe_visual_chart_tokens(tokens: list[str]) -> str:
    deduped: list[str] = []
    for token in tokens:
        if not deduped or deduped[-1] != token:
            deduped.append(token)
    return " ".join(deduped).strip()


def _clean_visual_chart_description(description: str) -> str:
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


def _is_visual_chart_number_text(text: str) -> bool:
    return bool(re.fullmatch(r"\d+", text) or re.fullmatch(r"\d{3}(?:\d{3})+", text))


def _merge_visual_chart_fragments(
    fragments: list[_VisualChartFragment],
) -> tuple[_VisualChartFragment, ...]:
    merged: list[_VisualChartFragment] = []
    for fragment in fragments:
        if (
            merged
            and fragment.start == merged[-1].end + 1
            and merged[-1].end % 65 == 0
            and _visual_chart_fragments_should_merge(merged[-1], fragment)
        ):
            previous = merged[-1]
            description = _merge_visual_chart_descriptions(previous.description, fragment.description)
            merged[-1] = _VisualChartFragment(start=previous.start, end=fragment.end, description=description)
            continue
        merged.append(fragment)
    return tuple(merged)


def _visual_chart_fragments_should_merge(
    previous: _VisualChartFragment,
    current: _VisualChartFragment,
) -> bool:
    return not (previous.description == "BLANCOS." and current.description != "BLANCOS.")


def _merge_visual_chart_descriptions(previous: str, current: str) -> str:
    parts = [description for description in (previous, current) if description != "BLANCOS."]
    return _clean_visual_chart_description(_join_pdf_parts(parts)) or "BLANCOS."


_VISUAL_CHART_HEADER_RE = re.compile(
    r"^MODELO\s+\d+\s+REGISTRO DE TIPO\s+(?P<record>\d+)\.?\s+(?P<title>REGISTRO DE .+)$",
    re.IGNORECASE,
)
_VISUAL_CHART_TYPE_CODE = "No consta en gráfico"
_REVERSED_VISUAL_CHART_WORDS = {
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
_REVERSED_VISUAL_CHART_TOKENS = {
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
    "DerivedDisenoCasilla",
    "DisenoCoverageReport",
    "RecordDesignField",
    "RecordDesignSheet",
    "build_diseno_coverage_report",
    "calculation_closure_casilla_ids",
    "calculation_closure_legal_refs",
    "calculation_closure_record_design_metadata",
    "derive_calculation_completeness_casillas",
    "derive_diseno_coverage_casillas",
    "extract_record_design",
    "extract_record_design_pdf",
    "extract_record_design_pdf_bytes",
    "extract_record_design_workbook",
]
