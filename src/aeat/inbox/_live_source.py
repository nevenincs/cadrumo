"""Live AEAT adapter bridging :class:`aeat.status.StatusReader` to the inbox.

:class:`LiveAeatNotificacionSource` structurally satisfies the
:class:`NotificacionSource` Protocol (see :mod:`aeat.inbox._protocols`)
by wrapping an object that conforms to a minimal "status-like" protocol
(``async fetch_notificaciones(since: date | None) -> tuple[status.Notificacion, ...]``)
and translating every returned ``status.Notificacion`` into an inbox
:class:`RawNotificacion`.

This adapter is **read-only** by construction: it only consumes an
already-constructed status reader and performs no I/O of its own. The
status reader is the sole component permitted to touch the browser,
and only through safe ``page.goto(..., wait_until="domcontentloaded")``
navigations — see the live-AEAT-write safety charter (#116).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..status import Notificacion as StatusNotificacion
from ._protocols import RawNotificacion


@runtime_checkable
class _StatusNotificacionReader(Protocol):
    """Structural protocol every status reader this adapter accepts.

    Captures the exact subset of :class:`aeat.status.StatusReader` the
    adapter needs. Declared here so test doubles can be plain Python
    classes with no Playwright runtime.
    """

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
        use_cache: bool = True,
    ) -> tuple[StatusNotificacion, ...]:
        """Fetch the status-shape notificaciones tuple."""
        ...


def _translate(record: StatusNotificacion) -> RawNotificacion:
    """Translate a :class:`aeat.status.Notificacion` into a :class:`RawNotificacion`.

    The inbox classifier depends on ``subject["es"]`` for longest-prefix
    matching, so we pass the status record's ``title`` through as the
    subject and use the same ``body_excerpt``. The inbox legal
    ``effective_at`` is set to the status record's ``received_at``
    (the *fecha de puesta a disposición*) — a conservative choice per
    the inbox ADR decision D5 until the Sede surface exposes the
    separate *fecha de notificación* field.
    """
    return RawNotificacion(
        notificacion_id=record.notificacion_id,
        subject=record.title,
        body_excerpt=record.body_excerpt,
        received_at=record.received_at,
        effective_at=record.received_at,
        references_modelo=None,
        references_period=None,
        attached_pdf_path=None,
        attached_pdf_sha256=None,
        source_url=record.source_page_url,
    )


class LiveAeatNotificacionSource:
    """:class:`NotificacionSource` adapter over a live AEAT status reader.

    The adapter does not own the reader's lifecycle; callers construct
    and close the reader. This matches the ownership contract declared
    on :class:`aeat.status.StatusReader`.

    Attributes:
        reader: A live or fake :class:`_StatusNotificacionReader`.
    """

    def __init__(self, reader: _StatusNotificacionReader) -> None:
        """Construct a live AEAT notificacion source.

        Args:
            reader: Any object structurally conformant to
                :class:`_StatusNotificacionReader`. In production this
                is a real :class:`aeat.status.StatusReader`; tests pass
                plain Python classes.
        """
        self.reader = reader

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
    ) -> tuple[RawNotificacion, ...]:
        """Fetch notifications from the reader and translate them."""
        rows = await self.reader.fetch_notificaciones(since=since)
        return tuple(_translate(record) for record in rows)
