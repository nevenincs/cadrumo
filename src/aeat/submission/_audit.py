"""Append-only audit records for dry-run and live submission attempts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aeat.submission._protocols import FilingDraftLike

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class SubmissionAuditEvent(StrEnum):
    """Discrete event kinds written to the append-only audit log."""

    DRY_RUN = "DRY_RUN"
    LIVE_REFUSED = "LIVE_REFUSED"
    LIVE_REQUESTED = "LIVE_REQUESTED"
    LIVE_RESULT = "LIVE_RESULT"


class LiveSubmitAuditRecord(BaseModel):
    """One append-only audit-log record for a submission attempt."""

    model_config = _STRICT_FROZEN

    event: SubmissionAuditEvent
    recorded_at: datetime
    submission_id: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    profile_tax_id: str = Field(min_length=1)
    draft_checksum_sha256: str = Field(min_length=64, max_length=64)
    dry_run: bool
    status: str = Field(min_length=1)
    reason: str | None = None
    error_type: str | None = None
    justificante_csv: str | None = None


def build_audit_record(
    *,
    event: SubmissionAuditEvent,
    submission_id: str,
    draft: FilingDraftLike,
    dry_run: bool,
    status: str,
    reason: str | None = None,
    error_type: str | None = None,
    justificante_csv: str | None = None,
    recorded_at: datetime | None = None,
) -> LiveSubmitAuditRecord:
    """Return a strict audit record for ``draft`` and ``submission_id``."""
    return LiveSubmitAuditRecord(
        event=event,
        recorded_at=recorded_at or datetime.now(UTC),
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        draft_checksum_sha256=compute_draft_checksum(draft),
        dry_run=dry_run,
        status=status,
        reason=reason,
        error_type=error_type,
        justificante_csv=justificante_csv,
    )


def default_audit_log_path(*, submissions_dir: Path) -> Path:
    """Return the default audit-log path derived from ``submissions_dir``."""
    if submissions_dir.name == "submissions" and submissions_dir.parent.name == "var":
        root = submissions_dir.parent.parent
    else:
        root = submissions_dir.parent
    return root / ".aeat" / "live-submit-audit.log"


def append_audit_record(path: Path, record: LiveSubmitAuditRecord) -> None:
    """Append ``record`` as one JSON line to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(record.model_dump_json())
        handle.write("\n")


def read_audit_records(path: Path, *, limit: int | None = None) -> tuple[LiveSubmitAuditRecord, ...]:
    """Read and parse every audit record in ``path``."""
    if not path.exists():
        return ()
    records = [
        LiveSubmitAuditRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if limit is not None:
        return tuple(records[-limit:])
    return tuple(records)


def compute_draft_checksum(draft: FilingDraftLike) -> str:
    """Return a stable SHA-256 checksum for the audit-relevant draft fields."""
    payload = json.dumps(
        _draft_snapshot(draft),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _draft_snapshot(draft: FilingDraftLike) -> dict[str, Any]:
    """Return a deterministic JSON-serializable snapshot of ``draft``."""
    return {
        "draft_id": draft.draft_id,
        "modelo": draft.modelo,
        "period": draft.period,
        "profile_tax_id": draft.profile_tax_id,
        "status": _normalize_value(getattr(draft.status, "value", draft.status)),
        "values": _normalize_value(draft.values),
        "findings": _normalize_value(draft.findings),
    }


def _normalize_value(value: object) -> object:
    """Normalize nested values into deterministic JSON-compatible shapes."""
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, tuple | list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, BaseModel):
        return _normalize_value(value.model_dump(mode="python"))
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, StrEnum):
        return value.value
    return value
