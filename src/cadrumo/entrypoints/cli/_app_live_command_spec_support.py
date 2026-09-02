"""Shared translation-key constructor for live CommandSpec declarations."""

from __future__ import annotations

__all__ = ["_key"]


def _key(value: str) -> TranslationKey:
    """TEMPORARY A/B copy."""
    return TranslationKey(value)
