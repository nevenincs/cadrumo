"""Domain errors for the AEAT filing-history read surface (#168).

Every error inherits from :class:`aeat.errors.AeatError` so callers
have a single root to catch across the package.
"""

from __future__ import annotations

from ..errors import AeatError


class HistoryError(AeatError):
    """Base class for every error raised by :mod:`aeat.history`."""


class HistoryFetchError(HistoryError):
    """Raised when the filing-history fetcher cannot retrieve a page.

    Typical causes are transport failures, an authenticated session
    that did not land, or a detail page returning a non-2xx HTTP
    status. The underlying exception is chained via ``__cause__``.
    """


class HistoryParseError(HistoryError):
    """Raised when a per-modelo parser cannot interpret the HTML.

    The message carries a short human-readable description of the
    parser expectation that failed (missing table, malformed row,
    unparseable decimal, etc.). The originating pydantic
    :class:`pydantic.ValidationError` or regex failure is chained.
    """


class HistoryUnsupportedModeloError(HistoryError):
    """Raised for a modelo that has no registered parser in v1.

    v1 covers modelos 130, 303, and 390. Every other modelo raises
    this error rather than returning an empty payload so callers
    never silently miss data.
    """
