"""Bucket-scoped expedientes snapshot service.

Wraps the read-only AEAT sede declarations walker
(:mod:`cadrumo.adapters.outbound.aeat.sede._declarations`) with
bucket-scoped persistence. Read-only by construction: no method calls
AEAT to mutate expediente state.

Verbs:
  capture(snapshot)   persist a fresh expedientes capture, deduplicated
  list_snapshots()    every captured snapshot, in capture order
  show(snapshot_id)   single snapshot by full id or unambiguous prefix
  latest()            most recent snapshot, or None

The fetch path (auth-gated walker, ``require_live_read`` invocation)
lives in the entrypoint that wires the adapter to this service.

The lifecycle helpers (content-addressed id derivation, dedup on
re-capture, list/show/latest) are routed through the shared
:class:`StatelessSnapshotService` base; the public class identity,
exception class names, secure-object storage layout, and per-call
``bucket_id`` signatures are preserved exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import override

from pydantic import BaseModel, Field

from ...adapters.outbound.aeat.sede import Declaracion, open_declarations_register, shared_playwright
from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage import LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE, secure_object_repository_for_bucket
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.hashing import sha256_hex
from ...core.identity import BucketId, SnapshotId
from ...core.resources import resources
from ...core.time import now
from .errors import LiveApplicationInputError
from .remote_state_models import ExpedientesBulkCaptureFailureRow, ExpedientesBulkCaptureReport
from .remote_state_outcomes import bounded_context_text
from .session import active_verified_session
from .snapshot_base import (
    SnapshotNotFoundError,
    StatelessSnapshotService,
)


class ExpedientesSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when an expedientes snapshot lookup misses by id."""


class ExpedientesCapture(BaseModel):
    """Slim wrapper around a Declaracion walker result.

    Mirrors the read-only marker pattern from
    :class:`NotificationsSnapshot`: ``mode='read'`` is the structural
    assertion that this capture cannot drive an AEAT-side mutation.
    """

    model_config = STRICT_FROZEN_CONFIG

    declarations: tuple[Declaracion, ...]
    captured_at: datetime
    source_url: str = Field(min_length=1)
    authenticated_identity: str | None = Field(default=None, max_length=32)
    mode: str = Field(default="read", pattern=r"^read$")


class PersistedExpedientesSnapshot(BaseModel):
    """Captured expedientes snapshot persisted to the active bucket."""

    model_config = STRICT_FROZEN_CONFIG

    snapshot_id: SnapshotId
    bucket_id: BucketId
    captured_at: datetime
    source_url: str = Field(min_length=1)
    authenticated_identity: str | None = Field(default=None, max_length=32)
    declarations: tuple[Declaracion, ...]
    persisted_at: datetime


def _derive_snapshot_id(capture: ExpedientesCapture) -> str:
    canonical = capture.model_dump_json()
    return sha256_hex(canonical.encode("utf-8"))


