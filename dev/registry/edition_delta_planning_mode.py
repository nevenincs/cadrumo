"""Classify authored edition ancestry for delta planning."""

from __future__ import annotations

from collections.abc import Mapping


def delta_authored(manifest: Mapping[str, object]) -> bool:
    """Whether a manifest introduces inherited members through a predecessor."""
    return isinstance(manifest.get("predecessor"), str)


def storage_authored(manifest: Mapping[str, object]) -> bool:
    """Whether casillas already name semantic or storage-only ancestry."""
    return delta_authored(manifest) or isinstance(manifest.get("casilla_storage_baseline"), str)
