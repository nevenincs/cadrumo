"""Shared helpers for the ``aeat inbox`` CLI sub-app.

Pure CLI glue: builds an :class:`InboxFetcher` with a concrete
file-backed :class:`NotificacionSource`. Production call sites will
rebase this onto a real adapter over :mod:`aeat.status` (#43) when
the status reader lands; until then, the CLI reads raw notification
payloads from a user-maintained JSON file pointed at by
``AEAT_INBOX_DIR / source.json``. The file-backed source is **not a
mock** — it is a real Python class that structurally satisfies the
:class:`NotificacionSource` Protocol.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aeat.config import Settings, load_settings
from aeat.inbox import InboxFetcher, RawNotificacion


class _FileBackedNotificacionSource:
    """Real file-backed :class:`NotificacionSource` for CLI v1.

    Reads a JSON document of the shape ``{"notifications": [...]}``
    where each element validates against :class:`RawNotificacion`.
    Absent file → empty tuple. Applies the ``since`` filter against
    :attr:`RawNotificacion.received_at`.
    """

    def __init__(self, source_file: Path) -> None:
        """Construct a file-backed source.

        Args:
            source_file: Path to a JSON file containing a
                ``{"notifications": [...]}`` envelope.
        """
        self.source_file = source_file

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
    ) -> tuple[RawNotificacion, ...]:
        """Return every :class:`RawNotificacion` in :attr:`source_file`."""
        if not self.source_file.exists():
            return ()
        envelope = _RawEnvelope.model_validate_json(self.source_file.read_text(encoding="utf-8"))
        if since is None:
            return envelope.notifications
        return tuple(n for n in envelope.notifications if n.received_at.date() >= since)


class _RawEnvelope(BaseModel):
    """Typed envelope for the file-backed notification source."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    notifications: tuple[RawNotificacion, ...] = Field(default_factory=tuple)


def build_fetcher(settings: Settings | None = None) -> InboxFetcher:
    """Construct an :class:`InboxFetcher` wired to the CLI file source.

    Args:
        settings: Optional :class:`Settings` override (used by tests).

    Returns:
        A fully wired :class:`InboxFetcher`.
    """
    cfg = settings or load_settings()
    inbox_file = cfg.aeat_inbox_dir / "inbox.json"
    source_file = cfg.aeat_inbox_dir / "source.json"
    return InboxFetcher(
        source=_FileBackedNotificacionSource(source_file),
        inbox_file=inbox_file,
        pdf_dir=cfg.aeat_inbox_pdf_dir,
    )
