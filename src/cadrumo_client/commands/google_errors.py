"""Shared refusal rendering for ``aeat config google`` commands."""

from __future__ import annotations

from cadrumo.adapters.outbound.google.errors import GoogleAuthError
from cadrumo.adapters.outbound.storage.errors import OutboundStorageError
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .errors import CliRefusedBoundaryError


def google_refusal(exc: GoogleAuthError | OutboundStorageError | RegistryValidationError) -> CliRefusedBoundaryError:
    """Project a Google or worksheet-ingress failure through the central error registry."""
    translated_message = getattr(exc, "translated_message", None)
    message_key = translated_message or get_registered_error_code(exc).message_key
    return CliRefusedBoundaryError(
        translated_message=message_key,
        context=getattr(exc, "context", None),
    )


__all__ = ["google_refusal"]
