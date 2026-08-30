"""Art. 58.1 / Art. 61 LIRPF eligibility conditions on the mínimo por descendientes.

The derivation used to test only cohabitation and age, so a descendant earning
above the Art. 58.1 ceiling, or filing their own return above the Art. 61
norma 2ª figure, still generated a full mínimo — an inflated allowance that
reduces the base and under-declares the tax. Art. 61 norma 1ª was likewise read
as the custodia-compartida rule rather than the entitlement rule it states, so
two cohabiting parents filing individually each claimed the whole amount.

Every expected figure below is the AEAT-published Art. 58 tranche read from the
revision's OWN registry parameters, combined only by the arithmetic the AEAT
Renta manual states in prose ("2.400 euros anuales por el primero", the
menor-3 "aumentará en 2.800 euros anuales", the norma 1ª "se prorrateará entre
ellos por partes iguales"). Nothing here re-derives an expected value from the
formula under test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.family_profile import RentaFamilyProfile
from ....domain.contribuyente.family_types import MinimoDescendientesThresholds
from ....domain.contribuyente.renta_codes import RentaMaritalStatus
from ..profile_binding import (
    inject_derived_anualidades_eligibility_facts,
    inject_derived_minimo_descendientes_facts,
    second_entitled_filer_indicated,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ENGINE_FILING_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


def _snapshot(year: int) -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=year, period="0A")


def _parameter(snapshot: RegistrySnapshot, suffix: str) -> Decimal:
    year = snapshot.filing_year
    by_id = {p.id: p for p in snapshot.revision.parameters}
    return resolve_parameter(
        by_id[f"renta-{year}-minimo-descendientes-{suffix}-{year}"],
        {"filing_period": date(year, 12, 31)},
    )


def _thresholds(snapshot: RegistrySnapshot) -> MinimoDescendientesThresholds:
    return MinimoDescendientesThresholds(
        rentas_anuales_limite=_parameter(snapshot, "rentas-anuales-limite"),
        declaracion_propia_rentas_limite=_parameter(snapshot, "declaracion-propia-rentas-limite"),
    )


def _estatal_key(year: int) -> str:
    return f"renta_family.descendientes_minimos_aggregate_{year}"


def _autonomico_key(year: int) -> str:
    return f"renta_family.descendientes_minimos_aggregate_autonomico_{year}"


def _inject(facts: dict[str, object], snapshot: RegistrySnapshot) -> None:
    narrowed: Any = facts
    inject_derived_minimo_descendientes_facts(narrowed, snapshot)


# ---------------------------------------------------------------------------
# The two thresholds are registry-grounded for every supported year.
# ---------------------------------------------------------------------------


def test_every_revision_publishes_both_eligibility_thresholds() -> None:
    """The ceilings are registry parameters, never Python literals.

    Their VALUES are asserted against the LIRPF text in the registry's own
    grounding gate; here the contract is that every engine-supported revision
    exposes both so the predicate is never evaluated against a missing ceiling.
    """
    for year in _ENGINE_FILING_YEARS:
        thresholds = _thresholds(_snapshot(year))
        assert thresholds.rentas_anuales_limite > 0, year
        assert thresholds.declaracion_propia_rentas_limite > 0, year


# ---------------------------------------------------------------------------
# Art. 58.1 rentas ceiling.
# ---------------------------------------------------------------------------


def test_descendant_above_rentas_cap_contributes_zero_to_both_aggregates() -> None:
    """A descendant over the Art. 58.1 ceiling generates no mínimo at all.

    Expected value is exact zero, which is what "no tenga rentas anuales,
    excluidas las exentas, superiores a 8.000 euros" means for a sole
    descendant: the condition fails, so the tranche never applies.
    """
    for year in _ENGINE_FILING_YEARS:
        snapshot = _snapshot(year)
        over_cap = _thresholds(snapshot).rentas_anuales_limite + Decimal("1")
        facts: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
            "renta_family.descendiente.0.rentas_anuales": str(over_cap),
        }
        _inject(facts, snapshot)
        assert facts[_estatal_key(year)] == Decimal("0"), year
        assert facts[_autonomico_key(year)] == Decimal("0"), year


def test_descendant_exactly_at_the_cap_keeps_the_full_minimo() -> None:
    """Art. 58.1 excludes rentas "superiores a" the ceiling, so equality qualifies.

    Anti-tautology pair for the test above: the same machinery that returns
    zero one euro over the ceiling must return the full published first-child
    tranche exactly at it. A predicate using ``>=`` would fail here.
    """
    for year in _ENGINE_FILING_YEARS:
        snapshot = _snapshot(year)
        at_cap = _thresholds(snapshot).rentas_anuales_limite
        facts: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
            "renta_family.descendiente.0.rentas_anuales": str(at_cap),
        }
        _inject(facts, snapshot)
        assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo"), year


def test_undeclared_rentas_do_not_exclude() -> None:
    """An absent figure is not evidence of income.

    Pins the deliberate direction of the default: a descendant nobody has
    entered a rentas figure for keeps the mínimo, because the alternative would
    zero the allowance for every ordinary young child.
    """
    year = 2024
    snapshot = _snapshot(year)
    facts: dict[str, object] = {"renta_family.descendiente.0.birth_date": f"{year - 10}-05-01"}
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo")


def test_excluded_descendant_does_not_consume_a_birth_order_rank() -> None:
    """An excluded elder sibling must not push the younger one down a tranche.

    The AEAT manual ranks "el primero / el segundo" over descendants who
    GENERATE the mínimo. An excluded descendant generates none, so the younger
    child is "el primero" and takes the first tranche, not the second.
    """
    year = 2024
    snapshot = _snapshot(year)
    over_cap = _thresholds(snapshot).rentas_anuales_limite + Decimal("1")
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 20}-01-01",
        "renta_family.descendiente.0.rentas_anuales": str(over_cap),
        "renta_family.descendiente.1.birth_date": f"{year - 10}-01-01",
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo")


# ---------------------------------------------------------------------------
# Art. 61 norma 2a own-return exclusion.
# ---------------------------------------------------------------------------


def test_own_return_above_norma_2a_figure_excludes() -> None:
    """ "No procederá la aplicación del mínimo ... presenten declaración ... superiores a 1.800 euros"."""
    year = 2024
    snapshot = _snapshot(year)
    above = _thresholds(snapshot).declaracion_propia_rentas_limite + Decimal("1")
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_family.descendiente.0.rentas_anuales": str(above),
        "renta_family.descendiente.0.declaracion_propia": "true",
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == Decimal("0")


def test_own_return_at_or_below_norma_2a_figure_keeps_the_minimo() -> None:
    """The AEAT manual states the below-threshold case explicitly.

    "Si el descendiente presenta declaración individual del IRPF ... con rentas
    iguales o inferiores a 1.800 euros, los contribuyentes con derecho pueden
    aplicar el mínimo por descendientes." Filing a return is not disqualifying
    on its own.
    """
    year = 2024
    snapshot = _snapshot(year)
    at_figure = _thresholds(snapshot).declaracion_propia_rentas_limite
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_family.descendiente.0.rentas_anuales": str(at_figure),
        "renta_family.descendiente.0.declaracion_propia": "true",
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo")


def test_rentas_below_norma_2a_figure_without_own_return_keep_the_minimo() -> None:
    """Rentas alone are governed by the Art. 58.1 ceiling, not by norma 2ª.

    Isolates the two conditions: a descendant with rentas between the norma 2ª
    figure and the Art. 58.1 ceiling who files NO return keeps the full mínimo.
    """
    year = 2024
    snapshot = _snapshot(year)
    thresholds = _thresholds(snapshot)
    between = thresholds.declaracion_propia_rentas_limite + Decimal("1")
    assert between < thresholds.rentas_anuales_limite
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_family.descendiente.0.rentas_anuales": str(between),
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo")


# ---------------------------------------------------------------------------
# Art. 61 norma 1a prorrateo, generalised to the entitlement rule.
# ---------------------------------------------------------------------------


def test_two_entitled_filers_declaring_individually_each_take_half() -> None:
    """The ordinary two-parent household, and the largest gap this closes.

    Norma 1ª: "Cuando dos o más contribuyentes tengan derecho a la aplicación
    del mínimo por descendientes ... su importe se prorrateará entre ellos por
    partes iguales." Custody is not mentioned. Expected value is the published
    first-child tranche halved, per that sentence.
    """
    year = 2024
    snapshot = _snapshot(year)
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
        "renta_filing.declaration_type": "1",
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo") * Decimal("0.5")


def test_conjunta_return_is_not_prorated() -> None:
    """A tributación conjunta unit files once, so there is no second filer to share with.

    Anti-tautology pair for the test above: the same profile switched to a
    joint return must take the FULL tranche, proving the halving is driven by
    the individual-return signal rather than by marital status alone.
    """
    year = 2024
    snapshot = _snapshot(year)
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
        "renta_filing.declaration_type": "2",
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo")


def test_unpartnered_individual_filer_takes_the_full_minimo() -> None:
    """No signal of a second entitled contribuyente means no prorrateo."""
    year = 2024
    snapshot = _snapshot(year)
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_taxpayer.marital_status": RentaMaritalStatus.SOLTERO.value,
        "renta_filing.declaration_type": "1",
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo")


def test_explicit_override_beats_the_derivation_in_both_directions() -> None:
    """An operator answer always wins over the inference.

    Both directions are asserted from the same partnered-individual profile, so
    neither outcome can be produced by the derivation alone.
    """
    year = 2024
    snapshot = _snapshot(year)
    full = _parameter(snapshot, "primer-hijo")
    base: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
        "renta_filing.declaration_type": "1",
    }

    claims_full = {**base, "renta_family.descendiente.0.prorrata_minimo": "false"}
    _inject(claims_full, snapshot)
    assert claims_full[_estatal_key(year)] == full

    accepts_split = {**base, "renta_family.descendiente.0.prorrata_minimo": "true"}
    _inject(accepts_split, snapshot)
    assert accepts_split[_estatal_key(year)] == full * Decimal("0.5")


def test_shared_custody_still_prorates_without_any_partner_signal() -> None:
    """Custodia compartida is preserved as a trigger of the general rule."""
    year = 2024
    snapshot = _snapshot(year)
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
        "renta_taxpayer.marital_status": RentaMaritalStatus.SOLTERO.value,
        "renta_filing.declaration_type": "1",
    }
    _inject(facts, snapshot)
    assert facts[_estatal_key(year)] == _parameter(snapshot, "primer-hijo") * Decimal("0.5")


def test_second_filer_derivation_reads_a_spouse_record_when_status_is_absent() -> None:
    """A spouse record alone indicates a second entitled contribuyente."""
    assert second_entitled_filer_indicated({"renta_spouse.tax_id": "12345678Z"}) is True
    assert second_entitled_filer_indicated({}) is False


# ---------------------------------------------------------------------------
# The third consumer: the anualidades Art. 64/75 flag.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("year", _ENGINE_FILING_YEARS)
def test_anualidades_flag_reads_sin_derecho_for_a_capped_descendant(year: int) -> None:
    """The one gap in this file's coverage that over-taxes rather than under-declares.

    A descendant above the Art. 58.1 ceiling generates no mínimo, so the payer
    IS "sin derecho a la aplicación ... del mínimo por descendientes" and the
    Art. 64 separate escala applies — flag 1. Before the predicate carried the
    ceiling this profile read 0 and the régimen was denied.

    Parameterised over every engine year rather than pinned at 2024. The flag's
    DEFAULT already had six-year coverage; the corrected behaviour -- the flag
    flipping for a capped descendant -- did not, so the coverage claim was
    broader than the test. The ceiling is read from each year's own registry
    parameters, so this asserts the predicate is year-parameterised in fact and
    not only by construction.
    """
    snapshot = _snapshot(year)
    over_cap = _thresholds(snapshot).rentas_anuales_limite + Decimal("1")
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_family.descendiente.0.rentas_anuales": str(over_cap),
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    narrowed: Any = facts
    inject_derived_anualidades_eligibility_facts(narrowed, snapshot)
    assert facts[f"renta_family.anualidades_sin_minimo_descendientes_{year}"] == Decimal("1")


@pytest.mark.parametrize("year", _ENGINE_FILING_YEARS)
def test_anualidades_flag_still_reads_con_derecho_for_an_eligible_shared_custody_child(year: int) -> None:
    """Anti-tautology pair: drop the rentas figure and the flag flips back to 0.

    Parameterised alongside its partner. A pair whose halves cover different
    year ranges is not a pair: the anti-tautology guarantee would hold at 2024
    and be absent everywhere else, which is the shape that reads as covered.
    """
    snapshot = _snapshot(year)
    facts: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": f"{year - 10}-05-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    narrowed: Any = facts
    inject_derived_anualidades_eligibility_facts(narrowed, snapshot)
    assert facts[f"renta_family.anualidades_sin_minimo_descendientes_{year}"] == Decimal("0")


# ---------------------------------------------------------------------------
# Persistence round-trip for the three new per-descendant facts.
# ---------------------------------------------------------------------------


def test_new_facts_survive_a_serialisation_round_trip() -> None:
    """The predicate can only see these values if they persist and reload."""
    from ....domain.contribuyente.descendant_facts import descendant_facts_from_list, descendant_list_from_facts

    original = DescendantInfo(
        birth_date=date(2010, 5, 1),
        rentas_anuales_euros=Decimal("9500.55"),
        presenta_declaracion_propia=True,
        prorrata_minimo=False,
    )
    facts = dict(descendant_facts_from_list([original]))
    restored = descendant_list_from_facts(facts)
    assert restored == (original,)


def test_an_unreadable_rentas_figure_refuses_rather_than_restoring_the_minimo() -> None:
    """Anti-tautology proof for the round-trip: a corrupted figure must not read as absent.

    Silently dropping an unparseable figure would restore the full mínimo — the
    exact silent over-claim the Art. 58.1 ceiling exists to prevent.
    """
    from ....core.errors import ProfileAnswerTypeError
    from ....domain.contribuyente.descendant_facts import descendant_list_from_facts

    with pytest.raises(ProfileAnswerTypeError):
        descendant_list_from_facts(
            {
                "renta_family.descendiente.0.birth_date": "2010-05-01",
                "renta_family.descendiente.0.rentas_anuales": "not-a-number",
            },
        )


def test_profile_carrying_the_new_facts_produces_a_prorated_and_capped_aggregate() -> None:
    """End-to-end: three descendants, one capped, one excluded, one entitled and prorated.

    Expected value is the published first-child tranche halved. The two
    excluded descendants contribute nothing AND surrender their birth-order
    ranks, so the surviving child is "el primero".
    """
    year = 2024
    snapshot = _snapshot(year)
    thresholds = _thresholds(snapshot)
    profile = RentaFamilyProfile(
        descendientes=(
            DescendantInfo(
                birth_date=date(year - 22, 1, 1),
                rentas_anuales_euros=thresholds.rentas_anuales_limite + Decimal("1"),
            ),
            DescendantInfo(
                birth_date=date(year - 20, 1, 1),
                rentas_anuales_euros=thresholds.declaracion_propia_rentas_limite + Decimal("1"),
                presenta_declaracion_propia=True,
            ),
            DescendantInfo(birth_date=date(year - 8, 1, 1)),
        ),
    )
    total = profile.minimo_descendientes_estatal(
        year,
        birth_order_amounts=[
            _parameter(snapshot, "primer-hijo"),
            _parameter(snapshot, "segundo-hijo"),
            _parameter(snapshot, "tercer-hijo"),
            _parameter(snapshot, "cuarto-y-siguientes"),
        ],
        menor_tres_supplement=_parameter(snapshot, "menor-tres-anos"),
        fallecimiento_amount=_parameter(snapshot, "fallecimiento"),
        thresholds=thresholds,
        second_filer_indicated=True,
    )
    assert total == _parameter(snapshot, "primer-hijo") * Decimal("0.5")
