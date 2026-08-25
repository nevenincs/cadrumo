"""Application-level domain errors for the auth surface.

:class:`AuthDiagnosticPhoneStateError` and :class:`AuthDiagnosticPayloadError`
specialise :class:`core.errors.CoreValidationError` for auth diagnostic
validation failures.
"""

from __future__ import annotations

from ...core.errors import CoreValidationError


class AuthDiagnosticPhoneStateError(CoreValidationError):
    """Raised when an unrecognised phone-state value is supplied to the auth diagnostic recorder.

    Replaces the bare :exc:`ValueError` at the validation guard in
    :func:`application.auth.diagnostics.record_auth_diagnostic_phone_state`
    so callers can catch a typed, registry-bound error.  Inherits from
    :class:`core.errors.CoreValidationError` (which inherits from
    :exc:`ValueError`) so any existing ``except ValueError`` guard continues
    to match.
    """


class AuthDiagnosticPayloadError(CoreValidationError):
    """Raised when an encrypted auth diagnostic payload fails structural validation.

    Replaces the bare :exc:`ValueError` raises in
    :func:`application.auth.diagnostics._payload` (non-object JSON body)
    and :func:`application.auth.diagnostics._summary_from_payload`
    (missing ``captured_at`` field).  Inherits from
    :class:`core.errors.CoreValidationError` (which inherits from
    :exc:`ValueError`) so any existing ``except ValueError`` guard continues
    to match.
    """


__all__ = ["AuthDiagnosticPayloadError", "AuthDiagnosticPhoneStateError"]
