"""Canonical Decimal helpers for the AEAT domain.

Public surface
--------------

* :func:`format_decimal` — render a :class:`~decimal.Decimal` in fixed-point
  notation, with optional normalization and ``None`` handling.
* :func:`coerce_decimal` — parse any raw input to :class:`~decimal.Decimal`
  with a configurable fallback default.
* :func:`coerce_decimal_strict` — same coercion but raises on unparseable
  input, for callers that must record the parse-failure type.
"""

from __future__ import annotations

from ._coerce import coerce_decimal, coerce_decimal_strict, normalize_decimal_separators
from ._format import format_decimal

__all__ = [
    "coerce_decimal",
    "coerce_decimal_strict",
    "format_decimal",
    "normalize_decimal_separators",
]
