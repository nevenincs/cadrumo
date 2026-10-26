"""Modelo 210 rate and imputation rows are stated once and stay open across its editions.

The TRLIRNR tipos de gravamen, the pension tariff, the imputed-income rates and
the income-code catalogue carry no annual table: the first Modelo 210 edition
states each row open-ended, and every later year's edition inherits that same
row rather than removing it and adding it back keyed from its own first day.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as CompiledAuthority
from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import ParameterDefinition

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "210"


def _first_edition() -> ModeloRevision:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", _MODELO))
    return min(modelo.revisions.values(), key=lambda revision: revision.valid_from)


def _authored_years() -> tuple[int, ...]:
    """The supported filing years an authored Modelo 210 edition covers."""
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    first = _first_edition().valid_from.year
    return tuple(year for year in support.years if year >= first)


AUTHORED_YEARS = _authored_years()


def _open_rows(parameter: ParameterDefinition) -> tuple[object, ...]:
    rows = (*parameter.values, *parameter.brackets, *parameter.keyed_brackets)
    return tuple(row for row in rows if row.valid_to is None)


@pytest.fixture(scope="module")
def edition(registry_authority: CompiledAuthority) -> Callable[[int], RegistrySnapshot]:
    """The Modelo 210 annual edition the canonical resolver selects for one filing year."""

    def select(filing_year: int) -> RegistrySnapshot:
        return registry_authority.snapshot(
            _MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        )

    return select


def test_later_years_are_judged_against_the_first_edition() -> None:
    first = _first_edition()
    assert any(_open_rows(parameter) for parameter in first.parameters), first.id
    assert len(AUTHORED_YEARS) > 1


@pytest.mark.parametrize("filing_year", AUTHORED_YEARS)
def test_every_open_row_of_the_first_edition_is_carried_unchanged(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    carried = {parameter.id: parameter for parameter in edition(filing_year).revision.parameters}
    missing = {
        parameter.id: [row for row in _open_rows(parameter) if row not in _open_rows(carried[parameter.id])]
        for parameter in _first_edition().parameters
        if parameter.id in carried
    }

    assert {parameter.id for parameter in _first_edition().parameters} <= set(carried), filing_year
    assert {key: rows for key, rows in missing.items() if rows} == {}, filing_year
