"""Canonical cross-revision casilla-continuity identity."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

__all__ = ["ContinuidadId"]


ContinuidadId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
"""Stable cross-revision casilla-continuity identity."""
