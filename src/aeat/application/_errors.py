"""Typed application errors for diagnostics model construction.

This module currently owns the diagnostics-specific validation error raised by
:class:`~aeat.application.diagnostics.DiagnosticCheck` validators. The class
inherits from :class:`~aeat.core.errors.CoreValidationError`, so it remains
catchable as ``ValueError`` for Pydantic validator compatibility while still
participating in the project-wide :class:`~aeat.core.errors.AeatError` registry
and :class:`~aeat.core.errors.ErrorEnvelope` rendering path.
"""

from __future__ import annotations

from ..core.errors import CoreValidationError


class DiagnosticModelError(CoreValidationError):
    """Raised when :class:`~aeat.application.diagnostics.DiagnosticCheck` violates its invariants.

    ``DiagnosticCheck`` rows with status ``fail`` or ``warn`` must carry exactly
    one of ``next_action`` or ``dead_end``; ``ok`` rows must carry neither. The
    validator raises this typed :class:`~aeat.core.errors.CoreValidationError`
    instead of a bare :class:`ValueError` so Pydantic can wrap it as the cause of
    a validation failure while CLI and JSON callers can still render a registered
    :class:`~aeat.core.errors.ErrorEnvelope` through
    :func:`~aeat.core.errors.build_error_envelope`.
    """


__all__ = ["DiagnosticModelError"]
