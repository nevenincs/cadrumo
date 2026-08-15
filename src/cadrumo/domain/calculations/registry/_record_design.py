"""Read-only extraction of official AEAT record-design rows.

Parses official AEAT record-design workbooks (PDF or XLS/XLSX) and derives
coverage casillas from a :class:`ModeloRevision` so that the extracted layout
can be compared against the registry declarations.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from io import BufferedReader, BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import ConfigDict, TypeAdapter, ValidationError

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these never need to exist at runtime. The parser
    # backends themselves (openpyxl, pdfplumber, pypdfium2, xlrd) are among the
    # heaviest third-party imports in the tree and are deferred into the
    # extraction functions that actually call them -- importing the registry
    # must not pay for a PDF/XLS parser stack no calculation touches.
    from openpyxl.worksheet.worksheet import Worksheet
    from pdfplumber.page import Page
    from xlrd.sheet import Sheet as XlrdSheet

from ....core.external_constants import PDF_EXTENSION as _PDF_EXTENSION
from ....core.external_constants import XLS_EXTENSION as _XLS_EXTENSION
from ....core.external_constants import XLSM_EXTENSION as _XLSM_EXTENSION
from ....core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from ....core.logging import get_logger
from ....core.paths import path_stat_fingerprint
from ....core.tabular import coerce_cell_text
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
from ._record_design_schema import (
    RecordDesignAuxiliaryEnvelopeHeader,
    RecordDesignAuxiliaryEnvelopeHeaderField,
    RecordDesignAuxiliaryEnvelopeHeaderRole,
    RecordDesignCompositeRelativeClosing,
    RecordDesignExtraction,
    RecordDesignField,
    RecordDesignRelativeSuffixMarker,
    RecordDesignSheet,
    RecordDesignSkippedSheet,
    RecordDesignVariableBodyMarker,
    RecordDesignVariableEnvelope,
    RecordDesignVariableTotalMarker,
)

_log = get_logger(__name__)

_OPENPYXL_HEADER_FOOTER_WARNING = "Cannot parse header or footer so it will be ignored"
_OPENPYXL_PRINT_AREA_WARNING = r"Print area cannot be set to Defined name: .*"
_NUMERIC_TUPLE_ADAPTER: TypeAdapter[tuple[int | float, ...]] = TypeAdapter(
    tuple[int | float, ...], config=ConfigDict(strict=True)
)


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


@dataclass
class _WorkbookSheetRows:
    """Parsed workbook rows retained until their sheet-level shape is known."""

    fields: list[RecordDesignField] = field(default_factory=list)
    total_positions: int | None = None
    variable_bodies: list[RecordDesignVariableBodyMarker] = field(default_factory=list)
    relative_suffixes: list[RecordDesignRelativeSuffixMarker] = field(default_factory=list)
    variable_totals: list[RecordDesignVariableTotalMarker] = field(default_factory=list)
    variable_body_marker_rows: list[int] = field(default_factory=list)
    relative_suffix_marker_rows: list[int] = field(default_factory=list)
    variable_total_marker_rows: list[int] = field(default_factory=list)
    mixed_total_rows: list[int] = field(default_factory=list)


def extract_record_design(path: Path) -> RecordDesignExtraction:
    """Return one official record-design source's parsed sheets AND what it could not read.

    Returns:
        The :class:`RecordDesignExtraction` for the source, which names both the
        sheets that parsed and any the extractor had to skip.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design source not found: {path}")
    return _extract_record_design_cached(*path_stat_fingerprint(resolved))


@lru_cache(maxsize=256)
def _extract_record_design_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
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


def _extraction(
    source_path: Path,
    sheets: list[RecordDesignSheet],
    skipped: list[RecordDesignSkippedSheet],
) -> RecordDesignExtraction:
    """Assemble one source's result, refusing only when NOTHING could be read.

    A source where every sheet failed is still a hard error -- there is no design
    there to hand back. A source where SOME sheets failed is a partial read, and
    it is returned rather than raised so a caller can decide: refusing outright
    would drop Modelo 232, whose ``TABLAS`` tab is a legitimate lookup table and
    not a record at all. The extractor cannot tell a lookup tab from a lost
    record body, so it reports both and adjudicates neither.
    """
    if not sheets:
        detail = "; ".join(f"{item.name!r}: {item.reason}" for item in skipped) if skipped else "none"
        raise RegistryValidationError(
            f"{source_path}: no record-design sheets found; skipped sheets: {detail}",
        )
    return RecordDesignExtraction(source=str(source_path), sheets=tuple(sheets), skipped=tuple(skipped))


