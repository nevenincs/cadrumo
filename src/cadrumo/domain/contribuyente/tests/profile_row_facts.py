"""Test support: address a repeating profile section's row as the fact paths a profile stores."""

from __future__ import annotations

from collections.abc import Mapping


def facts_for_row(section: str, clave: int, values: Mapping[str, str]) -> dict[str, str]:
    """Address a row's leaves as profile fact paths."""
    return {f"{section}.{clave}.{leaf}": value for leaf, value in values.items()}


__all__ = ["facts_for_row"]
