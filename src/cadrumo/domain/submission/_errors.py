"""Submission-domain error hierarchy."""

from __future__ import annotations

from ...core.errors import CadrumoError


class SubmissionError(CadrumoError):
    """Base class for submission-domain failures."""


class SubmissionPreflightError(SubmissionError):
    """Raised when a draft cannot pass local submission preflight."""


class SubmissionValidationError(SubmissionError, ValueError):
    """Raised when submission models violate state or shape invariants."""


__all__ = [
    "SubmissionError",
    "SubmissionPreflightError",
    "SubmissionValidationError",
]
