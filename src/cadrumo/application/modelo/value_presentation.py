"""How a casilla value reads for a person, in each output language.

One home for the figure conventions every surface shares: the grouping and
decimal marks of each language, how a money amount, a ratio, a count, a year, a
date, a yes-or-no and a bank account are spelled, and the words that stand in
for a value that is not there. The calculation summary and the modelo editor
both format through here, so a figure never reads one way on screen and another
way in the PDF a filer keeps.

Formatting never rounds. A value keeps every fractional digit it carries; a
money amount with fewer than two places is padded to two, which adds no
precision it did not have. A number whose spelling this module cannot read is
shown exactly as stored rather than guessed at.

Absence is never a figure. :func:`format_casilla_value` has no arm for ``None``:
a caller that holds no value shows :data:`VALUE_ABSENT_LOCALE_KEY` in words,
so "nothing was entered" can never render as a zero.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...core.iban import normalise_iban
from ...core.models import STRICT_FROZEN_CONFIG
from .edit_value_grammar import ModeloEditRatioUnit

VALUE_TRUE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.value_true"
VALUE_FALSE_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.value_false"
VALUE_ABSENT_LOCALE_KEY: Final[str] = "application.modelo.calculation_summary.value_absent"

SCREEN_MINUS_SIGN: Final[str] = "\u2212"
"""The minus sign figures carry on screen, so a negative amount reads as one."""

_EURO_SUFFIX: Final[str] = "\u00a0\u20ac"
_PERCENT_SUFFIX: Final[str] = "\u00a0%"
_PERCENT_SHIFT: Final[Mapping[ModeloEditRatioUnit, int]] = MappingProxyType(
    {ModeloEditRatioUnit.PERCENT: 0, ModeloEditRatioUnit.FRACTION: 2}
)
"""How far a ratio's decimal point moves to read as a percentage, for each unit the registry lets be known."""
_IBAN_MASK: Final[str] = "\u00b7\u00b7\u00b7\u00b7"
_DECIMAL_TOKEN: Final[re.Pattern[str]] = re.compile(r"^(?P<sign>-?)(?P<integer>\d+)(?:\.(?P<fraction>\d+))?$")


class LocaleNumberFormat(BaseModel):
    """How one language writes a figure and a date."""

    model_config = STRICT_FROZEN_CONFIG

    group_separator: str = Field(min_length=1, max_length=1)
    decimal_separator: str = Field(min_length=1, max_length=1)
    date_pattern: str = Field(min_length=1)


LOCALE_NUMBER_FORMATS: Final[Mapping[OutputLanguage, LocaleNumberFormat]] = MappingProxyType(
    {
        OutputLanguage.ES: LocaleNumberFormat(group_separator=".", decimal_separator=",", date_pattern="%d/%m/%Y"),
        OutputLanguage.CA: LocaleNumberFormat(group_separator=".", decimal_separator=",", date_pattern="%d/%m/%Y"),
        OutputLanguage.EN: LocaleNumberFormat(group_separator=",", decimal_separator=".", date_pattern="%d/%m/%Y"),
        # Hungarian groups thousands with a space; a no-break space keeps a figure
        # on one line and extracts as a plain space.
        OutputLanguage.HU: LocaleNumberFormat(
            group_separator="\u00a0", decimal_separator=",", date_pattern="%Y. %m. %d."
        ),
    },
)
"""Figure and date formatting per output language; total over the language axis."""


class ValuePresentationKind(StrEnum):
    """How a casilla's declared data type reads, independent of language."""

    MONEY = "money"
    RATIO = "ratio"
    DECIMAL = "decimal"
    INTEGER = "integer"
    YEAR = "year"
    BOOLEAN = "boolean"
    DATE = "date"
    IBAN = "iban"
    CODE = "code"
    TEXT = "text"


