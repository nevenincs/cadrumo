"""Canonical Decimal helpers for the AEAT domain.

Public surface
--------------

This namespace is inert; each symbol is imported from the module that defines
it.

``formatting``
  :func:`format_decimal` — render a :class:`~decimal.Decimal` in fixed-point
  notation, with optional normalization and ``None`` handling.

``coercion``
  :func:`coerce_decimal` — parse any raw input to :class:`~decimal.Decimal`
  with a configurable fallback default.
  :func:`coerce_decimal_strict` — same coercion but raises on unparseable
  input, for callers that must record the parse-failure type.
  :func:`normalize_decimal_separators` — convert comma-decimal text to the
  dot-decimal form accepted by :class:`~decimal.Decimal`.

``grammar``
  :func:`try_parse_canonical_decimal` — validate hand-typed text against the
  one canonical strict grammar, returning ``None`` rather than raising so each
  boundary supplies its own localised refusal.

``printed_money``
  :func:`is_aeat_printed_money` — the anchored shape check for AEAT's own
  printed-money rendering, consulted as a gate before a printed token is
  parsed.
  :data:`AEAT_THOUSANDS_SEPARATORS` — the code points AEAT prints between
  thousand groups, shared by that grammar and by the unanchored PDF capture
  group so the two cannot drift.

``fixed_width``
  :func:`coerce_fixed_width_decimal` — the strict, non-guessing coercion for
  fixed-width tax-return wire fields.

Two postures
------------

:func:`coerce_decimal` and :func:`normalize_decimal_separators` are *tolerant*:
they exist to admit messy machine-produced text (worksheet cells, bank exports,
AEAT PDF extraction). :func:`try_parse_canonical_decimal` is *strict*: it exists
to refuse anything outside one canonical form, because the text it validates was
typed by a human whose intent cannot be guessed. Pick by input provenance, not
by convenience.

:func:`is_aeat_printed_money` belongs to the strict side but answers a different
question: not "can a human have meant this" but "did AEAT print this". It
validates rather than parses, so it composes with either posture.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
