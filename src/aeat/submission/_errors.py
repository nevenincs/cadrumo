"""Domain errors for the filing submission engine.

All errors inherit from :class:`aeat.errors.AeatError` so callers have
a single root they can catch at integration boundaries.
"""

from __future__ import annotations

from aeat.errors import AeatError
from aeat.i18n import Translatable


class SubmissionError(AeatError):
    """Base class for every error raised by :mod:`aeat.submission`.

    Attributes:
        translated_message: Optional :class:`aeat.i18n.Translatable`
            payload carrying a user-facing version of the message.
    """

    def __init__(self, message: str, *, translated_message: Translatable | None = None) -> None:
        """Construct a submission error.

        Args:
            message: English-authoritative error message (logged).
            translated_message: Optional trilingual payload surfaced
                to the CLI and any user-facing consumer.
        """
        super().__init__(message)
        self.translated_message: Translatable | None = translated_message


class SubmissionPreflightError(SubmissionError):
    """Raised when preflight gating rejects a draft before any browser work."""


class AeatLiveSubmitNotEnabledError(SubmissionPreflightError):
    """Raised when a live submit is requested without the live-submit env gate."""


class AeatPytestLiveWriteRefusedError(SubmissionPreflightError):
    """Raised when a live submit is attempted while running under pytest."""


class AeatLiveSubmitConfirmationRefusedError(SubmissionPreflightError):
    """Raised when the operator does not enter the required live confirmation."""


class SubmissionFormFillError(SubmissionError):
    """Raised when the submitter cannot fill a casilla-keyed input on the portal."""


class SubmissionRejectionError(SubmissionError):
    """Raised when AEAT rejects the filled form during the live submit leg."""