def extract_record_design_workbook(path: Path) -> RecordDesignExtraction:
    """Return the :class:`RecordDesignExtraction` workbook ``path`` describes."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design workbook not found: {path}")
    return _extract_record_design_workbook_cached(*path_stat_fingerprint(resolved))


def extract_record_design_xls_workbook(path: Path) -> RecordDesignExtraction:
    """Return a legacy binary XLS workbook's parsed sheets AND any it could not read.

    Returns:
        The :class:`RecordDesignExtraction` for the workbook.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design XLS workbook not found: {path}")
    return _extract_record_design_xls_workbook_cached(*path_stat_fingerprint(resolved))


@lru_cache(maxsize=256)
def _extract_record_design_workbook_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    del byte_count, modified_ns
    from openpyxl import load_workbook

    source_path = Path(path)
    with _ignore_openpyxl_header_footer_metadata_warnings():
        workbook = load_workbook(source_path, read_only=True, data_only=True)
        try:
            sheets: list[RecordDesignSheet] = []
            skipped: list[RecordDesignSkippedSheet] = []
            for worksheet in workbook.worksheets:
                try:
                    sheets.append(_extract_sheet(worksheet))
                except ValueError as exc:
                    if "has no record-design header" not in str(exc):
                        raise
                    skipped.append(RecordDesignSkippedSheet(name=worksheet.title.strip(), reason=str(exc)))
            return _extraction(source_path, sheets, skipped)
        finally:
            workbook.close()


@lru_cache(maxsize=128)
def _extract_record_design_xls_workbook_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    del byte_count, modified_ns
    import xlrd

    source_path = Path(path)
    workbook = xlrd.open_workbook(str(source_path), on_demand=True)
    try:
        sheets: list[RecordDesignSheet] = []
        skipped: list[RecordDesignSkippedSheet] = []
        for sheet_name in workbook.sheet_names():
            worksheet = workbook.sheet_by_name(sheet_name)
            try:
                sheets.append(_extract_xls_sheet(worksheet))
            except ValueError as exc:
                if "has no record-design header" not in str(exc):
                    raise
                skipped.append(RecordDesignSkippedSheet(name=sheet_name.strip(), reason=str(exc)))
        return _extraction(source_path, sheets, skipped)
    finally:
        workbook.release_resources()


@contextmanager
def _ignore_openpyxl_header_footer_metadata_warnings() -> Generator[None]:
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


