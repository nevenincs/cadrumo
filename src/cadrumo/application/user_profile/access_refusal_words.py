"""Locale keys for the words served with each profile access refusal.

Every refusal reason has its own plain sentence in the error catalogue, so an
operator never sees the raw reason token. The key is derived from the reason's
stable value, which keeps the mapping total over the closed vocabulary.
"""

from __future__ import annotations

from typing import Final

from cadrumo_client.contracts.access_refusals import AccessDenialCode

_KEY_PREFIX: Final = "errors.refused.profile_access_"


def access_refusal_message_key(reason: AccessDenialCode | str) -> str:
    """Return the locale key whose words explain ``reason``.

    A value outside the closed vocabulary reads as the generic operation refusal,
    so an unknown token is never shown to the operator.
    """
    try:
        known = AccessDenialCode(reason)
    except ValueError:
        known = AccessDenialCode.OPERATION_DENIED
    return f"{_KEY_PREFIX}{known.value}"


__all__ = ["access_refusal_message_key"]
