"""Application-level domain errors for the diagnostics surface.

Used by :mod:`aeat.application.diagnostics` to signal contract violations
in :class:`~aeat.application.diagnostics.DiagnosticCheck`.
"""

from __future__ import annotations

from ..core.errors import CoreValidationError


class DiagnosticModelError(CoreValidationError):
    """Raised when a :class:`~aeat.application.diagnostics.DiagnosticCheck` violates its construction invariants.

    Replaces bare :exc:`ValueError` / :exc:`TypeError` raises inside
    Pydantic ``model_validator`` hooks so callers can catch a typed error
    without importing pydantic internals.  The error inherits from
    :class:`~aeat.core.errors.CoreValidationError` (which itself inherits
    from :exc:`ValueError`) so any existing ``except ValueError`` guard
    continues to match during the migration window.
    """


__all__ = ["DiagnosticModelError"]
