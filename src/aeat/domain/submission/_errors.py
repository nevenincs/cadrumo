"""Submission-domain error hierarchy."""

from __future__ import annotations

from ...core.errors import AeatError


class SubmissionError(AeatError):
    """Base class for submission-domain failures."""


class SubmissionPreflightError(SubmissionError):
    """Raised when a draft cannot pass local submission preflight."""


__all__ = [
    "SubmissionError",
    "SubmissionPreflightError",
]
