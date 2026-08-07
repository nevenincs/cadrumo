"""Domain errors raised by the :mod:`dev.sanitizer` subpackage.

All sanitiser errors inherit from :class:`SanitizationError` so callers
can catch the family without importing implementation details. The
hierarchy mirrors the failure surfaces the sanitiser pipeline can
encounter — source-parse failure, signature-present refusal,
already-sanitised guard, and unhandled PII surfaces.

The root is a bare :class:`Exception` rather than
:class:`cadrumo.core.errors.CadrumoError`. That hierarchy binds every
subclass to the product's operator-facing error-code registry at class
creation and expects a locale-catalogue message key per code; this
package is fixture-preparation tooling with no operator-facing surface,
so it has no code to register and no string to translate. Re-parenting it
would put unshipped tooling into the shipped error contract.
"""

from __future__ import annotations

from collections.abc import Mapping

_SANITIZER_SOURCE_LABEL = "<input-pdf>"


class SanitizationError(Exception):
    """Base error for the :mod:`dev.sanitizer` subpackage."""

    def __init__(self, message: str | None = None, *, context: Mapping[str, object] | None = None) -> None:
        """Construct a sanitiser error with optional redacted structured context.

        Args:
            message: Human-readable diagnostic text, already redacted by the
                caller.
            context: Structured detail safe to render — never a source path,
                a cleartext identity value, or a full digest.
        """
        if message:
            super().__init__(message)
        else:
            super().__init__()
        self.context: dict[str, object] | None = dict(context) if context is not None else None


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
            message: Positional diagnostic text, intentionally not
                rendered or copied into context because callers may pass
                raw pikepdf/QPDF diagnostics here.
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
