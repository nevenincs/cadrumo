"""Inbound parsers for the documents AEAT serves behind a notificación.

A notification's document is fetched by the outbound sede adapter and held only
as in-memory bytes plus encrypted custody; this package turns those bytes'
extracted text layer into a typed record. It reads, it never fetches, and it
never touches storage.

The one parser today is :func:`parse_sancion_document`, a deterministic
regex reader for sanción and liquidación acts. It is deliberately not a
language model: the figures it returns are figures a taxpayer pays or appeals
against, and it refuses with :class:`SancionParseError` rather than returning a
partial or zero-filled record.

See Also:
    :mod:`adapters.outbound.aeat.sede`
        Owns the notification fetch and the legal guard that admits only an
        already-read notification.
    :mod:`adapters.inbound.pdf`
        In-memory text-layer extraction; nothing here reads a path.
"""

from __future__ import annotations

from ._document_reader import NotificationDocumentReader
from ._sancion import parse_sancion_document
from .errors import NotificacionParseError, SancionArithmeticError, SancionParseError

__all__ = [
    "NotificacionParseError",
    "NotificationDocumentReader",
    "SancionArithmeticError",
    "SancionParseError",
    "parse_sancion_document",
]
