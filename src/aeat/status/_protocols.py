"""Protocol stubs for cross-module contracts used by the status reader.

The reader still prefers structural typing over hard imports from
the browser/auth layers, but the Protocol surface now mirrors the
real loaded-certificate object exposed by :mod:`aeat.auth`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - import cycles only in type checking
    from playwright.async_api import BrowserContext


@runtime_checkable
class BrowserSessionLike(Protocol):
    """Structural slice of :class:`aeat.browser.BrowserSession` the reader needs.

    The status reader only calls ``create_context``; exposing that
    narrow surface as a Protocol lets real Protocol-conforming test
    doubles slot in without subclassing the full browser session.
    """

    async def create_context(self) -> BrowserContext:
        """Create a new Playwright browser context."""
        ...


@runtime_checkable
class CertificateBackend(Protocol):
    """Minimal certificate-backend surface consumed by the status reader.

    Mirrors the real auth object surface now exposed by :mod:`aeat.auth`:

    - ``preload_into_browser_context`` is invoked exactly once per
      :class:`aeat.status.StatusReader` lifetime, before the first
      navigation to an authenticated AEAT surface.
    """

    def preload_into_browser_context(self, context: BrowserContext) -> None:
        """Preload the user's certificate into the given Playwright context.

        Args:
            context: The Playwright browser context that should carry
                the certificate on subsequent navigations.
        """
        ...
