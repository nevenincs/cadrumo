"""The Art. 58 economic-dependency assimilation, at its staged boundary.

This limb was RETIRED and the retirement was wrong. It rested on two claims,
both refuted against the live authority: that the statutory carve-out removes
the common household shape, and that no reachable case could be constructed.
The carve-out turns on anualidades actually being SATISFIED rather than on the
regime being available, and the authority states the supposedly unconstructible
case as entitled in terms - a progenitor with no custody, not even shared,
paying no judicial anualidades, who nonetheless contributes to the descendant's
economic upkeep.

What ships here is the staged boundary, not the whole rule. Per-child
attribution of anualidades does not exist, so a declared payment suppresses the
assimilation for EVERY descendant. That under-grants, which is the safe
direction, and the suppression is disclosed rather than silent.

Assertions are structural - which limb admits which household - so nothing
re-derives a registry formula against itself. No euro figure is expected here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..descendant import DescendantInfo
from ..descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family_profile import RentaFamilyProfile
from ..family_types import MinimoDescendientesThresholds

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2024

#: Registry-shaped ceilings. Their VALUES are irrelevant to every assertion
#: below: each case either declares no rentas at all, which both income
#: conditions read as non-excluding, or is decided by the household limb before
#: any ceiling applies. They are supplied only because the predicate requires
#: them, deliberately, so no caller can skip half the law.
_THRESHOLDS = MinimoDescendientesThresholds(
    rentas_anuales_limite=Decimal("8000"),
    declaracion_propia_rentas_limite=Decimal("1800"),
)


def _child(
    *,
    convive_con_contribuyente: bool = True,
    dependencia_economica: bool | None = None,
) -> DescendantInfo:
    return DescendantInfo(
        birth_date=date(2012, 1, 1),
        convive_con_contribuyente=convive_con_contribuyente,
        dependencia_economica=dependencia_economica,
    )


def _profile(child: DescendantInfo, anualidades: Decimal | None = None) -> RentaFamilyProfile:
    return RentaFamilyProfile(descendientes=(child,), anualidades_alimentos_euros=anualidades)


def _eligible(profile: RentaFamilyProfile) -> int:
    return profile.descendientes_eligible_minimum(_YEAR, thresholds=_THRESHOLDS)


# -- the case the retirement declared unconstructible -------------------------


def test_a_non_cohabiting_supporter_paying_no_anualidades_takes_the_minimo() -> None:
    """The household the authority names, which the retirement said did not exist."""
    profile = _profile(_child(convive_con_contribuyente=False, dependencia_economica=True))

    assert _eligible(profile) == 1
    assert profile.dependencia_assimilated_indices(_YEAR) == (0,)


def test_cohabitation_alone_still_qualifies_and_is_not_reported_as_assimilated() -> None:
    """Cohabitation stays sufficient; the new limb widens the rule rather than replacing it.

    The disclosure predicate is scoped to households where the assimilation is
    load-bearing, so a cohabiting descendant carrying the dependency fact too is
    not reported - the advisory would otherwise fire on filers whose entitlement
    never depended on the judgement.
    """
    profile = _profile(_child(dependencia_economica=True))

    assert _eligible(profile) == 1
    assert profile.dependencia_assimilated_indices(_YEAR) == ()


# -- unset never assimilates --------------------------------------------------


@pytest.mark.parametrize(
    ("dependencia", "reason"),
    [
        (None, "unset: the question was never put"),
        (False, "explicit no: the question was put and declined"),
    ],
)
def test_a_non_cohabiting_descendant_without_an_affirmative_takes_nothing(
    dependencia: bool | None,
    reason: str,
) -> None:
    """Only an explicit yes assimilates.

    Unset must not, because a defaulting field is how an excluded case becomes
    reachable through the only input available - the same shape the entry-date
    coherence rules guard against on the relación axis.
    """
    profile = _profile(_child(convive_con_contribuyente=False, dependencia_economica=dependencia))

    assert _eligible(profile) == 0, reason


def test_unset_and_an_explicit_no_are_distinguishable_end_to_end() -> None:
    """The tri-state survives the fact boundary rather than collapsing on the way.

    They mean different things - one is answerable, the other has been answered
    - so a boundary that folded them together would destroy the distinction the
    assimilation turns on and would do it invisibly.
    """
    unset = _child(convive_con_contribuyente=False)
    declined = _child(convive_con_contribuyente=False, dependencia_economica=False)

    reloaded = descendant_list_from_facts(dict(descendant_facts_from_list((unset, declined))))

    assert reloaded == (unset, declined)
    assert reloaded[0].dependencia_economica is None
    assert reloaded[1].dependencia_economica is False


# -- the anualidades carve-out ------------------------------------------------


def test_declared_anualidades_suppress_the_assimilation_and_say_so() -> None:
    """The staged narrowing, and the disclosure that keeps it from being silent."""
    profile = _profile(
        _child(convive_con_contribuyente=False, dependencia_economica=True),
        anualidades=Decimal("3600"),
    )

    assert _eligible(profile) == 0
    assert profile.dependencia_assimilation_available is False
    assert profile.dependencia_suppressed_indices() == (0,)
    assert profile.dependencia_assimilated_indices(_YEAR) == ()


def test_a_declared_zero_is_an_answer_and_does_not_suppress() -> None:
    """Zero anualidades means none are paid, which is the entitling case, not the barred one.

    Treating a declared zero as a suppressing "declaration" would withdraw the
    allowance from precisely the filer the authority names - one who pays no
    anualidades - on the strength of their having answered the question.
    """
    profile = _profile(
        _child(convive_con_contribuyente=False, dependencia_economica=True),
        anualidades=Decimal("0"),
    )

    assert _eligible(profile) == 1
    assert profile.dependencia_assimilation_available is True


def test_the_suppression_reaches_every_descendant_not_only_the_paid_one() -> None:
    """The narrowing is total by design, because attribution does not exist yet.

    Recorded as a test rather than a comment because it is the part a later
    reader is most likely to think is a bug: a filer paying anualidades for one
    child loses the assimilation for another they support outside any court
    order. It under-grants, and the advisory discloses it.
    """
    profile = RentaFamilyProfile(
        descendientes=(
            _child(convive_con_contribuyente=False, dependencia_economica=True),
            DescendantInfo(
                birth_date=date(2014, 6, 1),
                convive_con_contribuyente=False,
                dependencia_economica=True,
            ),
        ),
        anualidades_alimentos_euros=Decimal("1200"),
    )

    assert _eligible(profile) == 0
    assert profile.dependencia_suppressed_indices() == (0, 1)


def test_a_suppressed_profile_reports_nothing_when_no_dependency_was_declared() -> None:
    """The disclosure is scoped to filers it actually costs."""
    profile = _profile(_child(), anualidades=Decimal("1200"))

    assert profile.dependencia_suppressed_indices() == ()


# -- the default is the safe direction ----------------------------------------


def test_the_predicate_default_withholds_rather_than_grants() -> None:
    """A caller that forgets the flag gets the under-granting answer.

    The flag is keyword-only with a ``False`` default, so the failure mode of
    forgetting it is a withheld allowance rather than a granted one. That is the
    direction this predicate's defaults rest on, and it is why the anualidades
    injector can pass ``False`` explicitly and be correct.
    """
    supporter = _child(convive_con_contribuyente=False, dependencia_economica=True)

    assert supporter.meets_non_income_conditions(_YEAR) is False
    assert supporter.meets_non_income_conditions(_YEAR, dependencia_assimilation_available=True) is True


def test_cohabitation_is_never_overloaded_to_carry_the_dependency_case() -> None:
    """The two fields stay independent, which is why the filer need not misstate one.

    Before this limb existed a non-cohabiting supporter could only reach the
    allowance by claiming cohabitation. Asserting the fields are separately
    readable is what keeps a later simplification from re-merging them.
    """
    supporter = _child(convive_con_contribuyente=False, dependencia_economica=True)

    assert supporter.convive_con_contribuyente is False
    assert supporter.dependencia_economica is True
    assert supporter.qualifies_on_household_limb(dependencia_assimilation_available=True) is True


# -- entry doors and the persistence boundary ---------------------------------


@pytest.mark.parametrize(("token", "expected"), [("true", True), ("false", False)])
def test_the_flag_parser_carries_the_dependency_answer(token: str, expected: bool) -> None:
    parsed = parse_descendiente_flag(f"NACIMIENTO=2012-01-01,CONVIVENCIA=false,DEPENDENCIA={token}")

    assert parsed.dependencia_economica is expected


def test_omitting_the_flag_key_leaves_the_answer_unset() -> None:
    assert parse_descendiente_flag("NACIMIENTO=2012-01-01").dependencia_economica is None


def test_an_unreadable_dependency_answer_refuses_rather_than_defaulting() -> None:
    """A word the vocabulary cannot read is not an answer.

    Refusing matters more here than on a two-state field: resolving a typo onto
    the default would silently withdraw an allowance, while resolving it onto
    ``True`` would grant one nobody asserted.
    """
    with pytest.raises((ValueError, ValidationError)):
        parse_descendiente_flag("NACIMIENTO=2012-01-01,DEPENDENCIA=perhaps")


def test_the_profile_anualidades_figure_survives_a_strict_roundtrip() -> None:
    """Every defaultable field non-default, then strict equality across the boundary."""
    original = RentaFamilyProfile(
        descendientes=(
            DescendantInfo(
                birth_date=date(2012, 1, 1),
                convive_con_contribuyente=False,
                dependencia_economica=True,
                custodia_compartida=True,
                discapacidad_grado=33,
                presenta_declaracion_propia=True,
                prorrata_minimo=True,
                meses_madre_trabajo=(1, 2, 3, 4, 5),
                gastos_guarderia_euros=800,
                nif="00000000T",
            ),
        ),
        anualidades_alimentos_euros=Decimal("2400.50"),
    )

    reloaded = RentaFamilyProfile(
        descendientes=descendant_list_from_facts(dict(descendant_facts_from_list(original.descendientes))),
        anualidades_alimentos_euros=original.anualidades_alimentos_euros,
    )

    assert reloaded == original


def test_deleting_the_stored_dependency_fact_changes_the_reloaded_record() -> None:
    """Anti-tautology proof, and the degradation is toward under-grant.

    Without this, the roundtrip above could pass over a boundary that never
    carried the field. The direction matters as much as the observability: the
    record degrades to an unset answer, which withholds the allowance, rather
    than to an affirmative that would grant one.
    """
    supporter = _child(convive_con_contribuyente=False, dependencia_economica=True)
    facts = dict(descendant_facts_from_list((supporter,)))
    assert facts.pop("renta_family.descendiente.0.dependencia_economica") == "true"

    (reloaded,) = descendant_list_from_facts(facts)

    assert reloaded != supporter
    assert reloaded.dependencia_economica is None
    assert _eligible(_profile(reloaded)) == 0


def test_a_corrupted_stored_dependency_fact_refuses_rather_than_coercing() -> None:
    """A present but unreadable stored value is refused on the read path too."""
    supporter = _child(convive_con_contribuyente=False, dependencia_economica=True)
    facts = dict(descendant_facts_from_list((supporter,)))
    facts["renta_family.descendiente.0.dependencia_economica"] = "maybe"

    with pytest.raises((ValueError, ValidationError)):
        descendant_list_from_facts(facts)


def test_a_negative_anualidades_figure_is_refused() -> None:
    with pytest.raises((ValueError, ValidationError)):
        RentaFamilyProfile(anualidades_alimentos_euros=Decimal("-1"))
