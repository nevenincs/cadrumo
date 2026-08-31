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
    # Ambiguity is refused BY CONSTRUCTION, not by caller discipline. This
    # module exported the predicate and the parser side by side and left it to
    # each caller to remember to consult one before the other; two callers
    # forgot, and one of them read an operator's 12.500 euros as twelve fifty
    # on a threshold field. A parser that can detect the ambiguity and answers
    # anyway is guessing at a thousandfold error.
    #
    # This is what ``max_fraction_digits=2`` was standing in for, badly: the cap
    # caught the Spanish shape only because a grouping is always three digits,
    # while also refusing 0.335, which is not ambiguous at all. With the check
    # here, that parameter goes back to meaning precision.
    if european_thousands_reading_is_ambiguous(stripped):
        return None
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


#: A dot followed by exactly three digits, with a lead group that could open a
#: Spanish thousands run: one to three digits and no leading zero. ``1.234`` and
#: ``100.000`` match; ``0.333`` does not (nobody writes a thousands run whose
#: first group is ``0``), and neither does ``1000.000`` (a lead group of four
#: digits would itself have been grouped).
_AMBIGUOUS_THOUSANDS_RE = re.compile(r"^[1-9][0-9]{0,2}\.[0-9]{3}$")


def european_thousands_reading_is_ambiguous(text: str) -> bool:
    """Return whether a dot in *text* could equally mean thousands or decimals.

    Spanish writes one thousand two hundred and thirty-four as ``1.234`` and
    English writes one point two three four the same way. When that is the
    whole token there is no evidence in it to choose by, and a parser that
    picks anyway is not parsing — it is guessing, at a thousandfold error, on
    a number headed for a tax return.

    The ambiguity is narrow and this predicate keeps it that way, returning
    ``False`` for every token that carries its own evidence:

    * A comma anywhere settles it. Spanish uses the comma as the decimal mark,
      so ``1.234,56`` and ``1234,56`` are unambiguous and stay readable.
    * One or two digits after the dot cannot be a thousands group, which is
      always exactly three — ``1234.56`` and ``0.5`` are plainly decimals.
    * Four or more cannot be one either: ``1.2345`` is a decimal, since a
      grouped number would have broken it as ``12.345``.
    * A lead group that could not open a thousands run settles it too. A
      leading zero (``0.333``, an ordinary coefficient) or a lead longer than
      three digits (``1000.000``) means the token was never grouped.

    So the caller refuses ``1.234``, ``10.500`` and ``100.000`` and accepts
    everything else it accepted before. Coefficients and percentages written
    ``0.333`` keep working, which matters where this is used on values whose
    kind is not yet known.

    Returns:
        ``True`` when the token is genuinely two-way readable and the caller
        must refuse rather than choose.
    """
    candidate = text.strip().lstrip("+-")
    if "," in candidate:
        return False
    return _AMBIGUOUS_THOUSANDS_RE.fullmatch(candidate) is not None


def is_non_negative_canonical_decimal(text: str) -> bool:
    """Whether *text* is a canonical decimal carrying no sign.

    The question a wire payload asks about a stringified money column. A record
    that bounds a Decimal field at ``ge=0`` loses that bound the moment it is
    projected to a string, and the projection has to re-assert it or the
    published schema promises less than the record guarantees.

    It is a predicate rather than a validator because the callers differ on what
    an EMPTY value means, and that difference is real: an export column spells an
    absent optional as ``""`` and must accept it, while a balance is always
    present and an empty one is malformed. Each raises its own refusal for the
    same reason -- what must not differ is the grammar they test against.

    Written out twice before this existed, once for the ledger export columns and
    once for the IVA wallet balances, with the second docstring noting it was the
    "same shape" as the first.
    """
    return try_parse_canonical_decimal(text, signed=False) is not None
