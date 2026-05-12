"""Application-level errors for the :mod:`aeat.application.filing` subpackage."""

from __future__ import annotations

from ...domain.filing import FilingDraftError


class FilingApplicationError(FilingDraftError):
    """Base class for every error raised in the filing application layer."""


class FilingCalculateError(FilingApplicationError, ValueError):
    """Raised when summarizing or calculating a filing fails invariants."""
