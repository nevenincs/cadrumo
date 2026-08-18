"""Validation contracts for the workbook parity artefact report.

The report's two refusals both exist to stop a scan claiming more than it did: a
SCANNED status paired with an UNREADABLE kind asserts a successful read of
something never read, and a non-scanned status without an error leaves the
operator knowing a workbook failed and nothing about why.

These live beside the harness that owns them rather than under the package
tests: the workbook parity tooling is contributor-only and does not ship, so a
test importing it from ``cadrumo`` asserts a boundary the tree no longer has.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..parity._workbook_parity_models import WorkbookArtefactReport
from ..parity._workbook_parity_types import WorkbookKind, WorkbookScanStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HASH_64 = "a" * 64


def test_workbook_report_rejects_scanned_unreadable_kind() -> None:
    """A successful workbook scan cannot report an unreadable artefact kind."""
    with pytest.raises(ValidationError, match="scanned workbook cannot be unreadable"):
        WorkbookArtefactReport(
            path="modelo_303/files/bad.xlsx",
            modelo="303",
            extension=".xlsx",
            bytes=1,
            sha256=_HASH_64,
            workbook_kind=WorkbookKind.UNREADABLE,
            evidence_tier=None,
            scan_status=WorkbookScanStatus.SCANNED,
            formula_cells=0,
            elapsed_seconds=Decimal("0"),
        )


def test_workbook_report_requires_error_for_non_scanned_status() -> None:
    """A failed workbook scan must carry an operator-visible diagnostic."""
    with pytest.raises(ValidationError, match="non-scanned workbook report must include an error"):
        WorkbookArtefactReport(
            path="modelo_303/files/bad.xlsx",
            modelo="303",
            extension=".xlsx",
            bytes=1,
            sha256=_HASH_64,
            workbook_kind=WorkbookKind.UNREADABLE,
            evidence_tier=None,
            scan_status=WorkbookScanStatus.FAILED,
            formula_cells=0,
            elapsed_seconds=Decimal("0"),
        )


def test_workbook_report_accepts_failed_unreadable_with_error() -> None:
    """Failed unreadable reports remain representable when the diagnostic is present."""
    report = WorkbookArtefactReport(
        path="modelo_303/files/bad.xlsx",
        modelo="303",
        extension=".xlsx",
        bytes=1,
        sha256=_HASH_64,
        workbook_kind=WorkbookKind.UNREADABLE,
        evidence_tier=None,
        scan_status=WorkbookScanStatus.FAILED,
        formula_cells=0,
        error="BadZipFile: File is not a zip file",
        elapsed_seconds=Decimal("0"),
    )

    assert report.scan_status == "failed"
    assert report.error == "BadZipFile: File is not a zip file"
