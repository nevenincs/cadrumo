"""Domain errors raised by the :mod:`aeat.adapters.inbound.sanitizer` subpackage.

All sanitiser errors inherit from
:class:`aeat.core.errors.AeatError` so callers can catch the family
without importing implementation details. The hierarchy mirrors the
failure surfaces the sanitiser pipeline can encounter — source-parse
failure, signature-present refusal, already-sanitised guard, and
unhandled PII surfaces.
"""

from __future__ import annotations

from ....core.errors import AeatError

_SANITIZER_SOURCE_LABEL = "<input-pdf>"


class SanitizationError(AeatError):
    """Base error for the :mod:`aeat.adapters.inbound.sanitizer` subpackage."""



class SanitizerValidationError(SanitizationError, ValueError):
    """Raised when synthetic parameters or field values fail domain validation.

    This error inherits from both :class:`SanitizationError` and
    :class:`ValueError`, ensuring compatibility with Pydantic's
    validator contract while remaining catchable under the package's
    unified error hierarchy.
    """



class SanitizerSourceParseError(SanitizationError):
    """Raised when the source PDF cannot be opened by :mod:`pikepdf`.

    The rendered message and structured context intentionally avoid
    source paths, provider payloads, and QPDF/pikepdf raw diagnostics.
    Callers that need to report the underlying parser failure should
    log only the exception type at the boundary that catches it.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        failure: str | None = None,
    ) -> None:
        """Construct a redacted source-parse error.

        Args:
            message: Legacy positional diagnostic text. Accepted for
                compatibility, but intentionally not rendered or copied
                into context because historical callers passed raw
                pikepdf/QPDF diagnostics here.
            failure: Optional underlying parser exception type name,
                safe for debug envelopes because it excludes operator
                paths and provider payload text.
        """
        context: dict[str, object] = {"source": _SANITIZER_SOURCE_LABEL}
        if failure is not None:
            context["failure"] = failure
        super().__init__(
            f"source PDF could not be opened for sanitization: {_SANITIZER_SOURCE_LABEL}",
            context=context,
            translated_message="errors.fail.fail_sanitization_source_parse",
        )
        self.failure: str | None = failure


class SignaturePresentError(SanitizationError):
    """Raised when the source PDF carries a digital signature.

    Modifying a signed PDF silently invalidates the signature; the
    sanitiser refuses such inputs and requires the operator to
    escalate to human review.
    """



class AlreadySanitizedError(SanitizationError):
    """Raised when the source SHA-256 is already in :data:`SANITIZED_SHAS`.

    Prevents accidental "re-sanitise an already-committed fixture".
    Callers can opt out via
    ``sanitize_pdf(..., refuse_if_already_sanitized=False)``.
    """

    def __init__(self, *, source_sha256: str) -> None:
        """Construct the error carrying the offending source hash as a typed attribute.

        Args:
            source_sha256: The SHA-256 of the source bytes that
                matched a known committed fixture.
        """
        super().__init__(
            "source PDF is already a committed sanitised fixture; pass refuse_if_already_sanitized=False to override",
            context={"source_sha256_prefix": source_sha256[:16]},
            translated_message="errors.refused.refused_sanitization_already_sanitized",
        )
        self.source_sha256: str = source_sha256


class UnknownSurfaceError(SanitizationError):
    """Raised when a PII surface is detected that the sanitiser does not handle.

    Used for threat-model surfaces this version of the sanitiser is
    not yet wired to scrub (e.g. a future modelo introduces an
    ``OCProperties`` shape we have not characterised). The default
    policy is *fail*; callers can downgrade to a warning by toggling
    the relevant ``drop_*`` flag off and accepting the resulting
    warning.
    """
