"""Read-only extraction of official AEAT record-design rows.

Parses official AEAT record-design workbooks (PDF or XLS/XLSX) and derives
coverage casillas from a :class:`ModeloRevision` so that the extracted layout
can be compared against the registry declarations.
"""

from __future__ import annotations

import warnings
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these never need to exist at runtime. The parser
    # backends themselves (openpyxl, pdfplumber, pypdfium2, xlrd) are among the
    # heaviest third-party imports in the tree and are deferred into the
    # extraction functions that actually call them -- importing the registry
    # must not pay for a PDF/XLS parser stack no calculation touches.
    pass

from ....core.external_constants import PDF_EXTENSION as _PDF_EXTENSION
from ....core.external_constants import XLS_EXTENSION as _XLS_EXTENSION
from ....core.external_constants import XLSM_EXTENSION as _XLSM_EXTENSION
from ....core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from ....core.paths import path_stat_fingerprint
from .errors import RegistryValidationError
from .record_design_pdf_orchestration import extract_record_design_pdf_cached, extract_record_design_pdf_stream
from .record_design_schema import (
    RecordDesignExtraction,
    RecordDesignSheet,
    RecordDesignSkippedSheet,
)
from .record_design_sources import (
    load_corrections,
    load_declared_non_record_sheet_reasons,
)
from .record_design_workbook import extract_sheet, extract_xls_sheet

_OPENPYXL_HEADER_FOOTER_WARNING = "Cannot parse header or footer so it will be ignored"
_OPENPYXL_PRINT_AREA_WARNING = r"Print area cannot be set to Defined name: .*"


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
    corrections = load_corrections(source_path)
    declared_skip_reasons = load_declared_non_record_sheet_reasons(source_path)
    with _ignore_openpyxl_header_footer_metadata_warnings():
        workbook = load_workbook(source_path, read_only=True, data_only=True)
        try:
            sheets: list[RecordDesignSheet] = []
            skipped: list[RecordDesignSkippedSheet] = []
            for worksheet in workbook.worksheets:
                try:
                    sheets.append(extract_sheet(worksheet, corrections))
                except ValueError as exc:
                    if "has no record-design header" not in str(exc):
                        raise
                    sheet_title = worksheet.title.strip()
                    declared = declared_skip_reasons.get(sheet_title)
                    skipped.append(
                        RecordDesignSkippedSheet(
                            name=sheet_title,
                            reason=declared if declared is not None else str(exc),
                            declared_non_record=declared is not None,
                        ),
                    )
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
    corrections = load_corrections(source_path)
    declared_skip_reasons = load_declared_non_record_sheet_reasons(source_path)
    workbook = xlrd.open_workbook(str(source_path), on_demand=True)
    try:
        sheets: list[RecordDesignSheet] = []
        skipped: list[RecordDesignSkippedSheet] = []
        for sheet_name in workbook.sheet_names():
            worksheet = workbook.sheet_by_name(sheet_name)
            try:
                sheets.append(extract_xls_sheet(worksheet, corrections))
            except ValueError as exc:
                if "has no record-design header" not in str(exc):
                    raise
                stripped_name = sheet_name.strip()
                declared = declared_skip_reasons.get(stripped_name)
                skipped.append(
                    RecordDesignSkippedSheet(
                        name=stripped_name,
                        reason=declared if declared is not None else str(exc),
                        declared_non_record=declared is not None,
                    ),
                )
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
    return extract_record_design_pdf_cached(*path_stat_fingerprint(resolved))


#: The two halves of a row whose columns were emitted out of order. The first
#: line carries LENGTH, TYPE and the description; the second carries the ORDINAL
#: and POSITION, optionally followed by the casilla reference that belongs to
#: the description's tail.


def extract_record_design_pdf_bytes(
    pdf_bytes: bytes,
    *,
    source_label: str = "in-memory record-design PDF",
) -> RecordDesignExtraction:
    """Return the record design extracted from PDF bytes.

    Returns:
        The :class:`RecordDesignExtraction` for the PDF content.
    """
    return extract_record_design_pdf_stream(BytesIO(pdf_bytes), source_label=source_label)


__all__ = [
    "extract_record_design",
    "extract_record_design_pdf",
    "extract_record_design_pdf_bytes",
    "extract_record_design_workbook",
]
