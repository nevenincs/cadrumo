"""Protocol stubs for cross-subpackage contracts consumed by the fetcher.

The filing-history fetcher composes two collaborators:

- :class:`ExpedienteSource` — returns the list of
  :class:`aeat.status.Expediente` rows for a given ``(modelo,
  period)`` filter. The real implementation wraps
  :class:`aeat.status.StatusReader`; tests supply a real
  Protocol-conforming class backed by fixture data.
- :class:`FilingDetailFetcher` — returns raw HTML for the detail
  page of a single :class:`Expediente`. The real implementation
  drives a Playwright :class:`BrowserContext`; tests return fixture
  HTML keyed by ``expediente_id``.

A third Protocol, :class:`CertificateBackend`, mirrors the minimal
surface of :class:`aeat.status._protocols.CertificateBackend`. We do
**not** cross-import from that private module (ADR D9); the Protocol
is redeclared locally so test doubles structurally conform without
importing the real backend.

See [[2026-04-16-aeat-history-fetch-adr]] decisions D2 and D9.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import AnyHttpUrl

from ..status import Expediente

if TYPE_CHECKING:  # pragma: no cover - import cycles only in type checking
    from playwright.async_api import BrowserContext


@runtime_checkable
class ExpedienteSource(Protocol):
    """Structural contract for the upstream filing-list source.

    Any class that exposes ``async list_expedientes`` with this
    signature conforms. Concrete test doubles are real Python classes
    — no :mod:`unittest.mock`, no patches, no fakes.
    """

    async def list_expedientes(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
    ) -> tuple[Expediente, ...]:
        """Return every expediente matching ``modelo`` / ``period``.

        ``None`` on either filter means "do not filter on this field".
        """
        ...


@runtime_checkable
class FilingDetailFetcher(Protocol):
    """Structural contract for the per-filing detail-page fetcher.

    The real implementation drives a Playwright ``BrowserContext``
    via ``page.goto(detail_url, wait_until="domcontentloaded")`` and
    returns ``page.content()``. The fetcher is strictly read-only —
    no form submission, no cookie mutation beyond what a plain
    navigation performs. See ADR D1.
    """

    async def fetch_detail_html(
        self,
        expediente: Expediente,
    ) -> tuple[str, AnyHttpUrl]:
        """Return ``(raw_html, resolved_url)`` for the detail page."""
        ...


@runtime_checkable
class CertificateBackend(Protocol):
    """Minimal cert-backend surface — structural mirror of the #43 stub.

    ``preload_into_browser_context`` is invoked exactly once per live
    fetcher session, before the first navigation. Tests do not
    interact with this Protocol; it exists to document the contract
    the real :class:`FilingDetailFetcher` implementation (lands in a
    follow-up PR) will depend on.
    """

    async def preload_into_browser_context(self, context: BrowserContext) -> None:
        """Preload the user's certificate into ``context``."""
        ...
