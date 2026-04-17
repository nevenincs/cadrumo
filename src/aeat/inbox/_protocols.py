"""Protocol stubs for cross-subpackage dependencies still in flight.

The inbox composes the AEAT status reader (#43) for raw notification
payloads. Until #43 lands on ``main``, we declare a
:class:`RawNotificacion` strict pydantic model matching the surface
#43 will expose, plus a runtime-checkable :class:`NotificacionSource`
:class:`typing.Protocol` declaring the async method the fetcher
consumes. Rebase swap on merge is a one-file change: delete this
module, import from :mod:`aeat.status` directly.

See [[2026-04-12-notifications-inbox-adr]] decision D6.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from ..i18n import Translatable

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class RawNotificacion(BaseModel):
    """Rebase-swap stub for the raw payload shape #43 will emit.

    Attributes:
        notificacion_id: AEAT-issued stable identifier.
        subject: Trilingual subject line. The ``es`` field carries the
            canonical Spanish subject prefix the classifier reads.
        body_excerpt: Trilingual short excerpt of the notification body.
        received_at: UTC timestamp proxy for *fecha de puesta a
            disposición*.
        effective_at: UTC timestamp for the legal *fecha de
            notificación*.
        references_modelo: Optional AEAT modelo identifier.
        references_period: Optional filing period identifier.
        attached_pdf_path: Optional local path to a pre-downloaded PDF.
        attached_pdf_sha256: Optional 64-char hex digest of the PDF.
        source_url: The Sede Electrónica URL the entry was scraped from.
    """

    model_config = _STRICT_FROZEN

    notificacion_id: str = Field(min_length=1)
    subject: Translatable
    body_excerpt: Translatable
    received_at: datetime
    effective_at: datetime
    references_modelo: str | None = None
    references_period: str | None = None
    attached_pdf_path: Path | None = None
    attached_pdf_sha256: str | None = None
    source_url: AnyHttpUrl


@runtime_checkable
class NotificacionSource(Protocol):
    """Rebase-swap stub for :meth:`aeat.status.StatusReader.fetch_notificaciones`.

    Any class that provides ``async fetch_notificaciones`` with this
    signature structurally conforms. Concrete test doubles are real
    Python classes — no :mod:`unittest.mock`, no patches, no fakes.
    """

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
    ) -> tuple[RawNotificacion, ...]:
        """Fetch raw notifications from AEAT, optionally filtered by date."""
        ...
