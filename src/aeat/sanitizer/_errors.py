"""Domain errors raised by the :mod:`aeat.sanitizer` subpackage.

All sanitiser errors inherit from
:class:`aeat.errors.AeatError` so callers can catch the family
without importing implementation details. The hierarchy mirrors
the failure surfaces enumerated in the PDF-sanitiser ADR.
"""

from __future__ import annotations

from ..errors import AeatError


class SanitizationError(AeatError):
    """Base error for the :mod:`aeat.sanitizer` subpackage."""

    pass


class SanitizerSourceParseError(SanitizationError):
    """Raised when the source PDF cannot be opened by :mod:`pikepdf`.

    The original :class:`pikepdf.PdfError` (or whatever underlying
    cause QPDF surfaced) is chained as ``__cause__`` so the caller
    can inspect it via ``raise ... from``.
    """

    pass


class SignaturePresentError(SanitizationError):
    """Raised when the source PDF carries a digital signature.

    Modifying a signed PDF silently invalidates the signature; the
    sanitiser refuses such inputs and requires the operator to
    escalate to human review.
    """

    pass


class AlreadySanitizedError(SanitizationError):
    """Raised when the source SHA-256 is already in :data:`SANITIZED_SHAS`.

    Prevents accidental "re-sanitise an already-committed fixture".
    Callers can opt out via
    ``sanitize_pdf(..., refuse_if_already_sanitized=False)``.
    """

    def __init__(self, *, source_sha256: str) -> None:
        """Construct the error carrying the offending source hash.

        Args:
            source_sha256: The SHA-256 of the source bytes that
                matched a known committed fixture.
        """
        super().__init__(
            f"source PDF sha256={source_sha256!r} is already a committed sanitised fixture; "
            "pass refuse_if_already_sanitized=False to override"
        )
        self.source_sha256: str = source_sha256


class UnknownSurfaceError(SanitizationError):
    """Raised when a PII surface is detected that the sanitiser does not handle.

    Used for surfaces enumerated in the ADR's threat-model table
    that this version of the sanitiser is not yet wired to scrub
    (e.g. a future modelo introduces an `OCProperties` shape we
    have not characterised). The default policy is *fail*; callers
    can downgrade to a warning by toggling the relevant
    ``drop_*`` flag off and accepting the resulting warning.
    """

    pass
