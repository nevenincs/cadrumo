"""Typed JSON transport schemas for the live justificante service."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ...application.calculations import ObservationSourceKind
from ...application.live import SnapshotLifecycleState
from ...core import Modelo
from ...core.identity import (
    AeatCsv,
    AeatExpedienteId,
    BucketId,
    ContentDigest,
    FilingRecordId,
    SnapshotId,
)
from ...core.json_contract import OutputSchema
from ._app_live_payloads_support import JustificantePeriodToken


class JustificanteCaptureResult(OutputSchema):
    """Result envelope for a persisted :class:`JustificanteCaptureSnapshot`.

    The pull command stores the signed receipt PDF through
    :class:`JustificanteCaptureSnapshotService` and reports both the
    content-addressed ``pdf_sha256`` snapshot identity inputs and the
    best-effort local enrolment outcome from :class:`JustificanteCaptureOutcome`.
    ``filing_evidence_stamped`` is false when no current local filing record
    exists; the live capture remains persisted and can still back calendar
    evidence once metadata parses.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    expediente_id: AeatExpedienteId
    csv: AeatCsv
    pdf_sha256: ContentDigest
    source_kind: ObservationSourceKind
    state: SnapshotLifecycleState
    captured_at: datetime
    justificante_metadata_registered: bool
    calendar_evidence_available: bool
    modelo_filing_record_required: bool
    filing_evidence_stamped: bool
    filing_record_id: FilingRecordId | None = None


class JustificanteSnapshotSummaryPayload(OutputSchema):
    """Summary projection of one :class:`JustificanteCaptureSnapshot`.

    Used by :class:`JustificanteListResult` for active snapshots returned from
    :class:`JustificanteCaptureSnapshotService`.
    """

    snapshot_id: SnapshotId
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    pdf_sha256: ContentDigest
    state: SnapshotLifecycleState
    captured_at: datetime


class JustificanteListResult(OutputSchema):
    """List result from :class:`JustificanteCaptureSnapshotService`.

    ``rows`` contains :class:`JustificanteSnapshotSummaryPayload` projections
    for active :class:`JustificanteCaptureSnapshot` records in the active
    bucket, ordered by capture time and carrying the period token,
    :class:`SnapshotLifecycleState`, and raw-PDF hash needed to identify the
    official receipt without exposing the encrypted PDF bytes.
    """

    bucket_id: BucketId
    count: int
    rows: list[JustificanteSnapshotSummaryPayload]


class JustificanteViewResult(OutputSchema):
    """Detail view for one persisted :class:`JustificanteCaptureSnapshot`.

    The view resolves through :class:`JustificanteCaptureSnapshotService` and
    surfaces the AEAT expediente, CSV, official ``source_kind``,
    :class:`SnapshotLifecycleState`, and ``pdf_sha256`` so operators can
    reconcile the local evidence chain without printing the stored receipt body.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    expediente_id: AeatExpedienteId
    csv: AeatCsv
    pdf_sha256: ContentDigest
    source_kind: ObservationSourceKind
    state: SnapshotLifecycleState
    captured_at: datetime


__all__ = [
    "JustificanteCaptureResult",
    "JustificanteListResult",
    "JustificanteSnapshotSummaryPayload",
    "JustificanteViewResult",
]
