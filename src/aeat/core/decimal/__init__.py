"""Canonical Decimal helpers for the AEAT domain.

Public surface
--------------

* :func:`format_decimal` — render a :class:`~decimal.Decimal` in fixed-point
  notation, with optional normalization and ``None`` handling.
* :func:`coerce_decimal` — parse any raw input to :class:`~decimal.Decimal`
  with a configurable fallback default.
"""

from __future__ import annotations

from ._coerce import coerce_decimal
from ._format import format_decimal

__all__ = [
    "coerce_decimal",
    "format_decimal",
]
