"""Shared refusal rendering for ``aeat config google`` commands."""

from __future__ import annotations

from ....adapters.outbound.google.errors import GoogleAuthError
from ....adapters.outbound.storage import OutboundStorageError
from ....core.errors.error_codes import get_registered_error_code
from ..errors import CliRefusedBoundaryError


def _google_refusal(exc: GoogleAuthError | OutboundStorageError) -> CliRefusedBoundaryError:
    """Project a Google failure through the central error registry."""
    translated_message = getattr(exc, "translated_message", None)
    message_key = translated_message or get_registered_error_code(exc).message_key
    return CliRefusedBoundaryError(
        translated_message=message_key,
        context=getattr(exc, "context", None),
    )


__all__ = ["_google_refusal"]
