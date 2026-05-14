"""Bucket-scoped borrador 100 pre-fill snapshot service.

Wraps the read-only AEAT Renta WEB Open ``datos fiscales`` adapter
with bucket-scoped persistence. Snapshots produced here are consumed
by Modelo 100 binding pre-fill (bindings flagged ``aeat_prefilled=true``).

Structurally read-only:

  * the service has no submit / send / mutate verb;
  * the underlying driver calls
    :func:`AeatAccessGate.require_live_read` before remote contact;
  * the pre-fill values surfaced here are AEAT's own pre-fill data —
    the operator reviews, the operator never has the service push back.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ...core.config import Settings
from ...core.errors import AeatError


class BorradorSnapshotNotFoundError(AeatError):
    """Raised when a borrador snapshot lookup misses by id."""


class BorradorPrefillEntry(BaseModel):
    """One casilla pre-filled by AEAT's datos fiscales / borrador.

    ``source_label`` identifies the AEAT origin field (e.g.
    "Rendimientos del trabajo - Empresa X CIF Bxxxx") so the
    audit-replay can trace where the pre-fill came from.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: str = Field(min_length=1, max_length=32)
    value: Decimal
    source_label: str = Field(default="", max_length=200)

    @field_serializer("value", when_used="json")
    def _serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")


class Borrador100Snapshot(BaseModel):
    """One persisted borrador 100 datos-fiscales capture."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    snapshot_id: str = Field(min_length=64, max_length=64)
    bucket_id: str = Field(min_length=1)
    tax_year: int = Field(ge=2015, le=2100)
    captured_at: datetime
    source_url: str = Field(min_length=1)
    prefill_entries: tuple[BorradorPrefillEntry, ...] = Field(default_factory=tuple)
    persisted_at: datetime
    discarded: bool = False
    discarded_at: datetime | None = None
    discarded_reason: str = Field(default="", max_length=200)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _storage_path(settings: Settings, bucket_id: str) -> Path:
    root = settings.aeat_audit_dir / "live" / "borrador100"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{bucket_id}.jsonl"


def _canonical_payload(
    *,
    tax_year: int,
    captured_at: datetime,
    source_url: str,
    entries: tuple[BorradorPrefillEntry, ...],
) -> str:
    parts: list[str] = [
        f"tax_year={tax_year}",
        f"captured_at={captured_at.isoformat()}",
        f"source_url={source_url}",
    ]
    sorted_entries = sorted(entries, key=lambda e: e.casilla_id)
    for entry in sorted_entries:
        parts.append(f"entry={entry.casilla_id}:{format(entry.value, 'f')}")
    return "\n".join(parts)


def _derive_snapshot_id(
    *,
    tax_year: int,
    captured_at: datetime,
    source_url: str,
    entries: tuple[BorradorPrefillEntry, ...],
) -> str:
    canonical = _canonical_payload(
        tax_year=tax_year,
        captured_at=captured_at,
        source_url=source_url,
        entries=entries,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load(settings: Settings, bucket_id: str) -> list[Borrador100Snapshot]:
    path = _storage_path(settings, bucket_id)
    if not path.exists():
        return []
    return [
        Borrador100Snapshot.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _save(
    settings: Settings, bucket_id: str, snapshots: list[Borrador100Snapshot],
) -> None:
    path = _storage_path(settings, bucket_id)
    payload = "\n".join(s.model_dump_json() for s in snapshots)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


class BorradorService:
    """Bucket-scoped persistence + read surface over borrador 100 snapshots.

    Structurally read-only. No submit, send, push, or remote-mutation
    method exists. ``discard`` marks a LOCAL snapshot as no-longer-
    consumable without contacting AEAT.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def capture(
        self,
        *,
        bucket_id: str,
        tax_year: int,
        captured_at: datetime,
        source_url: str,
        prefill_entries: tuple[BorradorPrefillEntry, ...],
    ) -> Borrador100Snapshot:
        """Persist a borrador snapshot. Deduplicates identical replays."""
        snapshot_id = _derive_snapshot_id(
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            entries=prefill_entries,
        )
        snapshot = Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            tax_year=tax_year,
            captured_at=captured_at,
            source_url=source_url,
            prefill_entries=prefill_entries,
            persisted_at=_now(),
        )
        snapshots = _load(self._settings, bucket_id)
        existing = next((s for s in snapshots if s.snapshot_id == snapshot_id), None)
        if existing is not None:
            return existing
        snapshots.append(snapshot)
        _save(self._settings, bucket_id, snapshots)
        return snapshot

    def list_snapshots(
        self,
        *,
        bucket_id: str,
        include_discarded: bool = False,
    ) -> tuple[Borrador100Snapshot, ...]:
        snapshots = _load(self._settings, bucket_id)
        if not include_discarded:
            snapshots = [s for s in snapshots if not s.discarded]
        return tuple(snapshots)

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> Borrador100Snapshot:
        matches = [
            s
            for s in _load(self._settings, bucket_id)
            if s.snapshot_id == snapshot_id or s.snapshot_id.startswith(snapshot_id)
        ]
        if not matches:
            raise BorradorSnapshotNotFoundError(
                f"no borrador 100 snapshot matches {snapshot_id!r} in bucket {bucket_id!r}",
                suggestion="aeat app live borrador 100 list",
            )
        if len(matches) > 1:
            full_ids = sorted(s.snapshot_id for s in matches)
            raise BorradorSnapshotNotFoundError(
                f"prefix {snapshot_id!r} is ambiguous; matches {full_ids!r}",
                suggestion="provide a longer prefix",
            )
        return matches[0]

    def latest_for_year(
        self,
        *,
        bucket_id: str,
        tax_year: int,
    ) -> Borrador100Snapshot | None:
        """Return the most recent non-discarded snapshot for a tax year."""
        snapshots = [
            s
            for s in _load(self._settings, bucket_id)
            if s.tax_year == tax_year and not s.discarded
        ]
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)

    def discard(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
        reason: str = "",
    ) -> Borrador100Snapshot:
        """Locally mark a snapshot as no-longer-consumable.

        Does not contact AEAT. Use this when the operator no longer
        wants ``aeat app modelo calculate --borrador SNAPSHOT_ID`` to
        consume stale pre-fill data after a profile change.
        """
        snapshots = _load(self._settings, bucket_id)
        target = self.show(bucket_id=bucket_id, snapshot_id=snapshot_id)
        index = next(
            i for i, s in enumerate(snapshots) if s.snapshot_id == target.snapshot_id
        )
        updated = target.model_copy(
            update={
                "discarded": True,
                "discarded_at": _now(),
                "discarded_reason": reason,
            },
        )
        snapshots[index] = updated
        _save(self._settings, bucket_id, snapshots)
        return updated


__all__ = [
    "Borrador100Snapshot",
    "BorradorPrefillEntry",
    "BorradorService",
    "BorradorSnapshotNotFoundError",
]