_PRESENTATION_BY_DATA_TYPE: Final[Mapping[str, ValuePresentationKind]] = MappingProxyType(
    {
        "money": ValuePresentationKind.MONEY,
        "ratio": ValuePresentationKind.RATIO,
        "decimal": ValuePresentationKind.DECIMAL,
        "integer": ValuePresentationKind.INTEGER,
        "year": ValuePresentationKind.YEAR,
        "boolean": ValuePresentationKind.BOOLEAN,
        "date": ValuePresentationKind.DATE,
        "iban": ValuePresentationKind.IBAN,
        "nif": ValuePresentationKind.CODE,
        "nif_iva": ValuePresentationKind.CODE,
        "bic": ValuePresentationKind.CODE,
        "period_code": ValuePresentationKind.CODE,
        "country_code": ValuePresentationKind.CODE,
        "ccaa_code": ValuePresentationKind.CODE,
        "province_code": ValuePresentationKind.CODE,
        "postal_code": ValuePresentationKind.CODE,
        "municipality_code": ValuePresentationKind.CODE,
        "text": ValuePresentationKind.TEXT,
        "name": ValuePresentationKind.TEXT,
    },
)
"""The presentation of each registry data type; total over ``CasillaDataType``."""


class UnknownValuePresentationError(InternalInvariantError):
    """A data type has no declared presentation, so no figure is guessed for it."""


def value_presentation_kind(data_type: str) -> ValuePresentationKind:
    """Return how values of one registry data type read, refusing an undeclared type."""
    try:
        return _PRESENTATION_BY_DATA_TYPE[data_type]
    except KeyError:
        raise UnknownValuePresentationError(f"no presentation is declared for data type {data_type!r}") from None


def group_decimal_text(text: str, language: OutputLanguage, *, minus: str = "-") -> str | None:
    """Return a canonical decimal spelling with the language's marks, or ``None``.

    ``text`` is the canonical spelling a revision or report stores: an optional
    ``-``, digits, and an optional ``.`` fraction. Anything else is not a figure
    this function reads, and ``None`` says so instead of guessing.
    """
    match = _DECIMAL_TOKEN.match(text)
    if match is None:
        return None
    number_format = LOCALE_NUMBER_FORMATS[language]
    digits = match["integer"]
    groups: list[str] = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    groups.insert(0, digits)
    grouped = (minus if match["sign"] else "") + number_format.group_separator.join(groups)
    fraction = match["fraction"]
    return grouped if fraction is None else f"{grouped}{number_format.decimal_separator}{fraction}"


def _decimal_text(value: Decimal | int, *, minimum_places: int = 0) -> str:
    """Spell a finite number canonically, padding its fraction to ``minimum_places``."""
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError("a casilla figure must be finite")
    sign, _digits, exponent = number.as_tuple()
    if not isinstance(exponent, int):
        raise ValueError("a casilla figure must be finite")
    places = max(-exponent, minimum_places)
    text = f"{abs(number):.{places}f}"
    return f"-{text}" if sign and number != 0 else text


class ValuePresentationCatalogueError(InternalInvariantError):
    """The catalogue carries no words for a value state the screen must show."""


def _catalogue_text(translation_key: str, language: OutputLanguage) -> str:
    """Return one catalogue string, refusing a gap rather than showing its key."""
    text = lookup_translation(translation_key, locale=language.value)
    if text is None:
        raise ValuePresentationCatalogueError(f"{translation_key} has no {language.value} text")
    return text


def _yes_no(value: bool, language: OutputLanguage) -> str:
    return _catalogue_text(VALUE_TRUE_LOCALE_KEY if value else VALUE_FALSE_LOCALE_KEY, language)


def _masked_iban(value: str) -> str:
    canonical = normalise_iban(value)
    if len(canonical) <= 8:
        return canonical
    return f"{canonical[:4]} {_IBAN_MASK} {canonical[-4:]}"


def _format_declared_ratio(
    value: Decimal | int | str | bool | date,
    kind: ValuePresentationKind,
    ratio_unit: ModeloEditRatioUnit | None,
    language: OutputLanguage,
) -> str | None:
    shift = None if ratio_unit is None else _PERCENT_SHIFT.get(ratio_unit)
    if kind is ValuePresentationKind.RATIO and shift is not None:
        return _format_percentage(value, shift=shift, language=language)
    return None


