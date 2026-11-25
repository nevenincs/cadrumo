"""Persisted boolean tokens for calculation binding overrides."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

PERSISTED_BOOLEAN_BINDING_TOKENS: Final[Mapping[bool, str]] = MappingProxyType({True: "true", False: "false"})
"""How a boolean-channel binding's value is written into ``binding_overrides``.

The overrides mapping carries every binding channel as text: decimals as
canonical decimal strings, enums as their member, dates in ISO form, and a
boolean as one of these two tokens. A reader that expects a quantity must
recognise a truth token rather than refuse it as corrupt storage."""


def persisted_boolean_binding_value(raw: str) -> bool | None:
    """Read a persisted truth token back, or return ``None`` when ``raw`` is none."""
    for value, token in PERSISTED_BOOLEAN_BINDING_TOKENS.items():
        if raw == token:
            return value
    return None


__all__ = ["PERSISTED_BOOLEAN_BINDING_TOKENS", "persisted_boolean_binding_value"]
