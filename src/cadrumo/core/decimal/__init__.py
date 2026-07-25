"""Canonical Decimal helpers for the AEAT domain.

Public surface
--------------

* :func:`format_decimal` — render a :class:`~decimal.Decimal` in fixed-point
  notation, with optional normalization and ``None`` handling.
* :func:`coerce_decimal` — parse any raw input to :class:`~decimal.Decimal`
  with a configurable fallback default.
* :func:`coerce_decimal_strict` — same coercion but raises on unparseable
  input, for callers that must record the parse-failure type.
* :func:`normalize_decimal_separators` — convert comma-decimal text to the
  dot-decimal form accepted by :class:`~decimal.Decimal`.
* :func:`try_parse_canonical_decimal` — validate hand-typed text against the
  one canonical strict grammar, returning ``None`` rather than raising so each
  boundary supplies its own localised refusal.

Two postures
------------

:func:`coerce_decimal` and :func:`normalize_decimal_separators` are *tolerant*:
they exist to admit messy machine-produced text (worksheet cells, bank exports,
AEAT PDF extraction). :func:`try_parse_canonical_decimal` is *strict*: it exists
to refuse anything outside one canonical form, because the text it validates was
typed by a human whose intent cannot be guessed. Pick by input provenance, not
by convenience.
"""

from __future__ import annotations

from ._coerce import coerce_decimal, coerce_decimal_strict, normalize_decimal_separators
from ._format import format_decimal
from ._grammar import try_parse_canonical_decimal

__all__ = [
    "coerce_decimal",
    "coerce_decimal_strict",
    "format_decimal",
    "normalize_decimal_separators",
    "try_parse_canonical_decimal",
]
