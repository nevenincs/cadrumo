"""E2E enrollment: Modelo 200 (IS) cross-year art.13 dotaciones-deterioro carry.

A dotación por deterioro de créditos whose deducibility conditions (LIS art.
13.1: 6-month overdue / concurso / alzamiento / judicial claim) are not yet met
stays pending and carries to future periods. The end-of-year stock "pendiente de
integración en períodos futuros" — casilla 01498 (que NO han cumplido
condiciones) / 01499 (que SÍ han cumplido) — becomes the next ejercicio's stock
"pendiente de integración a principio del período" — casilla 01494 / 01495 —
tracked SEPARATELY per condition-state because only the cumplido stock may be
integrated. Two cross-year ``previous_filing`` bindings
(``modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores``
copies prior 01498 → 01494; the ``...-cumplido-anteriores`` copies prior 01499 →
01495) make those opening-stock casillas auto-resolve from the prior filing — the
operator does not re-key the carried dotación stock.

Grounding (non-tautological): the prior-year saldo final (01498/01499) is a
manual input the test supplies (no formula under test produces it at the Total
level — the per-generation detalle does, deferred to the option-B aggregation
pass); the assertion is the cross-year WIRING invariant — year N's opening stock
equals year N-1's persisted closing stock, per condition-state, year-isolated —
which LIS art. 13 establishes as the carry of the pending deterioro balance. The
saldo final 01498/01499 and the elective integrated amount 01496 stay
operator-input; this enrollment proves the STOCK carry, not a computed identity.

The cross-year hook relies on the previous_filing observation-coverage validator
semantics: because the repository validates every filed observation against a
real Modelo 200 revision, this test uses target years whose prior source years
are also modelled. Unsupported historical years must fail closed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id
from ....core.resources import resources
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation, resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.ids import RelationId
from cadrumo.domain.calculations.registry.relations import materialize_relation_binding_values
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .._binding_prefill import resolve_bindings_from_local_store
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_200 = "200"

#: Cross-year art.13 dotaciones-deterioro carry casillas (Total block, page-020d).
_SALDO_FINAL_NO_CUMPLIDO: CasillaId = validated_casilla_id(
    "01498",
    surface="_SALDO_FINAL_NO_CUMPLIDO",
)  # end-of-year pending, conditions NOT met
_SALDO_FINAL_CUMPLIDO: CasillaId = validated_casilla_id(
    "01499",
    surface="_SALDO_FINAL_CUMPLIDO",
)  # end-of-year pending, conditions met
_SALDO_INICIAL_NO_CUMPLIDO: CasillaId = validated_casilla_id(
    "01494",
    surface="_SALDO_INICIAL_NO_CUMPLIDO",
)  # opening pending no-cumplido (bound from prior 01498)
_SALDO_INICIAL_CUMPLIDO: CasillaId = validated_casilla_id(
    "01495",
    surface="_SALDO_INICIAL_CUMPLIDO",
)  # opening pending cumplido (bound from prior 01499)

_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

#: Distinct prior-year stock per source year + condition-state so a cross-year
#: contamination (or a condition-state channel swap) surfaces.
_STOCK_BY_SOURCE_YEAR: dict[int, dict[CasillaId, Decimal]] = {
    2024: {_SALDO_FINAL_NO_CUMPLIDO: Decimal("8000.00"), _SALDO_FINAL_CUMPLIDO: Decimal("5000.00")},
    2025: {_SALDO_FINAL_NO_CUMPLIDO: Decimal("3000.00"), _SALDO_FINAL_CUMPLIDO: Decimal("12000.00")},
}

_M200_PAGOS_RELATION = "modelo-200-2024-rel-202-pagos-fraccionados"
_M200_PAGOS_RELATION_40_2 = "modelo-200-2024-rel-202-pagos-fraccionados-40-2"

_PROFILE_DECIMAL_BINDINGS: dict[str, Decimal] = {
    "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
    "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
    "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
}
_PROFILE_ENUM_BINDINGS: dict[str, str] = {"modelo-200-2024-profile-legal-entity-form": "sl"}

_CLOCK = datetime(2027, 1, 20, 9, 0, 0, tzinfo=UTC)


def _seed_prior_saldo_final(*, source_year: int, obs_repo: CalculationObservationRepository) -> None:
    """Record a prior-year end-of-year dotaciones-deterioro saldo final (01498/01499)."""
    stock = _STOCK_BY_SOURCE_YEAR[source_year]
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=_MODELO_200,
                filing_year=source_year,
                period="0A",
                observations=registry_grounded_observations(
                    modelo=_MODELO_200,
                    filing_year=source_year,
                    period="0A",
                    casilla_values={
                        _SALDO_FINAL_NO_CUMPLIDO: stock[_SALDO_FINAL_NO_CUMPLIDO],
                        _SALDO_FINAL_CUMPLIDO: stock[_SALDO_FINAL_CUMPLIDO],
                    },
                    grade=RegistryAuthorityGrade.CALCULATION,
                ),
            ),
            source_kind="app_filing",
            captured_at=_CLOCK,
        )
    )


def _calculate_200(
    *,
    filing_year: int,
    relation_values: dict[RelationId, Decimal],
    obs_repo: CalculationObservationRepository,
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot(
        _MODELO_200, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    # Resolve every previous_filing binding (the art.13 dotaciones carry AND the
    # pre-existing BIN-stock 00670 carry) from the local observation store, so all
    # bound casillas have a fact. Bindings the store cannot satisfy default to
    # zero — the present-or-zero-carry semantics (a first-year filer has no prior
    # stock), leaving the available-value projector a complete carry set.
    prefilled = resolve_bindings_from_local_store(snapshot, repository=obs_repo).binding_values
    bound_binding_ids = {c.binding for c in snapshot.revision.casillas if c.input_kind.value == "bound" and c.binding}
    carry_defaults = {bid: Decimal("0") for bid in bound_binding_ids}
    binding_values = {**carry_defaults, **prefilled, **relation_binding_values, **_PROFILE_DECIMAL_BINDINGS}
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        enum_binding_values=_PROFILE_ENUM_BINDINGS,
        relation_values=relation_values,
        date_context={"filing_period": date(filing_year, 7, 25)},
    )


def _resolve_relations(*, filing_year: int, obs_repo: CalculationObservationRepository) -> dict[RelationId, Decimal]:
    snapshot = resources().modelos.authority.snapshot(
        _MODELO_200, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    resolved = {
        item.relation: item.value
        for item in resolve_relations_from_local_store(snapshot, repository=obs_repo).values
        if item.value is not None
    }
    resolved.setdefault(_M200_PAGOS_RELATION, Decimal("0"))
    resolved.setdefault(_M200_PAGOS_RELATION_40_2, Decimal("0"))
    return resolved


def test_opening_dotaciones_stock_resolves_from_prior_year_per_condition_state(tmp_path: Path) -> None:
    """01494/01495 auto-resolve to the prior year's 01498/01499, per condition-state.

    The cross-year continuity contract: once the prior M200 is recorded, the
    ``-1`` carry populates 01494 (no-cumplido) from prior 01498 and 01495
    (cumplido) from prior 01499 — distinct channels, no cross-contamination.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_prior_saldo_final(source_year=2024, obs_repo=obs_repo)
        resolved = _resolve_relations(filing_year=_YEAR_N, obs_repo=obs_repo)
        result = _calculate_200(filing_year=_YEAR_N, relation_values=resolved, obs_repo=obs_repo)
    assert Decimal(result.values[_SALDO_INICIAL_NO_CUMPLIDO]) == _STOCK_BY_SOURCE_YEAR[2024][_SALDO_FINAL_NO_CUMPLIDO]
    assert Decimal(result.values[_SALDO_INICIAL_CUMPLIDO]) == _STOCK_BY_SOURCE_YEAR[2024][_SALDO_FINAL_CUMPLIDO]
    # The two channels carry distinct values — a channel swap would surface here.
    assert result.values[_SALDO_INICIAL_NO_CUMPLIDO] != result.values[_SALDO_INICIAL_CUMPLIDO]


