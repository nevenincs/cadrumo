"""Canonical Decimal helpers for the AEAT domain.

Public surface
--------------

* :func:`format_decimal` — render a :class:`~decimal.Decimal` in fixed-point
  notation, with optional normalization and ``None`` handling.
"""

from __future__ import annotations

from ._format import format_decimal

__all__ = [
    "format_decimal",
]
