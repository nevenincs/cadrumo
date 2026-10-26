"""Canonical AEAT box/form number."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

__all__ = ["AeatBoxNumber"]


AeatBoxNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16, pattern=r"^\d+$"),
]
"""AEAT's printed or displayed box number for one casilla position."""
