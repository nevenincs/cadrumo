"""Closed workbook parity status and engine vocabulary."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

__all__ = [
    "ParityStatus",
    "WorkbookConversionStatus",
    "WorkbookKind",
    "WorkbookRunnerEngine",
    "WorkbookRunnerStatus",
    "WorkbookScanStatus",
]


class WorkbookKind(StrEnum):
    """Observable classification for a single discovered workbook artefact."""

    FORMULA_FORM = "formula_form"
    RECORD_DESIGN_LAYOUT = "record_design_layout"
    VALIDATION_HINTS = "validation_hints"
    STATIC_LAYOUT = "static_layout"
    UNSUPPORTED_BINARY_XLS = "unsupported_binary_xls"
    UNREADABLE = "unreadable"


class WorkbookScanStatus(StrEnum):
    """Observable status codes for a single workbook scan attempt."""

    SCANNED = "scanned"
    UNSUPPORTED = "unsupported"
    TIMEOUT = "timeout"
    FAILED = "failed"


WorkbookConversionStatus = Literal["converted", "failed"]
WorkbookRunnerStatus = Literal["available"]
WorkbookRunnerEngine = Literal["libreoffice-headless", "excel-com"]
ParityStatus = Literal["match", "mismatch", "not_run"]
