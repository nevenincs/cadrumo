"""Year-independent selection in the modelo application layer.

A derived profile selector, a dated advisory fact and a clock default must give
the same answer for every supported filing year unless the registry states a
difference. These tests enumerate the years from the support envelope.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ....domain.calculations.registry.facts.resolution import ResolvedMappingFact
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..art52_advisory import _registry_art52_declaration
from ..dt12_advisory import resolve_dt12_verification_mapping
from ..m145_communication import build_m145_communication_service_contract
from ..m145_communication_period import M145CommunicationPeriod
from ..profile_derived_facts import derived_selector_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ENVELOPE = filing_year_envelope()
_YEARS = tuple(_ENVELOPE.years)
_STEMS = (
    "renta_family.descendientes_minimos_aggregate",
    "renta_family.descendientes_minimos_aggregate_autonomico",
    "renta_family.anualidades_sin_minimo_descendientes",
    "renta_family.incremento_guarderia",
    "renta_family.deduccion_maternidad",
)


def _other_year(year: int) -> int:
    """Return a supported year different from ``year``."""
    return _ENVELOPE.floor if year != _ENVELOPE.floor else _ENVELOPE.horizon


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("stem", _STEMS)
def test_selector_declared_for_the_authored_year_is_used(year: int, stem: str) -> None:
    own = f"{stem}_{year}"
    declared = frozenset({own, f"{stem}_{_other_year(year)}"})

    assert derived_selector_name(stem, authored_year=year, declared_selectors=declared) == own


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("stem", _STEMS)
def test_selector_inherited_from_another_edition_is_used(year: int, stem: str) -> None:
    inherited = f"{stem}_{_other_year(year)}"

    assert derived_selector_name(stem, authored_year=year, declared_selectors=frozenset({inherited})) == inherited


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("stem", _STEMS)
def test_selector_of_another_stem_is_never_taken(year: int, stem: str) -> None:
    other_stems = frozenset(f"{other}_{_other_year(year)}" for other in _STEMS if other != stem)

    assert derived_selector_name(stem, authored_year=year, declared_selectors=other_stems) == f"{stem}_{year}"


@pytest.mark.parametrize("year", _YEARS)
def test_two_inherited_selectors_name_no_selector(year: int) -> None:
    stem = _STEMS[0]
    first = _other_year(year)
    second = next(candidate for candidate in _YEARS if candidate not in {year, first})
    declared = frozenset({f"{stem}_{first}", f"{stem}_{second}"})

    assert derived_selector_name(stem, authored_year=year, declared_selectors=declared) == f"{stem}_{year}"


@pytest.mark.parametrize("year", _YEARS)
def test_advisory_facts_resolve_at_every_supported_filing_coordinate(year: int) -> None:
    coordinate = date(year, 12, 31)
    with bundled_indexed_authority().operation() as operation:
        for fact_id in ("lirpf-dt12-reduction-verification-mapping", "lirpf-dt12-antiquity-verification-mapping"):
            resolved = resolve_dt12_verification_mapping(
                None, operation=operation, fact_id=fact_id, effective_date=coordinate
            )
            assert isinstance(resolved, ResolvedMappingFact)
        art52 = _registry_art52_declaration(None, operation=operation, modelo="100", effective_date=coordinate)
        assert isinstance(art52, ResolvedMappingFact)


@pytest.mark.parametrize("year", _YEARS)
def test_m145_contract_is_built_for_the_requested_year_only(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        contract = build_m145_communication_service_contract(
            period_token=M145CommunicationPeriod.COMMUNICATION,
            filing_year=year,
            operation=operation,
        )

    assert contract.period_token == M145CommunicationPeriod.COMMUNICATION.value
