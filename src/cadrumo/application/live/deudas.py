"""Bucket-scoped deudas snapshot service.

Wraps the read-only AEAT debts-consulta boundary record
(:mod:`cadrumo.adapters.outbound.aeat.sede.deudas`) with bucket-scoped
persistence. Read-only by construction: no method calls AEAT at all, and none
mutates deuda state.

Verbs:
  capture(snapshot)   persist a fresh deudas capture, deduplicated
  list_snapshots()    every captured snapshot, in capture order
  show(snapshot_id)   single snapshot by full id or unambiguous prefix
  latest()            most recent snapshot, or None

The fetch path is deliberately absent. It requires an operator-authorised
specimen of AEAT's consulta page, and the adapter's read-landing guard refuses
every landing until one exists, so this service persists and reads only what a
future capture supplies.

Nothing persisted here is a calculation input: a snapshot records what AEAT
reported as owed, which is downstream of the taxpayer's tax position for a
period rather than part of it. No binding source kind, aggregation channel,
relation or casilla resolution reads these records.

The lifecycle helpers (content-addressed id derivation, dedup on re-capture,
list/show/latest) are routed through the shared
:class:`StatelessSnapshotService` base, mirroring
:class:`~application.live.ExpedientesService` exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import override

from pydantic import BaseModel, Field

from ...adapters.outbound.aeat.sede import Deuda
from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage import LIVE_DEUDAS_SNAPSHOT_NAMESPACE, secure_object_repository_for_bucket
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.hashing import sha256_hex
from ...core.identity import BucketId, SnapshotId
from ...core.time import now
from .errors import LiveApplicationInputError
from .snapshot_base import (
    SnapshotNotFoundError,
    StatelessSnapshotService,
)


class DeudasSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when a deudas snapshot lookup misses by id."""


class DeudasCapture(BaseModel):
    """Slim wrapper around a debts-consulta read result.

    ``mode='read'`` is the structural assertion that this capture cannot drive
    an AEAT-side mutation — which is load-bearing on this surface, because the
    payment and aplazamiento controls sit beside the listing it comes from.
    """

    model_config = STRICT_FROZEN_CONFIG

    deudas: tuple[Deuda, ...]
    captured_at: datetime
    source_url: str = Field(min_length=1)
    authenticated_identity: str | None = Field(default=None, max_length=32)
    mode: str = Field(default="read", pattern=r"^read$")


class PersistedDeudasSnapshot(BaseModel):
    """Captured deudas snapshot persisted to the active bucket."""

    model_config = STRICT_FROZEN_CONFIG

    snapshot_id: SnapshotId
    bucket_id: BucketId
    captured_at: datetime
    source_url: str = Field(min_length=1)
    authenticated_identity: str | None = Field(default=None, max_length=32)
    deudas: tuple[Deuda, ...]
    persisted_at: datetime


def _derive_snapshot_id(capture: DeudasCapture) -> str:
    canonical = capture.model_dump_json()
    return sha256_hex(canonical.encode("utf-8"))


def deudas_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Execute this public contract operation."""
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            translated_message="application.live.deudas.errors.bucket_id_blank",
        )
    if not trimmed_snapshot:
        raise LiveApplicationInputError(
            translated_message="application.live.deudas.errors.snapshot_id_blank",
        )
    return f"deudas-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def _deudas_repository(
    settings: Settings,
    bucket_id: str,
) -> SecureSnapshotRepository[PersistedDeudasSnapshot]:
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=PersistedDeudasSnapshot,
        namespace_definition=LIVE_DEUDAS_SNAPSHOT_NAMESPACE,
        object_key=deudas_snapshot_object_key,
        not_found_factory=lambda snapshot_id: DeudasSnapshotNotFoundError(
            translated_message="application.live.deudas.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: DeudasSnapshotNotFoundError(
            translated_message="application.live.deudas.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="deudas",
        input_error_cls=LiveApplicationInputError,
        objects=secure_object_repository_for_bucket(bucket_id, settings),
    )


class DeudasService(StatelessSnapshotService[PersistedDeudasSnapshot, DeudasCapture]):
    """Bucket-scoped persistence + read surface over deudas snapshots.

    Structurally read-only per the live-AEAT charter. No pay, no aplazamiento
    request, no acknowledge, no method that mutates AEAT state. Each public
    verb accepts ``bucket_id`` per call; storage is one encrypted secure-object
    row per captured snapshot.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize this public contract."""
        self._settings = settings or load_settings()
        super().__init__(repository_factory=lambda bucket_id: _deudas_repository(self._settings, bucket_id))

    def capture(
        self,
        *,
        bucket_id: str,
        capture: DeudasCapture,
    ) -> PersistedDeudasSnapshot:
        """Execute this public contract operation."""
        return self._capture_stateless(bucket_id=bucket_id, capture=capture)

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> PersistedDeudasSnapshot:
        """Execute this public contract operation."""
        return self.resolve_snapshot(bucket_id=bucket_id, snapshot_id=snapshot_id)

    def latest(
        self,
        *,
        bucket_id: str,
    ) -> PersistedDeudasSnapshot | None:
        """Execute this public contract operation."""
        snapshots = self.list_snapshots(bucket_id=bucket_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)

    @override
    def _derive_snapshot_id(self, capture: DeudasCapture) -> str:
        return _derive_snapshot_id(capture)

    @override
    def _build_payload(
        self,
        *,
        snapshot_id: str,
        bucket_id: str,
        capture: DeudasCapture,
    ) -> PersistedDeudasSnapshot:
        return PersistedDeudasSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            authenticated_identity=capture.authenticated_identity,
            deudas=capture.deudas,
            persisted_at=now(),
        )


__all__ = [
    "DeudasCapture",
    "DeudasService",
    "DeudasSnapshotNotFoundError",
    "PersistedDeudasSnapshot",
    "deudas_snapshot_object_key",
]