def extract_record_design_pdf(path: Path) -> RecordDesignExtraction:
    """Return the :class:`RecordDesignExtraction` read from an official AEAT PDF."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design PDF not found: {path}")
    return _extract_record_design_pdf_cached(*path_stat_fingerprint(resolved))


@lru_cache(maxsize=256)
def _extract_record_design_pdf_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    del byte_count, modified_ns
    source_path = Path(path)
    with source_path.open("rb") as pdf_file:
        return _extract_record_design_pdf_stream(pdf_file, source_label=str(source_path))


def extract_record_design_pdf_bytes(
    pdf_bytes: bytes,
    *,
    source_label: str = "in-memory record-design PDF",
) -> RecordDesignExtraction:
    """Return the record design extracted from PDF bytes.

    Returns:
        The :class:`RecordDesignExtraction` for the PDF content.
    """
    return _extract_record_design_pdf_stream(BytesIO(pdf_bytes), source_label=source_label)


def _extract_record_design_pdf_stream(
    stream: BufferedReader | BytesIO,
    *,
    source_label: str,
) -> RecordDesignExtraction:
    import pdfplumber

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
            # The geometry reader either reconstructs every charted record or
            # returns nothing, so a result here is complete by construction.
            return RecordDesignExtraction(source=source_label, sheets=visual_chart)
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
    parsed_rows = _scan_sheet_rows(sheet_name, header, rows)
    terminal_extent = _require_contiguous_field_geometry(sheet_name, parsed_rows.fields)
    if parsed_rows.total_positions is not None and terminal_extent != parsed_rows.total_positions:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} declares {parsed_rows.total_positions} total positions "
            f"but parsed fields fill {terminal_extent}",
        )
    variable_envelope = _variable_envelope(sheet_name, parsed_rows, terminal_extent)
    auxiliary_envelope_header = (
        None
        if variable_envelope is not None
        else _auxiliary_envelope_header(sheet_name, parsed_rows.fields, parsed_rows.total_positions, terminal_extent)
    )
    return RecordDesignSheet(
        name=sheet_name,
        fields=tuple(parsed_rows.fields),
        total_positions=parsed_rows.total_positions,
        variable_envelope=variable_envelope,
        auxiliary_envelope_header=auxiliary_envelope_header,
    )


def _scan_sheet_rows(
    sheet_name: str,
    header: _WorkbookHeader,
    rows: Iterator[tuple[int, tuple[object, ...]]],
) -> _WorkbookSheetRows:
    parsed_rows = _WorkbookSheetRows()
    trailing_blank_rows = 0
    for row_number, row in rows:
        values = tuple(row)
        if _is_blank_row(values):
            trailing_blank_rows += 1
            if parsed_rows.fields and trailing_blank_rows >= 25:
                break
            continue
        trailing_blank_rows = 0
        if _consume_total_row(sheet_name, parsed_rows, row_number, values):
            continue
        _consume_field_row(sheet_name, parsed_rows, header, row_number, values)
    return parsed_rows


def _consume_total_row(
    sheet_name: str,
    parsed_rows: _WorkbookSheetRows,
    row_number: int,
    values: tuple[object, ...],
) -> bool:
    total_label_index = _total_label_index(values)
    if total_label_index is None:
        return False
    row_total = _positive_integer_after(values, total_label_index)
    has_variable_total = any(_optional_text(candidate) == "Variable" for candidate in values[total_label_index + 1 :])
    if has_variable_total:
        parsed_rows.variable_total_marker_rows.append(row_number)
    if row_total is not None and has_variable_total:
        parsed_rows.mixed_total_rows.append(row_number)
    if row_total is not None:
        if parsed_rows.total_positions is not None:
            raise RegistryValidationError(f"record-design sheet {sheet_name!r} declares duplicate fixed totals")
        parsed_rows.total_positions = row_total
    elif has_variable_total:
        parsed_rows.variable_totals.append(
            RecordDesignVariableTotalMarker(
                sheet=sheet_name,
                row=row_number,
                label="total",
                length="Variable",
            ),
        )
    return True


def _consume_field_row(
    sheet_name: str,
    parsed_rows: _WorkbookSheetRows,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
) -> None:
    # ``RecordDesignField.ordinal`` is the printed LABEL (``ordinal_text``), never
    # an arithmetic value -- it is now representable verbatim, so there is no more
    # "printed but unreadable" case to refuse for it. The two MARKER rows below
    # (variable-body, relative-suffix) are unrelated types whose own ``ordinal``
    # field is still a plain sequential ``int``, so they keep reading the
    # int-or-None form.
    ordinal_int = _int_or_none(_cell(values, header.ordinal_index))
    ordinal_text = _ordinal_text(_cell(values, header.ordinal_index))
    offset = _int_or_none(_cell(values, header.offset_index))
    length = _int_or_none(_cell(values, header.length_index))
    raw_offset = _optional_text(_cell(values, header.offset_index))
    raw_length = _optional_text(_cell(values, header.length_index))
    if raw_length == "Variable":
        parsed_rows.variable_body_marker_rows.append(row_number)
        if ordinal_int is not None and offset is not None:
            parsed_rows.variable_bodies.append(
                _variable_body_marker(sheet_name, header, row_number, values, ordinal_int, offset),
            )
        return
    if raw_offset == "***":
        parsed_rows.relative_suffix_marker_rows.append(row_number)
        if ordinal_int is not None and length is not None:
            parsed_rows.relative_suffixes.append(
                _relative_suffix_marker(sheet_name, header, row_number, values, ordinal_int, length),
            )
        return
    if offset is None or length is None:
        return
    field = _record_design_field(sheet_name, header, row_number, values, ordinal_text, offset, length)
    parent_index = _matching_component_parent_index(parsed_rows.fields, ordinal_text, offset, length)
    if parent_index is not None:
        parent = parsed_rows.fields[parent_index]
        parsed_rows.fields[parent_index] = parent.model_copy(update={"components": (*parent.components, field)})
        return
    parsed_rows.fields.append(field)


def _matching_component_parent_index(
    fields: list[RecordDesignField],
    ordinal_text: str | None,
    offset: int,
    length: int,
) -> int | None:
    """Return the index of the field ``ordinal_text``/``offset``/``length`` desglosa from.

    AEAT prints a component with a DOTTED ordinal (``19.1`` under parent ``19``),
    never a bare one -- Modelo 303's ``14bis`` has no dot and is a genuine peer,
    not a component of ``14``, and this is the discriminator that keeps them
    apart. The dotted integer prefix alone is not enough on its own -- an
    unrelated field elsewhere in the same sheet could coincidentally share an
    ordinal -- so BOTH conditions are required together: the immediately
    preceding field's ordinal is the exact dotted prefix, AND this row's byte
    span falls entirely inside that field's own already-declared span. Checked
    against only the immediately preceding field, matching every component's
    observed source position directly beneath its parent, never a scan of the
    whole sheet.
    """
    if ordinal_text is None or "." not in ordinal_text or not fields:
        return None
    prefix = ordinal_text.split(".", 1)[0]
    parent_index = len(fields) - 1
    parent = fields[parent_index]
    if parent.ordinal != prefix:
        return None
    if offset < parent.offset or offset + length > parent.offset + parent.length:
        return None
    return parent_index


def _variable_body_marker(
    sheet_name: str,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: int | None,
    offset: int,
) -> RecordDesignVariableBodyMarker:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    return RecordDesignVariableBodyMarker(
        sheet=sheet_name,
        row=row_number,
        ordinal=ordinal,
        offset=offset,
        length="Variable",
        type_code=_required_text(_cell(values, header.type_index), sheet_name, row_number, "type"),
        description=description,
        validation=validation,
        content=content,
    )


def _relative_suffix_marker(
    sheet_name: str,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: int,
    length: int,
) -> RecordDesignRelativeSuffixMarker:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    return RecordDesignRelativeSuffixMarker(
        sheet=sheet_name,
        row=row_number,
        ordinal=ordinal,
        offset="***",
        length=length,
        type_code=_required_text(_cell(values, header.type_index), sheet_name, row_number, "type"),
        description=description,
        validation=validation,
        content=content,
    )


def _record_design_field(
    sheet_name: str,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: str | None,
    offset: int,
    length: int,
) -> RecordDesignField:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    return RecordDesignField(
        sheet=sheet_name,
        row=row_number,
        ordinal=ordinal,
        offset=offset,
        length=length,
        type_code=_required_text(_cell(values, header.type_index), sheet_name, row_number, "type"),
        complementary=_optional_header_text(values, header.complementary_index),
        description=description,
        validation=validation,
        content=content,
    )


def _field_texts(
    sheet_name: str,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
) -> tuple[str | None, str | None, str]:
    validation = _optional_header_text(values, header.validation_index)
    content = _optional_header_text(values, header.content_index)
    return (
        validation,
        content,
        _field_description_text(
            values,
            header=header,
            content=content,
            sheet=sheet_name,
            row=row_number,
        ),
    )


def _variable_envelope(
    sheet_name: str,
    parsed_rows: _WorkbookSheetRows,
    terminal_extent: int | None,
) -> RecordDesignVariableEnvelope | None:
    if not (parsed_rows.variable_body_marker_rows or parsed_rows.mixed_total_rows):
        return None
    if parsed_rows.mixed_total_rows:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} mixes fixed and variable totals "
            f"in row {parsed_rows.mixed_total_rows[0]}",
        )
    _require_valid_variable_envelope_markers(sheet_name, parsed_rows)
    variable_body = parsed_rows.variable_bodies[0]
    closing_suffixes, terminator = _split_record_terminator(parsed_rows.relative_suffixes)
    closing = _relative_closing(sheet_name, closing_suffixes)
    closing_parts = _relative_closing_parts(closing)
    variable_total = parsed_rows.variable_totals[0]
    if parsed_rows.total_positions is not None or terminal_extent is None:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} mixes fixed-total and variable-envelope geometry",
        )
    if variable_body.offset != terminal_extent + 1:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} variable body starts at {variable_body.offset} "
            f"after fixed prefix extent {terminal_extent}",
        )
    _require_ordered_variable_envelope(
        sheet_name,
        parsed_rows.fields,
        variable_body,
        closing_parts,
        variable_total,
    )
    _require_terminator_closes_the_record(sheet_name, closing_parts, terminator)
    return RecordDesignVariableEnvelope(
        name=sheet_name,
        prefix_fields=tuple(parsed_rows.fields),
        prefix_extent=terminal_extent,
        body=variable_body,
        closing=closing,
        terminator=terminator,
        variable_total=variable_total,
    )


def _auxiliary_envelope_header(
    sheet_name: str,
    fields: list[RecordDesignField],
    declared_total: int | None,
    terminal_extent: int | None,
) -> RecordDesignAuxiliaryEnvelopeHeader | None:
    """Recognise only the exact total-less Modelo 390 page-zero source shape.

    Fixed sheets otherwise remain unchanged. A no-total 328-byte sheet is not
    permitted to acquire a fixed-record total from terminal extent; only an
    exact thirteen-field M390 header receives this distinct classification.
    """
    if (
        declared_total is not None
        or terminal_extent != 328
        or len(fields) != len(RecordDesignAuxiliaryEnvelopeHeaderRole)
    ):
        return None
    try:
        return RecordDesignAuxiliaryEnvelopeHeader(
            sheet=sheet_name,
            record_identity=sheet_name,
            fields=tuple(
                RecordDesignAuxiliaryEnvelopeHeaderField(role=role, field=field)
                for role, field in zip(RecordDesignAuxiliaryEnvelopeHeaderRole, fields, strict=True)
            ),
            emitted_extent=terminal_extent,
        )
    except ValueError:
        return None


def _require_valid_variable_envelope_markers(sheet_name: str, parsed_rows: _WorkbookSheetRows) -> None:
    malformed_marker_rows = (
        set(parsed_rows.variable_body_marker_rows) - {body.row for body in parsed_rows.variable_bodies}
    ) | (set(parsed_rows.relative_suffix_marker_rows) - {suffix.row for suffix in parsed_rows.relative_suffixes})
    if malformed_marker_rows:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has malformed variable-envelope marker "
            f"in row {min(malformed_marker_rows)}",
        )
    if len(parsed_rows.variable_bodies) > 1:
        raise RegistryValidationError(f"record-design sheet {sheet_name!r} declares duplicate variable-body markers")
    if len(parsed_rows.variable_totals) > 1:
        raise RegistryValidationError(f"record-design sheet {sheet_name!r} declares duplicate variable totals")
    if not parsed_rows.variable_bodies or not parsed_rows.relative_suffixes or not parsed_rows.variable_totals:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has an incomplete variable-envelope composition"
        )


def _require_ordered_variable_envelope(
    sheet_name: str,
    fields: list[RecordDesignField],
    variable_body: RecordDesignVariableBodyMarker,
    closing_parts: tuple[RecordDesignRelativeSuffixMarker, ...],
    variable_total: RecordDesignVariableTotalMarker,
) -> None:
    first_closing_part = closing_parts[0]
    last_closing_part = closing_parts[-1]
    # POSITION IS THE ORDERING AUTHORITY, NOT THE ORDINAL.
    #
    # This checked composition order twice, once on source row and once on ordinal,
    # and the ordinal half asserted nothing the row half did not: both ask whether
    # the body sits after the fixed prefix and before the closing. Where the two
    # could disagree, the ordinal is the one that would be wrong, because AEAT's
    # ordinal is a PRINTED LABEL rather than an arithmetic value -- it publishes
    # ``14bis`` to insert a field between 14 and 15 without renumbering, exactly as
    # the law numbers an inserted article. Comparing labels arithmetically assumes a
    # density AEAT never promised.
    #
    # The bytes order themselves and are checked as such elsewhere: the prefix must
    # be contiguous from offset 1, and the variable body must begin at
    # ``prefix_extent + 1``. Those are the real geometric assertions; this one is
    # about which SOURCE ROWS compose the envelope, so it reads rows.
    ordered_rows = max(item.row for item in fields) < variable_body.row < first_closing_part.row
    ordered_rows = ordered_rows and first_closing_part.row <= last_closing_part.row < variable_total.row
    if not ordered_rows:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has misordered variable-envelope composition markers",
        )


#: How AEAT NAMES the physical end-of-record row, in the wordings it uses across
#: both workbook and PDF designs. ONE definition with two consumers: the workbook
#: closing splitter below, and the PDF compact-row recogniser further down which
#: composes this into its own line pattern.
#:
#: Two independent notions of "what a CRLF row is" is how the two parsers came to
#: disagree about one domain fact -- the PDF path has recognised the terminator
#: since it was written, while the workbook path refused thirty designs across
#: eight modelos for declaring one.
_RECORD_TERMINATOR_PHRASE = r"fin de registro|salto de l[íi]nea|\bCRLF\b"
#: Matched on the declared MEANING rather than on width: a two-byte relative
#: suffix that is not a line terminator is part of the closing identifier and
#: must not be mistaken for one.
_RECORD_TERMINATOR = re.compile(_RECORD_TERMINATOR_PHRASE, re.IGNORECASE)


def _split_record_terminator(
    suffixes: list[RecordDesignRelativeSuffixMarker],
) -> tuple[list[RecordDesignRelativeSuffixMarker], RecordDesignRelativeSuffixMarker | None]:
    """Separate a trailing physical end-of-record row from the closing identifier.

    The closing identifies the record; the terminator ends the line. AEAT declares
    them as adjacent relative-offset rows, and the closing recogniser below reads
    only the first kind, so a design declaring both was refused outright -- thirty
    of them, across eight modelos, every one well formed.

    Split rather than skipped. The terminator is returned to the caller and stored
    on the envelope, because its two bytes are part of the record: discarding it
    would let all thirty parse while every emitted record came out two bytes short,
    which is a clean-looking wrong answer rather than a refusal.
    """
    if not suffixes:
        return suffixes, None
    last = suffixes[-1]
    if last.length == 2 and _RECORD_TERMINATOR.search(last.description):
        return suffixes[:-1], last
    return suffixes, None


def _relative_closing(
    sheet_name: str,
    suffixes: list[RecordDesignRelativeSuffixMarker],
) -> RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing:
    if len(suffixes) == 1 and suffixes[0].length == 18:
        return suffixes[0]
    if len(suffixes) != 6:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has an incomplete or ambiguous relative closing",
        )
    try:
        return RecordDesignCompositeRelativeClosing(
            tag_prefix=suffixes[0],
            modelo=suffixes[1],
            discriminant=suffixes[2],
            filing_year=suffixes[3],
            period=suffixes[4],
            tag_suffix=suffixes[5],
        )
    except ValidationError as exc:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has a malformed composite relative closing: {exc}",
        ) from exc


def _require_terminator_closes_the_record(
    sheet_name: str,
    closing_parts: tuple[RecordDesignRelativeSuffixMarker, ...],
    terminator: RecordDesignRelativeSuffixMarker | None,
) -> None:
    """Refuse a terminator that does not sit last in the record.

    Without this the split would accept a two-byte line-terminator row appearing
    anywhere among the closing parts and quietly reorder the record's tail. The
    terminator is the LAST thing in a record by definition, so a design declaring
    it earlier is either malformed or is something this parser has misread, and
    both deserve a refusal rather than a rearrangement.
    """
    if terminator is None:
        return
    last_part = closing_parts[-1]
    # Reads the SOURCE ROW only. An earlier version of this also compared ordinals,
    # which was the same mistake the envelope-order check carried: AEAT's ordinal is
    # a printed label, so ordering by it assumes a density the authority never
    # promised. It was harmless while every ordinal happened to be an integer and
    # would have failed the moment a ``bis`` label reached this comparison.
    if terminator.row <= last_part.row:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} declares an end-of-record terminator at row "
            f"{terminator.row} which does not follow its closing identifier at row "
            f"{last_part.row}; a terminator that is not last is not a terminator",
        )


def _relative_closing_parts(
    closing: RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing,
) -> tuple[RecordDesignRelativeSuffixMarker, ...]:
    if isinstance(closing, RecordDesignCompositeRelativeClosing):
        return closing.parts
    return (closing,)


def _require_contiguous_field_geometry(
    sheet_name: str,
    fields: list[RecordDesignField],
) -> int | None:
    """Return the exact terminal extent after proving source-order geometry."""
    expected_offset = 1
    for parsed_field in fields:
        if parsed_field.offset != expected_offset:
            defect = "an overlap" if parsed_field.offset < expected_offset else "a gap"
            raise RegistryValidationError(
                f"record-design sheet {sheet_name!r} has {defect} before field at row {parsed_field.row}: "
                f"expected offset {expected_offset}, got {parsed_field.offset}",
            )
        expected_offset = parsed_field.offset + parsed_field.length
    return expected_offset - 1 if fields else None


def _is_blank_row(values: tuple[object, ...]) -> bool:
    return all(value is None or str(value).strip() == "" for value in values)


def _find_header(worksheet: Worksheet) -> _WorkbookHeader:
    for row_number, row in enumerate(worksheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        values = tuple(row)
        if not _is_ordinal_header(_cell(values, 0)):
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
        if not _is_ordinal_header(_cell(values, 0)):
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


def _is_ordinal_header(value: object | None) -> bool:
    normalized = _normalise_header_cell(value)
    return normalized in {"no", "n"} or re.fullmatch(r"version \d+(?:\.\d+)*", normalized) is not None


def _cell(values: tuple[object, ...], index: int) -> object | None:
    return values[index] if index < len(values) else None


def _optional_text(value: object | None) -> str | None:
    cleaned = coerce_cell_text(value)
    return cleaned or None


def _ordinal_text(value: object | None) -> str | None:
    """Render a printed ordinal cell verbatim, including a non-numeric label.

    ``integral_floats_as_int=True`` because openpyxl hands back a whole-number
    ordinal cell as a ``float`` (``19.0``); rendering that as ``"19.0"`` would
    break BOTH the M390 auxiliary-header ordinal sequence (which compares
    against plain ``"1"``..``"13"``) and the dotted-component prefix match
    (``"19.1"``'s prefix must equal parent ``"19"``, not ``"19.0"``).
    """
    cleaned = coerce_cell_text(value, integral_floats_as_int=True)
    return cleaned or None


def _optional_header_text(values: tuple[object, ...], index: int | None) -> str | None:
    if index is None:
        return None
    return _optional_text(_cell(values, index))


def _required_text(value: object | None, sheet: str, row: int, field: str) -> str:
    cleaned = coerce_cell_text(value)
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
        coerce_cell_text(value)
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


def _header_token(value: str) -> str:
    """Return a header cell's identity, ignoring AEAT's abbreviating full stop.

    AEAT abbreviates header labels inconsistently WITHIN one workbook: Modelo
    115 writes ``Lon`` on its first sheet and ``Lon.`` on its second. Exact
    membership therefore matched one sheet and missed the other, and because a
    sheet failing header detection is skipped, the entire record body was
    dropped while the file looked healthy.

    The stop is typography, not identity, so it is ignored on BOTH sides rather
    than by enrolling each spelling separately -- which is what the accepted set
    already does ad hoc for ``posic.`` and ``oblig.``, and what would have to be
    remembered again for every future label.
    """
    return value.rstrip(".")


def _header_names_one_column(cell: str, expected: str) -> bool:
    """Whether a header cell names the column ``expected`` names.

    AEAT ABBREVIATES BY TRUNCATION, and inconsistently within a single workbook:
    the length column is ``Lon`` on one Modelo 115 sheet and ``Lon.`` on the next,
    and ``Long.`` throughout Modelo 100 and on Modelo 714's header sheet. Matching
    on truncation-compatibility rather than against an enrolled list of spellings
    is what stops the next abbreviation needing a code change -- and the enrolled
    pairs already in this module (``com``/``comp``, ``validacion``/``oblig.``) are
    that treadmill visible in progress.

    Measured across every bundled workbook design before shipping: 117 sources
    unchanged, 6 improved, ZERO degraded. Modelo 714's four editions go from a
    silently dropped sheet to a complete read, and Modelo 100's 2019 design from
    refusing outright to 41 sheets.

    The three-character floor stops a one- or two-letter cell prefix-matching its
    way onto a column it does not name; without it a stray ``N`` or ``No`` cell
    would claim whichever column happened to start with it.
    """
    if cell == expected:
        return True
    shorter, longer = sorted((cell, expected), key=len)
    return len(shorter) >= 3 and longer.startswith(shorter)


def _optional_header_index(values: tuple[object, ...], *header_names: str) -> int | None:
    expected = [_header_token(name) for name in header_names]
    for index, value in enumerate(values):
        cell = _header_token(_normalise_header_cell(value))
        if cell and any(_header_names_one_column(cell, candidate) for candidate in expected):
            return index
    return None


def _total_label_index(values: tuple[object, ...]) -> int | None:
    for index, value in enumerate(values):
        if _normalise_header_cell(value) in {"total", "total:"}:
            return index
    return None


def _positive_integer_after(values: tuple[object, ...], label_index: int) -> int | None:
    for candidate in values[label_index + 1 :]:
        total = _int_or_none(candidate)
        if total is not None and total > 0:
            return total
    return None


_COMPACT_PDF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+(?P<type>An|Num|N|A)\s+(?P<text>.+)$",
    re.IGNORECASE,
)
#: A PDF row declaring the physical end of record. Its DESCRIPTION half composes
#: the SHARED terminator phrase rather than carrying a second private spelling, so
#: the workbook splitter and this recogniser cannot drift on what a CRLF row is.
#: They already had: this one has known the terminator since it was written, while
#: the workbook path refused every design that declared one.
_COMPACT_PDF_CRLF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<type>An|Num|N|A)\s+"
    rf"(?P<text>(?:{_RECORD_TERMINATOR_PHRASE}).*)$",
    re.IGNORECASE,
)
_NARRATIVE_PDF_ROW_RE = re.compile(
    r"^\s*(?P<start>\d+)(?:\s*[-\u2013]\s*(?P<end>\d+))?\s+"
    r"(?P<type>Alfanum[eé]rico|Alfab[eé]tico|Num[eé]rico|Alphanumeric|Alphabetic|Numeric|Blank|[-\u2013]+)\s*"
    r"(?P<text>.*)$",
    re.IGNORECASE,
)
_PDF_PAGE_RECORD_RE = re.compile(r"^P[áa]g\s+(?P<page>\d+)\s+DISE[ÑN]O DE REGISTRO\b", re.IGNORECASE)
_PDF_RECORD_HEADING_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?(?:TIPO DE REGISTRO|Tipo de registro|RECORD TYPE|Record [Tt]ype)\s+"
    r"(?P<record>\d+)\s*:\s*(?P<title>.+)$",
    re.IGNORECASE,
)
#: English AEAT record-design translations also head a record with the reversed
#: word order "TYPE <n> RECORD: <title>" (observed in the modelo 604 ATF English
#: appendix), distinct from the "RECORD TYPE <n>: <title>" order above.
_PDF_RECORD_HEADING_REVERSED_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?TYPE\s+(?P<record>\d+)\s+RECORD\s*:\s*(?P<title>.+)$",
    re.IGNORECASE,
)


@dataclass
class _PdfFieldDraft:
    sheet: str
    row: int
    ordinal: str | None
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
            ordinal=row.ordinal if row.ordinal is not None else str(len(self.fields) + 1),
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
    ordinal: str | None
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
    import pypdfium2 as pdfium

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
    import pdfplumber

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

    def finalise(self) -> RecordDesignExtraction:
        """Return the parsed records, naming any the parser opened and could not fill.

        The empty-sheet filter here is the PDF equivalent of the workbook skip
        list: a record heading the parser recognised but found no field rows
        under is a record it did NOT read, and dropping it silently made the
        document look shorter than it is rather than incompletely read.
        """
        if self.current is not None:
            self.sheets.append(self.current.finish(source_label=self.source_label))
        non_empty = tuple(sheet for sheet in self.sheets if sheet.fields)
        if not non_empty:
            raise RegistryValidationError("record-design PDF did not contain parseable field rows")
        return RecordDesignExtraction(
            source=self.source_label,
            sheets=non_empty,
            skipped=tuple(
                RecordDesignSkippedSheet(
                    name=sheet.name,
                    reason="record heading recognised but no field rows parsed under it",
                )
                for sheet in self.sheets
                if not sheet.fields
            ),
        )

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


def _extract_pdf_lines(lines: tuple[str, ...], *, source_label: str) -> RecordDesignExtraction:
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
            ordinal=compact.group("ordinal"),
            offset=int(compact.group("offset")),
            length=int(compact.group("length")),
            type_code=compact.group("type"),
            description=compact.group("text").strip(),
        )

    crlf = _COMPACT_PDF_CRLF_ROW_RE.match(line)
    if crlf is not None:
        return _PdfRow(
            source_row=source_row,
            ordinal=crlf.group("ordinal"),
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
    if set(normalised) <= {"-", "\u2013"} or normalised == "blank":
        return "Blancos"
    if normalised.startswith(("alfanum", "alphanum")):
        return "Alfanumérico"
    if normalised.startswith(("alfab", "alphab")):
        return "Alfabético"
    if normalised.startswith("num"):
        return "Numérico"
    return value.strip()


def _pdf_page_name(line: str) -> str | None:
    match = _PDF_PAGE_RECORD_RE.match(line)
    if match is None:
        return None
    return f"Pág. {match.group('page')}"


def _pdf_record_heading_name(line: str) -> str | None:
    match = _PDF_RECORD_HEADING_RE.match(line) or _PDF_RECORD_HEADING_REVERSED_RE.match(line)
    if match is None:
        return None
    title = _normalise_pdf_sheet_name(match.group("title"))
    return f"Tipo {match.group('record')} - {title}"


# The column-header spellings AEAT prints across diseño-de-registro PDFs.
# Each variant is a list of required column groups; a group holds the
# interchangeable spellings of one column, so a line matches a variant when
# every group contributes at least one token.
_PDF_HEADER_VARIANTS: Final[tuple[tuple[tuple[str, ...], ...], ...]] = (
    (("POSICIONES", "POSICIÓN"), ("NATURALEZA",), ("DESCRIPCI",)),
    (("Nº POSIC",), ("LON",), ("TIPO",), ("DESCRIPCI",)),
    (("POSITIONS",), ("NATURE",), ("DESCRIPTION",)),
)


def _is_pdf_header(line: str) -> bool:
    normalised = line.upper()
    return any(
        all(any(token in normalised for token in column) for column in variant) for variant in _PDF_HEADER_VARIANTS
    )


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
            ordinal=str(ordinal),
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


def _is_black_fill(fill: object | None) -> bool:
    """Return whether a pdfplumber rect ``fill`` value is opaque black.

    pdfplumber reports a rect's ``non_stroking_color`` in whatever colour
    space the source PDF declared: a bare grayscale float (``0.0`` is
    black), an RGB triple (``(0.0, 0.0, 0.0)``), or a named/indexed
    colourspace string the geometry-only chart extractor does not attempt
    to resolve. Both numeric shapes are checked so a rule ruled in RGB
    (observed in the AEAT modelo 038 record-design PDF) is not silently
    excluded from the visual-chart grid the way a bare ``fill == 0.0``
    comparison would exclude it.
    """
    if isinstance(fill, int | float):
        return fill == 0.0
    if isinstance(fill, tuple):
        try:
            components = _NUMERIC_TUPLE_ADAPTER.validate_python(fill)
        except ValidationError:
            return False
        return bool(components) and all(component == 0.0 for component in components)
    return False


def _visual_chart_grid(page: _PdfPageSnapshot) -> tuple[float, float, tuple[_PdfRect, ...]] | None:
    horizontal_rules = tuple(
        rect for rect in page.rects if _is_black_fill(rect.fill) and rect.height <= 2.0 and rect.width >= 8.0
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
    "RecordDesignCompositeRelativeClosing",
    "RecordDesignExtraction",
    "RecordDesignField",
    "RecordDesignRelativeSuffixMarker",
    "RecordDesignSheet",
    "RecordDesignSkippedSheet",
    "RecordDesignVariableBodyMarker",
    "RecordDesignVariableEnvelope",
    "RecordDesignVariableTotalMarker",
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
