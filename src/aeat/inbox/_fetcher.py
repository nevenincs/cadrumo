"""Composition layer that fetches, classifies, and persists notifications.

:class:`InboxFetcher` wraps a :class:`NotificacionSource` (Protocol
stub for #43), runs every fetched payload through the classifier,
computes the appeal deadline, and persists the result to a single
on-disk :class:`Inbox` JSON file.

The inbox is the *read-only* side of the AEAT relationship — the
fetcher never writes back to AEAT. Acknowledgement is local state
only; see [[2026-04-12-notifications-inbox-adr]] decision D1.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from aeat.inbox._classifier import classify, compute_appeal_deadline
from aeat.inbox._errors import InboxAcknowledgeError, InboxFetchError
from aeat.inbox._models import Inbox, Notificacion
from aeat.inbox._protocols import NotificacionSource, RawNotificacion
from aeat.logging import get_logger

_LOGGER = get_logger(__name__)


class InboxFetcher:
    """Composes a :class:`NotificacionSource` with on-disk persistence.

    Attributes:
        source: The upstream :class:`NotificacionSource` (Protocol
            stub for #43).
        inbox_file: The canonical :class:`pathlib.Path` of the
            persisted inbox JSON file.
        pdf_dir: The directory under which attached PDFs are stored.
    """

    def __init__(
        self,
        source: NotificacionSource,
        *,
        inbox_file: Path,
        pdf_dir: Path,
    ) -> None:
        """Construct an inbox fetcher.

        Args:
            source: Structural conformant to
                :class:`NotificacionSource`.
            inbox_file: Path to the persisted inbox JSON file. The
                parent directory is created on write.
            pdf_dir: Directory under which notification PDFs are kept.
        """
        self.source = source
        self.inbox_file = inbox_file
        self.pdf_dir = pdf_dir

    def load_inbox(self) -> Inbox:
        """Load the persisted :class:`Inbox`, or return an empty one.

        Returns:
            The loaded :class:`Inbox`. If the file does not exist, an
            empty :class:`Inbox` is returned.

        Raises:
            InboxFetchError: If the file exists but cannot be parsed.
        """
        if not self.inbox_file.exists():
            return Inbox()
        try:
            return Inbox.model_validate_json(self.inbox_file.read_text(encoding="utf-8"))
        except Exception as exc:  # pydantic ValidationError or IO errors
            raise InboxFetchError(f"Could not load inbox from {self.inbox_file}: {exc}") from exc

    def save_inbox(self, inbox: Inbox) -> None:
        """Persist ``inbox`` to :attr:`inbox_file`.

        Args:
            inbox: The :class:`Inbox` to serialise.
        """
        self.inbox_file.parent.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_file.write_text(inbox.model_dump_json(indent=2), encoding="utf-8")

    async def fetch_new(self, *, since: datetime | None = None) -> tuple[Notificacion, ...]:
        """Fetch new notifications from the source and persist them.

        Each raw payload is classified, assigned an appeal deadline,
        and added to the persisted inbox. Records whose
        ``notificacion_id`` already exists are left untouched (the
        inbox is append-only against AEAT).

        Args:
            since: Optional lower bound on *fecha de puesta a
                disposición*. Forwarded to the source as a
                :class:`datetime.date` (the source contract accepts
                dates); :data:`None` fetches everything the source
                considers current.

        Returns:
            A tuple of every :class:`Notificacion` added to the inbox
            by this call, in source order.

        Raises:
            InboxFetchError: If the upstream source raises.
        """
        since_date: date | None = since.date() if since is not None else None
        try:
            raw_payloads = await self.source.fetch_notificaciones(since=since_date)
        except Exception as exc:
            raise InboxFetchError(f"Upstream notification source failed: {exc}") from exc

        inbox = self.load_inbox()
        added: list[Notificacion] = []
        for raw in raw_payloads:
            if raw.notificacion_id in inbox.entries:
                _LOGGER.debug("Skipping already-known notificacion %s", raw.notificacion_id)
                continue
            notificacion = self._build_notificacion(raw)
            inbox.upsert(notificacion)
            added.append(notificacion)
            _LOGGER.info(
                "Inbox fetched notificacion %s kind=%s priority=%s",
                notificacion.notificacion_id,
                notificacion.kind.value,
                notificacion.priority.value,
            )
        self.save_inbox(inbox)
        return tuple(added)

    async def acknowledge(self, notificacion_id: str, *, by: str) -> Notificacion:
        """Mark ``notificacion_id`` as acknowledged locally.

        Acknowledgement is **local state only** — it does not tell
        AEAT anything. See ADR decision D1.

        Args:
            notificacion_id: Which notification to mark.
            by: Short identifier for the acknowledging user (typically
                initials). Must be non-empty.

        Returns:
            The updated :class:`Notificacion`.

        Raises:
            InboxAcknowledgeError: If the id is unknown, ``by`` is
                empty, or the record is already acknowledged.
        """
        if not by:
            raise InboxAcknowledgeError("'by' must be a non-empty string")
        inbox = self.load_inbox()
        existing = inbox.get(notificacion_id)
        if existing is None:
            raise InboxAcknowledgeError(f"Unknown notificacion_id {notificacion_id!r}")
        if existing.acknowledged_at is not None:
            raise InboxAcknowledgeError(
                f"notificacion {notificacion_id!r} is already acknowledged by "
                f"{existing.acknowledged_by!r} at {existing.acknowledged_at.isoformat()}"
            )
        updated = existing.model_copy(
            update={
                "acknowledged_at": datetime.now(tz=UTC),
                "acknowledged_by": by,
            }
        )
        inbox.upsert(updated)
        self.save_inbox(inbox)
        _LOGGER.info("Inbox acknowledged notificacion %s by %s", notificacion_id, by)
        return updated

    def _build_notificacion(self, raw: RawNotificacion) -> Notificacion:
        """Classify ``raw`` and return the typed :class:`Notificacion`."""
        kind, priority = classify(raw)
        deadline = compute_appeal_deadline(raw.effective_at, kind)
        return Notificacion(
            notificacion_id=raw.notificacion_id,
            kind=kind,
            priority=priority,
            subject=raw.subject,
            body_excerpt=raw.body_excerpt,
            received_at=raw.received_at,
            effective_at=raw.effective_at,
            appeal_deadline=deadline,
            references_modelo=raw.references_modelo,
            references_period=raw.references_period,
            attached_pdf_path=raw.attached_pdf_path,
            attached_pdf_sha256=raw.attached_pdf_sha256,
            source_url=raw.source_url,
        )
