"""Unit tests for submission audit-log helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import pytest

from aeat.submission._audit import (
    SubmissionAuditEvent,
    append_audit_record,
    build_audit_record,
    read_audit_records,
)
from aeat.submission._protocols import DraftStatus, FilingDraftLike

pytestmark = pytest.mark.unit


class _Draft(FilingDraftLike):
    draft_id: ClassVar[str] = "draft-audit"
    modelo: ClassVar[str] = "130"
    period: ClassVar[str] = "2026Q1"
    profile_tax_id: ClassVar[str] = "X1234567L"
    status: ClassVar[DraftStatus] = DraftStatus.READY_TO_SUBMIT
    values: ClassVar[dict[str, str]] = {"01": "1000"}
    findings: ClassVar[tuple[object, ...]] = ()


def _record(*, submission_id: str, event: SubmissionAuditEvent) -> str:
    return (
        '{"event":"'
        + event.value
        + '","recorded_at":"'
        + datetime(2026, 4, 17, 8, 0, tzinfo=UTC).isoformat()
        + '","submission_id":"'
        + submission_id
        + '","draft_id":"draft-audit","modelo":"130","period":"2026Q1",'
        + '"profile_tax_id":"X1234567L","draft_checksum_sha256":"'
        + ("a" * 64)
        + '","dry_run":true,"status":"PENDING"}'
    )


def test_read_audit_records_skips_malformed_lines_and_applies_limit(tmp_path: Path) -> None:
    path = tmp_path / "live-submit-audit.log"
    path.write_text(
        "\n".join(
            [
                _record(submission_id="sub-1", event=SubmissionAuditEvent.DRY_RUN),
                "{not-json",
                _record(submission_id="sub-2", event=SubmissionAuditEvent.LIVE_REFUSED),
                "",
                _record(submission_id="sub-3", event=SubmissionAuditEvent.LIVE_RESULT),
            ]
        ),
        encoding="utf-8",
    )

    records = read_audit_records(path, limit=2)

    assert [record.submission_id for record in records] == ["sub-2", "sub-3"]
    assert [record.event for record in records] == [
        SubmissionAuditEvent.LIVE_REFUSED,
        SubmissionAuditEvent.LIVE_RESULT,
    ]


def test_append_then_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "append-only.log"
    append_audit_record(
        path,
        build_audit_record(
            event=SubmissionAuditEvent.DRY_RUN,
            submission_id="sub-9",
            draft=_Draft(),
            dry_run=True,
            status="PENDING",
        ),
    )

    records = read_audit_records(path)

    assert len(records) == 1
    assert records[0].submission_id == "sub-9"
