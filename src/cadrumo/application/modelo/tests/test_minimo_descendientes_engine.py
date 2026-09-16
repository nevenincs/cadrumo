"""Modelo 100 mínimo por descendientes computed engine.

Covers :func:`inject_derived_minimo_descendientes_facts` — the derived-fact
injector that computes the Art. 58/61 LIRPF mínimo por descendientes ESTATAL
aggregate from the active profile's ``renta_family.descendiente.*`` facts and
the revision's own registry parameters, and the AUTONÓMICO aggregate,
which resolves each birth-order tranche against the filer's declared
tax-residence CCAA first — Comunidad de Madrid publishes its own divergent
tranche amounts (Decreto Legislativo 1/2010, art. 2), every other CCAA mirrors
the estatal aggregate exactly. The application cases below prove the injector
routes both aggregates into the expected derived fact channels; profile-bound
binding and full calculate-path integration are owned by the outward profile
adapter test.

The engine and injector remain application policy tests: the resident registry
authority is the canonical source for every loaded :class:`RegistrySnapshot`,
while profile-bound persistence and calculate-path integration live in the
outward profile adapter test owner. Expected euro amounts
are read from the loaded revision's own ``renta-{year}-minimo-descendientes-*``
parameters (including the Madrid-specific ``-madrid-*`` tranches), never
hand-duplicated as a Decimal literal independent of the registry
(`aeat-quality-gates`); the parity assertion
(``test_all_six_revisions_expose_the_full_parameter_set``) would fail if any
revision's registry authoring drifted from the formula this engine consumes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..profile_binding import inject_derived_minimo_descendientes_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MINIMO_ESTATAL_ROLE = "irpf_minimo_descendientes_estatal"
_MINIMO_AUTONOMICO_ROLE = "irpf_minimo_descendientes_autonomico"
_ENGINE_FILING_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
# Years where Madrid's own table diverges only on the 3º/4º tranches (1º/2º/
# menor-3 coincide with the estatal Art. 58 figures per the bundled 2020/2021
# AEAT Renta manuals' own "Importante" note).
_MADRID_PARTIAL_DIVERGENCE_YEARS = (2020, 2021)
# Years where Madrid's own table diverges on all five tranches.
_MADRID_FULL_DIVERGENCE_YEARS = (2022, 2023, 2024, 2025)


@lru_cache
def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _aggregate_key(year: int) -> str:
    return f"renta_family.descendientes_minimos_aggregate_{year}"


def _autonomico_aggregate_key(year: int) -> str:
    return f"renta_family.descendientes_minimos_aggregate_autonomico_{year}"


def _registry_tranches(snapshot: RegistrySnapshot, *, ccaa_infix: str | None = None) -> tuple[list[Decimal], Decimal]:
    """Read the four birth-order amounts + menor-3 supplement from *snapshot*'s own params.

    When *ccaa_infix* is supplied, reads the CCAA-specific parameter for each
    tranche where the revision declares one (e.g. ``-madrid-``), falling back
    to the general Art. 58 parameter for any tranche the CCAA has not
    diverged on — mirroring the injector's own per-tranche fallback.
    """
    year = snapshot.filing_year
    suffixes = ("primer-hijo", "segundo-hijo", "tercer-hijo", "cuarto-y-siguientes")
    date_context = {"filing_period": date(year, 12, 31)}
    by_id = {p.id: p for p in snapshot.revision.parameters}

    def _resolve(suffix: str) -> Decimal:
        if ccaa_infix is not None:
            specific_id = f"renta-{year}-minimo-descendientes-{ccaa_infix}-{suffix}-{year}"
            if specific_id in by_id:
                return resolve_parameter(by_id[specific_id], date_context)
        return resolve_parameter(by_id[f"renta-{year}-minimo-descendientes-{suffix}-{year}"], date_context)

    tranches = [_resolve(suffix) for suffix in suffixes]
    menor_tres = _resolve("menor-tres-anos")
    return tranches, menor_tres


# ---------------------------------------------------------------------------
# Registry authoring parity: every engine-supported year exposes the full
# parameter set the injector depends on.
# ---------------------------------------------------------------------------


def test_all_six_revisions_expose_the_full_parameter_set() -> None:
    for year in _ENGINE_FILING_YEARS:
        snapshot = _snapshot(year)
        tranches, menor_tres = _registry_tranches(snapshot)
        assert len(tranches) == 4, year
        assert all(amount > 0 for amount in tranches), year
        assert menor_tres > 0, year


def test_estatal_and_autonomico_casillas_are_computed() -> None:
    for year in _ENGINE_FILING_YEARS:
        revision = _snapshot(year).revision
        estatal = next(c for c in revision.casillas if c.semantic_role == _MINIMO_ESTATAL_ROLE)
        autonomico = next(c for c in revision.casillas if c.semantic_role == _MINIMO_AUTONOMICO_ROLE)
        assert estatal.input_kind == "computed", year
        assert estatal.formula is not None, year
        assert autonomico.input_kind == "computed", year
        assert autonomico.formula is not None, year


# ---------------------------------------------------------------------------
# Derived-fact injector oracle: expected amounts read from the loaded
# revision's own parameters, not hand-duplicated literals.
# ---------------------------------------------------------------------------


def test_no_descendientes_facts_injects_legally_correct_zero() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        snapshot = _snapshot(2024)
        fact_index: dict[str, object] = {}
        fact_index_narrowed: Any = fact_index
        inject_derived_minimo_descendientes_facts(
            fact_index_narrowed, snapshot, operation=_authority_operation_for_test
        )
        assert fact_index[_aggregate_key(2024)] == Decimal("0")


def test_one_eligible_descendant_uses_first_tranche_plus_menor_tres() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        snapshot = _snapshot(2024)
        tranches, menor_tres = _registry_tranches(snapshot)
        fact_index: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": "2023-01-15",
            "renta_family.descendiente.0.convivencia": "true",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_minimo_descendientes_facts(
            fact_index_narrowed, snapshot, operation=_authority_operation_for_test
        )
        assert fact_index[_aggregate_key(2024)] == tranches[0] + menor_tres


def test_ineligible_descendant_over_25_contributes_nothing() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        snapshot = _snapshot(2024)
        fact_index: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": "1990-01-01",
            "renta_family.descendiente.0.convivencia": "true",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_minimo_descendientes_facts(
            fact_index_narrowed, snapshot, operation=_authority_operation_for_test
        )
        assert fact_index[_aggregate_key(2024)] == Decimal("0")


#: Signals that make a scenario an explicit SINGLE-FILER household.
#:
#: Art. 61 norma 1a prorates whenever a second contribuyente is also
#: entitled, and the engine derives that from marital status, a spouse
#: record and the declaration type. A scenario that declares NONE of those
#: exercises the unpartnered branch by omission, so it would assert a full
#: tranche while reading as an ordinary two-parent family. These fixtures
#: therefore say which household they model rather than leaving it to the
#: absence of a fact.
_SINGLE_FILER_HOUSEHOLD: dict[str, object] = {
    "renta_taxpayer.marital_status": "soltero",
    "renta_filing.declaration_type": "1",
}


def test_custodia_compartida_halves_the_contribution() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        snapshot = _snapshot(2024)
        tranches, _ = _registry_tranches(snapshot)
        fact_index: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": "2015-01-01",
            "renta_family.descendiente.0.convivencia": "true",
            "renta_family.descendiente.0.custodia_compartida": "true",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_minimo_descendientes_facts(
            fact_index_narrowed, snapshot, operation=_authority_operation_for_test
        )
        assert fact_index[_aggregate_key(2024)] == tranches[0] * Decimal("0.5")


def test_two_descendientes_stack_first_and_second_tranche_for_a_single_filer() -> None:
    """A SINGLE filer with two children takes both tranches whole.

    Explicitly a single-filer household: a partnered filer declaring
    individually would have each tranche prorated under Art. 61 norma 1a,
    so the full sum asserted here is specific to the sole-entitlement case.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        snapshot = _snapshot(2024)
        tranches, _ = _registry_tranches(snapshot)
        fact_index: dict[str, object] = {
            **_SINGLE_FILER_HOUSEHOLD,
            "renta_family.descendiente.0.birth_date": "2010-01-01",
            "renta_family.descendiente.0.convivencia": "true",
            "renta_family.descendiente.1.birth_date": "2015-01-01",
            "renta_family.descendiente.1.convivencia": "true",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_minimo_descendientes_facts(
            fact_index_narrowed, snapshot, operation=_authority_operation_for_test
        )
        assert fact_index[_aggregate_key(2024)] == tranches[0] + tranches[1]


def test_stored_fact_at_the_derived_path_is_overwritten_by_the_computation() -> None:
    """The Art. 58 computation wins over a value stored at the derived path.

    Inverted from the former idempotency test, which pinned the injector
    deferring to a stored fact. That deference was the override channel: a
    value written at the derived aggregate path suppressed the law's figure
    with no diagnostic. The injector now computes always.

    ``999`` remains the anti-tautology sentinel it was chosen to be -- the
    registry tranches and the menor-3 supplement are whole hundreds and every
    eligibility split is a halving, so no real Art. 58 arithmetic lands on it.
    The profile declares no descendants, so the computed answer is the
    legally-correct zero, and the assertion discriminates between the two.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        snapshot = _snapshot(2024)
        fact_index: dict[str, object] = {_aggregate_key(2024): Decimal("999")}
        fact_index_narrowed: Any = fact_index
        inject_derived_minimo_descendientes_facts(
            fact_index_narrowed, snapshot, operation=_authority_operation_for_test
        )
        assert fact_index[_aggregate_key(2024)] == Decimal("0")
        assert fact_index[_aggregate_key(2024)] != Decimal("999")


def test_one_eligible_descendant_matches_registry_first_tranche_across_all_years() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for year in _ENGINE_FILING_YEARS:
            snapshot = _snapshot(year)
            tranches, _ = _registry_tranches(snapshot)
            fact_index: dict[str, object] = {
                "renta_family.descendiente.0.birth_date": "2015-01-01",
                "renta_family.descendiente.0.convivencia": "true",
            }
            fact_index_narrowed: Any = fact_index
            inject_derived_minimo_descendientes_facts(
                fact_index_narrowed, snapshot, operation=_authority_operation_for_test
            )
            assert fact_index[_aggregate_key(year)] == tranches[0], year


# ---------------------------------------------------------------------------
# The autonómico aggregate mirrors estatal by default; Madrid diverges.
# ---------------------------------------------------------------------------


def _binding_id_for_autonomico(snapshot: RegistrySnapshot) -> str:
    matches = [b.id for b in snapshot.revision.bindings if b.id.endswith("profile-minimo-descendientes-autonomico")]
    assert len(matches) == 1
    return matches[0]


def test_every_revision_declares_the_autonomico_binding() -> None:
    for year in _ENGINE_FILING_YEARS:
        snapshot = _snapshot(year)
        binding_id = _binding_id_for_autonomico(snapshot)
        assert binding_id == "renta-profile-minimo-descendientes-autonomico"


def test_non_madrid_ccaa_autonomico_mirrors_estatal_for_two_descendants() -> None:
    """A CCAA absent from the wired divergence table mirrors the estatal aggregate.

    Cataluña, like every CCAA except Madrid, has no wired override, so the
    autonómico aggregate must equal the estatal one for the identical
    descendientes facts.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for year in _ENGINE_FILING_YEARS:
            snapshot = _snapshot(year)
            fact_index: dict[str, object] = {
                "tax_residence.ccaa": "cataluna",
                "renta_family.descendiente.0.birth_date": "2010-01-01",
                "renta_family.descendiente.0.convivencia": "true",
                "renta_family.descendiente.1.birth_date": "2015-06-01",
                "renta_family.descendiente.1.convivencia": "true",
            }
            fact_index_narrowed: Any = fact_index
            inject_derived_minimo_descendientes_facts(
                fact_index_narrowed, snapshot, operation=_authority_operation_for_test
            )
            assert fact_index[_aggregate_key(year)] == fact_index[_autonomico_aggregate_key(year)], year


def test_madrid_first_two_descendants_match_estatal_for_partial_divergence_years() -> None:
    """For 2020/2021 Madrid's 1º/2º tranches coincide with the estatal Art. 58 figures.

    Grounded in the bundled AEAT Renta 2020/2021 manuals' own "Importante"
    note: "las cuantías del mínimo por descendientes para el primer y segundo
    hijo ... coinciden con las fijadas artículo 58 de la Ley del IRPF".
    """
    for year in _MADRID_PARTIAL_DIVERGENCE_YEARS:
        snapshot = _snapshot(year)
        estatal_tranches, _ = _registry_tranches(snapshot)
        madrid_tranches, _ = _registry_tranches(snapshot, ccaa_infix="madrid")
        assert madrid_tranches[0] == estatal_tranches[0], year
        assert madrid_tranches[1] == estatal_tranches[1], year


def test_madrid_third_and_fourth_tranches_diverge_from_estatal_every_year() -> None:
    """Madrid's own tercer/cuarto-y-siguientes tranches diverge every engine year (DL 1/2010 art. 2)."""
    for year in _ENGINE_FILING_YEARS:
        snapshot = _snapshot(year)
        estatal_tranches, _ = _registry_tranches(snapshot)
        madrid_tranches, _ = _registry_tranches(snapshot, ccaa_infix="madrid")
        assert madrid_tranches[2] != estatal_tranches[2], year
        assert madrid_tranches[3] != estatal_tranches[3], year
        assert madrid_tranches[2] == Decimal("4400"), year
        assert madrid_tranches[3] == Decimal("4950"), year


def test_madrid_all_tranches_and_menor_tres_diverge_for_full_divergence_years() -> None:
    """From 2022 Madrid's own table diverges on every tranche including menor-3."""
    for year in _MADRID_FULL_DIVERGENCE_YEARS:
        snapshot = _snapshot(year)
        estatal_tranches, estatal_menor_tres = _registry_tranches(snapshot)
        madrid_tranches, madrid_menor_tres = _registry_tranches(snapshot, ccaa_infix="madrid")
        for madrid_amount, estatal_amount in zip(madrid_tranches, estatal_tranches, strict=True):
            assert madrid_amount != estatal_amount, year
        assert madrid_menor_tres != estatal_menor_tres, year


def test_madrid_resident_three_descendants_autonomico_exceeds_estatal() -> None:
    """A Madrid-resident filer with 3 descendants gets a higher autonómico aggregate.

    Three descendants trigger the diverging tercer tranche in every engine
    year; the autonómico aggregate (Madrid tranches) must exceed the estatal
    one (general Art. 58 tranches) for the identical descendientes facts —
    the exact under-computation Madrid family filers would otherwise see.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for year in _ENGINE_FILING_YEARS:
            snapshot = _snapshot(year)
            fact_index: dict[str, object] = {
                "tax_residence.ccaa": "madrid",
                "renta_family.descendiente.0.birth_date": "2005-01-01",
                "renta_family.descendiente.0.convivencia": "true",
                "renta_family.descendiente.1.birth_date": "2008-01-01",
                "renta_family.descendiente.1.convivencia": "true",
                "renta_family.descendiente.2.birth_date": "2012-01-01",
                "renta_family.descendiente.2.convivencia": "true",
            }
            fact_index_narrowed: Any = fact_index
            inject_derived_minimo_descendientes_facts(
                fact_index_narrowed, snapshot, operation=_authority_operation_for_test
            )

            estatal_value = fact_index[_aggregate_key(year)]
            autonomico_value = fact_index[_autonomico_aggregate_key(year)]
            assert isinstance(estatal_value, Decimal), f"{year}: Expected Decimal, got {type(estatal_value)}"
            assert isinstance(autonomico_value, Decimal), f"{year}: Expected Decimal, got {type(autonomico_value)}"
            assert autonomico_value > estatal_value, year

            estatal_tranches, _ = _registry_tranches(snapshot)
            madrid_tranches, _ = _registry_tranches(snapshot, ccaa_infix="madrid")
            assert estatal_value == estatal_tranches[0] + estatal_tranches[1] + estatal_tranches[2], year
            assert autonomico_value == madrid_tranches[0] + madrid_tranches[1] + madrid_tranches[2], year
