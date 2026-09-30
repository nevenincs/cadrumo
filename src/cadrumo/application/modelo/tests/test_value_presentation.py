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

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.schema_base import CasillaDataType
from ..edit_value_grammar import ModeloEditRatioUnit
from ..value_presentation import (
    LOCALE_NUMBER_FORMATS,
    UnknownValuePresentationError,
    ValuePresentationKind,
    absent_value_text,
    format_casilla_value,
    not_applicable_value_text,
    presentation_data_types,
    value_presentation_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NBSP = "\u00a0"
_MINUS = "\u2212"
_EURO = f"{_NBSP}\u20ac"
_PERCENT = f"{_NBSP}%"


def test_every_registry_data_type_and_language_has_a_presentation() -> None:
    assert presentation_data_types() == {member.value for member in CasillaDataType}
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
    assert format_casilla_value(Decimal(2026), data_type="year", language=OutputLanguage.ES) == "2026"
    assert format_casilla_value("2026", data_type="year", language=OutputLanguage.HU) == "2026"


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


def test_dates_follow_the_language_order() -> None:
    day = date(2026, 3, 31)

    assert format_casilla_value(day, data_type="date", language=OutputLanguage.ES) == "31/03/2026"
    assert format_casilla_value(day, data_type="date", language=OutputLanguage.HU) == "2026. 03. 31."


def test_a_bank_account_is_masked_unless_the_editor_asks_for_it() -> None:
    iban = "ES91 2100 0418 4502 0005 1332"

    assert (
        format_casilla_value(iban, data_type="iban", language=OutputLanguage.ES) == "ES91 \u00b7\u00b7\u00b7\u00b7 1332"
    )
    assert format_casilla_value(iban, data_type="iban", language=OutputLanguage.ES, mask_iban=False) == iban


def test_codes_and_text_are_shown_as_stored() -> None:
    assert format_casilla_value("00000001R", data_type="nif", language=OutputLanguage.EN) == "00000001R"
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
    not_applicable = not_applicable_value_text(language)

    assert absent
    assert not_applicable
    assert absent != not_applicable
    assert "0" not in absent
