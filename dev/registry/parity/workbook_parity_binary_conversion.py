"""Convert binary XLS artefacts and inspect converted workbook evidence."""

from __future__ import annotations

import shutil
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.core.external_constants import XLS_EXTENSION as _XLS_EXTENSION
from cadrumo.core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from cadrumo.core.hashing import hash_file as _hash_file
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import EvidenceTier

from .workbook_parity_libreoffice import _convert_with_libreoffice, _libreoffice_workspace, _LibreOfficeConversionError
from .workbook_parity_models import (
    WorkbookCellRef,
    WorkbookConversionReport,
)
from .workbook_parity_runner_resolution import _resolve_libreoffice_runner
from .workbook_parity_scanning import (
    _classify_xlsx,
    _dedupe_cells,
    _elapsed_decimal,
    _evidence_for_workbook_kind,
    _formula_references,
    _infer_modelo,
    _raise_if_timed_out,
)
from .workbook_parity_types import (
    WorkbookKind,
)

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these need not exist at runtime. openpyxl is one of
    # the heaviest third-party imports in the tree and this module is imported
    # eagerly by the registry facade, so the symbols that ARE needed at runtime
    # (``load_workbook``, ``Tokenizer``, and the ``TokenizerError`` /
    # ``InvalidFileException`` handler types) are imported inside the functions
    # that use them -- a taxpayer calculation must not load a spreadsheet engine.
    from openpyxl.cell.cell import Cell, MergedCell
    from openpyxl.worksheet.worksheet import Worksheet


_BINARY_XLS_CONVERSION_BYTES_CACHE: dict[tuple[str, int, str], bytes] = {}
_REFERENCE_HARVEST_LIMIT = 500


def _collect_sheet_formulas(
    worksheet: Worksheet,
    *,
    formulas: list[WorkbookCellRef],
    references: list[WorkbookCellRef],
    original_relative: str,
    cpu_started: float,
) -> None:
    """Walk every row in ``worksheet`` and append formula refs + a bounded set of references."""
    for row in worksheet.iter_rows(values_only=False):
        _raise_if_timed_out(cpu_started, _INSPECT_CONVERTED_XLSX_TIMEOUT_S, original_relative)
        for cell in row:
            _record_cell_if_formula(
                cell,
                sheet_title=worksheet.title,
                formulas=formulas,
                references=references,
            )


def _record_cell_if_formula(
    cell: Cell | MergedCell,
    *,
    sheet_title: str,
    formulas: list[WorkbookCellRef],
    references: list[WorkbookCellRef],
) -> None:
    """Append a formula record + (bounded) reference fan-out when ``cell`` carries an ``=…`` value."""
    value = cell.value
    if not (isinstance(value, str) and value.startswith("=")):
        return
    formulas.append(WorkbookCellRef(sheet=sheet_title, coordinate=cell.coordinate, formula=value))
    remaining = _REFERENCE_HARVEST_LIMIT - len(references)
    if remaining > 0:
        references.extend(_formula_references(sheet_title, value, remaining))


@dataclass(frozen=True)
class _BinaryXlsConversionContext:
    resolved_root: Path
    resolved_path: Path
    relative: str
    digest: str
    byte_count: int
    modelo: str | None


def convert_binary_xls_with_libreoffice(
    workbook_path: Path,
    *,
    root: Path,
    executable: str | None = None,
) -> WorkbookConversionReport:
    """Convert one official binary XLS in isolated storage and return a :class:`WorkbookConversionReport`."""
    started = time.monotonic()
    context = _binary_xls_conversion_context(workbook_path, root=root)
    runner = _resolve_libreoffice_runner(executable)
    try:
        with _converted_binary_xls_path(context, runner=runner) as converted_path:
            sheets, formulas, references = _inspect_converted_xlsx(
                converted_path,
                original_relative=context.relative,
            )
    except _LibreOfficeConversionError as exc:
        # A timeout and any other conversion failure both resolve to the same
        # "failed" WorkbookConversionReport: WorkbookConversionStatus carries no
        # distinct timed-out member, so there is nothing for a timeout branch to
        # report that the general failure path does not already carry in `error`.
        return _failed_conversion_report(
            relative=context.relative,
            modelo=context.modelo,
            byte_count=context.byte_count,
            digest=context.digest,
            error=str(exc),
            started=started,
        )
    kind = _classify_xlsx(context.relative, formulas)
    evidence_tier, not_evidence_for = _evidence_for_workbook_kind(kind)
    return WorkbookConversionReport(
        path=context.relative,
        modelo=context.modelo,
        bytes=context.byte_count,
        sha256=context.digest,
        converted_extension=_XLSX_EXTENSION,
        sheets=sheets,
        formula_cells=len(formulas),
        input_candidates=tuple(_dedupe_cells(references)),
        output_candidates=formulas,
        workbook_kind=kind,
        evidence_tier=evidence_tier,
        not_evidence_for=not_evidence_for,
        conversion_status="converted",
        elapsed_seconds=_elapsed_decimal(started),
    )