def expedientes_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Execute this public contract operation."""
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            translated_message="application.live.expedientes.errors.bucket_id_blank",
        )
    if not trimmed_snapshot:
        raise LiveApplicationInputError(
            translated_message="application.live.expedientes.errors.snapshot_id_blank",
        )
    return f"expedientes-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def _expedientes_repository(
    settings: Settings,
    bucket_id: str,
) -> SecureSnapshotRepository[PersistedExpedientesSnapshot]:
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=PersistedExpedientesSnapshot,
        namespace_definition=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
        object_key=expedientes_snapshot_object_key,
        not_found_factory=lambda snapshot_id: ExpedientesSnapshotNotFoundError(
            translated_message="application.live.expedientes.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: ExpedientesSnapshotNotFoundError(
            translated_message="application.live.expedientes.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="expedientes",
        input_error_cls=LiveApplicationInputError,
        objects=secure_object_repository_for_bucket(bucket_id, settings),
    )


class ExpedientesService(StatelessSnapshotService[PersistedExpedientesSnapshot, ExpedientesCapture]):
    """Bucket-scoped persistence + read surface over expedientes snapshots.

    Structurally read-only per the live-AEAT charter. No submit, no
    acknowledge, no method that mutates AEAT state. Each public verb
    accepts ``bucket_id`` per call; storage is one encrypted secure-object
    row per captured snapshot.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize this public contract."""
        self._settings = settings or load_settings()
        super().__init__(repository_factory=lambda bucket_id: _expedientes_repository(self._settings, bucket_id))

    def capture(
        self,
        *,
        bucket_id: str,
        capture: ExpedientesCapture,
    ) -> PersistedExpedientesSnapshot:
        """Execute this public contract operation."""
        return self._capture_stateless(bucket_id=bucket_id, capture=capture)

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> PersistedExpedientesSnapshot:
        """Execute this public contract operation."""
        return self.resolve_snapshot(bucket_id=bucket_id, snapshot_id=snapshot_id)

    def latest(
        self,
        *,
        bucket_id: str,
    ) -> PersistedExpedientesSnapshot | None:
        """Execute this public contract operation."""
        snapshots = self.list_snapshots(bucket_id=bucket_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)

    @override
    def _derive_snapshot_id(self, capture: ExpedientesCapture) -> str:
        return _derive_snapshot_id(capture)

    @override
    def _build_payload(
        self,
        *,
        snapshot_id: str,
        bucket_id: str,
        capture: ExpedientesCapture,
    ) -> PersistedExpedientesSnapshot:
        return PersistedExpedientesSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            authenticated_identity=capture.authenticated_identity,
            declarations=capture.declarations,
            persisted_at=now(),
        )


LIVE_EXPEDIENTES_READ_OPERATION = "live-expedientes-read"


async def capture_expedientes(*, bucket_id: str, modelo: str, year: int) -> PersistedExpedientesSnapshot:
    """Capture the selected declaration-register view as encrypted local evidence."""
    session, settings = await active_verified_session(operation=LIVE_EXPEDIENTES_READ_OPERATION)
    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(session, settings=settings, playwright=playwright) as register,
    ):
        declarations = await register.walk(modelo=modelo, ejercicio=year)
    capture = ExpedientesCapture(
        declarations=tuple(declarations),
        captured_at=now(),
        source_url=f"declarations:modelo={modelo}:ejercicio={year}",
        authenticated_identity=session.identity_nif,
    )
    return ExpedientesService(settings=settings).capture(bucket_id=bucket_id, capture=capture)


async def capture_expedientes_bulk(
    *,
    bucket_id: str,
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None = None,
) -> ExpedientesBulkCaptureReport:
    """Capture each requested declaration-register view while reporting isolated failures."""
    if year_from > year_to:
        raise LiveApplicationInputError(
            message="from-year must be less than or equal to to-year",
            translated_message="live.errors.year_range_invalid",
        )

    resolved_modelos = modelos if modelos is not None else tuple(str(modelo.id) for modelo in resources().modelos.all())
    session, settings = await active_verified_session(operation=LIVE_EXPEDIENTES_READ_OPERATION)
    service = ExpedientesService(settings=settings)
    snapshot_ids: list[str] = []
    failures: list[ExpedientesBulkCaptureFailureRow] = []
    declarations_for_snapshot: list[Declaracion] = []
    successful_query_count = 0

    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(session, settings=settings, playwright=playwright) as register,
    ):
        for code in resolved_modelos:
            for year in range(year_to, year_from - 1, -1):
                try:
                    declarations = await register.walk(modelo=code, ejercicio=year)
                except Exception as exc:
                    failures.append(
                        ExpedientesBulkCaptureFailureRow(
                            modelo=code,
                            year=year,
                            error_type=exc.__class__.__name__,
                            message=bounded_context_text(exc),
                        ),
                    )
                    continue
                successful_query_count += 1
                declarations_for_snapshot.extend(declarations)

    if successful_query_count:
        capture = ExpedientesCapture(
            declarations=tuple(declarations_for_snapshot),
            captured_at=now(),
            source_url=(f"declarations:bulk:modelos={','.join(resolved_modelos)}:ejercicios={year_from}-{year_to}"),
            authenticated_identity=session.identity_nif,
        )
        snapshot_ids.append(service.capture(bucket_id=bucket_id, capture=capture).snapshot_id)

    return ExpedientesBulkCaptureReport(
        bucket_id=bucket_id,
        modelos=tuple(resolved_modelos),
        year_from=year_from,
        year_to=year_to,
        captured_snapshot_count=len(snapshot_ids),
        declaration_count=len(declarations_for_snapshot),
        snapshot_ids=tuple(snapshot_ids),
        failures=tuple(failures),
    )


__all__ = [
    "LIVE_EXPEDIENTES_READ_OPERATION",
    "ExpedientesCapture",
    "ExpedientesService",
    "ExpedientesSnapshotNotFoundError",
    "PersistedExpedientesSnapshot",
    "capture_expedientes",
    "capture_expedientes_bulk",
    "expedientes_snapshot_object_key",
]
