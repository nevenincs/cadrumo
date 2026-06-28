"""Protocol definitions for the application-layer auth session boundary.

These protocols declare the interface the application layer depends on for
persisted auth session management.  Concrete implementations live in the
adapter layer (adapters/outbound/aeat/auth/_session_store.py) and satisfy
these protocols structurally.
:class:`SessionStoreProtocol` returns :class:`PersistedSessionDataProtocol`
records to the persisted-session service.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable


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
    direct import from adapters/outbound/aeat/auth/_session_store.py.
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
    "PersistedSessionDataProtocol",
    "SessionStoreProtocol",
]
