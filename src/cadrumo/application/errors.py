"""Typed application errors for diagnostics model construction.

This module currently owns the diagnostics-specific validation error raised by
:class:`application.diagnostic_models.DiagnosticCheck` validators while building
:class:`application.diagnostic_models.ConfigRepairReport` rows. The class
inherits from :class:`core.errors.hierarchy.CoreValidationError`, so it remains
catchable as ``ValueError`` for Pydantic validator compatibility while still
participating in the project-wide :class:`core.errors.hierarchy.CadrumoError` registry
and :class:`core.errors.error_codes.ErrorEnvelope` rendering path.
"""

from __future__ import annotations

from ..core.errors.hierarchy import CoreValidationError


class DiagnosticModelError(CoreValidationError):
    """Raised when :class:`application.diagnostic_models.DiagnosticCheck` violates its invariants.

    ``DiagnosticCheck`` rows with status ``fail`` or ``warn`` must carry exactly
    one of ``next_action`` or ``dead_end``; ``ok`` rows must carry neither. The
    per-cause :class:`application.diagnostic_models.DiagnosticFinding` rows stay
    supplementary; they do not replace the required recovery channel. The
    validator raises this typed :class:`core.errors.hierarchy.CoreValidationError`
    instead of a bare :class:`ValueError` so Pydantic can wrap it as the cause
    of a validation failure while CLI and JSON callers can still render a
    registered :class:`core.errors.error_codes.ErrorEnvelope` through
    :func:`core.errors.error_codes.build_error_envelope`.
    """


__all__ = ["DiagnosticModelError"]
