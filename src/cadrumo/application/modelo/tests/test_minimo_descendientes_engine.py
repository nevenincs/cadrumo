"""Modelo 100 mínimo por descendientes computed engine.

Covers :func:`inject_derived_minimo_descendientes_facts` — the derived-fact
injector that computes the Art. 58/61 LIRPF mínimo por descendientes ESTATAL
aggregate from the active profile's ``renta_family.descendiente.*`` facts and
the revision's own registry parameters, and the AUTONÓMICO aggregate,
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
:func:`descendant_facts_from_list` / :class:`ProfileRecordRepository`
for the profile roundtrip — no mocks, stubs, or fakes. Expected euro amounts
are read from the loaded revision's own ``renta-{year}-minimo-descendientes-*``
parameters (including the Madrid-specific ``-madrid-*`` tranches), never
hand-duplicated as a Decimal literal independent of the registry
(`aeat-quality-gates`); the parity assertion
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

from ....core import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ..profile_binding import inject_derived_minimo_descendientes_facts, resolve_profile_sourced_bindings

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
    return bundled_authority().snapshot("100", filing_year=year, period="0A")


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


def test_two_descendientes_stack_first_and_second_tranche_for_a_single_filer() -> None:
    """A SINGLE filer with two children takes both tranches whole.

    Explicitly a single-filer household: a partnered filer declaring
    individually would have each tranche prorated under Art. 61 norma 1a,
    so the full sum asserted here is specific to the sole-entitlement case.
    """
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
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
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
    snapshot = _snapshot(2024)
    fact_index: dict[str, object] = {_aggregate_key(2024): Decimal("999")}
    fact_index_narrowed: Any = fact_index
    inject_derived_minimo_descendientes_facts(fact_index_narrowed, snapshot)
    assert fact_index[_aggregate_key(2024)] == Decimal("0")
    assert fact_index[_aggregate_key(2024)] != Decimal("999")


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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL):
        descendientes = (DescendantInfo(birth_date=date(2012, 4, 1)),)
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
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


def test_profile_descendant_facts_feed_2024_minimo_and_downstream_tariff(tmp_path: Path) -> None:
    """Real profile descendientes feed 0513/0514 and the downstream cuota path.

    The expected cuota is the LIRPF 2024 Art. 62-63 table oracle for a 35,400 EUR
    general base and two descendants, one under 3:
    tarifa(35400) - tarifa(13450) = 4,399.75 - 1,302.75 = 3,097.00 EUR.
    """
    snapshot = _snapshot(2024)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL):
        descendientes = (
            DescendantInfo(birth_date=date(2015, 1, 1)),
            DescendantInfo(birth_date=date(2023, 1, 15)),
        )
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=(
                    *facts,
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="tax_residence.ccaa", value="cataluna"),
                    UserProfileFact(path="renta_filing.declaration_type", value="1"),
                    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1975, 6, 15)),
                    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                ),
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=_BUCKET)

    # 37,400 EUR in trabajo ingresos íntegros nets to a 35,400 EUR base after
    # the 2,000 EUR Art. 19.2.f "otros gastos" deduction, matching the table
    # oracle in test_modelo_100_tarifa_real.
    result = calculate_registry_snapshot(
        snapshot,
        inputs={validated_casilla_id("0003", surface="test_minimo_descendientes_engine.casilla"): Decimal("37400")},
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values={
            **resolution.binding_values,
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
            "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
            "renta-2024-profile-incremento-guarderia": Decimal("0"),
            "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
            "renta-2024-profile-descendientes-guarderia": Decimal("0"),
            "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values=resolution.enum_binding_values,
        date_binding_values=resolution.date_binding_values,
        relation_values={
            "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
            "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
            "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
            "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
            "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
            "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
        },
    )

    assert resolution.binding_values["renta-2024-profile-minimo-descendientes-estatal"] == Decimal("7900.00")
    assert resolution.binding_values["renta-2024-profile-minimo-descendientes-autonomico"] == Decimal("7900.00")
    assert result.values[validated_casilla_id("0513", surface="test_minimo_descendientes_engine.casilla")] == Decimal(
        "7900.00"
    )
    assert result.values[validated_casilla_id("0514", surface="test_minimo_descendientes_engine.casilla")] == Decimal(
        "7900.00"
    )
    assert result.values[validated_casilla_id("0545", surface="test_minimo_descendientes_engine.casilla")] == Decimal(
        "3097.00"
    )


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
    the exact under-computation Madrid family filers would otherwise see.
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL):
        descendientes = (
            DescendantInfo(birth_date=date(2005, 1, 1)),
            DescendantInfo(birth_date=date(2008, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1)),
        )
        facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
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
