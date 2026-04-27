"""Governed live-submit audit sink.

The legacy :mod:`aeat.submission._audit` writer emits identity-bearing
JSONL records (NIF, draft checksum, justificante CSV, submission URL,
process arguments) to ``.aeat/live-submit-audit.log`` — a path outside
any operator-configured root and outside the substrate's classification
gate. The upstream 2026-04-27 security audit graded that finding HIGH-2.

This module is the relocation. The new sink:

- targets ``aeat_audit_dir / live-submit-audit.envelope.jsonl`` so the
  log lands inside the operator's configured audit root rather than
  the project tree;
- routes every event through
  :func:`aeat.storage.redact_structured` against the AUDIT-class default
  rule set before writing JSONL — NIF SHA-256-prefixed, URL host-only,
  bearer-shaped tokens fingerprinted, opaque bearers fingerprinted;
- holds an :func:`exclusive_file_lock` for the duration of every append
  so concurrent writers serialise rather than interleave partial JSON.

The legacy writer is preserved so the existing engine code paths
continue to work; the migration helper
:func:`migrate_legacy_live_submit_audit` drains an existing
``.aeat/live-submit-audit.log`` through the redaction contract into the
new location and archives the legacy file.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..logging import get_logger
from ..storage import (
    SensitivityClass,
    exclusive_file_lock,
    redact_structured,
)
from ..storage._redaction import default_rules_for_class
from ._audit import LiveSubmitAuditRecord

_log = get_logger(__name__)

_GOVERNED_AUDIT_FILE_NAME = "live-submit-audit.envelope.jsonl"
_GOVERNED_AUDIT_LOCK_FILE_NAME = "live-submit-audit.envelope.lock"
_AUDIT_RULES = default_rules_for_class(SensitivityClass.AUDIT)


class GovernedAuditMigrationSummary(BaseModel):
    """Frozen summary of one ``migrate_legacy_live_submit_audit`` call.

    Attributes:
        imported: Number of legacy JSONL lines persisted to the
            governed sink (after redaction).
        errors: Number of legacy JSONL lines the helper could not parse;
            counted but not re-raised so a partial migration completes.
        legacy_archived_path: Path the legacy log was renamed to after
            a successful migration. ``None`` if the legacy log did not
            exist or was empty.
        sink_path: Resolved path to the governed JSONL sink.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    legacy_archived_path: str | None = None
    sink_path: str


class GovernedLiveSubmitAuditSink:
    """Append-only governed sink for live AEAT submission audit events.

    Every event is routed through :func:`redact_structured` against the
    AUDIT-class default rule set before serialisation, then written as
    one JSON object per line to
    ``<audit_dir>/live-submit-audit.envelope.jsonl`` under an exclusive
    file lock.
    """

    def __init__(self, *, audit_dir: Path) -> None:
        """Bind the sink to ``audit_dir``.

        Args:
            audit_dir: Operator-configured audit root, typically
                :attr:`aeat.config.AeatSettings.aeat_audit_dir`. The
                JSONL file and lock sidecar are created on first
                append.
        """
        self._audit_dir = Path(audit_dir)

    @property
    def audit_dir(self) -> Path:
        """Return the configured audit root."""
        return self._audit_dir

    @property
    def sink_path(self) -> Path:
        """Return the canonical JSONL sink path."""
        return self._audit_dir / _GOVERNED_AUDIT_FILE_NAME

    @property
    def lock_target(self) -> Path:
        """Return the canonical lock-sidecar path for the sink."""
        return self._audit_dir / _GOVERNED_AUDIT_LOCK_FILE_NAME

    def append(self, record: LiveSubmitAuditRecord) -> Path:
        """Redact, encode, and append ``record`` to the JSONL sink.

        Args:
            record: A typed live-submit audit record produced by the
                engine. The record itself is not mutated; the redacted
                copy is what lands in JSONL.

        Returns:
            The resolved JSONL sink path.
        """
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        event = record.model_dump(mode="json")
        redacted = redact_structured(event, rules=_AUDIT_RULES)
        line = json.dumps(redacted, sort_keys=True, separators=(",", ":")) + "\n"
        with (
            exclusive_file_lock(self.lock_target),
            self.sink_path.open("a", encoding="utf-8", newline="\n") as handle,
        ):
            handle.write(line)
        return self.sink_path

    def iter_events(self) -> Iterator[dict[str, object]]:
        """Yield every JSON record currently persisted to the sink.

        Each yielded dict is a redacted record — there is no plaintext
        copy of the event anywhere in this sink. The iterator opens the
        file under the same exclusive lock the writer uses so concurrent
        appends do not interleave with reads.
        """
        if not self.sink_path.exists():
            return
        with exclusive_file_lock(self.lock_target):
            text = self.sink_path.read_text(encoding="utf-8")
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            decoded: object = json.loads(stripped)
            if isinstance(decoded, dict):
                yield decoded


def migrate_legacy_live_submit_audit(
    legacy_path: Path,
    *,
    audit_dir: Path,
    archive_suffix: str = ".legacy",
) -> GovernedAuditMigrationSummary:
    """Drain ``legacy_path`` through the redaction contract into ``audit_dir``.

    Each JSONL line in the legacy log is parsed, validated against
    :class:`LiveSubmitAuditRecord`, redacted via
    :func:`redact_structured` under AUDIT-class rules, and appended to
    the governed sink. Lines that fail to parse or validate are logged
    and counted under ``errors`` but do not abort the migration. After a
    successful drain, the legacy log is renamed to
    ``<legacy_path>.legacy`` so the helper is idempotent — re-running
    against an already-archived legacy path is a no-op.

    Args:
        legacy_path: Path to ``.aeat/live-submit-audit.log`` (or any
            other legacy JSONL audit log).
        audit_dir: Destination operator-configured audit root.
        archive_suffix: Suffix appended to the legacy file after
            migration. Defaults to ``.legacy``.

    Returns:
        A frozen :class:`GovernedAuditMigrationSummary`.
    """
    sink = GovernedLiveSubmitAuditSink(audit_dir=audit_dir)
    if not legacy_path.exists():
        return GovernedAuditMigrationSummary(
            imported=0,
            errors=0,
            legacy_archived_path=None,
            sink_path=str(sink.sink_path.resolve()),
        )
    text = legacy_path.read_text(encoding="utf-8")
    imported = 0
    errors = 0
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            record = LiveSubmitAuditRecord.model_validate_json(stripped)
        except (ValueError, OSError) as exc:
            _log.warning("skipping unparseable legacy live-submit audit line: %s", exc)
            errors += 1
            continue
        sink.append(record)
        imported += 1
    archived_path: Path | None = None
    if imported > 0 or errors > 0:
        archive_target = legacy_path.with_name(legacy_path.name + archive_suffix)
        # Idempotency: if a previous migration already produced the
        # archive target, leave it in place and remove the legacy file
        # to avoid stacking suffixes.
        if archive_target.exists():
            legacy_path.unlink()
        else:
            legacy_path.rename(archive_target)
            archived_path = archive_target
    _log.info(
        "migrated legacy live-submit audit log %s -> %s: imported=%d errors=%d",
        legacy_path,
        sink.sink_path,
        imported,
        errors,
    )
    return GovernedAuditMigrationSummary(
        imported=imported,
        errors=errors,
        legacy_archived_path=str(archived_path.resolve()) if archived_path is not None else None,
        sink_path=str(sink.sink_path.resolve()),
    )


__all__ = [
    "GovernedAuditMigrationSummary",
    "GovernedLiveSubmitAuditSink",
    "migrate_legacy_live_submit_audit",
]
