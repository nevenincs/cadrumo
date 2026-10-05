"""Resolve and execute workbook recalculation backends."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import (
    WorkbookOutputId,
)

from .workbook_parity_models import (
    WorkbookCellRef,
    WorkbookRunnerAvailability,
)
from .workbook_parity_output_ids import _workbook_output_id_set
from .workbook_parity_runner_resolution import _resolve_libreoffice_runner
from .workbook_parity_types import (
    WorkbookRunnerEngine,
)
from .workbook_parity_values import _coerce_excel_result, _excel_value

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these need not exist at runtime. openpyxl is one of
    # the heaviest third-party imports in the tree and this module is imported
    # eagerly by the registry facade, so the symbols that ARE needed at runtime
    # (``load_workbook``, ``Tokenizer``, and the ``TokenizerError`` /
    # ``InvalidFileException`` handler types) are imported inside the functions
    # that use them -- a taxpayer calculation must not load a spreadsheet engine.
    pass


# Runner-engine string constant — single source for every callsite.
_ENGINE_LIBREOFFICE: WorkbookRunnerEngine = "libreoffice-headless"


def _com_member(raw: object, name: str) -> object:
    """Read one required late-bound COM member with an explicit failure mode."""
    member: object = getattr(raw, name, None)
    if member is None:
        raise RegistryValidationError(f"Excel COM object is missing required member {name!r}")
    return member


def _com_method(raw: object, name: str) -> Callable[..., object]:
    """Read one required callable late-bound COM member."""
    member = _com_member(raw, name)
    if not callable(member):
        raise RegistryValidationError(f"Excel COM member {name!r} is not callable")
    return member


def _set_com_member(raw: object, name: str, value: object) -> None:
    """Set one verified late-bound COM property."""
    _com_member(raw, name)
    setattr(raw, name, value)


class _ExcelWorkbook:
    """Typed adapter for the limited workbook operations used by parity runs."""

    def __init__(self, raw: object) -> None:
        self._raw = raw

    def set_cell_value(self, cell: WorkbookCellRef, value: str | int | bool) -> None:
        worksheet: object = _com_member(self._raw, "Worksheets")
        sheet: object = _com_method(worksheet, "__call__")(cell.sheet)
        range_: object = _com_method(sheet, "Range")(cell.coordinate)
        _set_com_member(range_, "Value", value)

    def cell_value(self, cell: WorkbookCellRef) -> object:
        worksheet: object = _com_member(self._raw, "Worksheets")
        sheet: object = _com_method(worksheet, "__call__")(cell.sheet)
        range_: object = _com_method(sheet, "Range")(cell.coordinate)
        return _com_member(range_, "Value")

    def close_without_saving(self) -> None:
        _com_method(self._raw, "Close")(SaveChanges=False)


class _ExcelApplication:
    """Typed adapter for the checked late-bound Excel recalculation surface."""

    def __init__(self, raw: object) -> None:
        self._raw = raw

    def configure_read_only(self) -> None:
        _set_com_member(self._raw, "Visible", False)
        _set_com_member(self._raw, "DisplayAlerts", False)
        _set_com_member(self._raw, "AskToUpdateLinks", False)

    def open_read_only_workbook(self, path: Path) -> _ExcelWorkbook:
        workbooks = _com_member(self._raw, "Workbooks")
        workbook: object = _com_method(workbooks, "Open")(str(path), UpdateLinks=0, ReadOnly=True)
        return _ExcelWorkbook(workbook)

    def calculate_full_rebuild(self) -> None:
        _com_method(self._raw, "CalculateFullRebuild")()

    def quit(self) -> None:
        _com_method(self._raw, "Quit")()


def detect_workbook_runner() -> WorkbookRunnerAvailability:
    """Resolve the local sanctioned spreadsheet recalculation runner.

    LibreOffice headless (or, on Windows, Excel COM) is required infrastructure
    for the workbook parity backend. This resolver does not attempt a graceful
    fallback: if no runner is locatable, it raises so the caller surfaces the
    missing dependency instead of silently downgrading evidence quality.

    Returns:
        A :class:`WorkbookRunnerAvailability` describing the detected runner.
    """
    for executable in ("soffice", "libreoffice"):
        found = shutil.which(executable)
        if found:
            return WorkbookRunnerAvailability(
                status="available",
                engine=_ENGINE_LIBREOFFICE,
                executable=found,
                detail="LibreOffice executable found for local workbook recalculation",
            )
    excel_clsid = _detect_excel_com_clsid()
    if excel_clsid is not None:
        return WorkbookRunnerAvailability(
            status="available",
            engine="excel-com",
            executable=excel_clsid,
            detail="Excel COM automation is registered for local read-only workbook recalculation",
        )
    raise RegistryValidationError(
        "No LibreOffice/soffice executable or Excel COM automation found on this host. "
        "Install LibreOffice and make soffice or libreoffice available on PATH.",
    )


def _execution_runner_availability(executable: str | None) -> WorkbookRunnerAvailability:
    if executable is None:
        return detect_workbook_runner()
    runner = _resolve_libreoffice_runner(executable)
    return WorkbookRunnerAvailability(
        status="available",
        engine=_ENGINE_LIBREOFFICE,
        executable=str(runner),
        detail="LibreOffice executable provided for this workbook parity run",
    )


def run_workbook_with_excel_com(
    workbook_path: Path,
    *,
    inputs: Mapping[WorkbookCellRef, Decimal | int | str | bool],
    outputs: Mapping[WorkbookOutputId, WorkbookCellRef],
) -> Mapping[WorkbookOutputId, Decimal | int | str | bool | None]:
    """Run a local XLSX workbook with Excel COM and return selected output values.

    The workbook is opened read-only, link updates are disabled, alerts are
    disabled, and it is closed with ``SaveChanges=False``.
    """
    _workbook_output_id_set("workbook output cells", outputs)
    if _detect_excel_com_clsid() is None:
        raise RegistryValidationError("Excel COM automation is not registered")
    resolved = workbook_path.resolve()
    if not resolved.is_file():
        raise RegistryValidationError(f"workbook does not exist: {workbook_path}")
    if resolved.suffix.lower() != _XLSX_EXTENSION:
        raise RegistryValidationError("Excel COM runner currently accepts only XLSX workbooks")

    import pythoncom

    pythoncom.CoInitialize()
    excel = _dispatch_excel_application()
    workbook: _ExcelWorkbook | None = None
    try:
        excel.configure_read_only()
        workbook = excel.open_read_only_workbook(resolved)
        for cell, value in inputs.items():
            workbook.set_cell_value(cell, _excel_value(value))
        excel.calculate_full_rebuild()
        result: dict[WorkbookOutputId, Decimal | int | str | bool | None] = {}
        for output_id, cell in outputs.items():
            result[output_id] = _coerce_excel_result(workbook.cell_value(cell))
        return result
    finally:
        workbook.close_without_saving()
        excel.quit()
        pythoncom.CoUninitialize()


def _dispatch_excel_application() -> _ExcelApplication:
    """Create Excel through pywin32 and validate its late-bound COM shape."""
    from importlib import import_module

    client = import_module("win32com.client")
    dispatch_ex = getattr(client, "DispatchEx", None)
    if not callable(dispatch_ex):
        raise RegistryValidationError("pywin32 does not expose win32com.client.DispatchEx")
    candidate: object = dispatch_ex("Excel.Application")
    return _ExcelApplication(candidate)


def _detect_excel_com_clsid() -> str | None:
    # ``sys`` is imported at module level rather than here: a checker narrows
    # ``sys.platform`` only through a module-level binding, so the function-local
    # import left the winreg block analysed on every platform. The positive
    # block, rather than an early return off Windows, is what narrows ``winreg``
    # to the platform that ships it: it is the only guard shape every checker
    # this project runs honours, which is what retired the suppressions that
    # used to sit on the two calls below.
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application\CLSID") as key:
                value, _kind = winreg.QueryValueEx(key, "")
            return str(value)
        except (FileNotFoundError, OSError, ImportError):
            return None
    return None
