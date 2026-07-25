"""Canonical strict decimal *grammar* for operator-supplied numeric text.

This module owns the accepted *shape* of a hand-typed decimal amount; it does
not own any refusal surface. :func:`try_parse_canonical_decimal` returns
``None`` for text that does not conform, and each boundary wraps it with its own
typed, localised refusal — the CLI raises
:exc:`~typer.BadParameter` with the operator-facing catalogue message, the
calculate-input boundary raises its own typed application error. One grammar,
many error contracts.

Relationship to the sibling helpers
-----------------------------------

:mod:`._coerce` is the *tolerant* half of this package: :func:`coerce_decimal`
swallows a parse failure and returns a configured default, and
:func:`normalize_decimal_separators` transforms European separators for callers
that must accept machine-produced text (bank exports, AEAT PDF extraction).
Those exist to *admit* messy real-world input. This module is the opposite
posture: it exists to *refuse* anything outside one canonical form, because the
text it validates was typed by a human whose intent cannot be guessed.

Accepted grammar
----------------

An optional leading ``-`` (only when ``signed``), one or more digits, and an
optional dot-separated fractional part. There is no thousands grouping, no
comma decimal separator, no scientific notation, no leading ``+``, no embedded
whitespace, and no ``NaN``/``Infinity``. The regex runs *before*
:class:`~decimal.Decimal` construction so a caller's refusal message describes
the grammar rather than a constructor failure, and
:meth:`~decimal.Decimal.is_finite` is asserted afterwards as defence in depth.

Fractional-digit cap
--------------------

``max_fraction_digits`` is the one axis on which conforming callers legitimately
differ, so it is a parameter rather than a second grammar:

* Pass ``2`` for a hand-typed euro amount. The cap is what makes the
  Spanish thousands shape ``1.000`` refuse instead of silently becoming
  ``Decimal("1.0")`` — a one-euro transaction where the operator meant one
  thousand.
* Pass ``None`` for a calculation input channel. Sub-cent precision is
  legitimate there: the AEAT fixed-width encoder rounds a value such as
  ``Decimal("2.345")`` to cents with ``ROUND_HALF_UP`` per the AEAT
  Instrucciones, so refusing it at the input boundary would reject a value the
  export layer is built to accept.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_UNSIGNED_ANY_FRACTION = re.compile(r"^\d+(\.\d+)?$")
_SIGNED_ANY_FRACTION = re.compile(r"^-?\d+(\.\d+)?$")


def _pattern(*, signed: bool, max_fraction_digits: int | None) -> re.Pattern[str]:
    if max_fraction_digits is None:
        return _SIGNED_ANY_FRACTION if signed else _UNSIGNED_ANY_FRACTION
    sign = "-?" if signed else ""
    return re.compile(rf"^{sign}\d+(\.\d{{1,{max_fraction_digits}}})?$")


def try_parse_canonical_decimal(
    text: str,
    *,
    signed: bool = True,
    max_fraction_digits: int | None = None,
) -> Decimal | None:
    """Parse *text* as a canonical-grammar decimal, or ``None`` when it does not conform.

    Never raises: a non-conforming input returns ``None`` so the calling
    boundary can raise its own typed, localised refusal. Surrounding whitespace
    is stripped before validation; whitespace *inside* the number never
    conforms.

    Args:
        text: The raw operator-supplied string.
        signed: When ``True`` (the default) a leading ``-`` conforms; when
            ``False`` a negative input does not conform.
        max_fraction_digits: Maximum fractional digits accepted. ``None`` (the
            default) accepts any number of fractional digits; pass ``2`` for a
            hand-typed euro amount so the Spanish thousands shape ``1.000``
            refuses.

    Returns:
        The parsed decimal, or ``None`` when *text* does not conform.

    Examples:
        >>> try_parse_canonical_decimal("1234.56")
        Decimal('1234.56')
        >>> try_parse_canonical_decimal("-1000")
        Decimal('-1000')
        >>> try_parse_canonical_decimal("2.345")
        Decimal('2.345')
        >>> try_parse_canonical_decimal("1.000", max_fraction_digits=2) is None
        True
        >>> try_parse_canonical_decimal("1e3") is None
        True
        >>> try_parse_canonical_decimal("+100") is None
        True
        >>> try_parse_canonical_decimal("1.234,56") is None
        True
        >>> try_parse_canonical_decimal("NaN") is None
        True
        >>> try_parse_canonical_decimal("-1000", signed=False) is None
        True
    """
    stripped = text.strip()
    if _pattern(signed=signed, max_fraction_digits=max_fraction_digits).fullmatch(stripped) is None:
        return None
    try:
        parsed = Decimal(stripped)
    except InvalidOperation:
        # Unreachable for a regex-conforming string; kept so a pathological
        # input (e.g. a digit run beyond the decimal context's limits) still
        # produces the caller's refusal rather than escaping as a raw error.
        return None
    if not parsed.is_finite():
        return None
    return parsed
