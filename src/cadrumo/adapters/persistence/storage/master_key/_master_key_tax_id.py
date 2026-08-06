"""Tax-id classifier used by the unsecured master-key canary."""

from __future__ import annotations

from typing import Final

__all__ = ["looks_like_real_tax_id"]

_SYNTHETIC_TAX_IDS: Final[frozenset[str]] = frozenset(
    {
        "00000000T",
        "X0000000T",
        "Z0000000T",
        "Y0000000Z",
        "B00000000",
    },
)


def looks_like_real_tax_id(value: str) -> bool:
    """Return ``True`` when ``value`` parses as a real Spanish tax id."""
    from .....core.identity import IdentityError, validate_spanish_tax_id

    try:
        canonical = validate_spanish_tax_id(value)
    except (ValueError, IdentityError):
        return False
    return canonical not in _SYNTHETIC_TAX_IDS
