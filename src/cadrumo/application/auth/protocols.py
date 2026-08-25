"""Protocol definitions for the application-layer auth session boundary.

These protocols declare the interface the application layer depends on for
persisted auth session management.  Concrete implementations live in the
adapter layer (adapters/outbound/aeat/auth/session_store.py) and satisfy
these protocols structurally.
:class:`SessionStoreProtocol` returns :class:`PersistedSessionDataProtocol`
records to the persisted-session service.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...core import AuthProviderKind

if TYPE_CHECKING:
    from ...core.config import Settings


@runtime_checkable
class AeatSessionPort(Protocol):
    """Secret-free authenticated-session facts consumed outside auth adapters."""

    @property
    def authenticated_at(self) -> datetime:
        """Timestamp at which AEAT authentication succeeded."""
        ...

    @property
    def idle_deadline(self) -> datetime:
        """Deadline after which the live session must be refreshed."""
        ...

    @property
    def storage_state_path(self) -> Path | None:
        """Logical encrypted browser-state key, when persistence exists."""
        ...

    @property
    def identity_nif(self) -> str:
        """Tax identity proved by the authenticated session."""
        ...

    @property
    def provider_kind(self) -> AuthProviderKind:
        """Provider that established the session."""
        ...


@runtime_checkable
class AeatLoginAssertionPort(Protocol):
    """Secret-free result of probing one authenticated AEAT session."""

    @property
    def is_valid(self) -> bool:
        """Whether the protected-resource probe confirmed the session."""
        ...

    @property
    def status_code(self) -> int:
        """HTTP status observed by the probe."""
        ...

    @property
    def error_message(self) -> str | None:
        """Non-secret provider diagnostic for a failed probe."""
        ...

    @property
    def assertion_detail(self) -> object:
        """Provider-specific, secret-free assertion evidence."""
        ...


class BrowserSessionFactoryPort(Protocol):
    """Async browser-session constructor accepted by auth composition."""

    async def __call__(self, settings: Settings) -> object:
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


__all__ = [
    "AeatLoginAssertionPort",
    "AeatSessionPort",
    "BrowserSessionFactoryPort",
    "PersistedSessionDataProtocol",
    "SessionStoreProtocol",
]
