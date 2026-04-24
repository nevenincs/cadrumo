"""Shared helpers for the ``aeat inbox`` CLI sub-app.

Pure CLI glue: builds an :class:`InboxFetcher` with either a
file-backed :class:`NotificacionSource` (the default, keeps offline
dev fast) or a :class:`LiveAeatNotificacionSource` that pulls from the
live AEAT Sede via the authenticated status reader (#170). The file-
backed source is **not a mock** — it is a real Python class that
structurally satisfies the :class:`NotificacionSource` Protocol.

Charter #116 (no-write mandate): both sources are strictly read-only.
The live source delegates to :class:`aeat.status.StatusReader`, which
performs only safe ``page.goto(..., wait_until="domcontentloaded")``
navigations.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...config import Settings, load_settings
from ...inbox import InboxFetcher, NotificacionSource, RawNotificacion


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


def build_fetcher(
    settings: Settings | None = None,
    *,
    source: NotificacionSource | None = None,
) -> InboxFetcher:
    """Construct an :class:`InboxFetcher` wired to a notificacion source.

    Args:
        settings: Optional :class:`Settings` override (used by tests).
        source: Optional :class:`NotificacionSource` override. When
            omitted, the file-backed source is used — that is the
            safe default for offline dev. The live path injects a
            :class:`LiveAeatNotificacionSource` constructed around an
            authenticated :class:`StatusReader`.

    Returns:
        A fully wired :class:`InboxFetcher`.
    """
    cfg = settings or load_settings()
    inbox_file = cfg.aeat_inbox_dir / "inbox.json"
    source_file = cfg.aeat_inbox_dir / "source.json"
    resolved = source if source is not None else _FileBackedNotificacionSource(source_file)
    return InboxFetcher(
        source=resolved,
        inbox_file=inbox_file,
        pdf_dir=cfg.aeat_inbox_pdf_dir,
    )


def build_live_source() -> NotificacionSource:
    """Live source entry point — wired to :mod:`aeat.sede.notifications`.

    The pre-discovery cert-only :class:`LiveAeatNotificacionSource` was
    deleted in the #239 rewrite because its integration path (the
    cert-only :class:`aeat.status.StatusReader.fetch_notificaciones`)
    never reached live AEAT. The replacement lives under
    :mod:`aeat.sede.notifications` and is selected there when it
    lands. Until then, the ``--live`` mode raises with an actionable
    message rather than silently falling back.
    """
    raise NotImplementedError(
        "Live inbox source is being rewired through aeat.sede.notifications (#239). "
        "Run `aeat sede list-expedientes` today; a Clave-capable live inbox fetch lands next."
    )
