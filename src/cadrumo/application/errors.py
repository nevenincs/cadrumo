"""Typed application errors for diagnostics model construction.

This module currently owns the diagnostics-specific validation error raised by
:class:`application.diagnostics.DiagnosticCheck` validators while building
:class:`application.diagnostics.ConfigRepairReport` rows. The class
inherits from :class:`core.errors.CoreValidationError`, so it remains
catchable as ``ValueError`` for Pydantic validator compatibility while still
participating in the project-wide :class:`core.errors.CadrumoError` registry
and :class:`core.errors.ErrorEnvelope` rendering path.
"""

from __future__ import annotations

from ..core.errors.hierarchy import CoreValidationError


class DiagnosticModelError(CoreValidationError):
    """Raised when :class:`application.diagnostics.DiagnosticCheck` violates its invariants.

    ``DiagnosticCheck`` rows with status ``fail`` or ``warn`` must carry exactly
    one of ``next_action`` or ``dead_end``; ``ok`` rows must carry neither. The
    per-cause :class:`application.diagnostics.DiagnosticFinding` rows stay
    supplementary; they do not replace the required recovery channel. The
    validator raises this typed :class:`core.errors.CoreValidationError`
    instead of a bare :class:`ValueError` so Pydantic can wrap it as the cause
    of a validation failure while CLI and JSON callers can still render a
    registered :class:`core.errors.ErrorEnvelope` through
    :func:`core.errors.build_error_envelope`.
    """


__all__ = ["DiagnosticModelError"]
