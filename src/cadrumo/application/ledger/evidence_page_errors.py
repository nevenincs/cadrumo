"""Typed refusals of the stored-document page read.

Each refusal names one reason a page could not be shown, so every frontend can
say it in words without reading exception text. None carries the document's
bytes, its digest or where it came from.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError

__all__ = [
    "LedgerEvidencePageDigestMismatchError",
    "LedgerEvidencePageNotFoundError",
    "LedgerEvidencePageOutOfRangeError",
    "LedgerEvidencePageTooLargeError",
    "LedgerEvidencePageUnreadableError",
    "LedgerEvidencePageUnsupportedMediaError",
]


class LedgerEvidencePageNotFoundError(CadrumoError):
    """The named evidence record or attachment is not stored in the profile."""


class LedgerEvidencePageDigestMismatchError(CadrumoError):
    """The stored bytes do not hash to the digest their record names."""


class LedgerEvidencePageUnsupportedMediaError(CadrumoError):
    """The document is of a media type the page read cannot draw."""


class LedgerEvidencePageTooLargeError(CadrumoError):
    """The document, or the image drawn from it, is above the read's byte or pixel bound."""


class LedgerEvidencePageOutOfRangeError(CadrumoError):
    """The document has no page with the requested number."""


class LedgerEvidencePageUnreadableError(CadrumoError):
    """The bytes claim a supported media type but cannot be decoded as one."""
