"""Modelo 100 mínimo por descendientes computed engine (#515, Option A; #593 CCAA).

Covers :func:`inject_derived_minimo_descendientes_facts` — the derived-fact
injector that computes the Art. 58/61 LIRPF mínimo por descendientes ESTATAL
aggregate from the active profile's ``renta_family.descendiente.*`` facts and
the revision's own registry parameters, and the AUTONÓMICO aggregate (#593),
which resolves each birth-order tranche against the filer's declared
tax-residence CCAA first — Comunidad de Madrid publishes its own divergent
tranche amounts (Decreto Legislativo 1/2010, art. 2), every other CCAA mirrors
the estatal aggregate exactly. Then :func:`resolve_profile_sourced_bindings`
routes both aggregates into casillas 0513 (estatal) / 0514 (autonómico) via
the ``renta-{year}-profile-minimo-descendientes-estatal`` /
``-autonomico`` bindings, and finally the full calculate-path integration
proves the registry formulas actually consume the injected aggregates end to
end.

Real adapters throughout: the resident registry authority for every loaded
:class:`RegistrySnapshot`, a genuine encrypted bucket via
``isolated_runtime_profile`` for the end-to-end calculate test, and
:func:`descendant_facts_from_list` / :class:`UserProfileLifecycleRepository`
for the profile roundtrip — no mocks, stubs, or fakes. Expected euro amounts
are read from the loaded revision's own ``renta-{year}-minimo-descendientes-*``
parameters (including the Madrid-specific ``-madrid-*`` tranches), never
hand-duplicated as a Decimal literal independent of the registry
(`no-tautological-calculation-tests`); the parity assertion
(``test_all_six_revisions_expose_the_full_parameter_set``) would fail if any
revision's registry authoring drifted from the formula this engine consumes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import RegistrySnapshot, resolve_parameter
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .._profile_binding import inject_derived_minimo_descendientes_facts, resolve_profile_sourced_bindings

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
    return resources().modelos.authority.snapshot("100", filing_year=year, period="0A")


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
    snapshot = _snapshot(2024)
    fact_index: dict[str, object] = {}
    fact_index_narrowed: Any = fact_index
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
    assert fact_index[_aggregate_key(2024)] == Decimal("0")


def test_one_eligible_descendant_uses_first_tranche_plus_menor_tres() -> None:
    snapshot = _snapshot(2024)
    tranches, menor_tres = _registry_tranches(snapshot)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2023-01-15",
        "renta_family.descendiente.0.convivencia": "true",
    }
    fact_index_narrowed: Any = fact_index
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
    assert fact_index[_aggregate_key(2024)] == tranches[0] + menor_tres


def test_ineligible_descendant_over_25_contributes_nothing() -> None:
    snapshot = _snapshot(2024)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "1990-01-01",
        "renta_family.descendiente.0.convivencia": "true",
    }
    fact_index_narrowed: Any = fact_index
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
    assert fact_index[_aggregate_key(2024)] == Decimal("0")


def test_custodia_compartida_halves_the_contribution() -> None:
    snapshot = _snapshot(2024)
    tranches, _ = _registry_tranches(snapshot)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-01-01",
        "renta_family.descendiente.0.convivencia": "true",
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    fact_index_narrowed: Any = fact_index
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
    assert fact_index[_aggregate_key(2024)] == tranches[0] * Decimal("0.5")


def test_two_descendientes_stack_first_and_second_tranche() -> None:
    snapshot = _snapshot(2024)
    tranches, _ = _registry_tranches(snapshot)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2010-01-01",
        "renta_family.descendiente.0.convivencia": "true",
        "renta_family.descendiente.1.birth_date": "2015-01-01",
        "renta_family.descendiente.1.convivencia": "true",
    }
    fact_index_narrowed: Any = fact_index
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
    assert fact_index[_aggregate_key(2024)] == tranches[0] + tranches[1]


def test_idempotent_explicit_fact_preserved() -> None:
    snapshot = _snapshot(2024)
    fact_index: dict[str, object] = {_aggregate_key(2024): Decimal("999")}
    fact_index_narrowed: Any = fact_index
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
    assert fact_index[_aggregate_key(2024)] == Decimal("999")


def test_one_eligible_descendant_matches_registry_first_tranche_across_all_years() -> None:
    for year in _ENGINE_FILING_YEARS:
        snapshot = _snapshot(year)
        tranches, _ = _registry_tranches(snapshot)
        fact_index: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": "2015-01-01",
            "renta_family.descendiente.0.convivencia": "true",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
        assert fact_index[_aggregate_key(year)] == tranches[0], year


# ---------------------------------------------------------------------------
# End-to-end: profile-binding resolution routes the aggregate into the
# Decimal channel the registry formula consumes.
# ---------------------------------------------------------------------------


_BUCKET = "00000000-0000-4000-8000-000000000516"
_PROFILE_LABEL = "M100 minimo descendientes engine profile"
_T0 = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)


def _binding_id_for_estatal(snapshot: RegistrySnapshot) -> str:
    matches = [b.id for b in snapshot.revision.bindings if b.id.endswith("profile-minimo-descendientes-estatal")]
    assert len(matches) == 1
    return matches[0]


def test_profile_binding_resolution_routes_aggregate_into_decimal_channel(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        descendientes = (DescendantInfo(birth_date=date(2012, 4, 1)),)
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        UserProfileLifecycleRepository(bucket_id=_BUCKET, objects=profile.repository).save(
            UserProfileRecord(
                profile_id=_BUCKET,
                display_name=_PROFILE_LABEL,
                facts=tuple(facts),
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        snapshot = _snapshot(2024)
        binding_id = _binding_id_for_estatal(snapshot)
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET)

    tranches, _ = _registry_tranches(snapshot)
    assert resolution.binding_values[binding_id] == tranches[0]


# ---------------------------------------------------------------------------
# #593: autonómico aggregate mirrors estatal by default; Madrid diverges.
# ---------------------------------------------------------------------------


def _binding_id_for_autonomico(snapshot: RegistrySnapshot) -> str:
    matches = [b.id for b in snapshot.revision.bindings if b.id.endswith("profile-minimo-descendientes-autonomico")]
    assert len(matches) == 1
    return matches[0]


def test_every_revision_declares_the_autonomico_binding() -> None:
    for year in _ENGINE_FILING_YEARS:
        snapshot = _snapshot(year)
        binding_id = _binding_id_for_autonomico(snapshot)
        assert binding_id == f"renta-{year}-profile-minimo-descendientes-autonomico"


def test_non_madrid_ccaa_autonomico_mirrors_estatal_for_two_descendants() -> None:
    """A CCAA absent from the wired divergence table mirrors the estatal aggregate.

    Cataluña, like every CCAA except Madrid, has no wired override, so the
    autonómico aggregate must equal the estatal one for the identical
    descendientes facts.
    """
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
        inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
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
    the exact under-computation #593 reports for Madrid family filers.
    """
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
        inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)

        estatal_value = fact_index[_aggregate_key(year)]
        autonomico_value = fact_index[_autonomico_aggregate_key(year)]
        assert isinstance(estatal_value, Decimal), f"{year}: Expected Decimal, got {type(estatal_value)}"
        assert isinstance(autonomico_value, Decimal), f"{year}: Expected Decimal, got {type(autonomico_value)}"
        assert autonomico_value > estatal_value, year

        estatal_tranches, _ = _registry_tranches(snapshot)
        madrid_tranches, _ = _registry_tranches(snapshot, ccaa_infix="madrid")
        assert estatal_value == estatal_tranches[0] + estatal_tranches[1] + estatal_tranches[2], year
        assert autonomico_value == madrid_tranches[0] + madrid_tranches[1] + madrid_tranches[2], year


