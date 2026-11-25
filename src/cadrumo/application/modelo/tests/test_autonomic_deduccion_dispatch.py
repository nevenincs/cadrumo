"""The shared dispatch on the descendant entry-window axis: Madrid nacimiento/adopción (box 1039).

Madrid's nacimiento/adopción deducción (DL 1/2010 arts. 4 and 18.1) is enrolled on
the descendant entry-window axis with a unidad familiar income limit. The dispatch
supplies its weighted count for a determinable single or monoparental Madrid filer.
A joint return or a partnered filer stays at zero: the unidad familiar limit needs
the other members' base, which no stored fact holds, so the box keeps its earlier
behaviour until a door can state it. A filer outside Madrid gets zero and is told
that the regional deducciones of their comunidad are not computed.

The count path is an ordinary profile field rather than a derived one, so a stored
value survives except where the dispatch computes a positive count.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    projected_exercise,
)

from ....domain.calculations.registry.autonomic_deduccion_enrolment_checks import autonomic_deduccion_enrolments
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import published_profile_schema, published_snapshot
from ....domain.user_profile.values import UserProfileFactValue
from ..autonomic_deduccion_dispatch import (
    AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON,
    AutonomicDeduccionDerivation,
    inject_autonomic_deduccion_facts,
)
from ..profile_derived_facts import family_fact_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_REVIEWED_EDITION = newest_authored_edition("100")
_ROLE = "irpf_deduccion_madrid_nacimiento_adopcion"
_COUNT_KEY = "renta_family.madrid_nacimiento_adopcion_eligible_count"
_OTROS_KEY = "renta_family.unidad_familiar_otros_miembros_base"
_BUCKET = "0de41ce4-0000-4000-8000-000000001039"
_UNREACHABLE_COUNT = Decimal("97.25")


def _facts(
    overrides: dict[str, UserProfileFactValue] | None = None, *, year: int = _REVIEWED_EDITION
) -> dict[str, UserProfileFactValue]:
    base: dict[str, UserProfileFactValue] = {
        "tax_residence.ccaa": "madrid",
        "renta_filing.declaration_type": "1",
        "renta_taxpayer.marital_status": "1",
        "renta_family.descendiente.0.birth_date": f"{year - 1}-06-01",
        "renta_family.descendiente.0.convivencia": "true",
    }
    base.update(overrides or {})
    return base


def _dispatch(
    facts: dict[str, UserProfileFactValue], operation: PinnedAuthorityOperation, year: int = _REVIEWED_EDITION
) -> AutonomicDeduccionDerivation:
    snapshot = published_snapshot("100", filing_year=year, period="0A")
    return inject_autonomic_deduccion_facts(
        facts,
        snapshot,
        schema=published_profile_schema(),
        context=family_fact_context(snapshot, operation=operation),
        bucket_id=_BUCKET,
    )


def _enrols_the_box(snapshot: RegistrySnapshot) -> bool:
    return any(
        enrolment.target_semantic_role == _ROLE
        for _formula, enrolment in autonomic_deduccion_enrolments(snapshot.revision)
    )


def test_madrid_single_individual_filer_gets_the_weighted_count(authority_operation: PinnedAuthorityOperation) -> None:
    facts = _facts()

    derivation = _dispatch(facts, authority_operation)

    assert facts[_COUNT_KEY] == Decimal("1")
    assert facts[_OTROS_KEY] == Decimal("0")
    assert derivation.withheld_paths == frozenset()


def test_shared_custody_child_counts_by_its_equal_parts_share(authority_operation: PinnedAuthorityOperation) -> None:
    facts = _facts({"renta_family.descendiente.0.custodia_compartida": "true"})

    _dispatch(facts, authority_operation)

    assert facts[_COUNT_KEY] == Decimal("0.5")


def test_the_count_spans_the_window_and_skips_children_outside_it(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = _REVIEWED_EDITION
    facts = _facts(
        {
            "renta_family.descendiente.1.birth_date": f"{year - 2}-02-01",
            "renta_family.descendiente.1.convivencia": "true",
            "renta_family.descendiente.2.birth_date": f"{year - 5}-01-01",
            "renta_family.descendiente.2.convivencia": "true",
            "renta_family.descendiente.3.birth_date": f"{year}-01-01",
            "renta_family.descendiente.3.convivencia": "false",
        }
    )

    _dispatch(facts, authority_operation)

    assert facts[_COUNT_KEY] == Decimal("2")


@pytest.mark.parametrize(
    "overrides",
    [
        {"renta_family.descendiente.0.birth_date": f"{_REVIEWED_EDITION - 6}-01-01"},
        {"renta_family.descendiente.0.convivencia": "false"},
        {"renta_filing.declaration_type": "2"},
        {"renta_taxpayer.marital_status": "2"},
    ],
    ids=["out-of-window", "non-cohabiting", "conjunta", "married"],
)
def test_a_madrid_filer_without_a_determinable_entitlement_stays_at_zero(
    overrides: dict[str, UserProfileFactValue], authority_operation: PinnedAuthorityOperation
) -> None:
    facts = _facts(overrides)

    derivation = _dispatch(facts, authority_operation)

    assert facts[_COUNT_KEY] == Decimal("0")
    assert derivation.withheld_paths == frozenset()


@pytest.mark.parametrize("ccaa", ["cataluna", "ceuta"])
def test_non_madrid_resident_stays_at_zero_and_is_served_the_limitation(
    ccaa: str, authority_operation: PinnedAuthorityOperation
) -> None:
    """A ciudad autónoma is covered too: it approves no deducción of its own."""
    facts = _facts({"tax_residence.ccaa": ccaa})

    derivation = _dispatch(facts, authority_operation)

    assert facts[_COUNT_KEY] == Decimal("0")
    assert facts[_OTROS_KEY] == Decimal("0")
    assert [diagnostic.reason for diagnostic in derivation.diagnostics] == [AUTONOMIC_DEDUCCIONES_NOT_ENROLLED_REASON]


def test_a_madrid_resident_is_not_served_the_limitation(authority_operation: PinnedAuthorityOperation) -> None:
    derivation = _dispatch(_facts(), authority_operation)

    assert derivation.diagnostics == ()


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_the_count_is_supplied_exactly_where_the_edition_enrols_the_box(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    """Enrolment presence decides; a year projected from the reviewed edition inherits it."""
    snapshot = published_snapshot("100", filing_year=year, period="0A")
    facts = _facts(year=year)

    _dispatch(facts, authority_operation, year)

    if _enrols_the_box(snapshot):
        assert facts[_COUNT_KEY] == Decimal("1")
        assert facts[_OTROS_KEY] == Decimal("0")
    else:
        assert _COUNT_KEY not in facts
        assert _OTROS_KEY not in facts


def test_the_projected_year_enrols_the_box_through_its_authored_edition() -> None:
    assert _enrols_the_box(published_snapshot("100", filing_year=projected_exercise("100"), period="0A"))


def test_a_stored_count_survives_outside_madrid(authority_operation: PinnedAuthorityOperation) -> None:
    """The count is an ordinary profile field: outside Madrid the dispatch only defaults it."""
    facts = _facts({"tax_residence.ccaa": "cataluna", _COUNT_KEY: _UNREACHABLE_COUNT})

    _dispatch(facts, authority_operation)

    assert facts[_COUNT_KEY] == _UNREACHABLE_COUNT


def test_a_stored_count_is_overwritten_by_a_positive_madrid_count(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    facts = _facts({_COUNT_KEY: _UNREACHABLE_COUNT})

    _dispatch(facts, authority_operation)

    assert facts[_COUNT_KEY] == Decimal("1")


def test_a_stored_other_members_base_is_never_overwritten(authority_operation: PinnedAuthorityOperation) -> None:
    seeded = _facts({_OTROS_KEY: _UNREACHABLE_COUNT})
    computed = _facts()

    _dispatch(seeded, authority_operation)
    _dispatch(computed, authority_operation)

    assert seeded[_OTROS_KEY] == _UNREACHABLE_COUNT
    assert computed[_OTROS_KEY] == Decimal("0")
