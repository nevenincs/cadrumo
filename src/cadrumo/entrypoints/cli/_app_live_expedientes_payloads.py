"""Typed JSON transport schemas for the live expedientes service."""

from __future__ import annotations

from typing import Literal

from ...core.identity import (
    AeatExpedienteId,
    BucketId,
    SnapshotId,
)
from ...core.json_contract import OutputSchema


class ExpedienteDeclarationPayload(OutputSchema):
    """One declaration-register row inside an expedientes-view payload.

    Mirrors :class:`Declaracion` rows persisted in a
    :class:`PersistedExpedientesSnapshot`.
    Link-text and cell-index fields report what the read-only AEAT register
    exposed; they are not downloaded artefacts and do not imply a remote
    mutation.
    """

    modelo: str
    ejercicio: int
    period: str
    expediente_id: AeatExpedienteId
    estado: str
    tipo_solicitud: str | None
    observaciones: str | None
    presented_at: str
    justificante_link_text: str | None
    archive_link_text: str | None
    declaration_copy_link_text: str | None
    justificante_cell_index: int
    archive_cell_index: int | None
    declaration_copy_cell_index: int | None
    mode: str


class ExpedienteSnapshotSummaryPayload(OutputSchema):
    """Summary row for one persisted expedientes snapshot.

    Used by :class:`ExpedientesListResult` for rows returned from
    :class:`ExpedientesService`; full :class:`ExpedienteDeclarationPayload`
    detail remains on :class:`ExpedientesViewResult`.
    """

    snapshot_id: SnapshotId
    captured_at: str
    source_url: str
    declaration_count: int


class ExpedientesCaptureFailurePayload(OutputSchema):
    """One failed modelo/year row from a bulk expedientes pull.

    Mirrors :class:`ExpedientesBulkCaptureFailureRow` entries in
    :class:`ExpedientesBulkCaptureReport`, preserving the failed input
    coordinates and redacted diagnostic text without inventing a partial
    :class:`PersistedExpedientesSnapshot`.
    """

    modelo: str
    year: int
    error_type: str
    message: str


class ExpedientesCaptureResult(OutputSchema):
    """Typed result for one or more persisted expedientes pulls.

    ``mode`` distinguishes a single-modelo capture from a bulk year-range
    capture. Successful :class:`PersistedExpedientesSnapshot` records are
    persisted by :class:`ExpedientesService`; failed modelo/year pairs are
    reported as :class:`ExpedientesCaptureFailurePayload` rows without inventing
    declaration data.
    """

    mode: Literal["single", "bulk"] = "single"
    bucket_id: BucketId
    snapshot_id: SnapshotId | None = None
    captured_at: str | None = None
    persisted_at: str | None = None
    declaration_count: int
    source_url: str | None = None
    modelos: list[str] = []
    year_from: int | None = None
    year_to: int | None = None
    captured_snapshot_count: int = 0
    snapshot_ids: list[str] = []
    failed_count: int = 0
    failures: list[ExpedientesCaptureFailurePayload] = []


class ExpedientesListResult(OutputSchema):
    """Typed listing of persisted expedientes snapshots.

    ``rows`` is the compact :class:`ExpedienteSnapshotSummaryPayload`
    projection returned by :class:`ExpedientesService` ``list_snapshots``; use
    :class:`ExpedientesViewResult` for per-declaration detail.
    """

    bucket_id: BucketId
    count: int
    rows: list[ExpedienteSnapshotSummaryPayload]


class ExpedientesViewResult(OutputSchema):
    """Typed detail view for one persisted expedientes snapshot.

    The command resolves a stored :class:`PersistedExpedientesSnapshot` through
    :class:`ExpedientesService` and projects each declaration into
    :class:`ExpedienteDeclarationPayload`.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: str
    source_url: str
    declaration_count: int
    declarations: list[ExpedienteDeclarationPayload]


class ExpedientesLatestResult(OutputSchema):
    """Typed newest-snapshot response for expedientes.

    ``snapshot_id`` is ``None`` when the bucket has no captured expedientes
    snapshot from :class:`ExpedientesService`; in that case every
    :class:`PersistedExpedientesSnapshot`-derived field is also ``None`` to keep
    the payload shape stable for JSON clients.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: str | None = None
    source_url: str | None = None
    declaration_count: int | None = None


__all__ = [
    "ExpedienteDeclarationPayload",
    "ExpedienteSnapshotSummaryPayload",
    "ExpedientesCaptureFailurePayload",
    "ExpedientesCaptureResult",
    "ExpedientesLatestResult",
    "ExpedientesListResult",
    "ExpedientesViewResult",
]