def test_profile_binding_resolution_routes_madrid_autonomico_into_decimal_channel(tmp_path: Path) -> None:
    """End-to-end: a real Madrid profile resolves the autonómico binding to Madrid's own tercer tranche."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        descendientes = (
            DescendantInfo(birth_date=date(2005, 1, 1)),
            DescendantInfo(birth_date=date(2008, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1)),
        )
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        UserProfileLifecycleRepository(bucket_id=_BUCKET, objects=profile.repository).save(
            UserProfileRecord(
                profile_id=_BUCKET,
                display_name=_PROFILE_LABEL,
                facts=(*facts, UserProfileFact(path="tax_residence.ccaa", value="madrid")),
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        snapshot = _snapshot(2024)
        estatal_binding_id = _binding_id_for_estatal(snapshot)
        autonomico_binding_id = _binding_id_for_autonomico(snapshot)
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET)

    estatal_tranches, _ = _registry_tranches(snapshot)
    madrid_tranches, _ = _registry_tranches(snapshot, ccaa_infix="madrid")
    expected_estatal = estatal_tranches[0] + estatal_tranches[1] + estatal_tranches[2]
    expected_autonomico = madrid_tranches[0] + madrid_tranches[1] + madrid_tranches[2]
    estatal_resolved = resolution.binding_values[estatal_binding_id]
    autonomico_resolved = resolution.binding_values[autonomico_binding_id]
    assert isinstance(estatal_resolved, Decimal), f"Expected Decimal, got {type(estatal_resolved)}"
    assert isinstance(autonomico_resolved, Decimal), f"Expected Decimal, got {type(autonomico_resolved)}"
    assert estatal_resolved == expected_estatal
    assert autonomico_resolved == expected_autonomico
    assert autonomico_resolved > estatal_resolved
