"""Coerce a caller-supplied value into a token a governed vocabulary declares."""

from __future__ import annotations

from .....core.registry_token import RegistryToken
from ..errors import RegistryValidationError


def require_declared_registry_token[T: RegistryToken](
    value: object,
    *,
    token_type: type[T],
    declared: frozenset[T],
    subject: str,
    fact_id: str,
) -> T:
    """Return ``value`` as a ``token_type`` only when the governing fact declares it.

    An already projected token is accepted as is; text is stripped and projected
    through ``token_type.from_registry``. Anything else, an empty or unprojectable
    text, and a token missing from ``declared`` are refused under ``subject``.

    Raises:
        RegistryValidationError: When ``value`` is not a non-empty token text or
            projected token, or is not declared by ``fact_id``.
    """
    if isinstance(value, token_type):
        token = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise RegistryValidationError(f"{subject} token must be non-empty")
        try:
            token = token_type.from_registry(raw)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(f"{subject} token must be a non-empty string") from exc
    else:
        raise RegistryValidationError(f"{subject} token must be a string token")
    if token not in declared:
        raise RegistryValidationError(f"{subject} token {str(token)!r} is not declared by fact {fact_id!r}")
    return token
