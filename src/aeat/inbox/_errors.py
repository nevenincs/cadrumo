"""Domain errors for the AEAT notifications inbox.

Every error inherits from :class:`aeat.errors.AeatError` so integration
boundaries have a single root they can catch.
"""

from __future__ import annotations

from aeat.errors import AeatError
from aeat.i18n import Translatable


class InboxError(AeatError):
    """Base class for every error raised by :mod:`aeat.inbox`.

    Attributes:
        translated_message: Optional :class:`aeat.i18n.Translatable`
            payload carrying a user-facing version of the message.
    """

    def __init__(self, message: str, *, translated_message: Translatable | None = None) -> None:
        """Construct an inbox error.

        Args:
            message: English-authoritative error message (logged).
            translated_message: Optional trilingual payload surfaced to
                the CLI and other user-facing consumers.
        """
        super().__init__(message)
        self.translated_message: Translatable | None = translated_message


class InboxFetchError(InboxError):
    """Raised when a notification source fails to deliver a payload."""


class InboxAcknowledgeError(InboxError):
    """Raised when :meth:`InboxFetcher.acknowledge` cannot apply the change."""
