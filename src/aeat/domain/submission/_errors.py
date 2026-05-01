"""Domain errors for the filing submission engine.

All errors inherit from :class:`aeat.core.errors.AeatError` so callers
have a single root they can catch at integration boundaries.
"""

from __future__ import annotations

from ...core.errors import AeatError
from ...core.i18n import Translatable


class SubmissionError(AeatError):
    """Base class for every error raised by :mod:`aeat.domain.submission`.

    Attributes:
        translated_message: Optional :class:`aeat.core.i18n.Translatable`
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


class LiveSubmitForbiddenError(SubmissionPreflightError):
    """Raised when any caller attempts a permanently forbidden live AEAT write."""

    def __init__(
        self,
        message: str = (
            "live AEAT submission is permanently forbidden; use produce -> verify -> "
            "export and upload the file yourself in the AEAT portal"
        ),
        *,
        translated_message: Translatable | None = None,
    ) -> None:
        """Construct the permanent live-submit refusal error."""
        default_translatable: Translatable = {
            "es": (
                "El envío en vivo a AEAT está permanentemente prohibido. "
                "Usa produce -> verify -> export y sube el fichero tú mismo "
                "en el portal de AEAT."
            ),
            "en": (
                "Live AEAT submission is permanently forbidden. "
                "Use produce -> verify -> export and upload the file yourself "
                "in the AEAT portal."
            ),
            "hu": (
                "Az élő AEAT beküldés véglegesen tiltott. "
                "Használd a produce -> verify -> export folyamatot, és töltsd "
                "fel a fájlt te magad az AEAT portálon."
            ),
        }
        super().__init__(
            message,
            translated_message=translated_message or default_translatable,
        )
