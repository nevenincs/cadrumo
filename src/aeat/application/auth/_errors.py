"""Application-level domain errors for the auth surface."""

from __future__ import annotations

from ...core.errors import CoreValidationError


class AuthDiagnosticPhoneStateError(CoreValidationError):
    """Raised when an unrecognised phone-state value is supplied to the auth diagnostic recorder.

    Replaces the bare :exc:`ValueError` at the validation guard in
    :func:`~aeat.application.auth._diagnostics.record_auth_diagnostic_phone_state`
    so callers can catch a typed, registry-bound error.  Inherits from
    :class:`~aeat.core.errors.CoreValidationError` (which inherits from
    :exc:`ValueError`) so any existing ``except ValueError`` guard continues
    to match.
    """


__all__ = ["AuthDiagnosticPhoneStateError"]
