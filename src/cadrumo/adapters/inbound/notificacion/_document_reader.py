"""Adapter that reads a fetched notification document in memory."""

from __future__ import annotations

from ....application.live.notification_ports import NotificationDocumentProtocol
from ....domain.notifications import SancionLiquidacion
from ..pdf import extract_pages_text_from_bytes
from ._sancion import parse_sancion_document
from .errors import NotificacionParseError, SancionParseError


class NotificationDocumentReader:
    """Extract and parse one fetched notification document without storage."""

    def read(
        self,
        document: NotificationDocumentProtocol,
    ) -> tuple[SancionLiquidacion | None, str | None]:
        """Return the complete reading, or an explicit refusal reason."""
        try:
            pages = extract_pages_text_from_bytes(
                document.pdf_bytes,
                error_class=NotificacionParseError,
                pdf_label="an AEAT notification document",
                source_label="the fetched notification PDF",
            )
        except NotificacionParseError as exc:
            return None, f"{type(exc).__name__}: {exc}"[:512]

        try:
            return (
                parse_sancion_document(
                    "\n".join(pages),
                    certificado_id=str(document.certificado_id),
                    document_sha256=document.pdf_sha256,
                ),
                None,
            )
        except SancionParseError as exc:
            return None, f"{type(exc).__name__}: {exc}"[:512]


__all__ = ["NotificationDocumentReader"]
