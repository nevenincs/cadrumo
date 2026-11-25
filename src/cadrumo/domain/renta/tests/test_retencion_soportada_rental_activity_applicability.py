"""Whether an urban rental carried on as an activity is declared, read from the declared activities' IAE group.

The rental is activity income, but so is every other activity, so the activity
category alone cannot say whether one exists. RIRPF art. 75.3.g).3.º classifies
the lessor's urban rental activity under group 861 of the sección primera of
the IAE tariffs (RDLeg 1175/1990). Each expectation below is derived from that
rule, not from a run.

The groups are a governed fact. These tests read the fact and the support
envelope from the published generation and resolve them through the real
resolver.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from ....core.retencion_soportada import RetencionSoportadaClase
from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from ...calculations.registry.governed_fact_scope import CandidateFactAuthority
from ...calculations.registry.iae_activity_groups import iae_activity_groups
from ...calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from ..retencion_soportada_applicability import (
    IAE_URBAN_RENTAL_GROUPS_FACT_ID,
    RetencionSoportadaApplicability,
    arrendamiento_actividad_applicability,
    retencion_soportada_applicability,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_RENTAL_ACTIVITY = RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD
_ACTIVITY_INCOME = frozenset({"actividad_economica"})


def _authored_fact_table() -> dict[str, Any]:
    with bundled_indexed_authority().operation() as operation:
        return operation.governed_fact(IAE_URBAN_RENTAL_GROUPS_FACT_ID).model_dump(mode="json")


def _support() -> SupportedFilingYearsCatalogue:
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years()


def _authority(table: dict[str, Any]) -> CandidateFactAuthority:
    fact = GovernedFact.model_validate(table, strict=False)
    return CandidateFactAuthority(GovernedFactCatalogue(facts={fact.fact_id: fact}), _support())


def _with_entities(entities: list[str]) -> CandidateFactAuthority:
    table = _authored_fact_table()
    table["variants"][0]["payload"]["entities"] = entities
    return _authority(table)


@pytest.fixture(scope="module")
def authority() -> CandidateFactAuthority:
    return _authority(_authored_fact_table())


@pytest.fixture(scope="module")
def ejercicio_end() -> date:
    return date(_support().horizon, 12, 31)


def _supported_years() -> range:
    support = _support()
    # One year past the horizon too: the envelope is open above it.
    return range(support.floor, support.horizon + 2)


def test_the_fact_is_the_one_the_module_reads() -> None:
    assert _authored_fact_table()["fact_id"] == IAE_URBAN_RENTAL_GROUPS_FACT_ID


@pytest.mark.parametrize("filing_year", _supported_years())
def test_every_supported_year_reads_the_rental_group(authority: CandidateFactAuthority, filing_year: int) -> None:
    assert iae_activity_groups(
        IAE_URBAN_RENTAL_GROUPS_FACT_ID, effective_date=date(filing_year, 12, 31), authority=authority
    ) == {"861"}


def test_a_year_below_the_support_floor_is_refused(authority: CandidateFactAuthority) -> None:
    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        iae_activity_groups(
            IAE_URBAN_RENTAL_GROUPS_FACT_ID, effective_date=date(_support().floor - 1, 12, 31), authority=authority
        )


@pytest.mark.parametrize("entities", [["86"], ["861.1"], ["8611"]])
def test_a_fact_entity_that_is_not_a_three_digit_group_is_refused(entities: list[str]) -> None:
    with pytest.raises(RegistryValidationError, match="three-digit IAE groups"):
        iae_activity_groups(
            IAE_URBAN_RENTAL_GROUPS_FACT_ID,
            effective_date=date(_support().horizon, 12, 31),
            authority=_with_entities(entities),
        )


def test_the_group_compared_is_the_fact_s_not_one_held_in_code(ejercicio_end: date) -> None:
    rural = _with_entities(["862"])
    assert (
        arrendamiento_actividad_applicability(("862",), effective_date=ejercicio_end, authority=rural)
        is RetencionSoportadaApplicability.DECLARED
    )
    assert (
        arrendamiento_actividad_applicability(("861.1",), effective_date=ejercicio_end, authority=rural)
        is RetencionSoportadaApplicability.DECLARED_ABSENT
    )


@pytest.mark.parametrize(
    ("epigraphs", "expected"),
    [
        # Group 861 with or without its epigraph digit, surrounding blanks trimmed.
        (("861.1",), RetencionSoportadaApplicability.DECLARED),
        (("861",), RetencionSoportadaApplicability.DECLARED),
        ((" 861.2 ",), RetencionSoportadaApplicability.DECLARED),
        # One rental among other activities is enough.
        (("844", "861.1"), RetencionSoportadaApplicability.DECLARED),
        # An 861 among unreadable epigraphs still needs the payer evidence.
        (("861", None), RetencionSoportadaApplicability.DECLARED),
        # Another group starting with 8, and the rural rental group 862, are not 861.
        (("841",), RetencionSoportadaApplicability.DECLARED_ABSENT),
        (("862",), RetencionSoportadaApplicability.DECLARED_ABSENT),
        (("751.2", "844"), RetencionSoportadaApplicability.DECLARED_ABSENT),
        # No prefix match: neither a shorter nor a longer group reads as 861.
        (("86",), RetencionSoportadaApplicability.UNKNOWN),
        (("8611",), RetencionSoportadaApplicability.UNKNOWN),
        (("861.12",), RetencionSoportadaApplicability.UNKNOWN),
        # An activity without an epigraph, or with one that does not parse, is unknown.
        ((None,), RetencionSoportadaApplicability.UNKNOWN),
        (("844", "otros"), RetencionSoportadaApplicability.UNKNOWN),
        # No declared activity says nothing either way.
        ((), RetencionSoportadaApplicability.UNKNOWN),
        (None, RetencionSoportadaApplicability.UNKNOWN),
    ],
)
def test_the_rental_activity_is_read_from_the_exact_iae_group(
    authority: CandidateFactAuthority,
    ejercicio_end: date,
    epigraphs: tuple[str | None, ...] | None,
    expected: RetencionSoportadaApplicability,
) -> None:
    assert (
        arrendamiento_actividad_applicability(epigraphs, effective_date=ejercicio_end, authority=authority) is expected
    )


def test_a_profile_declaring_no_activity_income_proves_the_rental_activity_absent(
    authority: CandidateFactAuthority, ejercicio_end: date
) -> None:
    assert (
        retencion_soportada_applicability(
            _RENTAL_ACTIVITY, frozenset({"trabajo"}), ("861",), effective_date=ejercicio_end, authority=authority
        )
        is RetencionSoportadaApplicability.DECLARED_ABSENT
    )


def test_declared_activity_income_is_refined_by_the_activities_groups(
    authority: CandidateFactAuthority, ejercicio_end: date
) -> None:
    def applicability(epigraphs: tuple[str, ...] | None) -> RetencionSoportadaApplicability:
        return retencion_soportada_applicability(
            _RENTAL_ACTIVITY, _ACTIVITY_INCOME, epigraphs, effective_date=ejercicio_end, authority=authority
        )

    assert applicability(("861.1",)) is RetencionSoportadaApplicability.DECLARED
    assert applicability(("844",)) is RetencionSoportadaApplicability.DECLARED_ABSENT
    assert applicability(None) is RetencionSoportadaApplicability.UNKNOWN


def test_an_undeclared_category_set_stays_unknown_whatever_the_activities_say(
    authority: CandidateFactAuthority, ejercicio_end: date
) -> None:
    assert (
        retencion_soportada_applicability(
            _RENTAL_ACTIVITY, None, ("844",), effective_date=ejercicio_end, authority=authority
        )
        is RetencionSoportadaApplicability.UNKNOWN
    )


def test_the_other_activity_class_does_not_read_the_epigraphs(
    authority: CandidateFactAuthority, ejercicio_end: date
) -> None:
    for epigraphs in (("861",), None):
        assert (
            retencion_soportada_applicability(
                RetencionSoportadaClase.ACTIVIDAD_ECONOMICA,
                _ACTIVITY_INCOME,
                epigraphs,
                effective_date=ejercicio_end,
                authority=authority,
            )
            is RetencionSoportadaApplicability.DECLARED
        )
