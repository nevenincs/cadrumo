"""Canonical :class:`~decimal.Decimal` coercion helpers for the AEAT domain.

Consolidates three independent ``_coerce_decimal`` copies that previously
lived in :mod:`_calc_sheets_pull`, :mod:`_row_set_assembly`, and
:mod:`invoices._models`. All call-sites use :func:`coerce_decimal`,
:func:`coerce_decimal_strict`, or :func:`normalize_decimal_separators` from this
module rather than open-coding decimal parsing.

Variant analysis
----------------

* ``_calc_sheets_pull`` — returned ``Decimal | None`` with no default.
  Callers checked for ``None`` explicitly to detect empty cells.
* ``_row_set_assembly`` — took a required ``default: Decimal`` keyword
  argument and always returned ``Decimal``.  Callers passed ``Decimal("0")``.
* ``invoices._models`` — raised ``TypeError`` on unparseable input (strict
  pydantic-validator context).

Canonical resolution
--------------------

:func:`coerce_decimal` uses ``coerce_decimal(value, *, default=None) -> Decimal | None``.

A single ``default`` keyword argument covers all three patterns:

* Pass ``default=None`` (or omit it) for the nullable-cell pattern —
  callers check the return value and skip or handle ``None`` themselves.
* Pass ``default=Decimal("0")`` for the aggregation pattern — guaranteed
  ``Decimal`` return, no ``None`` check needed.
* Raise on ``None`` for the strict-validator pattern: pass no default and
  raise :exc:`TypeError` when the return is ``None`` — the validator itself
  turns that into a :exc:`pydantic.ValidationError`.

The helper treats ``int`` inputs as valid (the ``_models.py`` variant did;
the other two would have produced ``Decimal(str(int))`` anyway), allowing
callers that pass mixed int / str / Decimal worksheet values to work
without pre-conversion.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import overload

from ..logging import get_logger

_logger = get_logger(__name__)


@overload
def coerce_decimal(value: object, *, default: Decimal) -> Decimal: ...
@overload
def coerce_decimal(value: object, *, default: None = None) -> Decimal | None: ...
def coerce_decimal(
    value: object,
    *,
    default: Decimal | None = None,
) -> Decimal | None:
    """Coerce *value* to a :class:`~decimal.Decimal`, falling back to *default*.

    Args:
        value: Raw input. Accepts :class:`~decimal.Decimal`, :class:`int`,
            :class:`float`, :class:`str`, or ``None``. Empty strings (``""``)
            are treated as absent.
        default: Value returned when *value* is ``None``, an empty string,
            or cannot be parsed. Defaults to ``None``.

    Returns:
        Parsed decimal, or *default* when coercion fails.

    Examples:
        >>> from decimal import Decimal
        >>> coerce_decimal("12.34")
        Decimal('12.34')
        >>> coerce_decimal(None) is None
        True
        >>> coerce_decimal(None, default=Decimal("0"))
        Decimal('0')
        >>> coerce_decimal("bad", default=Decimal("0"))
        Decimal('0')
        >>> coerce_decimal(42)
        Decimal('42')
    """
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        _logger.debug(
            "coerce_decimal: could not parse value, returning configured default",
            extra={
                "value_type": type(value).__name__,
                "default_is_none": default is None,
                "error_type": type(exc).__name__,
            },
        )
        return default


def coerce_decimal_strict(value: object) -> Decimal:
    """Coerce *value* to :class:`~decimal.Decimal`, raising on unparseable input.

    Unlike :func:`coerce_decimal` — which swallows the parse failure and returns a
    default — this variant lets the underlying :exc:`~decimal.InvalidOperation` (or
    :exc:`ValueError`) propagate, so callers that need to record *which* parse error
    occurred (e.g. a redaction-safe diagnostic that logs ``type(exc).__name__``) can
    catch it themselves. The caller is responsible for the empty/``None`` case.

    Args:
        value: Raw input. Accepts :class:`~decimal.Decimal`, :class:`int`,
            :class:`float`, or :class:`str`. Leading/trailing whitespace in a
            string is stripped by the :class:`~decimal.Decimal` constructor.

    Returns:
        The parsed decimal.

    Raises:
        decimal.InvalidOperation: When the string form is not a valid decimal.
        ValueError: When the value cannot be coerced to a decimal.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def normalize_decimal_separators(text: str, *, strip_thousands: bool) -> str:
    """Normalise a European-formatted numeric string to a dot-decimal form.

    Maps the decimal comma to a dot so the result is parsable by
    :class:`~decimal.Decimal`. When ``strip_thousands`` is ``True`` the
    thousands dot is removed first (Spanish ``"1.234,56"`` -> ``"1234.56"``);
    when ``False`` only the comma is converted (``"1234,56"`` -> ``"1234.56"``),
    for inputs already free of thousands separators.

    Single canonical home for the comma/dot separator normalisation that the
    sede, registry-export, renta-web-oracle, and PDF-label parsers previously
    open-coded inline. Each caller keeps its own surrounding validation,
    symbol-stripping, locale-detection, and error handling; only the separator
    transform is shared.
    """
    if strip_thousands:
        return text.replace(".", "").replace(",", ".")
    return text.replace(",", ".")
