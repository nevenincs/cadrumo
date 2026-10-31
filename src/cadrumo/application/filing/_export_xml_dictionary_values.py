"""Render signed XML dictionary scalar values in their declared wire types."""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from ...core.decimal.coercion import coerce_decimal
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...domain.calculations.registry.export_xml_dictionary import SINO_DICTIONARY_TYPE, XML_DICTIONARY_BOOLEAN_TYPES
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.filing.errors import FilingExportValidationError

# The registry owns the two boolean wire types. A new dictionary type does not
# accept booleans until it is explicitly declared there.
# The date row type, and the exact form AEAT accepts in it. The pattern is
# copied from the ``tipo_Fecha`` facet the bundled XSD declares -- an
# ``xs:string`` restricted to ``([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})`` -- so day and
# month may be one or two digits and the year must be four. That is exactly what
# rendering a :class:`~datetime.date` below produces, which is why a value that
# arrives already typed never meets this check.
_DATE_DICTIONARY_TYPE = "FEC"
_DATE_DICTIONARY_TEXT = re.compile(r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}")

_HOLDER_DICTIONARY_TYPE = "TIT"
_HOLDER_CODES_FACT = "modelo-100-profile-form-codes"

# The dictionary's numeric type codes are self-describing: ``P<width><scale>``
# and ``N<width><scale>`` name the field's integer width and its fractional-digit
# count, so the trailing digit is the scale to render at. Confirmed against every
# code the Modelo 100 dictionary uses across all six revisions by reading the
# ``fractionDigits`` facet of the XSD type each code lands on: ``P010``/``P020``/
# ``P030``/``P040`` resolve to ``xs:integer`` types carrying no fractional digits,
# while ``P012``/``P032``/``P072``/``P102``/``N102`` resolve to ``xs:decimal``
# types declaring ``fractionDigits="2"``. Reading the scale off the code keeps a
# future code correct without this module being edited.
_NUMERIC_DICTIONARY_TYPE = re.compile(r"^[NP]\d{2}(?P<scale>\d)$")


def is_xml_dictionary_numeric_type(data_type: str) -> bool:
    """Recognize the numeric wire types whose declared suffix carries their scale."""
    return _NUMERIC_DICTIONARY_TYPE.match(data_type.upper()) is not None


def format_xml_dictionary_value(data_type: str, value: object) -> str:
    """Render one value in the form the dictionary row's declared type accepts.

    The row's ``data_type`` decides the rendering, not the Python type of the
    value. Deciding from the value alone cannot distinguish rows that happen to
    carry the same Python type but are declared differently by AEAT: every
    boolean rendered as ``"S"``/``"N"`` regardless of whether the row was
    ``tipo_logico`` (which accepts only ``0``/``1``) or ``tipo_SINO_Exclusivo``
    (only ``SI``/``NO``), and every numeric row was rendered with two decimals
    even where the row is an ``xs:integer``.

    Args:
        data_type: The dictionary row's declared type code.
        value: The scalar to render.

    Returns:
        The rendered text for the XML element or attribute.
    """
    normalized_type = data_type.upper()
    if isinstance(value, bool):
        return _format_xml_dictionary_boolean_value(data_type, normalized_type, value)
    if isinstance(value, date):
        return f"{value.day}/{value.month}/{value.year}"
    numeric = _NUMERIC_DICTIONARY_TYPE.match(normalized_type)
    if numeric is not None:
        return _format_xml_dictionary_numeric_value(data_type, value, numeric)
    if normalized_type == _HOLDER_DICTIONARY_TYPE:
        holder = str(value).strip().casefold()
        holder_codes = resolve_form_codes(_HOLDER_CODES_FACT).under("holder")
        if holder in holder_codes.values():
            return holder
        try:
            return holder_codes[holder]
        except KeyError as exc:
            raise FilingExportValidationError(
                f"holder for a {data_type} row must be one of {', '.join(holder_codes)}, got {value!r}"
            ) from exc
    return _format_xml_dictionary_text_value(data_type, normalized_type, value)