def _format_quantity_or_identity(
    value: Decimal | int | str | bool | date,
    kind: ValuePresentationKind,
    language: OutputLanguage,
    mask_iban: bool,
) -> str:
    if kind in {ValuePresentationKind.MONEY, ValuePresentationKind.RATIO, ValuePresentationKind.DECIMAL}:
        return _format_quantity(value, kind=kind, language=language)
    if kind is ValuePresentationKind.INTEGER and isinstance(value, (int, Decimal)):
        return group_decimal_text(_decimal_text(value), language, minus=SCREEN_MINUS_SIGN) or str(value)
    if kind is ValuePresentationKind.IBAN and isinstance(value, str) and mask_iban:
        return _masked_iban(value)
    return str(value)


def format_casilla_value(
    value: Decimal | int | str | bool | date,
    *,
    data_type: str,
    language: OutputLanguage,
    mask_iban: bool = True,
    ratio_unit: ModeloEditRatioUnit | None = None,
) -> str:
    """Format one present casilla value for a person reading ``language``.

    Money carries two places at least and a euro sign; a ratio whose
    ``ratio_unit`` is known reads as a percentage, a fraction shifted by exactly
    two places, and one whose unit is not declared keeps its bare figure rather
    than guess a hundredfold; a decimal or count keeps its own places and takes
    the language's marks; a year stays four plain digits; a yes-or-no is a
    word; a date follows the language's order; a bank account is masked to its
    first and last four characters unless ``mask_iban`` is false. Codes and
    text are shown as stored.
    """
    kind = value_presentation_kind(data_type)
    if isinstance(value, bool):
        return _yes_no(value, language)
    if isinstance(value, date):
        return value.strftime(LOCALE_NUMBER_FORMATS[language].date_pattern)
    if kind is ValuePresentationKind.BOOLEAN and isinstance(value, (int, Decimal)) and value in (0, 1):
        return _yes_no(bool(value), language)
    percentage = _format_declared_ratio(value, kind, ratio_unit, language)
    if percentage is not None:
        return percentage
    return _format_quantity_or_identity(value, kind, language, mask_iban)


def _format_quantity(value: object, *, kind: ValuePresentationKind, language: OutputLanguage) -> str:
    """Format a money, ratio or decimal quantity, or show an unreadable spelling as stored."""
    if isinstance(value, (Decimal, int)):
        text = _decimal_text(value, minimum_places=2 if kind is ValuePresentationKind.MONEY else 0)
    else:
        text = str(value).strip()
        if kind is ValuePresentationKind.MONEY:
            match = _DECIMAL_TOKEN.match(text)
            if match is not None and len(match["fraction"] or "") < 2:
                text = _decimal_text(Decimal(text), minimum_places=2)
    grouped = group_decimal_text(text, language, minus=SCREEN_MINUS_SIGN)
    if grouped is None:
        return text
    return f"{grouped}{_EURO_SUFFIX}" if kind is ValuePresentationKind.MONEY else grouped


def _format_percentage(value: object, *, shift: int, language: OutputLanguage) -> str | None:
    """Format a ratio as a percentage, moving the decimal point ``shift`` places; ``None`` when unreadable.

    Moving the point is exact, so a stored fraction reads as its percentage
    with every digit it carried and nothing rounded.
    """
    if isinstance(value, (Decimal, int)):
        number = Decimal(value)
    else:
        text = str(value).strip()
        if _DECIMAL_TOKEN.match(text) is None:
            return None
        number = Decimal(text)
    grouped = group_decimal_text(_decimal_text(number.scaleb(shift)), language, minus=SCREEN_MINUS_SIGN)
    return None if grouped is None else f"{grouped}{_PERCENT_SUFFIX}"


def absent_value_text(language: OutputLanguage) -> str:
    """Return the words that stand in for a value nobody supplied."""
    return _catalogue_text(VALUE_ABSENT_LOCALE_KEY, language)


__all__ = [
    "LOCALE_NUMBER_FORMATS",
    "SCREEN_MINUS_SIGN",
    "VALUE_ABSENT_LOCALE_KEY",
    "VALUE_FALSE_LOCALE_KEY",
    "VALUE_TRUE_LOCALE_KEY",
    "LocaleNumberFormat",
    "UnknownValuePresentationError",
    "ValuePresentationCatalogueError",
    "ValuePresentationKind",
    "absent_value_text",
    "format_casilla_value",
    "group_decimal_text",
    "value_presentation_kind",
]
