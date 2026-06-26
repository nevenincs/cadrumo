"""E2E continuity: Modelo 130 prior-quarter negative-result carry-forward.

The autónomo's full-year experience spans four quarterly Modelo 130
pago-fraccionado filings. RD 439/2007 art. 110 and the AEAT M130
instructions define a cross-quarter carry-forward: when a quarter's
liquidation result (casilla 19) is negative, its absolute value flows
into the *next* quarter's casilla 15 ("Resultados negativos de
trimestres anteriores") and is subtracted there. Casilla 15 is bound
via ``source = "previous_filing"`` (binding
``modelo-130-resultados-negativos-anteriores``), an ``op=copy`` of the
prior quarter's ``saldo-negativo-fin-periodo``.

The 303->390 annual reconciliation carry-forward is covered by
``test_binding_prefill``; the M130 quarter-to-quarter carry-forward —
the autónomo's most common continuity path — had no end-to-end coverage.
This module closes that gap.

The test drives the real continuity contract with real adapters (real
encrypted SQLite repos, the real registry authority, the real
``previous_filing`` resolver — no mocks): it computes a loss-making Q1,
records it as a prior-period observation, and asserts that Q2's
casilla 15 auto-resolves to Q1's carried saldo with no manual re-entry.

Grounding (non-tautological): the Q1 saldo is produced by the engine
from the loss scenario, not hand-computed; the assertion is the
*wiring* invariant — Q2's casilla 15 equals Q1's persisted
``saldo-negativo-fin-periodo`` — which the AEAT instruction defines as
the prior-quarter negative result carried forward "sin signo".
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import (
    BindingId,
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import CalculationRevision
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo import calculate_modelo_revision, create_work_unit
from .._binding_prefill import resolve_bindings_from_local_store
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
    CalculationObservationRepository,
]

_CLOCK = datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC)

_CARRY_FORWARD_BINDING: BindingId = "modelo-130-resultados-negativos-anteriores"
_PREV_YEAR_BINDING: BindingId = "irpf.previous_year_economic_activity_net_income"
_PRIOR_YEAR_NET_INCOME = Decimal("5000")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M130 carry-forward fixture casilla key {value!r} is not a CasillaId") from exc


_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")
_M130_PREVIOUS_PAYMENTS_CASILLA: CasillaId = _casilla_id("05")
_M130_RETENCIONES_CASILLA: CasillaId = _casilla_id("06")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = _casilla_id("07")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = _casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = _casilla_id("10")
_M130_CARRY_FORWARD_CASILLA: CasillaId = _casilla_id("15")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = _casilla_id("16")
_M130_DIFERENCIA_CASILLA: CasillaId = _casilla_id("17")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = _casilla_id("18")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = _casilla_id("saldo-negativo-fin-periodo")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = _casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = _casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = _casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = _casilla_id("1577")

# Loss-making Q1 scenario (empirically grounded against the engine):
#   ingresos 3000, gastos 1000 -> rendimiento neto 2000
#   casilla 04 = 20% * 2000 = 400 (statutory rate, RD 439/2007 art. 110.1.a)
#   retenciones 06 = 500 > 400 -> casilla 07 = -100 -> casilla 12 = max(0, -100) = 0
#   prior-year net income 5000 (<= 12000) -> minoración casilla 13 = 100
#   casilla 14 = 0 - 100 = -100 -> casilla 17 = -100 -> casilla 19 = -100
#   saldo-negativo-fin-periodo = max(0, -(-100)) = 100  <-- carried into Q2
_Q1_INPUTS: dict[CasillaId, Decimal] = {
    _M130_INGRESOS_CASILLA: Decimal("3000"),
    _M130_GASTOS_CASILLA: Decimal("1000"),
    _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
    _M130_RETENCIONES_CASILLA: Decimal("500"),
    _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
    _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}
_Q1_BINDINGS: dict[BindingId, Decimal] = {
    _PREV_YEAR_BINDING: _PRIOR_YEAR_NET_INCOME,
    _CARRY_FORWARD_BINDING: Decimal("0"),  # Q1 has no prior quarter.
}
_EXPECTED_Q1_SALDO = Decimal("100.00")


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over an isolated profile — no mocks."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
            CalculationObservationRepository(objects=objects),
        )


def _calculate_quarter(
    repos: _Repos,
    *,
    period: str,
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
) -> CalculationRevision:
    wu_repo, cr_repo, bv_repo, _obs_repo = repos
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, period),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_CLOCK,
    )
    return calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )


def _observation_from_revision(revision: CalculationRevision, *, period: str) -> RegistryModeloObservation:
    if not revision.observations:
        raise AssertionError("calculation revision must carry typed CasillaObservation provenance")
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period=period,
        observations=revision.observations,
    )


def _seed_prior_year_m100(obs_repo: CalculationObservationRepository) -> None:
    """Record the prior-year annual Renta (M100 2025) net-income observation.

    M130's casilla-13 minoración reads ``irpf.previous_year_economic_activity_net_income``
    — a ``previous_filing`` binding summing M100 casillas 0224/1479/1553/1577 of
    the prior ejercicio. The quarterly pipeline therefore depends on the prior
    annual filing being observed; seeding it here exercises the full continuity
    (prior-year Renta + prior-quarter 130 both feeding the current quarter).
    """
    # The binding sums M100 casillas 0224/1479/1553/1577 and requires all four
    # observed; the net income lands in 0224, the other rendimiento-source
    # casillas are zero for a pure-actividad-económica filer.
    obs_repo.save_observation(
        registry_grounded_modelo_observation(
            modelo="100",
            filing_year=2025,
            period="0A",
            casilla_values={
                _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _PRIOR_YEAR_NET_INCOME,
                _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
            },
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def test_q1_loss_produces_carry_forward_saldo(repos: _Repos) -> None:
    """A loss-making Q1 produces a positive ``saldo-negativo-fin-periodo``.

    This is the seed the next quarter carries forward. The value is
    produced by the engine from the loss scenario (retenciones exceed the
    20% pago fraccionado, with a minoración that cannot be absorbed),
    never hand-computed against the formula under test.
    """
    revision = _calculate_quarter(repos, period="1T", casilla_inputs=_Q1_INPUTS, binding_values=_Q1_BINDINGS)
    assert Decimal(revision.casilla_values[_M130_DIFERENCIA_CASILLA]) == Decimal("-100.00")
    assert Decimal(revision.casilla_values[_M130_SALDO_NEGATIVO_CASILLA]) == _EXPECTED_Q1_SALDO


def test_q2_casilla_15_auto_resolves_from_prior_quarter_filing(repos: _Repos) -> None:
    """Q2's carry-forward binding auto-resolves to Q1's persisted saldo.

    The cross-period continuity contract: once Q1 is recorded as a
    prior-period observation, the ``previous_filing`` resolver populates
    Q2's casilla-15 binding with Q1's ``saldo-negativo-fin-periodo`` —
    the operator does not re-key the prior-quarter loss by hand.
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo = repos
    q1 = _calculate_quarter(repos, period="1T", casilla_inputs=_Q1_INPUTS, binding_values=_Q1_BINDINGS)
    obs_repo.save_observation(
        _observation_from_revision(q1, period="1T"),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )
    _seed_prior_year_m100(obs_repo)

    q2_snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="2T")
    report = resolve_bindings_from_local_store(q2_snapshot, repository=obs_repo)

    # Both M130 previous_filing bindings auto-resolve from the local store:
    # the prior-quarter carry-forward and the prior-year Renta net income.
    assert report.binding_values.get(_CARRY_FORWARD_BINDING) == _EXPECTED_Q1_SALDO
    assert report.binding_values.get(_PREV_YEAR_BINDING) == _PRIOR_YEAR_NET_INCOME


