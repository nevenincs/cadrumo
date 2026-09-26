"""Operator-facing explanation of a settled operation refusal."""

from __future__ import annotations

from ....core.errors.error_codes import declared_error_codes_by_qualname
from ....core.i18n.render import tr


def public_refusal_explanation(code: str | None) -> str | None:
    """Return the registry's complete public explanation for a refusal code, when it declares one.

    A settled refusal persists only its registry code, never the exception's
    context, so only a code whose registered message is itself the public text
    can be explained; any other code stays a bare code.
    """
    if code is None:
        return None
    for error_code in declared_error_codes_by_qualname().values():
        if error_code.code == code and error_code.public_message_from_registry:
            return tr(error_code.message_key)
    return None


__all__ = ["public_refusal_explanation"]
