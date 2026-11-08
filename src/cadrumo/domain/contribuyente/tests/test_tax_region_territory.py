"""Classify a recorded tax-region token against the dated residence catalogue."""

from __future__ import annotations

import pytest

from ...calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue
from ..tax_residence import ResidenceTerritory, classify_tax_region, parse_tax_region

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize(
    "recorded",
    [
        "Araba",
        "Álava",
        "alava",
        "Bizkaia",
        "Vizcaya",
        "Gipuzkoa",
        "Guipúzcoa",
        "guipuzcoa",
        "Navarra",
        "pais_vasco",
        "País Vasco",
        "euskadi",
    ],
)
def test_each_foral_territory_and_spelling_is_foral(recorded: str) -> None:
    assert classify_tax_region(recorded) is ResidenceTerritory.FORAL


def test_every_alias_the_catalogue_declares_foral_is_foral() -> None:
    aliases = resolve_ccaa_catalogue().foral_aliases

    assert aliases
    assert {classify_tax_region(alias) for alias in aliases} == {ResidenceTerritory.FORAL}


def test_every_common_territory_the_catalogue_declares_is_common() -> None:
    choices = resolve_ccaa_catalogue().choices

    assert choices
    assert {classify_tax_region(str(choice)) for choice in choices} == {ResidenceTerritory.COMMON}


@pytest.mark.parametrize("recorded", ["ceuta", "melilla", "Ceuta", "Melilla", "CEU", "MEL"])
def test_a_ciudad_autonoma_is_a_recorded_common_residence(recorded: str) -> None:
    """LIRPF DA 32 makes the two cities territorio común, not an unsupported territory.

    Their residents file Modelo 100 and take the artículo 65 autonomic scale, so a
    recorded residence in either city parses and classifies instead of refusing.
    """
    assert classify_tax_region(recorded) is ResidenceTerritory.COMMON


@pytest.mark.parametrize("token", ["ceuta", "melilla"])
def test_a_ciudad_autonoma_parses_to_its_own_catalogue_token(token: str) -> None:
    assert str(parse_tax_region(token)) == token


def test_neither_city_remains_an_excluded_territory() -> None:
    assert {"ceuta", "melilla"}.isdisjoint(resolve_ccaa_catalogue().excluded_territories)


def test_an_absent_reading_is_common() -> None:
    assert classify_tax_region(None) is ResidenceTerritory.COMMON


@pytest.mark.parametrize("recorded", ["atlantis", "", "   ", "Bizkaya", "madrid, navarra"])
def test_an_unparseable_reading_is_unresolved_not_common(recorded: str) -> None:
    assert classify_tax_region(recorded) is ResidenceTerritory.UNRESOLVED
