"""Application-level domain errors for the auth surface.

:class:`AuthDiagnosticPhoneStateError` and :class:`AuthDiagnosticPayloadError`
specialise :class:`core.errors.hierarchy.CoreValidationError` for auth diagnostic
validation failures.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CoreValidationError


class AuthDiagnosticPhoneStateError(CoreValidationError):
    """Raised when an unrecognised phone-state value is supplied to the auth diagnostic recorder.

    Replaces the bare :exc:`ValueError` at the validation guard in
    :func:`application.auth.diagnostics.record_auth_diagnostic_phone_state`
    so callers can catch a typed, registry-bound error.  Inherits from
    :class:`core.errors.hierarchy.CoreValidationError`; protocol boundaries translate
    it to a builtin only where an external validator requires that contract.
    """


class AuthDiagnosticPayloadError(CoreValidationError):
    """Raised when an encrypted auth diagnostic payload fails structural validation.

    Replaces the bare :exc:`ValueError` raises in
    :func:`~entrypoints.cli._ledger_counterparty_cli._payload` (non-object JSON body)
    and :func:`application.auth.diagnostics._summary_from_payload`
    (missing ``captured_at`` field).  Inherits from
    :class:`core.errors.hierarchy.CoreValidationError`; callers catch the canonical
    registered type rather than relying on builtin ancestry.
    """


__all__ = ["AuthDiagnosticPayloadError", "AuthDiagnosticPhoneStateError"]
