"""Application-level errors for the :mod:`aeat.application.filing` subpackage."""

from __future__ import annotations

from ...domain.filing import ModeloDraftError


class ModeloApplicationError(ModeloDraftError):
    """Base class for every error raised in the filing application layer."""


class ModeloCalculateError(ModeloApplicationError, ValueError):
    """Raised when summarizing or calculating a filing fails invariants."""