def _format_xml_dictionary_boolean_value(data_type: str, normalized_type: str, value: bool) -> str:
    """Render a boolean only for the two dictionary types AEAT declares boolean."""
    # A boolean renders on exactly the two rows AEAT declares boolean, and is a
    # type error anywhere else. Stated this way round on purpose: asking what the
    # row IS keeps the declared type in charge, which is the rule this whole
    # function exists to enforce, while asking what it is NOT inverts the
    # dependency and leaves every unlisted row inheriting the last branch by
    # accident.
    #
    # The damage that makes this worth refusing rather than rendering is clearest
    # on an amount row: ``True`` on a euro-cent row reads as one euro, the XSD
    # accepts it, nothing on the export path validates anyway, and a taxpayer
    # files a figure they never stated. Same decision the unreadable-amount
    # branch below makes, for the same reason -- a wrong number that satisfies
    # every downstream check is worse than a refusal, because the refusal is the
    # only place the error is still visible.
    #
    # No route delivers a boolean here today: the casilla input door refuses one
    # for every declared family, and no Modelo 100 revision declares a boolean
    # casilla on a non-boolean row. This guards a route added later, so it stays
    # total and cheap rather than trying to interpret the value.
    if normalized_type not in XML_DICTIONARY_BOOLEAN_TYPES:
        raise FilingExportValidationError(
            f"a {data_type} row cannot carry the boolean {value!r}. Only "
            f"{'/'.join(sorted(XML_DICTIONARY_BOOLEAN_TYPES))} rows are declared boolean by AEAT. "
            "The value reaching this row has the wrong type; correct it at the source rather "
            "than rendering it, because a boolean written to an amount row is filed as 1 or 0.",
        )
    if normalized_type == SINO_DICTIONARY_TYPE:
        return "SI" if value else "NO"
    return "1" if value else "0"


def _format_xml_dictionary_numeric_value(data_type: str, value: object, numeric: re.Match[str]) -> str:
    """Parse and quantize one dictionary numeric value at its declared scale."""
    scale = int(numeric["scale"])
    # A text amount is read through the canonical grammar, which refuses on two
    # independent grounds and they are easy to confuse.
    #
    # The CAP is precision: at most ``scale`` fractional digits, never below two.
    # Capping an integer row at its own scale of zero would refuse ``1.6``,
    # unambiguous input this renderer has always rounded.
    #
    # The AMBIGUITY guard is separate and the row's scale does not relax it.
    # ``european_thousands_reading_is_ambiguous`` refuses a token that could
    # equally be read as a Spanish thousands group -- a lead of one to three
    # digits with no leading zero, then exactly three fractional digits. The
    # scale disambiguates the FIELD, never the STRING: an operator writing one
    # thousand types the same characters whatever the row declares, so ``1.000``
    # refuses on a three-decimal row exactly as it does on a euro-cent one. Tokens
    # carrying their own evidence still parse at any scale -- ``0.239`` (a lead
    # of zero was never grouped) and ``1234.239`` (a four-digit lead would itself
    # have been grouped).
    #
    # A value that already arrives typed carries no such ambiguity and skips the
    # text grammar entirely.
    amount = (
        try_parse_canonical_decimal(value, max_fraction_digits=max(scale, 2))
        if isinstance(value, str)
        else coerce_decimal(value)
    )
    if amount is None:
        raise FilingExportValidationError(
            f"amount for a {data_type} row could not be read: {value!r}. "
            f"The accepted form is a dot decimal separator with at most {scale} "
            "fractional digit(s) and no thousands grouping, e.g. 1234.56. A value "
            "is also refused when its shape cannot be told from a Spanish thousands "
            "group -- a lead of one to three digits with no leading zero, then "
            "exactly three more, as in 1.000 or 100.000 -- because that text reads "
            "as both one and one thousand and no parser can choose. This row's "
            "declared scale does not settle it: the scale says what the field can "
            "hold, not which reading was meant. Write the amount unambiguously "
            "(1000 or 1.0) at the source.",
        )
    return f"{amount.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)}"


def _format_xml_dictionary_text_value(data_type: str, normalized_type: str, value: object) -> str:
    """Pass through text values, validating the XML dictionary date shape."""
    text = str(value).strip()
    if normalized_type == _DATE_DICTIONARY_TYPE and not _DATE_DICTIONARY_TEXT.fullmatch(text):
        # A date row reached by text rather than by a ``date``. The typed value
        # is rendered above and never arrives here, so this is the case where
        # something upstream held a date as a string -- and an ISO one renders
        # verbatim, which AEAT's own ``tipo_Fecha`` pattern rejects.
        #
        # Checked rather than parsed, deliberately. Reading ``03/04/2024`` would
        # mean choosing between day-month and month-day, and this renderer has no
        # basis for that choice; the numeric branch above refuses an ambiguous
        # amount for the same reason. Text already in AEAT's form passes through
        # untouched, so the check costs a correct caller nothing.
        raise FilingExportValidationError(
            f"date for a {data_type} row is not in the form AEAT accepts: {value!r}. "
            "The accepted form is d/m/yyyy with a four-digit year, e.g. 2/1/1980. "
            "Supply the value as a date rather than as text and it is rendered "
            "correctly without this check.",
        )
    return text
