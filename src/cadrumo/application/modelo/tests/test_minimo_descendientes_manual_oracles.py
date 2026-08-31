"""AEAT manual worked-example oracles for the Art. 58/61 mínimo por descendientes.

Ground truth is the bundled AEAT Manual práctico de Renta 2024, Parte 1,
Capítulo 14 ("Ejemplos prácticos"), declared in
``corpus/manual_oracles/modelo-100-2024-minimo-descendientes-prorrateo-asturias.json``
and ``…-declaracion-propia-valenciana.json``.

Every expected figure here is a number AEAT printed. Nothing is recomputed from
the predicate under test, and nothing is derived as a complement of another
assertion: the prorrateo pair asserts 4.550 AND 9.100 as two separately printed
totals that happen to stand in a 2:1 relation, rather than asserting one and
halving it.

Three hazards govern what these tests may assert, all recorded in the fixture
notes and all reproduced by the author against the extraction before use:

* The Asturias example states the comunidad exercised NO normative competence,
  so estatal and autonómico carry the same figure and casilla 0514 can be
  asserted alongside 0513. The Valencian example states the opposite, so only
  the estatal casilla 0513 is asserted there.
* In the Valencian example the excluded child holds 4.050 euros — BELOW the
  Art. 58.1 ceiling of 8.000. That child is excluded by the Art. 61 norma 2ª
  own-return rule alone, so this oracle grounds norma 2ª and not the cap.
* The conjunta table of the Asturias example carries an extraction artefact on
  the "Total mínimo por contribuyente" row (5.500 estatal against 5.550
  autonómico, contradicting both the line above it and the example's own
  footnote). Only the "Total mínimo por descendientes" rows are asserted, which
  are what casillas 0513/0514 hold.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests._manual_oracle_support import read_manual_worked_example
from ....domain.contribuyente.renta_codes import RentaMaritalStatus
from ....domain.user_profile.values import UserProfileFactValue
from ..profile_binding import (
    inject_derived_anualidades_eligibility_facts,
    inject_derived_minimo_descendientes_facts,
    second_entitled_filer_indicated,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ORACLE_YEAR = 2024
_ASTURIAS_ORACLE = "modelo-100-2024-minimo-descendientes-prorrateo-asturias.json"
_VALENCIANA_ORACLE = "modelo-100-2024-minimo-descendientes-declaracion-propia-valenciana.json"
_RIOJA_ORACLE = "modelo-100-2024-minimo-descendientes-adopcion-mayor-de-tres-rioja.json"


def _expected(name: str, casilla_id: str) -> Decimal:
    """Return the AEAT-printed figure for *casilla_id*, from the fixture on disk."""
    return Decimal(read_manual_worked_example(name).expected_by_casilla_id[casilla_id])


def _snapshot() -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=_ORACLE_YEAR, period="0A")


def _injected_decimal(facts: dict[str, UserProfileFactValue], key: str) -> Decimal:
    """Return the injected fact at ``key``, proving it is the Decimal it claims to be.

    The fact mapping is ``object``-valued, so the aggregate the injector writes
    has to be narrowed before it can be compared against an AEAT figure. Doing it
    by assertion rather than by suppression means the narrowing is checked: if the
    injector ever writes a string or a float here, this fails with the offending
    type instead of the comparison silently succeeding on a coerced value.
    """
    value = facts[key]
    assert isinstance(value, Decimal), f"{key} should be injected as a Decimal, got {type(value).__name__}"
    return value


def _aggregates(facts: dict[str, UserProfileFactValue]) -> tuple[Decimal, Decimal]:
    narrowed: Any = facts
    inject_derived_minimo_descendientes_facts(narrowed, _snapshot())
    return (
        _injected_decimal(facts, f"renta_family.descendientes_minimos_aggregate_{_ORACLE_YEAR}"),
        _injected_decimal(facts, f"renta_family.descendientes_minimos_aggregate_autonomico_{_ORACLE_YEAR}"),
    )


# ---------------------------------------------------------------------------
# The fixtures are real, loadable, and declare what these tests claim.
# ---------------------------------------------------------------------------


def test_both_oracle_fixtures_load_and_declare_their_provenance() -> None:
    for name in (_ASTURIAS_ORACLE, _VALENCIANA_ORACLE):
        payload = read_manual_worked_example(name)
        assert payload.modelo == "100", name
        assert payload.filing_year == _ORACLE_YEAR, name
        assert payload.source_kind == "aeat_manual_worked_example", name
        assert payload.raw_evidence_locator.startswith("corpus/manuals/renta/2024/"), name
        assert payload.expected_by_casilla_id, name


def test_the_valenciana_oracle_grounds_only_the_estatal_casilla() -> None:
    """The CCAA hazard is structural, not a comment.

    Comunitat Valenciana exercised normative competence, so its autonómico
    column carries divergent tranches the engine does not wire. If a later
    author adds 0514 to that fixture the assertion below fails, which is the
    point: the omission must stay deliberate rather than decay into an
    oversight.
    """
    assert set(read_manual_worked_example(_VALENCIANA_ORACLE).expected_by_casilla_id) == {"0513"}
    assert set(read_manual_worked_example(_ASTURIAS_ORACLE).expected_by_casilla_id) == {"0513", "0514"}


# ---------------------------------------------------------------------------
# Oracle A - Art. 61 norma 1a prorrateo, both sides AEAT-printed.
# ---------------------------------------------------------------------------


def _asturias_children() -> dict[str, UserProfileFactValue]:
    """Matrimonio, three cohabiting children aged 27 (discapacidad 33 %), 22 and 19.

    The manual states no child holds rentas above 8.000 nor files their own
    return, so both income conditions are satisfied and only the prorrateo is
    in play. The eldest is 27 and qualifies through the discapacidad limb.
    """
    return {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 27}-01-01",
        "renta_family.descendiente.0.discapacidad": "33",
        "renta_family.descendiente.1.birth_date": f"{_ORACLE_YEAR - 22}-01-01",
        "renta_family.descendiente.2.birth_date": f"{_ORACLE_YEAR - 19}-01-01",
        "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
    }


def test_asturias_individual_matches_the_printed_prorated_total() -> None:
    """AEAT prints 4.550 for each spouse filing individually, each tranche at 50 %."""
    estatal, autonomico = _aggregates({**_asturias_children(), "renta_filing.declaration_type": "1"})
    assert estatal == _expected(_ASTURIAS_ORACLE, "0513")
    assert autonomico == _expected(_ASTURIAS_ORACLE, "0514")


def test_asturias_conjunta_matches_the_printed_full_total() -> None:
    """AEAT prints 9.100 for the joint return, at the full tranches.

    Anti-tautology pair for the test above, with an AEAT-printed figure on BOTH
    sides: married spouses form one unidad familiar (LIRPF art. 82.1.1ª), so no
    second contribuyente remains to prorate with and the tranches are whole.
    """
    facts = {**_asturias_children(), "renta_filing.declaration_type": "2"}
    estatal, autonomico = _aggregates(facts)
    assert estatal == Decimal("9100")
    assert autonomico == Decimal("9100")
    # The two printed totals stand in the 2:1 relation norma 1a describes.
    assert _expected(_ASTURIAS_ORACLE, "0513") * 2 == estatal


def test_asturias_oracle_does_not_assert_the_artefacted_contribuyente_row() -> None:
    """The extraction artefact is excluded by construction, not by discipline.

    The conjunta table renders the mínimo del contribuyente as 5.500 in the
    estatal column against 5.550 in the autonómico one. Neither figure belongs
    to casilla 0513/0514, and this asserts the fixture never smuggled one in.
    """
    expected = read_manual_worked_example(_ASTURIAS_ORACLE).expected_by_casilla_id.values()
    assert Decimal("5500") not in {Decimal(value) for value in expected}
    assert Decimal("5550") not in {Decimal(value) for value in expected}


# ---------------------------------------------------------------------------
# Oracle B - Art. 61 norma 2a own-return exclusion.
# ---------------------------------------------------------------------------


def _valenciana_children(*, youngest_files_own_return: bool) -> dict[str, UserProfileFactValue]:
    """Pareja de hecho, three cohabiting children aged 18, 12 and 6.

    The youngest holds 4.050 euros of rendimientos del capital mobiliario —
    below the 8.000 Art. 58.1 ceiling, so the cap does NOT exclude this child.
    """
    facts: dict[str, UserProfileFactValue] = {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 18}-01-01",
        "renta_family.descendiente.1.birth_date": f"{_ORACLE_YEAR - 12}-01-01",
        "renta_family.descendiente.2.birth_date": f"{_ORACLE_YEAR - 6}-01-01",
        "renta_family.descendiente.2.rentas_anuales": "4050",
        "renta_taxpayer.marital_status": RentaMaritalStatus.PAREJA_HECHO.value,
        "renta_filing.declaration_type": "1",
    }
    if youngest_files_own_return:
        facts["renta_family.descendiente.2.declaracion_propia"] = "true"
    return facts


def test_valenciana_individual_matches_the_printed_estatal_total() -> None:
    """AEAT prints 2.550 estatal: 1.200 + 1.350 + 0 for the excluded youngest."""
    estatal, _ = _aggregates(_valenciana_children(youngest_files_own_return=True))
    assert estatal == _expected(_VALENCIANA_ORACLE, "0513")


def test_the_youngest_child_is_excluded_by_norma_2a_and_not_by_the_cap() -> None:
    """Anti-tautology pair isolating WHICH condition excludes.

    4.050 is below the Art. 58.1 ceiling, so removing only the own-return flag
    must restore that child's full tranche. If the cap were doing the work the
    total would not move, and this test would fail.
    """
    without_own_return, _ = _aggregates(_valenciana_children(youngest_files_own_return=False))
    printed_with_exclusion = _expected(_VALENCIANA_ORACLE, "0513")
    assert without_own_return > printed_with_exclusion
    # The restored child is the third by birth order, so it takes the 4.000
    # tranche at the same 50 % prorrateo the other two carry.
    assert without_own_return == printed_with_exclusion + Decimal("4000") * Decimal("0.5")


# ---------------------------------------------------------------------------
# Oracle B, conjunta - LIRPF art. 82.1's two modalities of unidad familiar.
# ---------------------------------------------------------------------------


def _valenciana_conjunta() -> dict[str, UserProfileFactValue]:
    """The same three children, filed jointly by one unmarried progenitor.

    In the joint return the youngest does not present a separate declaración,
    so the norma 2ª own-return flag is absent for this filing while the rentas
    figure stays on record. Only the marital status and declaration type differ
    from the individual case above.
    """
    return {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 18}-01-01",
        "renta_family.descendiente.1.birth_date": f"{_ORACLE_YEAR - 12}-01-01",
        "renta_family.descendiente.2.birth_date": f"{_ORACLE_YEAR - 6}-01-01",
        "renta_family.descendiente.2.rentas_anuales": "4050",
        "renta_taxpayer.marital_status": RentaMaritalStatus.PAREJA_HECHO.value,
        "renta_filing.declaration_type": "2",
    }


#: The first three Art. 58.1 tranches WHOLE, as AEAT prints them.
#:
#: Ejemplo 1 prints exactly this for a married couple's joint return, and both
#: examples' first three children draw the same 1º/2º/3º tranches, so it is the
#: un-prorated total for either household. Taken from the manual rather than
#: recomputed, like every other figure in this module.
_PRINTED_THREE_CHILD_WHOLE_TRANCHES = Decimal("9100")

#: What Ejemplo 2 prints for the SAME three children filed jointly by one
#: unmarried progenitor: 1.200 + 1.350 + 4.000.
_PRINTED_UNMARRIED_CONJUNTA_TOTAL = Decimal("6550")


def test_the_manual_itself_shows_an_unmarried_conjunta_is_prorated() -> None:
    """Ground the DIRECTION in AEAT's printed figures before asserting anything of the engine.

    Ejemplo 2's conjunta block prints 6.550 for three children whose whole
    tranches sum to 9.100. A joint return that were NOT prorated would print
    9.100 -- which is exactly what Ejemplo 1's married conjunta does print for
    the same three tranches. So the manual states, in figures, that an
    unmarried couple's joint return still prorates: LIRPF art. 82.1.2ª, since
    absent a marriage the unidad familiar is one progenitor plus the minor
    children and the other progenitor stays separately entitled.

    Touches no engine output, so it cannot be satisfied by the engine being
    wrong. Both figures are module constants transcribed from the manual: the
    fixtures assert the individual cases, and neither conjunta total appears in
    an ``expected_by_casilla_id`` map.
    """
    assert _PRINTED_UNMARRIED_CONJUNTA_TOTAL < _PRINTED_THREE_CHILD_WHOLE_TRANCHES
    # Consistency check on the whole-tranche constant, NOT a second printed
    # figure: it doubles the fixture's printed INDIVIDUAL total through the 2:1
    # relation norma 1a describes. The married-conjunta 9.100 is grounded in the
    # Asturias fixture's notes (L47434-L47445), not in its expected map, so
    # nothing here reads it from the fixture.
    assert _expected(_ASTURIAS_ORACLE, "0513") * 2 == _PRINTED_THREE_CHILD_WHOLE_TRANCHES


def test_an_unmarried_conjunta_return_is_prorated_and_a_married_one_is_not() -> None:
    """The campaign's most consequential correction, pinned on its own input.

    Before it, every conjunta return took whole tranches: the derivation read
    the declaration type alone and never asked whether marriage put the other
    progenitor inside the same unit. That over-granted 2.550 euros on this very
    household -- an under-declaration of the tax.

    The assertion is a STRICT INEQUALITY against the un-prorated total rather
    than an equality against a figure, because the engine cannot yet reach the
    printed 6.550 (see the recorded gap below) and re-pinning whatever it does
    produce would bless the shortfall as correct. What must hold, and what the
    branch exists to make hold, is that the unmarried joint return is prorated
    while the married one is not.
    """
    whole = _PRINTED_THREE_CHILD_WHOLE_TRANCHES

    unmarried, _ = _aggregates(_valenciana_conjunta())
    married, _ = _aggregates(
        {**_valenciana_conjunta(), "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value}
    )

    # Married: both progenitores inside the one unit, nobody to share with.
    assert married == whole
    # Unmarried: the other progenitor is a separate entitled contribuyente.
    assert unmarried < whole
    assert unmarried < married


def test_the_unmarried_conjunta_branch_is_the_thing_being_exercised() -> None:
    """Pins the derivation input directly, so the branch cannot go unentered.

    The engine assertions above run through several layers; this one names the
    predicate. Replacing the conjunta branch's return with a constant flips
    exactly this pair.
    """
    conjunta = _valenciana_conjunta()
    assert second_entitled_filer_indicated(conjunta) is True
    assert (
        second_entitled_filer_indicated({**conjunta, "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value})
        is False
    )


def test_the_printed_conjunta_total_is_a_recorded_gap_not_an_expectation() -> None:
    """The engine cannot yet reach 6.550, and the fixture must not claim it can.

    AEAT prints 1.200 + 1.350 + 4.000: hijos 1º and 2º prorated, hijo 3º WHOLE.
    The third child sits inside this joint return, whose rentas exceed the
    norma 2ª figure, which bars the OTHER progenitor and leaves sole
    entitlement for that child alone. Per-descendant unidad-familiar membership
    is not a fact the profile carries, so the engine prorates all three and
    lands below the printed figure -- an under-grant, the safe direction, and
    far better than the over-grant it replaced.

    Asserts the fixture does NOT list the conjunta figure as an expectation,
    which is what keeps the shortfall an honest recorded gap rather than a
    silent one. The moment membership becomes expressible, this test is what
    says the fixture may claim it.
    """
    payload = read_manual_worked_example(_VALENCIANA_ORACLE)
    assert set(payload.expected_by_casilla_id) == {"0513"}
    assert Decimal(payload.expected_by_casilla_id["0513"]) == Decimal("2550"), (
        "the grounded expectation is the individual case"
    )
    assert "6.550" in payload.notes, "the printed conjunta figure must stay recorded as evidence"


# ---------------------------------------------------------------------------
# One predicate, three consuming surfaces.
# ---------------------------------------------------------------------------


def test_the_same_predicate_change_moves_both_aggregates_together() -> None:
    """Estatal and autonómico are driven by one predicate, proven on a real oracle.

    Asturias exercised no normative competence, so the two casillas must agree
    exactly — both when the prorrateo applies and when it does not. A predicate
    wired into only one of the two injectors fails this.
    """
    individual = _aggregates({**_asturias_children(), "renta_filing.declaration_type": "1"})
    conjunta = _aggregates({**_asturias_children(), "renta_filing.declaration_type": "2"})
    assert individual[0] == individual[1]
    assert conjunta[0] == conjunta[1]
    assert individual[0] != conjunta[0]


def test_the_anualidades_flag_consumes_the_same_eligibility_predicate() -> None:
    """The third consumer moves with the other two, in the opposite direction.

    A descendant excluded by the Art. 58.1 cap generates no mínimo, so the payer
    IS sin derecho and the Art. 64/75 separate escala applies (flag 1). Dropping
    the exclusion restores the mínimo and withdraws the régimen (flag 0), which
    is the mutation pair proving the flag reads the predicate rather than a
    constant.
    """
    key = f"renta_family.anualidades_sin_minimo_descendientes_{_ORACLE_YEAR}"

    excluded: dict[str, UserProfileFactValue] = {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 10}-01-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
        "renta_family.descendiente.0.rentas_anuales": "8001",
    }
    narrowed_excluded: Any = excluded
    inject_derived_anualidades_eligibility_facts(narrowed_excluded, _snapshot())
    assert excluded[key] == Decimal("1")

    eligible: dict[str, UserProfileFactValue] = {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 10}-01-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    narrowed_eligible: Any = eligible
    inject_derived_anualidades_eligibility_facts(narrowed_eligible, _snapshot())
    assert eligible[key] == Decimal("0")


# ---------------------------------------------------------------------------
# Oracle C, adopcion - Art. 58.2's age-independent limb.
# ---------------------------------------------------------------------------


def _rioja_adopted_child(*, adoption_year: int) -> dict[str, UserProfileFactValue]:
    """Ejemplo 6's child: five years old, adopted, cohabiting.

    *adoption_year* is a parameter rather than a constant so the window's far
    edge can be probed with the same household. The birth date is held fixed at
    five years before the filing year, so age never satisfies the ordinary limb
    and only the adopcion limb can grant the increase.
    """
    return {
        "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 5}-01-01",
        "renta_family.descendiente.0.inscripcion_registro_civil": f"{adoption_year}-05-05",
        "renta_family.descendiente.0.convivencia": "true",
    }


def test_an_adopted_child_over_three_takes_the_printed_supplement() -> None:
    """AEAT grants the bajo-3-anos increase to a FIVE-year-old, and prints the figure.

    The whole point of Art. 58.2's second sentence: adoption suspends the age
    test for the inscription period and the two following. The engine tested
    only ``age_at_year_end < 3`` before this, so it returned the bare tranche
    and the 2.800 was silently lost for three consecutive years.
    """
    estatal, _ = _aggregates(_rioja_adopted_child(adoption_year=_ORACLE_YEAR))
    assert estatal == _expected(_RIOJA_ORACLE, "0513")


def test_both_rioja_casillas_carry_the_printed_descendientes_figure() -> None:
    """La Rioja diverged on the discapacidad minimo only, so 0514 equals 0513 here.

    Asserted rather than assumed: the manual's nota (3) puts the 3.000/3.300
    divergence on the discapacidad concept, and both columns print the
    descendientes rows identically. If a future revision wired a Rioja
    descendientes table this would fail rather than quietly diverge.
    """
    estatal, autonomico = _aggregates(_rioja_adopted_child(adoption_year=_ORACLE_YEAR))
    assert autonomico == _expected(_RIOJA_ORACLE, "0514")
    assert autonomico == estatal


def test_the_supplement_lapses_once_the_third_period_has_passed() -> None:
    """Anti-tautology pair: the window is bounded, so a stale adoption grants nothing.

    Art. 58.2 gives the inscription period "y en los dos siguientes" -- three
    periods, not indefinitely. A predicate that granted on the mere presence of
    an adoption date would pass the test above and fail this one.
    """
    inside, _ = _aggregates(_rioja_adopted_child(adoption_year=_ORACLE_YEAR - 2))
    outside, _ = _aggregates(_rioja_adopted_child(adoption_year=_ORACLE_YEAR - 3))
    assert inside == _expected(_RIOJA_ORACLE, "0513")
    assert outside < inside


def test_a_child_over_three_without_an_adoption_date_takes_no_supplement() -> None:
    """The tutela guard, and the reason this limb keys on the inscription date.

    Art. 58.1 assimilates "tutela y acogimiento"; Art. 58.2's age-independent
    sentence names "adopcion o acogimiento" and NOT tutela. A descendant under
    tutela therefore generates the tranche but never this increase. Keying the
    limb on ``inscripcion_registro_civil_date`` -- the Registro Civil
    inscription that both anchors the window and infers the adoptado
    relación, and which a tutela placement does not have -- is what keeps
    that outcome correct without a relationship-kind fact.
    """
    facts = _rioja_adopted_child(adoption_year=_ORACLE_YEAR)
    del facts["renta_family.descendiente.0.inscripcion_registro_civil"]
    estatal, _ = _aggregates(facts)
    assert estatal < _expected(_RIOJA_ORACLE, "0513")


def test_the_ordinary_under_three_limb_still_grants_without_any_adoption() -> None:
    """The first limb is untouched: a biological under-three keeps the increase."""
    estatal, _ = _aggregates(
        {
            "renta_family.descendiente.0.birth_date": f"{_ORACLE_YEAR - 1}-01-01",
            "renta_family.descendiente.0.convivencia": "true",
        },
    )
    assert estatal == _expected(_RIOJA_ORACLE, "0513")