@contextmanager
def converted_binary_xls_with_libreoffice(
    workbook_path: Path,
    *,
    root: Path,
    executable: str | None = None,
) -> Generator[Path]:
    """Yield a temporary XLSX converted from official binary XLS input."""
    context = _binary_xls_conversion_context(workbook_path, root=root)
    runner = _resolve_libreoffice_runner(executable)
    try:
        with _converted_binary_xls_path(context, runner=runner) as converted_path:
            yield converted_path
    except _LibreOfficeConversionError as exc:
        raise exc.as_registry_error() from exc


def _binary_xls_conversion_context(workbook_path: Path, *, root: Path) -> _BinaryXlsConversionContext:
    resolved_root = root.resolve()
    resolved_path = workbook_path.resolve()
    if resolved_root not in resolved_path.parents and resolved_root != resolved_path:
        raise RegistryValidationError(f"workbook path escapes conversion root: {workbook_path}")
    if resolved_path.suffix.lower() != _XLS_EXTENSION:
        raise RegistryValidationError("binary workbook conversion accepts only XLS artefacts")
    relative = resolved_path.relative_to(resolved_root).as_posix()
    digest, byte_count = _hash_file(resolved_path)
    return _BinaryXlsConversionContext(
        resolved_root=resolved_root,
        resolved_path=resolved_path,
        relative=relative,
        digest=digest,
        byte_count=byte_count,
        modelo=_infer_modelo(relative),
    )


@contextmanager
def _converted_binary_xls_path(
    context: _BinaryXlsConversionContext,
    *,
    runner: Path,
) -> Generator[Path]:
    with _libreoffice_workspace() as workspace:
        converted_path = workspace.output / f"{context.resolved_path.stem}{_XLSX_EXTENSION}"
        cache_key = (context.digest, context.byte_count, str(runner))
        cached_bytes = _BINARY_XLS_CONVERSION_BYTES_CACHE.get(cache_key)
        if cached_bytes is None:
            # LibreOffice names its output after its input, so converting a
            # short-named copy keeps every path it writes bounded by the
            # workspace rather than by the official artefact's file name.
            source_copy = workspace.root / f"in{_XLS_EXTENSION}"
            shutil.copyfile(context.resolved_path, source_copy)
            produced = _convert_with_libreoffice(
                runner,
                source_copy,
                workspace=workspace,
                operation="binary XLS conversion",
            )
            produced.replace(converted_path)
            _BINARY_XLS_CONVERSION_BYTES_CACHE[cache_key] = converted_path.read_bytes()
        else:
            converted_path.write_bytes(cached_bytes)
        yield converted_path


def _failed_conversion_report(
    *,
    relative: str,
    modelo: str | None,
    byte_count: int,
    digest: str,
    error: str,
    started: float,
) -> WorkbookConversionReport:
    return WorkbookConversionReport(
        path=relative,
        modelo=modelo,
        bytes=byte_count,
        sha256=digest,
        workbook_kind=WorkbookKind.UNREADABLE,
        formula_cells=0,
        evidence_tier=None,
        not_evidence_for=(
            EvidenceTier.LEGAL_AUTHORITY,
            EvidenceTier.OFFICIAL_SOURCE_GUIDANCE,
            EvidenceTier.EXECUTABLE_PARITY_EVIDENCE,
            EvidenceTier.LAYOUT_AUTHORITY,
        ),
        conversion_status="failed",
        error=error,
        elapsed_seconds=_elapsed_decimal(started),
    )


_INSPECT_CONVERTED_XLSX_TIMEOUT_S = 120


def _inspect_converted_xlsx(
    path: Path,
    *,
    original_relative: str,
) -> tuple[tuple[str, ...], tuple[WorkbookCellRef, ...], tuple[WorkbookCellRef, ...]]:
    from openpyxl import load_workbook

    # The budget starts here, not when the conversion started: the LibreOffice
    # process time before it is bounded by its own timeout.
    cpu_started = time.thread_time()
    workbook = load_workbook(path, data_only=False, read_only=True)
    try:
        sheets: list[str] = []
        formulas: list[WorkbookCellRef] = []
        references: list[WorkbookCellRef] = []
        for worksheet in workbook.worksheets:
            _raise_if_timed_out(cpu_started, _INSPECT_CONVERTED_XLSX_TIMEOUT_S, original_relative)
            sheets.append(worksheet.title)
            _collect_sheet_formulas(
                worksheet,
                formulas=formulas,
                references=references,
                original_relative=original_relative,
                cpu_started=cpu_started,
            )
        return tuple(sheets), tuple(formulas), tuple(references)
    finally:
        workbook.close()
