"""Strict pydantic v2 records for the AEAT notifications inbox.

Every type that crosses a public boundary — wire (#43 status reader),
disk (the persisted inbox JSON file), or CLI — is a strict+frozen
:class:`pydantic.BaseModel` or a closed :class:`enum.StrEnum`. No
dataclasses; no bare ``dict[str, Any]``. See
[[2026-04-12-notifications-inbox-adr]] decision D4.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from aeat.i18n import Translatable

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_STRICT_MUTABLE = ConfigDict(strict=True, extra="forbid")


class NotificacionKind(StrEnum):
    """Closed enumeration of the notification kinds the inbox recognises.

    See [[2026-04-12-notifications-inbox-research]] for the Spanish
    subject-prefix mapping that drives the classifier.
    """

    REQUERIMIENTO = "REQUERIMIENTO"
    PROPUESTA_LIQUIDACION = "PROPUESTA_LIQUIDACION"
    ACUERDO_LIQUIDACION = "ACUERDO_LIQUIDACION"
    NOTIFICACION_EMBARGO = "NOTIFICACION_EMBARGO"
    ACUSE_RECIBO = "ACUSE_RECIBO"
    COMUNICACION_GENERAL = "COMUNICACION_GENERAL"
    OTRO = "OTRO"


class NotificacionPriority(StrEnum):
    """Closed enumeration of notification priority bands.

    ``CRITICAL`` drives alerting through ``aeat inbox next-deadline``;
    ``HIGH`` is the default for any unclassified notification — see
    ADR decision D3.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    INFO = "INFO"


class Notificacion(BaseModel):
    """A single AEAT notification with classification and audit metadata.

    Attributes:
        notificacion_id: The AEAT-issued stable identifier for the
            notification. Must be non-empty.
        kind: The classified :class:`NotificacionKind`.
        priority: The classified :class:`NotificacionPriority`.
        subject: Trilingual subject line.
        body_excerpt: Trilingual short excerpt of the body.
        received_at: UTC timestamp at which the inbox first observed
            the entry. Proxy for *fecha de puesta a disposición*.
        effective_at: UTC timestamp of the legal *fecha de
            notificación* — appeal-deadline arithmetic uses this and
            never :attr:`received_at` (see ADR decision D5).
        appeal_deadline: Optional calendar date the taxpayer has to
            respond by. ``None`` for informational kinds.
        references_modelo: Optional AEAT modelo this notification
            refers to (e.g. ``"130"``, ``"303"``).
        references_period: Optional period this notification refers to
            (e.g. ``"2026Q1"``).
        attached_pdf_path: Optional local filesystem path to the
            downloaded notification PDF.
        attached_pdf_sha256: Optional hex-encoded SHA-256 of the
            attached PDF bytes.
        source_url: The Sede Electrónica URL the entry came from.
        acknowledged_at: UTC timestamp at which the user ack'd this
            record, or ``None`` if unread. Acknowledgement is local
            state only — see ADR decision D1.
        acknowledged_by: Short identifier (typically user initials)
            of whoever ack'd the record, or ``None``.
        notes: Free-form local annotation; defaults to ``""``.
    """

    model_config = _STRICT_FROZEN

    notificacion_id: str = Field(min_length=1)
    kind: NotificacionKind
    priority: NotificacionPriority
    subject: Translatable
    body_excerpt: Translatable
    received_at: datetime
    effective_at: datetime
    appeal_deadline: date | None = None
    references_modelo: str | None = None
    references_period: str | None = None
    attached_pdf_path: Path | None = None
    attached_pdf_sha256: str | None = None
    source_url: AnyHttpUrl
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _check_ack_consistency(self) -> Notificacion:
        """Enforce ack-field consistency and basic time ordering."""
        if (self.acknowledged_at is None) != (self.acknowledged_by is None):
            raise ValueError("acknowledged_at and acknowledged_by must both be set or both be None")
        if self.acknowledged_at is not None and self.acknowledged_at < self.received_at:
            raise ValueError(f"acknowledged_at ({self.acknowledged_at}) is before received_at ({self.received_at})")
        if self.effective_at < self.received_at:
            raise ValueError(f"effective_at ({self.effective_at}) is before received_at ({self.received_at})")
        if self.attached_pdf_sha256 is not None and len(self.attached_pdf_sha256) != 64:
            raise ValueError("attached_pdf_sha256 must be a 64-character hex digest")
        return self


class Inbox(BaseModel):
    """Typed container wrapping a map of :class:`Notificacion` records.

    The container validates uniqueness of :attr:`Notificacion.notificacion_id`
    across all entries and is the single on-disk persistence shape for
    the inbox.

    Attributes:
        entries: Mapping of ``notificacion_id`` to
            :class:`Notificacion`. Every key must equal its value's
            :attr:`Notificacion.notificacion_id`.
    """

    model_config = _STRICT_MUTABLE

    entries: dict[str, Notificacion] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_unique_ids(self) -> Inbox:
        """Ensure every dict key equals its record's ``notificacion_id``."""
        for key, record in self.entries.items():
            if key != record.notificacion_id:
                raise ValueError(f"Inbox key {key!r} does not match record notificacion_id {record.notificacion_id!r}")
        return self

    def get(self, notificacion_id: str) -> Notificacion | None:
        """Return the notification with ``notificacion_id``, or ``None``."""
        return self.entries.get(notificacion_id)

    def upsert(self, notificacion: Notificacion) -> None:
        """Insert or replace ``notificacion`` in the inbox."""
        self.entries[notificacion.notificacion_id] = notificacion

    def values(self) -> tuple[Notificacion, ...]:
        """Return every notification as an ordered tuple."""
        return tuple(self.entries.values())
