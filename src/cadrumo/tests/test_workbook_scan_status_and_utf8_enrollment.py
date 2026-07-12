"""Runtime contracts for workbook reports and frozen persistence records."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..adapters.persistence.storage.bucket import bucket_paths
from ..adapters.persistence.storage.sql import SecureObjectRawRow
from ..domain.calculations.registry import WorkbookArtefactReport, WorkbookKind, WorkbookScanStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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


def test_bucket_paths_record_is_frozen(tmp_path: Path) -> None:
    """Bucket path records are immutable after path resolution."""
    paths = bucket_paths(root=tmp_path, bucket_id="profile")

    assert paths.bucket_dir.as_posix().endswith("buckets/profile")
    with pytest.raises(ValidationError, match="Instance is frozen"):
        paths.db_dir = paths.root


def test_secure_object_raw_row_is_frozen_and_validates_revision_hashes() -> None:
    """Raw secure-object records freeze payload metadata and enforce hash width."""
    row = SecureObjectRawRow(
        row_id=1,
        namespace="aeat.test",
        object_key=b"object-key",
        classification="cache",
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=b"payload",
        revision_id=_HASH_64,
    )

    assert row.revision_id == _HASH_64
    with pytest.raises(ValidationError, match="Instance is frozen"):
        row.payload = b"changed"
    with pytest.raises(ValidationError, match="String should have at least 64 characters"):
        SecureObjectRawRow(
            row_id=1,
            namespace="aeat.test",
            object_key=b"object-key",
            classification="cache",
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"payload",
            revision_id="short",
        )
