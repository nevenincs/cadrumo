"""Domain errors for the AEAT status reader (#43).

Every status-reader error inherits from :class:`aeat.errors.AeatError`
so consumers can catch the package-wide base class.
"""

from __future__ import annotations

from ..errors import AeatError


class StatusReaderError(AeatError):
    """Base class for all status-reader errors."""


class StatusAuthError(StatusReaderError):
    """Raised when cert preload or AEAT login navigation fails."""


class StatusParseError(StatusReaderError):
    """Raised when a parser cannot coerce raw HTML into a typed record."""


class StatusNotFoundError(StatusReaderError):
    """Raised when the requested status surface returns no rows."""
