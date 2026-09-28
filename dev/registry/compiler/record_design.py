"""Development-only extraction of official AEAT record-design rows.

Parses official AEAT record-design workbooks (PDF or XLS/XLSX) and derives
coverage casillas from a :class:`ModeloRevision` so that the extracted layout
can be compared against the registry declarations.
"""

from __future__ import annotations

import multiprocessing
import os
import warnings
from collections.abc import Generator, Iterable
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from functools import lru_cache
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

from cadrumo.core.external_constants import PDF_EXTENSION as _PDF_EXTENSION
from cadrumo.core.external_constants import XLS_EXTENSION as _XLS_EXTENSION
from cadrumo.core.external_constants import XLSM_EXTENSION as _XLSM_EXTENSION
from cadrumo.core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.core.paths import path_stat_fingerprint
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev.registry.compiler.record_design_schema import (
    RecordDesignExtraction,
    RecordDesignSheet,
    RecordDesignSkippedSheet,
)

from .record_design_cache import (
    load_cached_record_design,
    load_cached_record_design_refusal,
    record_design_cache_dir,
    record_design_cache_key,
    record_design_outcome_is_cached,
    store_cached_record_design,
    store_cached_record_design_refusal,
)
from .record_design_pdf_orchestration import extract_record_design_pdf_cached
from .record_design_sources import (
    load_corrections,
    load_declared_non_record_sheet_reasons,
)
from .record_design_workbook import extract_sheet, extract_xls_sheet

_OPENPYXL_HEADER_FOOTER_WARNING = "Cannot parse header or footer so it will be ignored"
_OPENPYXL_PRINT_AREA_WARNING = r"Print area cannot be set to Defined name: .*"
_EXTRACTABLE_SUFFIXES = frozenset({_PDF_EXTENSION, _XLSX_EXTENSION, _XLSM_EXTENSION, _XLS_EXTENSION})


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


#: Upper bound on the processes one warm-up starts; a cold corpus has far more
#: sources than this, and each worker holds a whole parsed document.
_MAX_WARM_WORKERS = 8
#: How long a second warm-up waits for the first before reading serially.
_WARM_LOCK_TIMEOUT_S = 1800.0


def warm_record_design_cache(paths: Iterable[Path], *, max_workers: int | None = None) -> int:
    """Extract, in parallel, every source the cross-process cache does not yet hold.

    Sources are independent and each is persisted under its own content key, so
    a cold corpus is read at the speed of the machine's cores rather than one
    source at a time. Every source goes through :func:`extract_record_design`,
    the same call a serial reader makes, so the cached readings and refusals are
    exactly what that reader would have written. A worker that fails for any
    other reason leaves its source uncached, and the next serial read of it
    then behaves as it always did.

    Concurrent warm-ups, such as several test workers reaching their first
    design read together, take turns through one lock beside the cache: the
    later one then finds the sources the earlier one extracted already cached
    instead of extracting them again. One that cannot get the lock in time
    extracts nothing and leaves every source to the serial reader.

    Returns:
        The number of sources that were not cached when this warm-up got its turn.
    """
    cache_dir = record_design_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_file_lock(cache_dir / "warm-up", timeout=_WARM_LOCK_TIMEOUT_S):
            return _warm_uncached(paths, max_workers=max_workers)
    except LockAcquisitionError:
        return 0


def _warm_uncached(paths: Iterable[Path], *, max_workers: int | None) -> int:
    pending: list[str] = []
    for path in dict.fromkeys(path.resolve() for path in paths):
        if not path.is_file() or path.suffix.lower() not in _EXTRACTABLE_SUFFIXES:
            continue
        fingerprint = path_stat_fingerprint(path)
        if not record_design_outcome_is_cached(record_design_cache_key(Path(fingerprint[0]), fingerprint)):
            pending.append(str(path))
    workers = min(len(pending), max_workers or min(_MAX_WARM_WORKERS, os.process_cpu_count() or 1))
    if workers < 2:
        return len(pending)
    # Spawned, never forked: a test worker is multi-threaded, and a forked child
    # can inherit a lock another thread held at the moment of the fork.
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        for _ in pool.map(_extract_into_cache, pending):
            pass
    return len(pending)


def _extract_into_cache(path: str) -> None:
    """Worker entry: extract one source so its outcome lands in the cache."""
    try:
        extract_record_design(Path(path))
    except Exception:
        # The serial read of this source meets and reports the same failure.
        return


@lru_cache(maxsize=256)
def _extract_record_design_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == _PDF_EXTENSION:
        extractor = extract_record_design_pdf
    elif suffix in {_XLSX_EXTENSION, _XLSM_EXTENSION}:
        extractor = extract_record_design_workbook
    elif suffix == _XLS_EXTENSION:
        extractor = extract_record_design_xls_workbook
    else:
        raise RegistryValidationError(f"unsupported record-design source extension: {source_path.suffix}")
    cache_key = record_design_cache_key(source_path, (path, byte_count, modified_ns))
    cached = load_cached_record_design(cache_key)
    if cached is not None:
        return cached
    # A refusal is persisted alongside a reading, because this memo cannot hold
    # one: ``lru_cache`` records only returns, so an unreadable source re-parsed
    # on every call in every process. Six bundled designs refuse, at 19s a
    # process. The message is replayed rather than summarised so a caller reads
    # the same refusal whether or not a cache served it.
    refused = load_cached_record_design_refusal(cache_key)
    if refused is not None:
        raise RegistryValidationError(refused)
    try:
        extraction = extractor(source_path)
    except RegistryValidationError as refusal:
        store_cached_record_design_refusal(cache_key, str(refusal))
        raise
    store_cached_record_design(cache_key, extraction)
    return extraction


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
                except RegistryValidationError as exc:
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
            except RegistryValidationError as exc:
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


__all__ = [
    "extract_record_design",
    "extract_record_design_pdf",
    "extract_record_design_workbook",
    "warm_record_design_cache",
]
