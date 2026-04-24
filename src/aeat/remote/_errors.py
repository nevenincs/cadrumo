"""Error hierarchy for the :mod:`aeat.remote` read-only surface.

Every error defined here inherits from :class:`aeat.errors.AeatError` so
cross-subpackage catch blocks stay uniform. The hierarchy mirrors the
``*Error`` / ``*ParseError`` / ``*NavigationError`` split already
established by :mod:`aeat.status` and :mod:`aeat.history`.
"""

from __future__ import annotations

from ..errors import AeatError


class RemoteFetchError(AeatError):
    """Base error for any failure while fetching data from the AEAT remote surface."""


class RemoteParseError(RemoteFetchError):
    """Raised when a parsed AEAT page cannot be coerced into a typed record."""


class RemoteNavigationError(RemoteFetchError):
    """Raised when post-auth navigation to a remote AEAT surface fails."""


__all__ = [
    "RemoteFetchError",
    "RemoteNavigationError",
    "RemoteParseError",
]
