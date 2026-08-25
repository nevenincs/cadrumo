"""Typed JSON transport schemas for the live notifications service."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    Field,
    model_validator,
)

from ...core.identity import (
    AeatCertificadoId,
    AeatClaveLiquidacion,
    BucketId,
    ContentDigest,
    SnapshotId,
)
from ...core.json_contract import OutputSchema


class NotificationRowPayload(OutputSchema):
    """One DEHú notification row in a viewed persisted snapshot.

    Mirrors :class:`RemoteNotification` rows stored inside
    :class:`PersistedNotificationsSnapshot`.
    The payload is a CLI projection of already-captured evidence; rendering it
    does not acknowledge, mark, or mutate a notification in AEAT.
    """

    certificado_id: AeatCertificadoId
    tipo: str
    concepto: str
    titular_nif: str
    titular_nombre: str
    destinatario_nif: str
    destinatario_nombre: str
    fecha_emision: str
    fecha_notificacion: str | None
    modo_notificacion: str | None
    leida: bool | None
    source_url: str
    mode: str


class NotificationSnapshotListingPayload(OutputSchema):
    """Summary row for one persisted DEHu notification snapshot.

    Used by :class:`NotificationsListResult` to expose the bucket snapshot id,
    capture timestamp, and row count returned by
    :class:`NotificationsService` without expanding the underlying
    :class:`NotificationRowPayload` records.
    """

    snapshot_id: SnapshotId
    captured_at: datetime
    row_count: int = Field(ge=0)


class NotificationsCaptureResult(OutputSchema):
    """Typed result for a persisted DEHu notification pull.

    The pull command performs the live read before this schema is built; the
    payload records the bucket-scoped :class:`PersistedNotificationsSnapshot`
    written by :class:`NotificationsService`, not an AEAT-side write or
    acknowledgement.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    persisted_at: datetime
    row_count: int = Field(ge=0)
    source_url: str = Field(min_length=1)


class NotificationsListResult(OutputSchema):
    """Typed listing of persisted DEHu notification snapshots.

    ``rows`` contains :class:`NotificationSnapshotListingPayload` summaries
    returned by :class:`NotificationsService` ``list_snapshots``; message
    detail stays on :class:`NotificationsViewResult`.
    """

    bucket_id: BucketId
    count: int = Field(ge=0)
    rows: list[NotificationSnapshotListingPayload]


class NotificationsViewResult(OutputSchema):
    """Typed detail view for one persisted DEHu notification snapshot.

    The command resolves a stored snapshot through
    :class:`NotificationsService` ``show`` and expands its
    :class:`PersistedNotificationsSnapshot` rows as
    :class:`NotificationRowPayload` records. It is a bucket read, not a remote
    notification-state mutation.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    source_url: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    rows: list[NotificationRowPayload]


class NotificationsLatestResult(OutputSchema):
    """Typed newest-snapshot response for DEHu notifications.

    ``snapshot_id`` is ``None`` when the bucket has no captured notification
    snapshot from :class:`NotificationsService` ``latest``; in that empty case
    every :class:`PersistedNotificationsSnapshot`-derived field is also
    ``None`` so JSON clients can keep one stable schema for present and absent
    data.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: datetime | None = None
    source_url: str | None = None
    row_count: int | None = Field(default=None, ge=0)


class SancionReadingPayload(OutputSchema):
    """JSON projection of one :class:`SancionLiquidacion` reading.

    Every amount is the figure PRINTED on the document AEAT served, carried as
    a string so the persisted ``Decimal`` scale survives the wire exactly —
    ``774.29`` and ``774.290`` are different printings and JSON's float would
    lose the difference. Nothing here is computed by this application, and an
    absent reducción stays ``None`` rather than becoming ``"0"``, because a
    reducción AEAT did not grant is not a reducción it granted at zero.
    """

    certificado_id: AeatCertificadoId
    clave_liquidacion: AeatClaveLiquidacion
    referencia: str
    nif: str
    objeto_tributario: str
    base_sancion: str
    porcentaje_minimo: str
    sancion_resultante: str
    reduccion_conformidad: str | None
    reduccion_pronto_pago: str | None
    diferencia: str | None
    importe_a_ingresar: str
    document_sha256: ContentDigest


class NotificationDocumentPayload(OutputSchema):
    """Shared projection of one stored :class:`NotificationDocumentRecord`.

    The bytes themselves never appear here and never will: they live in the
    encrypted attachment store, and this payload carries their content address
    and digest so an operator can tie a reading back to the exact custody bytes
    without the document leaving secure storage.

    ``sancion`` and ``parse_refusal`` are mutually exclusive by construction —
    the reader either vouched for a reading or refused to — and the refusal is
    reported as primary result data rather than smuggled into a bespoke
    advisory field, with the operator-facing diagnostic riding the envelope's
    ``notices`` channel.
    """

    bucket_id: BucketId
    certificado_id: AeatCertificadoId
    attachment_id: ContentDigest
    document_sha256: ContentDigest
    byte_size: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    fetched_at: datetime
    sancion_parsed: bool
    sancion: SancionReadingPayload | None = None
    parse_refusal: str | None = Field(default=None, min_length=1, max_length=512)
    mode: Literal["read"] = "read"

    @model_validator(mode="after")
    def _a_reading_is_present_or_refused_never_both_nor_neither(self) -> NotificationDocumentPayload:
        """Keep the reading flag honest against the two fields it summarises.

        A payload claiming ``sancion_parsed`` with no reading, or reporting
        neither a reading nor a reason, would let an operator conclude the
        document held no figures when the truth is that nobody looked.
        """
        if self.sancion_parsed != (self.sancion is not None):
            raise ValueError("sancion_parsed must agree with the presence of a sancion reading")
        if (self.sancion is None) == (self.parse_refusal is None):
            raise ValueError("a stored document carries either a sancion reading or the reason there is none")
        return self


class NotificationDocumentPullResult(NotificationDocumentPayload):
    """Typed result for one guarded notification-document fetch.

    ``already_in_custody`` is the idempotency outcome: a retry against a
    certificado already held stores nothing and returns the row that was there,
    which is otherwise indistinguishable from a first store. It is result data
    rather than a diagnostic — the matching operator-facing advisory rides the
    envelope's ``notices`` channel — and an agent routing on retries needs the
    field, not the prose.
    """

    already_in_custody: bool


class NotificationDocumentViewResult(NotificationDocumentPayload):
    """Typed read-back of one stored notification document.

    Resolved entirely from bucket-local encrypted custody through
    :class:`NotificationDocumentService`. The verb that emits this contacts
    AEAT not at all, so it can never be the act that serves a notification.
    """


class NotificationDocumentHistoryEntry(OutputSchema):
    """One parsed document in custody, with only its own reported figures."""

    certificado_id: AeatCertificadoId
    fetched_at: datetime
    sancion: SancionReadingPayload


class NotificationDocumentHistoryResult(OutputSchema):
    """Parsed notification documents held by this profile, without a total."""

    bucket_id: BucketId
    count: int = Field(ge=0)
    documents: list[NotificationDocumentHistoryEntry]


__all__ = [
    "NotificationDocumentHistoryEntry",
    "NotificationDocumentHistoryResult",
    "NotificationDocumentPayload",
    "NotificationDocumentPullResult",
    "NotificationDocumentViewResult",
    "NotificationRowPayload",
    "NotificationSnapshotListingPayload",
    "NotificationsCaptureResult",
    "NotificationsLatestResult",
    "NotificationsListResult",
    "NotificationsViewResult",
    "SancionReadingPayload",
]
