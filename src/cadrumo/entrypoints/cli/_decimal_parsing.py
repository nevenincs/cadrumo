"""Canonical decimal-amount validation at the CLI boundary.

One accepted grammar for every manual-entry numeric input: a dot decimal
separator, an optional one- or two-digit (euro-cent) fractional part, no
thousands grouping, no scientific notation, no ``NaN``/``Infinity``. The
two-digit fractional cap is what makes the Spanish thousands-grouping shape
``1.000`` (a dot followed by three digits) refuse rather than silently become
``1.0``. ``1234.56`` and a bare ``1000`` / ``0`` accept; ``1.000``,
``1.234,56``, ``1e3``, ``NaN``, ``Infinity`` all refuse.

The grammar itself lives in
:func:`~cadrumo.core.decimal.try_parse_canonical_decimal`, in ``core`` rather
than here, because the application-layer calculate-input boundary needs the
same shape and cannot import from ``entrypoints``. What stays here is the
thing that is genuinely CLI-owned: the localised, instructive refusal. One
grammar, one refusal per boundary.

See Also:
    :class:`~cadrumo.core.Period`
        The sibling operator-input boundary; both refuse in one place per axis.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.decimal._grammar import try_parse_canonical_decimal
from ...core.i18n._render import tr
from ._common import _bad

__all__ = ["optional_decimal_text", "parse_decimal_amount", "parse_optional_decimal_amount"]


# One accepted grammar for every manual-entry numeric input: a dot decimal
# separator, an optional one- or two-digit (euro-cent) fractional part, no
# thousands grouping, no scientific notation, no ``NaN``/``Infinity``. The
# two-digit fractional cap is what makes the Spanish thousands-grouping shape
# ``1.000`` (a dot followed by three digits) refuse rather than silently become
# ``1.0``. ``1234.56`` and a bare ``1000`` / ``0`` accept; ``1.000``,
# ``1.234,56``, ``1e3``, ``NaN``, ``Infinity`` all refuse.
#
# The grammar itself lives in
# :func:`~cadrumo.core.decimal.try_parse_canonical_decimal`, in ``core`` rather
# than here, because the application-layer calculate-input boundary needs the
# same shape and cannot import from ``entrypoints``. What stays here is the
# thing that is genuinely CLI-owned: the localised, instructive refusal. One
# grammar, one refusal per boundary.


def parse_decimal_amount(raw: str, *, label: str, signed: bool = True) -> Decimal:
    """Parse a required canonical-grammar decimal at the CLI boundary.

    Validates ``raw`` against the canonical decimal regex (dot separator, no
    thousands grouping, no scientific notation, no ``NaN``/``Infinity``) before
    constructing :class:`~decimal.Decimal`, then asserts :meth:`~decimal.Decimal.is_finite`
    as defence-in-depth. Refuses ``1.000``, ``1.234,56``, ``1e3``, ``NaN``,
    ``Infinity``, and ``-Infinity`` with the localised
    ``cli.ledger.errors.invalid_decimal`` refusal that names the field, echoes
    the raw value, and states the accepted form.

    Args:
        raw: The operator-supplied raw string.
        label: The field label echoed in the refusal message.
        signed: When ``True`` (default) a leading ``-`` is accepted; when
            ``False`` the non-negative variant is used and a negative input
            refuses.
    """
    parsed = try_parse_canonical_decimal(raw, signed=signed, max_fraction_digits=2)
    if parsed is None:
        raise _bad(tr("cli.ledger.errors.invalid_decimal", label=label, raw=raw))
    return parsed


def parse_optional_decimal_amount(raw: str | None, *, label: str, signed: bool = True) -> Decimal | None:
    """Parse an optional canonical-grammar decimal, or ``None`` when unset.

    Returns ``None`` when ``raw`` is ``None`` (the field was not supplied);
    otherwise delegates to
    :func:`parse_decimal_amount`, so the same
    canonical grammar and :meth:`~decimal.Decimal.is_finite` guard apply.
    """
    if raw is None:
        return None
    return parse_decimal_amount(raw, label=label, signed=signed)


def optional_decimal_text(value: Decimal | None) -> str | None:
    """Render an optional decimal without scientific notation."""
    if value is None:
        return None
    return format(value, "f")
