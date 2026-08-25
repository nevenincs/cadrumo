"""Browser protocols for concrete live AEAT authentication adapters.

The protocols mirror the subset of
:class:`adapters.outbound.aeat.browser.BrowserSession` that auth providers
need, so tests and adapter callers can satisfy the same structural contract
without importing Playwright directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import SecretStr

from .....core.errors import AeatLoginAssertionError
from .certificate import CertificateHealth

if TYPE_CHECKING:
    from .....core.config import Settings


class PersistedSessionInvalidError(AeatLoginAssertionError):
    """Raised when a persisted AEAT browser session cannot be trusted."""


@runtime_checkable
class BrowserPageLike(Protocol):
    """Minimal Playwright page surface consumed by auth verification flows."""

    @property
    def url(self) -> str:
        """Final page URL after navigation and redirects."""
        ...

    async def goto(
        self,
        url: str,
        *,
        timeout: float | None = None,
    ) -> BrowserResponseLike | None:
        """Navigate to ``url`` and return the observed :class:`BrowserResponseLike`, if any."""
        ...

    async def click(self, selector: str) -> None:
        """Click a selector while driving an authentication flow."""
        ...

    async def close(self) -> None:
        """Close the page after the auth probe completes."""
        ...


@runtime_checkable
class BrowserResponseLike(Protocol):
    """Minimal response surface needed to classify an AEAT probe."""

    @property
    def ok(self) -> bool:
        """Whether Playwright classifies the response as successful."""
        ...

    @property
    def status(self) -> int:
        """HTTP status observed by the verification navigation."""
        ...


@runtime_checkable
class BrowserContextLike(Protocol):
    """Minimal Playwright context surface used by auth providers."""

    async def new_page(self) -> BrowserPageLike:
        """Create a :class:`BrowserPageLike` for a live verification or selector flow."""
        ...

    async def storage_state(self) -> Mapping[str, object]:
        """Return Playwright storage state for encrypted session persistence."""
        ...

    async def close(self) -> None:
        """Close the context during provider teardown."""
        ...


@runtime_checkable
class BrowserSessionLike(Protocol):
    """Browser-session factory surface used by certificate and Cl@ve auth.

    The signature mirrors
    :meth:`adapters.outbound.aeat.browser.BrowserSession.create_context`:
    certificate auth may pass a context provisioner, while resume paths pass
    decrypted in-memory storage state. Auth never asks the browser layer to
    reopen a plaintext filesystem path.

    Every implementation owns a browser lifecycle and therefore provides
    deterministic asynchronous closure.
    """

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> BrowserContextLike:
        """Create a :class:`BrowserContextLike` with optional auth provider state."""
        ...

    async def close(self) -> None:
        """Close the owned browser process. Must be safe to call repeatedly."""
        ...


@runtime_checkable
class CertificateHealthCheck(Protocol):
    """Callable shape used to evaluate a loaded certificate's health."""

    def __call__(
        self,
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        friendly_name: str | None = ...,
        now: datetime | None = ...,
    ) -> CertificateHealth:
        """Return :class:`CertificateHealth` for the supplied PKCS#12 bundle."""
        ...


class BrowserSessionFactory(Protocol):
    """Async factory for objects satisfying :class:`BrowserSessionLike`."""

    async def __call__(self, settings: Settings) -> BrowserSessionLike:
        """Create a browser session configured from ``settings``."""
        ...


__all__ = [
    "BrowserContextLike",
    "BrowserPageLike",
    "BrowserResponseLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
    "CertificateHealthCheck",
    "PersistedSessionInvalidError",
]

