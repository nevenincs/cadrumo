"""Official AEAT workbook parity discovery and verification backend."""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from openpyxl import load_workbook
from openpyxl.formula import Tokenizer
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._errors import RegistryValidationError

WorkbookKind = Literal[
    "formula_form",
    "record_design_layout",
    "validation_hints",
    "static_layout",
    "unsupported_binary_xls",
    "unreadable",
]
WorkbookScanStatus = Literal["scanned", "unsupported", "timeout", "failed"]
WorkbookRunnerStatus = Literal["available", "unavailable"]
WorkbookRunnerEngine = Literal["libreoffice-headless", "excel-com"]
ParityStatus = Literal["match", "mismatch", "not_run"]

_WORKBOOK_SUFFIXES = {".xlsx", ".xls"}
_MODELO_PATTERN = re.compile(r"(?:^|[\\/])modelo[_-](?P<modelo>\d{3})(?:[\\/]|$)", re.IGNORECASE)
_CELL_REF_PATTERN = re.compile(r"(?<![A-Z0-9_])(?:'[^']+'!)?\$?[A-Z]{1,3}\$?\d+(?![A-Z0-9_])")


class WorkbookParityModel(BaseModel):
    """Strict frozen base for workbook parity records."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class WorkbookCellRef(WorkbookParityModel):
    """A cell participating in official workbook parity evidence."""

    sheet: str
    coordinate: str
    formula: str | None = None


class WorkbookArtefactReport(WorkbookParityModel):
    """Discovery report for one AEAT workbook artefact."""

    path: str
    modelo: str | None
    extension: Literal[".xlsx", ".xls"]
    bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    sheets: tuple[str, ...] = ()
    formula_cells: int = Field(ge=0)
    input_candidates: tuple[WorkbookCellRef, ...] = ()
    output_candidates: tuple[WorkbookCellRef, ...] = ()
    workbook_kind: WorkbookKind
    scan_status: WorkbookScanStatus
    error: str | None = None
    elapsed_seconds: Decimal

    @model_validator(mode="after")
    def _validate_status(self) -> WorkbookArtefactReport:
        if self.scan_status == "scanned" and self.workbook_kind in {"unreadable", "unsupported_binary_xls"}:
            raise ValueError("scanned workbook cannot be unreadable or unsupported")
        if self.scan_status != "scanned" and self.error is None:
            raise ValueError("non-scanned workbook report must include an error")
        return self


class SyntheticInputValue(WorkbookParityModel):
    """One synthetic value shared by registry and workbook parity execution."""

    id: str
    value: Decimal | int | str | bool
    workbook_cell: WorkbookCellRef | None = None
    registry_binding: str | None = None

    @model_validator(mode="after")
    def _validate_target(self) -> SyntheticInputValue:
        if self.workbook_cell is None and self.registry_binding is None:
            raise ValueError("synthetic input must target a workbook cell, registry binding, or both")
        return self


class SyntheticInputSet(WorkbookParityModel):
    """Synthetic parity fixture applied to both registry and workbook execution."""

    id: str
    modelo: str
    revision: str
    values: tuple[SyntheticInputValue, ...] = Field(min_length=1)


class WorkbookRunnerAvailability(WorkbookParityModel):
    """Availability of a local workbook recalculation runner."""

    status: WorkbookRunnerStatus
    engine: WorkbookRunnerEngine | None = None
    executable: str | None = None
    detail: str


class WorkbookParityComparison(WorkbookParityModel):
    """One registry-vs-workbook output comparison."""

    output_id: str
    workbook_cell: WorkbookCellRef
    expected_workbook_value: Decimal | int | str | bool | None
    actual_registry_value: Decimal | int | str | bool | None
    status: ParityStatus
    tolerance: Decimal = Decimal("0")
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    detail: str | None = None


class WorkbookParityRunReport(WorkbookParityModel):
    """Trace report for one parity execution attempt."""

    synthetic_input_id: str
    registry_snapshot_id: str | None = None
    workbook: WorkbookArtefactReport
    runner: WorkbookRunnerAvailability
    comparisons: tuple[WorkbookParityComparison, ...] = ()
    status: ParityStatus


class WorkbookModeloCoverage(WorkbookParityModel):
    """Per-modelo workbook coverage summary for model-law ledgers."""

    modelo: str
    workbook_count: int = Field(ge=0)
    formula_workbook_count: int = Field(ge=0)
    unsupported_xls_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


class WorkbookBackendVerificationReport(WorkbookParityModel):
    """Backend-level verification report for workbook calculation coverage."""

    root: str
    workbook_count: int = Field(ge=0)
    scanned_count: int = Field(ge=0)
    formula_workbook_count: int = Field(ge=0)
    unsupported_xls_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    runner: WorkbookRunnerAvailability
    reports: tuple[WorkbookArtefactReport, ...]
    modelo_coverage: tuple[WorkbookModeloCoverage, ...] = ()

    @property
    def backend_exists(self) -> bool:
        """Return whether discovery and guardable reports exist."""

        return self.workbook_count > 0 and self.scanned_count + self.unsupported_xls_count + self.failed_count > 0


@dataclass(frozen=True)
class WorkbookScanOptions:
    """Controls for bounded workbook discovery."""

    per_file_timeout_seconds: float = 15.0
    max_formula_refs: int = 500


def discover_workbooks(root: Path) -> tuple[Path, ...]:
    """Return every official workbook artefact below ``root``."""

    resolved = root.resolve()
    if not resolved.exists():
        raise RegistryValidationError(f"workbook root does not exist: {root}")
    return tuple(sorted(p for p in resolved.rglob("*") if p.suffix.lower() in _WORKBOOK_SUFFIXES and p.is_file()))


def scan_workbook(path: Path, *, root: Path, options: WorkbookScanOptions | None = None) -> WorkbookArtefactReport:
    """Scan one workbook and classify formula coverage."""

    opts = options or WorkbookScanOptions()
    started = time.monotonic()
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_root not in resolved_path.parents and resolved_root != resolved_path:
        raise RegistryValidationError(f"workbook path escapes scan root: {path}")

    relative = resolved_path.relative_to(resolved_root).as_posix()
    digest, byte_count = _hash_file(resolved_path)
    suffix = resolved_path.suffix.lower()
    modelo = _infer_modelo(relative)

    if suffix == ".xls":
        return WorkbookArtefactReport(
            path=relative,
            modelo=modelo,
            extension=".xls",
            bytes=byte_count,
            sha256=digest,
            workbook_kind="unsupported_binary_xls",
            scan_status="unsupported",
            formula_cells=0,
            error="binary XLS support requires a reviewed parser or conversion path",
            elapsed_seconds=_elapsed_decimal(started),
        )

    try:
        workbook = load_workbook(resolved_path, data_only=False, read_only=True)
        sheets: list[str] = []
        formulas: list[WorkbookCellRef] = []
        references: list[WorkbookCellRef] = []
        for worksheet in workbook.worksheets:
            _raise_if_timed_out(started, opts.per_file_timeout_seconds, relative)
            sheets.append(worksheet.title)
            for row in worksheet.iter_rows(values_only=False):
                _raise_if_timed_out(started, opts.per_file_timeout_seconds, relative)
                for cell in row:
                    value = cell.value
                    if isinstance(value, str) and value.startswith("="):
                        ref = WorkbookCellRef(sheet=worksheet.title, coordinate=cell.coordinate, formula=value)
                        formulas.append(ref)
                        if len(references) < opts.max_formula_refs:
                            references.extend(
                                _formula_references(
                                    worksheet.title,
                                    value,
                                    opts.max_formula_refs - len(references),
                                )
                            )
        workbook.close()
        kind = _classify_xlsx(relative, formulas)
        return WorkbookArtefactReport(
            path=relative,
            modelo=modelo,
            extension=".xlsx",
            bytes=byte_count,
            sha256=digest,
            sheets=tuple(sheets),
            formula_cells=len(formulas),
            input_candidates=tuple(_dedupe_cells(references)),
            output_candidates=tuple(formulas),
            workbook_kind=kind,
            scan_status="scanned",
            elapsed_seconds=_elapsed_decimal(started),
        )
    except TimeoutError as exc:
        return _failed_report(
            relative=relative,
            modelo=modelo,
            suffix=".xlsx",
            byte_count=byte_count,
            digest=digest,
            status="timeout",
            error=str(exc),
            started=started,
        )
    except Exception as exc:
        return _failed_report(
            relative=relative,
            modelo=modelo,
            suffix=".xlsx",
            byte_count=byte_count,
            digest=digest,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            started=started,
        )


def inventory_workbook_coverage(
    root: Path,
    *,
    options: WorkbookScanOptions | None = None,
    limit: int | None = None,
    previous_reports: Iterable[WorkbookArtefactReport] = (),
) -> tuple[WorkbookArtefactReport, ...]:
    """Scan official workbook artefacts and return deterministic coverage reports."""

    paths = discover_workbooks(root)
    if limit is not None:
        paths = paths[:limit]
    previous_by_path = {report.path: report for report in previous_reports}
    reports: list[WorkbookArtefactReport] = []
    resolved_root = root.resolve()
    for path in paths:
        relative = path.resolve().relative_to(resolved_root).as_posix()
        previous = previous_by_path.get(relative)
        if previous is not None and previous.sha256 == _hash_file(path)[0]:
            reports.append(previous)
            continue
        reports.append(scan_workbook(path, root=root, options=options))
    return tuple(reports)


def detect_workbook_runner() -> WorkbookRunnerAvailability:
    """Detect the local sanctioned spreadsheet recalculation runner."""

    from shutil import which

    for executable in ("soffice", "libreoffice"):
        found = which(executable)
        if found:
            return WorkbookRunnerAvailability(
                status="available",
                engine="libreoffice-headless",
                executable=found,
                detail="LibreOffice executable found for future workbook recalculation integration",
            )
    excel_clsid = _detect_excel_com_clsid()
    if excel_clsid is not None:
        return WorkbookRunnerAvailability(
            status="available",
            engine="excel-com",
            executable=excel_clsid,
            detail="Excel COM automation is registered for local read-only workbook recalculation",
        )
    return WorkbookRunnerAvailability(
        status="unavailable",
        engine=None,
        executable=None,
        detail="No LibreOffice/soffice executable or Excel COM automation found; workbook execution is unavailable",
    )


def run_workbook_with_excel_com(
    workbook_path: Path,
    *,
    inputs: Mapping[WorkbookCellRef, Decimal | int | str | bool],
    outputs: Mapping[str, WorkbookCellRef],
) -> Mapping[str, Decimal | int | str | bool | None]:
    """Run a local XLSX workbook with Excel COM and return selected output values.

    The workbook is opened read-only, link updates are disabled, alerts are
    disabled, and it is closed with ``SaveChanges=False``.
    """

    if _detect_excel_com_clsid() is None:
        raise RegistryValidationError("Excel COM automation is not registered")
    resolved = workbook_path.resolve()
    if not resolved.is_file():
        raise RegistryValidationError(f"workbook does not exist: {workbook_path}")
    if resolved.suffix.lower() != ".xlsx":
        raise RegistryValidationError("Excel COM runner currently accepts only XLSX workbooks")

    import pythoncom
    import win32com.client

    pythoncom_module = cast(Any, pythoncom)
    pythoncom_module.CoInitialize()
    excel = win32com.client.DispatchEx("Excel.Application")
    workbook = None
    try:
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AskToUpdateLinks = False
        workbook = excel.Workbooks.Open(str(resolved), UpdateLinks=0, ReadOnly=True)
        for cell, value in inputs.items():
            workbook.Worksheets(cell.sheet).Range(cell.coordinate).Value = _excel_value(value)
        excel.CalculateFullRebuild()
        result: dict[str, Decimal | int | str | bool | None] = {}
        for output_id, cell in outputs.items():
            result[output_id] = _coerce_excel_result(workbook.Worksheets(cell.sheet).Range(cell.coordinate).Value)
        return result
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        excel.Quit()
        pythoncom_module.CoUninitialize()


def compare_registry_to_workbook(
    *,
    synthetic_input: SyntheticInputSet,
    workbook: WorkbookArtefactReport,
    runner: WorkbookRunnerAvailability,
    expected_workbook_values: Mapping[str, Decimal | int | str | bool | None],
    actual_registry_values: Mapping[str, Decimal | int | str | bool | None],
    output_cells: Mapping[str, WorkbookCellRef],
    registry_snapshot_id: str | None = None,
    legal_refs: Mapping[str, tuple[str, ...]] | None = None,
    source_refs: Mapping[str, tuple[str, ...]] | None = None,
    tolerance: Decimal = Decimal("0"),
) -> WorkbookParityRunReport:
    """Build a deterministic parity comparison report from already-computed values."""

    comparisons: list[WorkbookParityComparison] = []
    for output_id in sorted(set(expected_workbook_values) | set(actual_registry_values)):
        expected = expected_workbook_values.get(output_id)
        actual = actual_registry_values.get(output_id)
        cell = output_cells.get(output_id)
        if cell is None:
            raise RegistryValidationError(f"missing workbook output cell for {output_id!r}")
        status = _comparison_status(expected, actual, tolerance)
        comparisons.append(
            WorkbookParityComparison(
                output_id=output_id,
                workbook_cell=cell,
                expected_workbook_value=expected,
                actual_registry_value=actual,
                status=status,
                tolerance=tolerance,
                legal_refs=(legal_refs or {}).get(output_id, ()),
                source_refs=(source_refs or {}).get(output_id, ()),
                detail=None if status == "match" else "registry output differs from workbook output",
            )
        )
    run_status: ParityStatus = "match" if all(c.status == "match" for c in comparisons) else "mismatch"
    return WorkbookParityRunReport(
        synthetic_input_id=synthetic_input.id,
        registry_snapshot_id=registry_snapshot_id,
        workbook=workbook,
        runner=runner,
        comparisons=tuple(comparisons),
        status=run_status,
    )


def verify_workbook_backend(
    root: Path,
    *,
    scan_limit: int | None = 25,
    per_file_timeout_seconds: float = 10.0,
    previous_report: WorkbookBackendVerificationReport | None = None,
) -> WorkbookBackendVerificationReport:
    """Verify that the workbook parity backend can discover and classify artefacts."""

    reports = inventory_workbook_coverage(
        root,
        options=WorkbookScanOptions(per_file_timeout_seconds=per_file_timeout_seconds),
        limit=scan_limit,
        previous_reports=previous_report.reports if previous_report is not None else (),
    )
    runner = detect_workbook_runner()
    return WorkbookBackendVerificationReport(
        root=root.resolve().as_posix(),
        workbook_count=len(discover_workbooks(root)) if root.exists() else 0,
        scanned_count=sum(1 for report in reports if report.scan_status == "scanned"),
        formula_workbook_count=sum(1 for report in reports if report.workbook_kind == "formula_form"),
        unsupported_xls_count=sum(1 for report in reports if report.workbook_kind == "unsupported_binary_xls"),
        failed_count=sum(1 for report in reports if report.scan_status in {"failed", "timeout"}),
        runner=runner,
        reports=reports,
        modelo_coverage=_build_modelo_coverage(reports),
    )


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as handle:
        while chunk := handle.read(65_536):
            digest.update(chunk)
            length += len(chunk)
    return digest.hexdigest(), length


def _build_modelo_coverage(reports: Iterable[WorkbookArtefactReport]) -> tuple[WorkbookModeloCoverage, ...]:
    buckets: dict[str, list[WorkbookArtefactReport]] = {}
    for report in reports:
        modelo = report.modelo or "unknown"
        buckets.setdefault(modelo, []).append(report)
    return tuple(
        WorkbookModeloCoverage(
            modelo=modelo,
            workbook_count=len(modelo_reports),
            formula_workbook_count=sum(1 for report in modelo_reports if report.workbook_kind == "formula_form"),
            unsupported_xls_count=sum(
                1 for report in modelo_reports if report.workbook_kind == "unsupported_binary_xls"
            ),
            failed_count=sum(1 for report in modelo_reports if report.scan_status in {"failed", "timeout"}),
        )
        for modelo, modelo_reports in sorted(buckets.items())
    )


def _detect_excel_com_clsid() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application\CLSID") as key:
            value, _kind = winreg.QueryValueEx(key, "")
        return str(value)
    except (FileNotFoundError, OSError, ImportError):
        return None


def _infer_modelo(relative_path: str) -> str | None:
    match = _MODELO_PATTERN.search(relative_path)
    return match.group("modelo") if match else None


def _raise_if_timed_out(started: float, timeout_seconds: float, relative: str) -> None:
    if time.monotonic() - started > timeout_seconds:
        raise TimeoutError(f"workbook scan timed out for {relative!r} after {timeout_seconds:.1f}s")


def _elapsed_decimal(started: float) -> Decimal:
    return Decimal(str(round(time.monotonic() - started, 6)))


def _classify_xlsx(relative: str, formulas: Iterable[WorkbookCellRef]) -> WorkbookKind:
    formula_count = sum(1 for _ in formulas)
    lowered = relative.lower()
    if formula_count > 0:
        return "formula_form"
    if "valid" in lowered or "valida" in lowered:
        return "validation_hints"
    if "dr" in lowered or "dise" in lowered or "registro" in lowered:
        return "record_design_layout"
    return "static_layout"


def _formula_references(sheet: str, formula: str, remaining: int) -> tuple[WorkbookCellRef, ...]:
    if remaining <= 0:
        return ()
    refs: list[WorkbookCellRef] = []
    try:
        tokens = Tokenizer(formula).items
        token_values = (token.value for token in tokens)
    except Exception:
        token_values = (match.group(0) for match in _CELL_REF_PATTERN.finditer(formula))
    for value in token_values:
        for match in _CELL_REF_PATTERN.finditer(value):
            if len(refs) >= remaining:
                return tuple(refs)
            ref_sheet = sheet
            coordinate = match.group(0).replace("$", "")
            if "!" in coordinate:
                raw_sheet, coordinate = coordinate.rsplit("!", 1)
                ref_sheet = raw_sheet.strip("'")
            refs.append(WorkbookCellRef(sheet=ref_sheet, coordinate=coordinate))
    return tuple(refs)


def _dedupe_cells(cells: Iterable[WorkbookCellRef]) -> tuple[WorkbookCellRef, ...]:
    seen: set[tuple[str, str]] = set()
    deduped: list[WorkbookCellRef] = []
    for cell in cells:
        key = (cell.sheet, cell.coordinate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cell)
    return tuple(deduped)


def _failed_report(
    *,
    relative: str,
    modelo: str | None,
    suffix: Literal[".xlsx", ".xls"],
    byte_count: int,
    digest: str,
    status: Literal["timeout", "failed"],
    error: str,
    started: float,
) -> WorkbookArtefactReport:
    return WorkbookArtefactReport(
        path=relative,
        modelo=modelo,
        extension=suffix,
        bytes=byte_count,
        sha256=digest,
        workbook_kind="unreadable",
        scan_status=status,
        formula_cells=0,
        error=error,
        elapsed_seconds=_elapsed_decimal(started),
    )


def _comparison_status(
    expected: Decimal | int | str | bool | None,
    actual: Decimal | int | str | bool | None,
    tolerance: Decimal,
) -> ParityStatus:
    if expected is None or actual is None:
        return "match" if expected is actual else "mismatch"
    if isinstance(expected, Decimal | int) and isinstance(actual, Decimal | int):
        return "match" if abs(Decimal(expected) - Decimal(actual)) <= tolerance else "mismatch"
    return "match" if expected == actual else "mismatch"


def _excel_value(value: Decimal | int | str | bool) -> str | int | bool:
    if isinstance(value, Decimal):
        return str(value)
    return value


def _coerce_excel_result(value: object) -> Decimal | int | str | bool | None:
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return str(value)
