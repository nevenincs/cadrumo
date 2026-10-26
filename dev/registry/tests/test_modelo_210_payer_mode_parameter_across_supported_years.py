"""Modelo 210 code-35 payer-mode rule across every authored edition.

Income code 35 is defined by the multiple-payer grouping it permits, so the
parameter declaring that requirement belongs to the first edition that enrols
code 35 and is inherited, unchanged, by every later one. A copy re-keyed onto a
later edition would leave the earlier years without the rule while their code
catalogue already admits the code.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as CompiledAuthority
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import ParameterDefinition

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "210"
_CODES = "m210-tipo-renta-code"
_PAYER_MODE = "m210-tipo-renta-multiple-payers-required"
_GROUPED_RENTAL_CODE = "35"


def _authored_years() -> tuple[int, ...]:
    """The supported filing years an authored Modelo 210 edition covers."""
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", _MODELO))
    first = min(revision.valid_from.year for revision in modelo.revisions.values())
    return tuple(year for year in support.years if year >= first)


AUTHORED_YEARS = _authored_years()


@pytest.fixture(scope="module")
def edition(registry_authority: CompiledAuthority) -> Callable[[int], RegistrySnapshot]:
    """The Modelo 210 annual edition the canonical resolver selects for one filing year."""

    def select(filing_year: int) -> RegistrySnapshot:
        return registry_authority.snapshot(
            _MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        )

    return select


def _parameter(snapshot: RegistrySnapshot, parameter_id: str) -> ParameterDefinition:
    return next(parameter for parameter in snapshot.revision.parameters if parameter.id == parameter_id)


def _in_force(parameter: ParameterDefinition, filing_year: int) -> set[str]:
    return {
        str(entry.key)
        for entry in parameter.keyed_brackets
        if entry.valid_from.year <= filing_year and (entry.valid_to is None or entry.valid_to.year >= filing_year)
    }


def test_more_than_one_authored_edition_is_judged() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", _MODELO))
    assert len({revision.id for revision in modelo.revisions.values()}) > 1
    assert len(AUTHORED_YEARS) > 1


@pytest.mark.parametrize("filing_year", AUTHORED_YEARS)
def test_code_35_requires_multiple_payers_wherever_it_is_enrolled(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    snapshot = edition(filing_year)
    codes = _in_force(_parameter(snapshot, _CODES), filing_year)
    required = _in_force(_parameter(snapshot, _PAYER_MODE), filing_year)

    assert _GROUPED_RENTAL_CODE in codes, filing_year
    assert required == {_GROUPED_RENTAL_CODE}, (filing_year, required)
    assert required <= codes


def test_the_rule_is_stated_once_on_the_first_edition() -> None:
    root = bundled_path("registry", "aeat", "modelos", _MODELO, "revisions")
    stating = sorted(
        path.parent.parent.name
        for path in root.glob("*/parameters/*.toml")
        if f'id = "{_PAYER_MODE}"' in path.read_text(encoding="utf-8")
    )
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", _MODELO))
    first = min(modelo.revisions.values(), key=lambda revision: revision.valid_from)

    assert stating == [str(first.id)]
