"""Typed JSON transport schemas for the live deudas service."""

from __future__ import annotations

from ...core.identity import (
    AeatClaveLiquidacion,
    BucketId,
    SnapshotId,
)
from ...core.json_contract import OutputSchema


class DeudaRowPayload(OutputSchema):
    """One AEAT-reported liability inside a deudas-view payload.

    Mirrors :class:`Deuda` rows persisted in a
    :class:`PersistedDeudasSnapshot`. Every field reports what AEAT's debts
    consulta stated; nothing here is computed by this application, and nothing
    here is an input to any modelo casilla.

    ``importe_pendiente`` is a non-negative magnitude carried as a string so
    the JSON payload preserves the persisted ``Decimal`` scale exactly.
    Direction lives on ``direccion``, never in the sign of the amount.
    """

    clave_liquidacion: AeatClaveLiquidacion
    objeto_tributario: str
    importe_pendiente: str
    direccion: str
    periodo: str | None
    situacion: str
    mode: str


class DeudaSnapshotSummaryPayload(OutputSchema):
    """Summary row for one persisted deudas snapshot.

    Used by :class:`DeudasListResult` for rows returned from
    :class:`DeudasService`; full :class:`DeudaRowPayload` detail remains on
    :class:`DeudasViewResult`.
    """

    snapshot_id: SnapshotId
    captured_at: str
    source_url: str
    deuda_count: int


class DeudasListResult(OutputSchema):
    """Typed listing of persisted deudas snapshots.

    ``rows`` is the compact :class:`DeudaSnapshotSummaryPayload` projection
    returned by :class:`DeudasService` ``list_snapshots``; use
    :class:`DeudasViewResult` for per-liability detail.
    """

    bucket_id: BucketId
    count: int
    rows: list[DeudaSnapshotSummaryPayload]


class DeudasViewResult(OutputSchema):
    """Typed detail view for one persisted deudas snapshot.

    The command resolves a stored :class:`PersistedDeudasSnapshot` through
    :class:`DeudasService` and projects each liability into
    :class:`DeudaRowPayload`.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: str
    source_url: str
    deuda_count: int
    deudas: list[DeudaRowPayload]


class DeudasLatestResult(OutputSchema):
    """Typed newest-snapshot response for deudas.

    ``snapshot_id`` is ``None`` when the bucket has no captured deudas
    snapshot from :class:`DeudasService`; in that case every
    :class:`PersistedDeudasSnapshot`-derived field is also ``None`` to keep the
    payload shape stable for JSON clients. An empty register is reported as
    empty rather than triggering a live AEAT read.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: str | None = None
    source_url: str | None = None
    deuda_count: int | None = None


__all__ = [
    "DeudaRowPayload",
    "DeudaSnapshotSummaryPayload",
    "DeudasLatestResult",
    "DeudasListResult",
    "DeudasViewResult",
]
