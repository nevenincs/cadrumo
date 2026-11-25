"""Casilla values read the way each language writes figures, never rounded, never guessed.

Expectations are written by hand in each language's convention rather than
derived from the formatter, so a regression that drops a grouping mark, pads a
ratio, rounds a fraction or turns a missing value into a zero cannot pass by
agreeing with itself.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from babel.dates import format_date

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..calculation_summary_presentation import VALUE_NOT_APPLICABLE_LOCALE_KEY
from ..edit_value_grammar import ModeloEditRatioUnit
from ..value_presentation import (
    LOCALE_NUMBER_FORMATS,
    UnknownValuePresentationError,
    ValuePresentationKind,
    absent_value_text,
    format_casilla_value,
    value_presentation_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_NBSP = "\u00a0"
_MINUS = "\u2212"
_EURO = f"{_NBSP}\u20ac"
_PERCENT = f"{_NBSP}%"


def test_every_registry_data_type_and_language_has_a_presentation() -> None:
    for data_type in CasillaDataType:
        assert isinstance(value_presentation_kind(data_type.value), ValuePresentationKind)
    assert set(LOCALE_NUMBER_FORMATS) == set(OutputLanguage)


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        (OutputLanguage.ES, (f"12.345,67{_EURO}", f"0,00{_EURO}", f"{_MINUS}2.750,40{_EURO}", f"1.000,50{_EURO}")),
        (OutputLanguage.CA, (f"12.345,67{_EURO}", f"0,00{_EURO}", f"{_MINUS}2.750,40{_EURO}", f"1.000,50{_EURO}")),
        (OutputLanguage.EN, (f"12,345.67{_EURO}", f"0.00{_EURO}", f"{_MINUS}2,750.40{_EURO}", f"1,000.50{_EURO}")),
        (
            OutputLanguage.HU,
            (
                f"12{_NBSP}345,67{_EURO}",
                f"0,00{_EURO}",
                f"{_MINUS}2{_NBSP}750,40{_EURO}",
                f"1{_NBSP}000,50{_EURO}",
            ),
        ),
    ),
)
def test_money_reads_in_the_language_convention_with_two_places(
    language: OutputLanguage, expected: tuple[str, ...]
) -> None:
    values = (Decimal("12345.67"), Decimal(0), Decimal("-2750.40"), "1000.5")

    rendered = tuple(format_casilla_value(value, data_type="money", language=language) for value in values)

    assert rendered == expected


# What the window's `Intl.NumberFormat(locale, {minimumFractionDigits: 2, maximumFractionDigits: 2,
# useGrouping: "always"})` writes for 999.00, 1234.56, 12345.67 and 1234567.89, produced once by Node 26 (ICU 78, CLDR 48)
# and held as literals so this table does not agree with the formatter by construction.
_INTL_FIGURES = (
    (OutputLanguage.EN, ("999.00", "1,234.56", "12,345.67", "1,234,567.89")),
    (OutputLanguage.ES, ("999,00", "1.234,56", "12.345,67", "1.234.567,89")),
    (OutputLanguage.CA, ("999,00", "1.234,56", "12.345,67", "1.234.567,89")),
    (OutputLanguage.HU, ("999,00", f"1{_NBSP}234,56", f"12{_NBSP}345,67", f"1{_NBSP}234{_NBSP}567,89")),
)
_INTL_AMOUNTS = (Decimal("999.00"), Decimal("1234.56"), Decimal("12345.67"), Decimal("1234567.89"))


@pytest.mark.parametrize(("language", "expected"), _INTL_FIGURES)
def test_a_decimal_groups_exactly_where_the_windows_intl_does(
    language: OutputLanguage, expected: tuple[str, ...]
) -> None:
    rendered = tuple(format_casilla_value(value, data_type="decimal", language=language) for value in _INTL_AMOUNTS)

    assert rendered == expected


@pytest.mark.parametrize(("language", "expected"), _INTL_FIGURES)
def test_money_groups_exactly_where_the_windows_intl_does(language: OutputLanguage, expected: tuple[str, ...]) -> None:
    rendered = tuple(format_casilla_value(value, data_type="money", language=language) for value in _INTL_AMOUNTS)

    assert rendered == tuple(f"{figure}{_EURO}" for figure in expected)


# The euro sign follows the number after one no-break space in every language, and a negative amount carries the
# screen minus before its digits. The window's `formatAmount(locale, value, { currency: "EUR" })` writes these same
# literals (tests/shared/numbers.spec.ts, SHARED_EURO_AMOUNTS); both tables are spelled out in full so neither side
# agrees with the other by construction.
_SHARED_EURO_INPUTS = ("0", "999", "1234.56", "12345.67", "1234567.89", "-1234.56")
_SHARED_EURO_AMOUNTS = (
    (
        OutputLanguage.EN,
        (
            "0.00\u00a0\u20ac",
            "999.00\u00a0\u20ac",
            "1,234.56\u00a0\u20ac",
            "12,345.67\u00a0\u20ac",
            "1,234,567.89\u00a0\u20ac",
            "\u22121,234.56\u00a0\u20ac",
        ),
    ),
    (
        OutputLanguage.ES,
        (
            "0,00\u00a0\u20ac",
            "999,00\u00a0\u20ac",
            "1.234,56\u00a0\u20ac",
            "12.345,67\u00a0\u20ac",
            "1.234.567,89\u00a0\u20ac",
            "\u22121.234,56\u00a0\u20ac",
        ),
    ),
    (
        OutputLanguage.CA,
        (
            "0,00\u00a0\u20ac",
            "999,00\u00a0\u20ac",
            "1.234,56\u00a0\u20ac",
            "12.345,67\u00a0\u20ac",
            "1.234.567,89\u00a0\u20ac",
            "\u22121.234,56\u00a0\u20ac",
        ),
    ),
    (
        OutputLanguage.HU,
        (
            "0,00\u00a0\u20ac",
            "999,00\u00a0\u20ac",
            "1\u00a0234,56\u00a0\u20ac",
            "12\u00a0345,67\u00a0\u20ac",
            "1\u00a0234\u00a0567,89\u00a0\u20ac",
            "\u22121\u00a0234,56\u00a0\u20ac",
        ),
    ),
)


@pytest.mark.parametrize(("language", "expected"), _SHARED_EURO_AMOUNTS)
def test_the_euro_sign_follows_the_number_exactly_as_the_window_writes_it(
    language: OutputLanguage, expected: tuple[str, ...]
) -> None:
    rendered = tuple(format_casilla_value(value, data_type="money", language=language) for value in _SHARED_EURO_INPUTS)

    assert rendered == expected


@pytest.mark.parametrize(("language", "expected"), _INTL_FIGURES)
def test_a_negative_figure_groups_by_its_digits_not_its_sign(
    language: OutputLanguage, expected: tuple[str, ...]
) -> None:
    rendered = tuple(format_casilla_value(-value, data_type="decimal", language=language) for value in _INTL_AMOUNTS)

    assert rendered == tuple(f"{_MINUS}{figure}" for figure in expected)


def test_quantities_keep_every_place_they_carry_and_are_never_rounded() -> None:
    assert format_casilla_value(Decimal("1234.5678"), data_type="decimal", language=OutputLanguage.ES) == "1.234,5678"
    assert format_casilla_value(Decimal("21"), data_type="ratio", language=OutputLanguage.ES) == "21"
    assert format_casilla_value(Decimal("0.125"), data_type="ratio", language=OutputLanguage.EN) == "0.125"
    assert format_casilla_value(Decimal("12.3456"), data_type="money", language=OutputLanguage.EN) == f"12.3456{_EURO}"


def test_a_ratio_reads_as_a_percentage_only_where_its_unit_is_declared() -> None:
    def ratio(value: Decimal | str, unit: ModeloEditRatioUnit | None, language: OutputLanguage) -> str:
        return format_casilla_value(value, data_type="ratio", language=language, ratio_unit=unit)

    assert ratio(Decimal("21"), ModeloEditRatioUnit.PERCENT, OutputLanguage.EN) == f"21{_PERCENT}"
    assert ratio(Decimal("10.50"), ModeloEditRatioUnit.PERCENT, OutputLanguage.ES) == f"10,50{_PERCENT}"
    assert ratio("4", ModeloEditRatioUnit.PERCENT, OutputLanguage.CA) == f"4{_PERCENT}"
    # A fraction moves its point by exactly two places, keeping every digit it carried.
    assert ratio(Decimal("0.21"), ModeloEditRatioUnit.FRACTION, OutputLanguage.EN) == f"21{_PERCENT}"
    assert ratio(Decimal("0.1275"), ModeloEditRatioUnit.FRACTION, OutputLanguage.HU) == f"12,75{_PERCENT}"
    assert ratio(Decimal("-0.5"), ModeloEditRatioUnit.FRACTION, OutputLanguage.EN) == f"{_MINUS}50{_PERCENT}"
    # Without a declared unit the figure stays bare rather than guessing a hundredfold.
    assert ratio(Decimal("21"), ModeloEditRatioUnit.UNDECLARED, OutputLanguage.EN) == "21"
    assert ratio(Decimal("0.21"), None, OutputLanguage.EN) == "0.21"
    # A unit never turns another kind of figure into a percentage, nor an unreadable one into a guess.
    assert (
        format_casilla_value(
            Decimal("21"), data_type="money", language=OutputLanguage.EN, ratio_unit=ModeloEditRatioUnit.PERCENT
        )
        == f"21.00{_EURO}"
    )
    assert ratio("1e3", ModeloEditRatioUnit.PERCENT, OutputLanguage.EN) == "1e3"


def test_counts_group_and_years_stay_plain_digits() -> None:
    assert format_casilla_value(1234, data_type="integer", language=OutputLanguage.ES) == "1.234"
    assert format_casilla_value(Decimal(_YEAR), data_type="year", language=OutputLanguage.ES) == str(_YEAR)
    assert format_casilla_value(str(_YEAR), data_type="year", language=OutputLanguage.HU) == str(_YEAR)


@pytest.mark.parametrize(
    ("language", "yes", "no"),
    (
        (OutputLanguage.ES, "Sí", "No"),
        (OutputLanguage.EN, "Yes", "No"),
    ),
)
def test_a_yes_or_no_is_a_word_whatever_channel_carries_it(language: OutputLanguage, yes: str, no: str) -> None:
    assert format_casilla_value(True, data_type="boolean", language=language) == yes
    assert format_casilla_value(Decimal(0), data_type="boolean", language=language) == no
    assert format_casilla_value(1, data_type="boolean", language=language) == yes


def test_dates_read_as_the_window_writes_them() -> None:
    day = date(_YEAR, 3, 31)

    assert format_casilla_value(day, data_type="date", language=OutputLanguage.EN) == f"Mar 31, {_YEAR}"
    assert format_casilla_value(day, data_type="date", language=OutputLanguage.ES) == f"31 mar {_YEAR}"
    assert format_casilla_value(day, data_type="date", language=OutputLanguage.CA) == f"31 de març {_YEAR}"
    assert format_casilla_value(day, data_type="date", language=OutputLanguage.HU) == f"{_YEAR}. márc. 31."


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("month", range(1, 13))
def test_every_month_reads_as_the_languages_medium_date(language: OutputLanguage, month: int) -> None:
    for day in (date(_YEAR, month, 5), date(_YEAR, month, 20)):
        written = format_casilla_value(day, data_type="date", language=language)

        assert written == format_date(day, format="medium", locale=language.value)


def test_a_bank_account_is_masked_unless_the_editor_asks_for_it() -> None:
    iban = "ES91 2100 0418 4502 0005 1332"

    assert (
        format_casilla_value(iban, data_type="iban", language=OutputLanguage.ES) == "ES \u00b7\u00b7\u00b7\u00b7 1332"
    )
    assert format_casilla_value(iban, data_type="iban", language=OutputLanguage.ES, mask_iban=False) == iban


def test_codes_and_text_are_shown_as_stored() -> None:
    assert format_casilla_value("00001005Q", data_type="nif", language=OutputLanguage.EN) == "00001005Q"
    assert format_casilla_value("1T", data_type="period_code", language=OutputLanguage.ES) == "1T"
    assert value_presentation_kind("postal_code") is ValuePresentationKind.CODE


def test_an_unreadable_figure_is_shown_as_stored_rather_than_guessed() -> None:
    assert format_casilla_value("1e3", data_type="money", language=OutputLanguage.ES) == "1e3"


def test_an_undeclared_data_type_is_refused() -> None:
    with pytest.raises(UnknownValuePresentationError):
        value_presentation_kind("colour")


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_absence_and_non_applicability_have_their_own_words(language: OutputLanguage) -> None:
    absent = absent_value_text(language)
    not_applicable = lookup_translation(VALUE_NOT_APPLICABLE_LOCALE_KEY, locale=language.value)

    assert absent
    assert not_applicable is not None and not_applicable
    assert absent != not_applicable
    assert "0" not in absent