def test_q2_carry_forward_flows_into_casilla_15_value(repos: _Repos) -> None:
    """The resolved carry-forward lands in Q2's casilla 15 through a real calculate.

    End-to-end: Q1 recorded -> Q2 prefill -> Q2 calculate with the
    resolved binding (no manual casilla-15 entry). Casilla 15 must equal
    Q1's saldo (100), confirming the loss propagates to the next quarter
    exactly as the AEAT instruction prescribes ("importe sin signo de los
    resultados negativos de trimestres anteriores").
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo = repos
    q1 = _calculate_quarter(repos, period="1T", casilla_inputs=_Q1_INPUTS, binding_values=_Q1_BINDINGS)
    obs_repo.save_observation(
        _observation_from_revision(q1, period="1T"),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )
    _seed_prior_year_m100(obs_repo)

    q2_snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="2T")
    resolved = resolve_bindings_from_local_store(q2_snapshot, repository=obs_repo).binding_values

    # Q2 cumulative (Jan-Jun): ingresos 8000, gastos 2000 -> rendimiento 6000,
    # casilla 04 = 1200. Both carry-forward casilla 15 and the prior-year net
    # income come solely from the resolver — nothing re-keyed by hand.
    q2 = _calculate_quarter(
        repos,
        period="2T",
        casilla_inputs={
            _M130_INGRESOS_CASILLA: Decimal("8000"),
            _M130_GASTOS_CASILLA: Decimal("2000"),
            _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        binding_values=dict(resolved),
    )
    assert Decimal(q2.casilla_values[_M130_CARRY_FORWARD_CASILLA]) == _EXPECTED_Q1_SALDO


# Shared parity-fixture inputs (named so the expected casilla-05 identity is
# derived from the same constants the fixture seeds, never a hand-summed literal).
_PRIOR_07_1T = Decimal("500")
_PRIOR_16_1T = Decimal("60")
_PRIOR_07_2T = Decimal("300")
_PRIOR_16_2T = Decimal("40")
_PRIOR_2T_SALDO = Decimal("150")


def test_casilla_15_copy_and_casilla_05_sum_carries_resolve_on_shared_fixture(repos: _Repos) -> None:
    """Parity: the casilla-15 op=copy carry and the casilla-05 op=sum carry coexist.

    The casilla-15 single-offset op=copy carry (binding
    ``modelo-130-resultados-negativos-anteriores``) and the casilla-05
    expanding-span op=sum carry (binding ``modelo-130-pagos-fraccionados-anteriores``)
    both resolve from the same multi-quarter local store on a 3T target, proving the
    expanding-span selector extension does not regress the single-offset carry
    (the modelo-130-relation-regression guarantee).

    Shared fixture (prior 1T/2T observations, engine-independent for this wiring gate):
      1T: casilla 07 = +500 (a real pago fraccionado), casilla 16 = 60, saldo = 0
      2T: casilla 07 = +300, casilla 16 = 40, saldo = 150 (a loss carried to 3T)

    At 3T:
      casilla-15 (op=copy, offset -1) = 2T saldo (the single immediately-prior quarter)
      casilla-05 (op=sum, expanding span {1T, 2T}) = Σ max(0, 07) − Σ 16,
                computed in-test from the seeded fixture inputs (not a hand-summed literal).
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo = repos
    _seed_prior_year_m100(obs_repo)

    obs_repo.save_observation(
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=2026,
            period="1T",
            casilla_values={
                _M130_PAGO_FRACCIONADO_CASILLA: _PRIOR_07_1T,
                _M130_HOME_DEDUCTION_CASILLA: _PRIOR_16_1T,
                _M130_SALDO_NEGATIVO_CASILLA: Decimal("0"),
            },
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )
    obs_repo.save_observation(
        registry_grounded_modelo_observation(
            modelo="130",
            filing_year=2026,
            period="2T",
            casilla_values={
                _M130_PAGO_FRACCIONADO_CASILLA: _PRIOR_07_2T,
                _M130_HOME_DEDUCTION_CASILLA: _PRIOR_16_2T,
                _M130_SALDO_NEGATIVO_CASILLA: _PRIOR_2T_SALDO,
            },
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )

    snapshot_3t = resources().modelos.authority.snapshot("130", filing_year=2026, period="3T")
    resolved = resolve_bindings_from_local_store(snapshot_3t, repository=obs_repo).binding_values

    # Independent identity (a different code path than the span binding): the
    # positive part of each prior 07 minus each prior 16, computed here from the
    # seeded fixture inputs rather than asserted against a hand-summed literal.
    expected_casilla_05 = (max(Decimal("0"), _PRIOR_07_1T) + max(Decimal("0"), _PRIOR_07_2T)) - (
        _PRIOR_16_1T + _PRIOR_16_2T
    )
    assert resolved.get("modelo-130-pagos-fraccionados-anteriores") == expected_casilla_05
    # The single-offset op=copy carry still reads exactly the immediately-prior quarter's saldo.
    assert resolved.get(_CARRY_FORWARD_BINDING) == _PRIOR_2T_SALDO
