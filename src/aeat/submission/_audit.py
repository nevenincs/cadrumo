"""Private append-only audit log for live AEAT submissions."""

from __future__ import annotations

import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..config import PROJECT_ROOT

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_AUDIT_LOG_PATH = PROJECT_ROOT / ".aeat" / "live-submit-audit.log"


class LiveSubmitAuditRecord(BaseModel):
    """Typed JSONL record for one live AEAT submission attempt."""

    model_config = _STRICT_FROZEN

    timestamp_utc: datetime
    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    taxpayer_nif: str = Field(min_length=1)
    draft_checksum: str = Field(min_length=1)
    submission_url: str = Field(min_length=1)
    response_status: str = Field(min_length=1)
    justificante_csv: str | None = None
    confirmation_phrase: str = Field(min_length=1)
    env_state: dict[str, str]
    pid: int
    argv: tuple[str, ...]


def append_live_submit_audit(
    record: LiveSubmitAuditRecord,
    *,
    target: Path | None = None,
) -> Path:
    """Append ``record`` to the fixed JSONL audit log path."""
    target = target or _AUDIT_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    _set_writable(target)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(record.model_dump_json())
        handle.write("\n")
    _set_read_only(target)
    return target


def build_live_submit_audit_record(
    *,
    modelo: str,
    period: str,
    taxpayer_nif: str,
    draft_checksum: str,
    submission_url: str,
    response_status: str,
    justificante_csv: str | None,
    confirmation_phrase: str,
    env_state: dict[str, str] | None = None,
) -> LiveSubmitAuditRecord:
    """Build a typed audit record using the live call environment snapshot."""
    return LiveSubmitAuditRecord(
        timestamp_utc=datetime.now(UTC),
        modelo=modelo,
        period=period,
        taxpayer_nif=taxpayer_nif,
        draft_checksum=draft_checksum,
        submission_url=submission_url,
        response_status=response_status,
        justificante_csv=justificante_csv,
        confirmation_phrase=confirmation_phrase,
        env_state=env_state
        or {
            "AEAT_LIVE_TESTS_ENABLED": os.environ.get("AEAT_LIVE_TESTS_ENABLED", ""),
            "AEAT_LIVE_SUBMIT_ENABLED": os.environ.get("AEAT_LIVE_SUBMIT_ENABLED", ""),
            "PYTEST_CURRENT_TEST": os.environ.get("PYTEST_CURRENT_TEST", ""),
        },
        pid=os.getpid(),
        argv=tuple(sys.argv),
    )


def _set_writable(path: Path) -> None:
    if not path.exists():
        return
    try:
        current = path.stat().st_mode
        path.chmod(current | stat.S_IWRITE)
    except OSError:
        return


def _set_read_only(path: Path) -> None:
    try:
        current = path.stat().st_mode
        path.chmod((current | stat.S_IREAD) & ~stat.S_IWRITE)
    except OSError:
        return
