"""Protocol definitions for the application-layer auth session boundary.

These protocols declare the interface the application layer depends on for
persisted auth session management.  Concrete implementations live in the
adapter layer (adapters/outbound/aeat/auth/session_store.py) and satisfy
these protocols structurally.
:class:`SessionStoreProtocol` returns :class:`PersistedSessionDataProtocol`
records to the persisted-session service.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...core.config import Settings


@runtime_checkable
class BrowserResponsePort(Protocol):
    """Minimal response surface needed to classify an authentication probe."""

    @property
    def ok(self) -> bool:
        """Whether the browser classified the response as successful."""
        ...

    @property
    def status(self) -> int:
        """HTTP status observed by the browser."""
        ...


@runtime_checkable
class BrowserPagePort(Protocol):
    """Minimal page surface consumed by authentication providers."""

    @property
    def url(self) -> str:
        """Final page URL after redirects."""
        ...

    async def goto(
        self,
        url: str,
        *,
        timeout: float | None = None,
    ) -> BrowserResponsePort | None:
        """Navigate to ``url`` and return its response, if any."""
        ...

    async def click(self, selector: str) -> None:
        """Click one selector while driving an authentication flow."""
        ...

    async def close(self) -> None:
        """Close the page after the authentication probe completes."""
        ...


@runtime_checkable
class BrowserContextPort(Protocol):
    """Minimal browser context used by authentication providers."""

    async def new_page(self) -> BrowserPagePort:
        """Create a page for a live verification flow."""
        ...

    async def storage_state(self) -> Mapping[str, object]:
        """Return the in-memory browser storage state."""
        ...

    async def close(self) -> None:
        """Close the context during provider teardown."""
        ...


@runtime_checkable
class BrowserSessionPort(Protocol):
    """Browser lifecycle required by concrete authentication providers."""

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> BrowserContextPort:
        """Create a context with optional provider or persisted state."""
        ...

    async def close(self) -> None:
        """Close the owned browser process."""
        ...


class BrowserSessionFactoryPort(Protocol):
    """Async browser-session constructor accepted by auth composition."""

    async def __call__(self, settings: Settings) -> BrowserSessionPort:
        """Create the concrete outbound browser session for ``settings``."""
        ...


@runtime_checkable
class PersistedSessionDataProtocol(Protocol):
    """Minimal surface the application layer reads from a persisted session record."""

    @property
    def metadata(self) -> Mapping[str, object]:
        """Provider-specific session metadata."""
        ...


@runtime_checkable
class SessionStoreProtocol(Protocol):
    """Structural interface for the persisted browser session store.

    The application layer depends on this protocol rather than the concrete
    adapter module so that application/auth/_sessions.py does not carry a
    direct import from adapters/outbound/aeat/auth/session_store.py.
    """

    def exists(self, path: Path) -> bool:
        """Return whether a session is persisted at logical ``path``."""
        ...

    def load(self, path: Path) -> PersistedSessionDataProtocol | None:
        """Load persisted session data for ``path``.

        Returns a :class:`PersistedSessionDataProtocol`, or ``None`` when absent.
        """
        ...

    def delete(self, path: Path) -> bool:
        """Delete persisted session data at ``path``, returning True when removed."""
        ...


_BOUND_SESSION_STORE: ContextVar[SessionStoreProtocol] = ContextVar("cadrumo_auth_session_store")


@contextmanager
def bind_session_store(store: SessionStoreProtocol) -> Generator[SessionStoreProtocol]:
    """Bind the encrypted outbound session store for one runtime scope."""
    token = _BOUND_SESSION_STORE.set(store)
    try:
        yield store
    finally:
        _BOUND_SESSION_STORE.reset(token)


def session_store() -> SessionStoreProtocol:
    """Return the session store installed by outward composition."""
    try:
        return _BOUND_SESSION_STORE.get()
    except LookupError as exc:
        raise RuntimeError("AEAT authentication session-store composition is not bound") from exc


__all__ = [
    "BrowserContextPort",
    "BrowserPagePort",
    "BrowserResponsePort",
    "BrowserSessionFactoryPort",
    "BrowserSessionPort",
    "PersistedSessionDataProtocol",
    "SessionStoreProtocol",
    "bind_session_store",
    "session_store",
]
