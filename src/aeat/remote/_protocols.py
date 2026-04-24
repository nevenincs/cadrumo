"""Typed duck-typing Protocols for remote AEAT fetchers.

Both Protocols are ``@runtime_checkable`` so ``isinstance`` checks stay
cheap in unit tests. They duck-type the public facade surfaces already
exposed by :class:`aeat.status.StatusReader` but narrow the return type
to the typed :mod:`aeat.remote` aggregates rather than the raw history
tuples. The Protocols therefore act as the integration seam between
the Phase 2 read-only fetchers and any in-flight work landing through
sibling PRs — no cross-imports of private modules are required.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ._schema import RemoteFiling, RemoteNotification


@runtime_checkable
class RemoteFilingFetcher(Protocol):
    """Duck-typed fetcher for ``(modelo, period)``-scoped remote filings.

    Mirrors :meth:`aeat.status.StatusReader.fetch_filing_detail` but
    yields typed :class:`aeat.remote.RemoteFiling` aggregates instead of
    raw history records so callers never have to re-coerce Spanish
    status prose or untyped casilla strings.
    """

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[RemoteFiling, ...]:
        """Return every :class:`RemoteFiling` matching ``(modelo, period)``.

        Args:
            modelo: Required AEAT modelo code (``"130"``, ``"303"``, ...).
            period: Required period identifier (``"2025-1T"``, ``"2025"``).
            use_cache: When ``True`` (default) the fetcher honours its
                read-side TTL cache; ``False`` forces a live re-fetch.

        Returns:
            A possibly-empty tuple of :class:`RemoteFiling` ordered as
            AEAT surfaces them. An empty tuple signals that AEAT has no
            expediente for the requested pair, which the reconciler
            interprets as ``NOT_YET_FOUND``.
        """
        ...


@runtime_checkable
class NotificationReader(Protocol):
    """Duck-typed reader for the post-auth notifications centre.

    Mirrors :meth:`aeat.status.StatusReader.fetch_notificaciones` but
    returns :class:`aeat.remote.RemoteNotification` instead of the
    loosely-typed :class:`aeat.status.Notificacion` record.
    """

    async def fetch_notificaciones(
        self,
        *,
        since: date | None = None,
        use_cache: bool = True,
    ) -> tuple[RemoteNotification, ...]:
        """Return every notification AEAT surfaces for the active session.

        Args:
            since: Optional inclusive lower bound on ``issued_at``; when
                ``None`` the reader returns every available notification.
            use_cache: When ``True`` (default) the reader honours its
                read-side TTL cache; ``False`` forces a live re-fetch.

        Returns:
            A possibly-empty tuple of :class:`RemoteNotification`
            ordered newest-first, matching AEAT's own presentation.
        """
        ...


__all__ = [
    "NotificationReader",
    "RemoteFilingFetcher",
]