def test_dotaciones_stock_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end: art.13 dotaciones stock carry across two renta years.

    Year N's prior filing is in the store but must not contaminate Year N+1's
    resolver. A single-year or stub run raises at
    :func:`assert_enrollment_matches_manifest`.
    """
    recorder = EnrollmentRecorder(_MODELO_200)
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_prior_saldo_final(source_year=2024, obs_repo=obs_repo)
        _seed_prior_saldo_final(source_year=2025, obs_repo=obs_repo)

        resolved_n = _resolve_relations(filing_year=_YEAR_N, obs_repo=obs_repo)
        result_n = _calculate_200(filing_year=_YEAR_N, relation_values=resolved_n, obs_repo=obs_repo)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=len(result_n.values))

        resolved_n1 = _resolve_relations(filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        result_n1 = _calculate_200(filing_year=_YEAR_N_PLUS_1, relation_values=resolved_n1, obs_repo=obs_repo)
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=len(result_n1.values))

    assert Decimal(result_n.values[_SALDO_INICIAL_CUMPLIDO]) == _STOCK_BY_SOURCE_YEAR[2024][_SALDO_FINAL_CUMPLIDO]
    assert Decimal(result_n1.values[_SALDO_INICIAL_CUMPLIDO]) == _STOCK_BY_SOURCE_YEAR[2025][_SALDO_FINAL_CUMPLIDO]
    assert (
        Decimal(result_n1.values[_SALDO_INICIAL_NO_CUMPLIDO]) == _STOCK_BY_SOURCE_YEAR[2025][_SALDO_FINAL_NO_CUMPLIDO]
    )

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
