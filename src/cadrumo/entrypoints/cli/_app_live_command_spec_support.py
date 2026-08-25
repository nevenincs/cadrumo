"""Shared translation-key constructor for live CommandSpec declarations."""

from __future__ import annotations

from ._command_spec import TranslationKey


def _key(value: str) -> TranslationKey:
    return TranslationKey(value)


__all__ = ["_key"]
