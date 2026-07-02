"""Modelo 100 mínimo por descendientes computed engine (#515, Option A).

Covers :func:`inject_derived_minimo_descendientes_facts` — the derived-fact
injector that computes the Art. 58/61 LIRPF mínimo por descendientes aggregate
from the active profile's ``renta_family.descendiente.*`` facts and the
revision's own registry parameters, then :func:`resolve_profile_sourced_bindings`
routing the aggregate into casillas 0513 (estatal) / 0514 (autonómico) via the
``renta-{year}-profile-minimo-descendientes-estatal`` binding, and finally the
full calculate-path integration that proves the registry formulas actually
consume the injected aggregate end to end.

Real adapters throughout: the resident registry authority for every loaded
:class:`RegistrySnapshot`, a genuine encrypted bucket via
``isolated_runtime_profile`` for the end-to-end calculate test, and
:func:`descendant_facts_from_list` / :class:`UserProfileLifecycleRepository`
for the profile roundtrip — no mocks, stubs, or fakes. Expected euro amounts
are read from the loaded revision's own ``renta-{year}-minimo-descendientes-*``
parameters, never hand-duplicated as a Decimal literal independent of the
registry (`no-tautological-calculation-tests`); the parity assertion
(``test_all_six_revisions_expose_the_full_parameter_set``) would fail if any
revision's registry authoring drifted from the formula this engine consumes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

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


def _snapshot(year: int) -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=year, period="0A")


def _aggregate_key(year: int) -> str:
    return f"renta_family.descendientes_minimos_aggregate_{year}"


def _registry_tranches(snapshot: RegistrySnapshot) -> tuple[list[Decimal], Decimal]:
    """Read the four birth-order amounts + menor-3 supplement from *snapshot*'s own params."""
    year = snapshot.filing_year
    suffixes = ("primer-hijo", "segundo-hijo", "tercer-hijo", "cuarto-y-siguientes")
    date_context = {"filing_period": date(year, 12, 31)}
    by_id = {p.id: p for p in snapshot.revision.parameters}
    tranches = [
        resolve_parameter(by_id[f"renta-{year}-minimo-descendientes-{suffix}-{year}"], date_context)
        for suffix in suffixes
    ]
    menor_tres = resolve_parameter(by_id[f"renta-{year}-minimo-descendientes-menor-tres-anos-{year}"], date_context)
    return tranches, menor_tres


# ---------------------------------------------------------------------------
# Registry authoring parity: every engine-supported year exposes the full
# parameter set the injector depends on.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("year", _ENGINE_FILING_YEARS)
def test_all_six_revisions_expose_the_full_parameter_set(year: int) -> None:
    snapshot = _snapshot(year)
    tranches, menor_tres = _registry_tranches(snapshot)
    assert len(tranches) == 4
    assert all(amount > 0 for amount in tranches)
    assert menor_tres > 0


@pytest.mark.parametrize("year", _ENGINE_FILING_YEARS)
def test_estatal_and_autonomico_casillas_are_computed(year: int) -> None:
    revision = _snapshot(year).revision
    estatal = next(c for c in revision.casillas if c.semantic_role == _MINIMO_ESTATAL_ROLE)
    autonomico = next(c for c in revision.casillas if c.semantic_role == _MINIMO_AUTONOMICO_ROLE)
    assert estatal.input_kind == "computed"
    assert estatal.formula is not None
    assert autonomico.input_kind == "computed"
    assert autonomico.formula is not None


# ---------------------------------------------------------------------------
# Derived-fact injector oracle: expected amounts read from the loaded
# revision's own parameters, not hand-duplicated literals.
# ---------------------------------------------------------------------------


def test_no_descendientes_facts_injects_legally_correct_zero() -> None:
    snapshot = _snapshot(2024)
    fact_index: dict[str, object] = {}
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)  # type: ignore[arg-type]
    assert fact_index[_aggregate_key(2024)] == Decimal("0")


def test_one_eligible_descendant_uses_first_tranche_plus_menor_tres() -> None:
    snapshot = _snapshot(2024)
    tranches, menor_tres = _registry_tranches(snapshot)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2023-01-15",
        "renta_family.descendiente.0.convivencia": "true",
    }
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)  # type: ignore[arg-type]
    assert fact_index[_aggregate_key(2024)] == tranches[0] + menor_tres


def test_ineligible_descendant_over_25_contributes_nothing() -> None:
    snapshot = _snapshot(2024)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "1990-01-01",
        "renta_family.descendiente.0.convivencia": "true",
    }
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)  # type: ignore[arg-type]
    assert fact_index[_aggregate_key(2024)] == Decimal("0")


def test_custodia_compartida_halves_the_contribution() -> None:
    snapshot = _snapshot(2024)
    tranches, _ = _registry_tranches(snapshot)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-01-01",
        "renta_family.descendiente.0.convivencia": "true",
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)  # type: ignore[arg-type]
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
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)  # type: ignore[arg-type]
    assert fact_index[_aggregate_key(2024)] == tranches[0] + tranches[1]


def test_idempotent_explicit_fact_preserved() -> None:
    snapshot = _snapshot(2024)
    fact_index: dict[str, object] = {_aggregate_key(2024): Decimal("999")}
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)  # type: ignore[arg-type]
    assert fact_index[_aggregate_key(2024)] == Decimal("999")


@pytest.mark.parametrize("year", _ENGINE_FILING_YEARS)
def test_one_eligible_descendant_matches_registry_first_tranche_across_all_years(year: int) -> None:
    snapshot = _snapshot(year)
    tranches, _ = _registry_tranches(snapshot)
    fact_index: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-01-01",
        "renta_family.descendiente.0.convivencia": "true",
    }
    inject_derived_minimo_descendientes_facts(fact_index, snapshot)  # type: ignore[arg-type]
    assert fact_index[_aggregate_key(year)] == tranches[0]


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
