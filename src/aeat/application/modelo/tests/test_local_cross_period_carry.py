"""Automatic local cross-period previous_filing carry.

These tests exercise the local ``file`` -> next-period ``calculate`` carry seam end
to end with real encrypted-SQLite repositories and the real registry — no mocks,
stubs, skips, or xfail.

The carry vehicle is Modelo 130 (IRPF pago fraccionado, estimación directa). Casilla
15 ("Resultados negativos de trimestres anteriores") is bound via
``source = "previous_filing"`` to the prior quarter's computed
``saldo-negativo-fin-periodo`` (RD 439/2007 art. 110.5). When a quarter's Diferencia
(casilla 17) is negative the absolute value seeds the next quarter's casilla 15.

The four behaviours under test:

* E2E (carry): filing 1T with a negative Diferencia persists an ``app_filing``
  observation; calculating 2T then auto-fills casilla 15 from it WITHOUT any manual
  ``--casilla`` / ``--binding``.
* D1 (clean-state non-official): the ``app_filing`` observation does NOT satisfy the
  cross-period clean-state gate for FILING a dependent period — it still blocks with
  ``LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE``.
* D2 (override precedence): a caller ``--binding`` beats the auto-carried value and is
  NOT rejected as a source-owned collision.
* D3 (303 exclusion): the carry resolver never emits the M303 IVA-compensation
  binding (the iva-wallet decision owns it).
* D4 (grupo fan-in non-goal): documented as out of scope in
  :mod:`aeat.application.modelo._filed_revision_observation`; no test asserts member
  fan-in for the local-filing flow.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ...calculations import CalculationObservationRepository
from ...calculations._binding_prefill import _MODELO_303_IVA_COMPENSATION_BINDING_ID
from ...calculations._cross_period_clean_state import _OFFICIAL_SOURCE_KINDS
from .. import (
    APP_FILING_SOURCE_KIND,
    calculate_modelo_revision,
    create_work_unit,
    mark_revision_verificado_completo,
)
from .._calculation_actions import (
    _previous_filing_resolution_excluding_iva_compensation,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ._file_flow_support import (
    _DEFAULT_130_BINDING_VALUES,
    _file_revision,
    _Repos,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T1 = datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 11, 9, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 7, 10, 9, 0, 0, tzinfo=UTC)

# The M130 carry binding casilla 15 lifts. Casilla 15 (input_kind=bound) reads its
# value from this previous_filing binding; the carried saldo-negativo flows through it.
_CARRY_BINDING_ID = "modelo-130-resultados-negativos-anteriores"

# Inputs that drive Modelo 130 1T to a NEGATIVE Diferencia (casilla 17):
# rendimiento neto 30000 - 12000 = 18000; pago fraccionado 20% = 3600; minoracion
# casilla 13 = 100 (prev-year net income binding defaults to 0); casilla 14 = 3500;
# a manual casilla-16 deduction of 5000 forces casilla 17 = 3500 - 0 - 5000 = -1500,
# so saldo-negativo-fin-periodo = max(0, 1500) = 1500 > 0 and seeds the next quarter.
_NEGATIVE_1T_INPUTS: dict[str, Decimal] = {
    "01": Decimal("30000"),
    "02": Decimal("12000"),
    "05": Decimal("0"),
    "06": Decimal("0"),
    "08": Decimal("0"),
    "10": Decimal("0"),
    "15": Decimal("0"),
    "16": Decimal("5000"),
    "18": Decimal("0"),
}
# Casilla "01" (actividad-económica gross income) is now owned by the enrolled
# LedgerRentaIncomeAggregationSourceResolver.  Callers must not supply it
# on the aggregation path; the resolver returns zero for an empty transaction
# bucket, which is correct for these carry-forward tests that do not seed income
# transactions.  The carry-forward assertion (casilla 15 == 1T saldo-negativo)
# is independent of casilla 01 and remains valid with resolver-supplied zero.
_2T_INPUTS_WITHOUT_15: dict[str, Decimal] = {
    "02": Decimal("12000"),
    "05": Decimal("0"),
    "06": Decimal("0"),
    "08": Decimal("0"),
    "10": Decimal("0"),
    "16": Decimal("0"),
    "18": Decimal("0"),
}


def _seed_130(repos_: _Repos, *, period: str, clock: datetime):
    wu_repo = repos_[0]
    return create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=clock,
    )


def _file_1t_with_negative_result(repos_: _Repos) -> Decimal:
    """File Modelo 130 1T with a negative Diferencia; return its saldo-negativo seed.

    Returns the value the 1T revision actually computed for
    ``saldo-negativo-fin-periodo`` (read back from the persisted revision, never
    hand-derived from the formula — anti-tautology).
    """
    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos_
    work_unit = _seed_130(repos_, period="1T", clock=_T1)
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_NEGATIVE_1T_INPUTS,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    saldo = Decimal(revision.casilla_values["saldo-negativo-fin-periodo"])
    assert saldo > 0, "1T inputs must produce a positive carry-forward seed for the test to be meaningful"
    mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    # 1T's own previous_filing binding is absent-by-design (max_year_delta=0, no prior
    # quarter), so the clean-state guard has no upstream to satisfy: filing succeeds.
    # _file_revision threads the workflow gate and lets file_modelo_revision use its
    # default CalculationObservationRepository(), which binds to the active bucket and
    # persists the app_filing carry observation co-emitted with MODELO_FILED.
    _file_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T3,
    )
    return saldo


def test_local_file_then_next_period_calculate_carries_previous_filing_value(repos: _Repos) -> None:
    """E2E: filing 1T auto-carries its saldo-negativo into 2T's casilla 15 on calculate.

    No manual ``--casilla 15`` / ``--binding`` is supplied for 2T. The carry contract:
    2T's casilla 15 equals the value the 1T revision actually computed for
    ``saldo-negativo-fin-periodo`` (read back from the filed revision, not hand-derived
    from the formula — anti-tautology).
    """
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    carried_seed = _file_1t_with_negative_result(repos)

    work_unit_2t = _seed_130(repos, period="2T", clock=_T4)
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_2t.work_unit_id,
        casilla_inputs=_2T_INPUTS_WITHOUT_15,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    carried_casilla_15 = Decimal(result.revision.casilla_values["15"])
    assert carried_casilla_15 == carried_seed, (
        f"2T casilla 15 must auto-carry the filed 1T saldo-negativo {carried_seed}; got {carried_casilla_15}"
    )


def test_app_filing_source_kind_is_not_official_evidence() -> None:
    """D1 (structural): the local-filing source_kind is NOT in the official-evidence set.

    The cross-period clean-state guard grants filing only when the upstream observation
    carries an official source_kind. ``app_filing`` must never join that set, or an
    unevidenced local chain would launder past the filing gate.
    """
    assert APP_FILING_SOURCE_KIND == "app_filing"
    assert APP_FILING_SOURCE_KIND not in _OFFICIAL_SOURCE_KINDS


def test_locally_filed_upstream_does_not_satisfy_filing_clean_state(repos: _Repos) -> None:
    """D1 (E2E): a locally-filed 1T does NOT let 2T FILE — it still blocks on evidence.

    Filing 1T persists an ``app_filing`` carry observation. When 2T is then verified and
    filed, the cross-period clean-state guard must still raise
    ``LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`` for the carried dependency: auto-carry
    feeds calculate/draft, but filing a dependent period requires real external evidence.
    The non-official source is the single decision that keeps the carry from laundering
    an unevidenced chain past the filing gate.
    """
    from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
    from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
    from ...calculations._cross_period_clean_state import CrossPeriodCleanStateBlocker
    from .. import file_modelo_revision
    from .._action_errors import ModeloCrossPeriodCleanStateError
    from .._verification_actions import _cross_period_clean_state_verdict_for_work_unit

    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    _file_1t_with_negative_result(repos)
    # Confirm the carry observation was persisted under the non-official source_kind.
    stored = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))
    assert stored is not None
    assert stored.source_kind == APP_FILING_SOURCE_KIND

    work_unit_2t = _seed_130(repos, period="2T", clock=_T4)
    revision_2t = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_2t.work_unit_id,
        casilla_inputs=_2T_INPUTS_WITHOUT_15,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    ).revision
    mark_revision_verificado_completo(
        revision_2t.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T4,
    )

    # Structural proof (robust to message truncation): the 2T clean-state verdict for the
    # 1T previous_filing dependency carries LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE, the
    # exact blocker that fires because the upstream observation's source_kind is the
    # non-official app_filing. This is the single decision that keeps the carry from
    # laundering an unevidenced chain past the filing gate.
    verdict = _cross_period_clean_state_verdict_for_work_unit(
        work_unit_2t,
        observation_repository=CalculationObservationRepository(),
        filing_repository=ModeloRecordCatalogueRepository(objects=bv_repo.secure_object_repository),
        calculation_repository=cr_repo,
        verification_repository=VerificationReportCatalogueRepository(objects=bv_repo.secure_object_repository),
    )
    assert verdict is not None
    assert not verdict.clean
    assert CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE in verdict.blockers

    from ....domain.deadlines import IVARegime, TaxpayerProfile

    profile = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    # And the filing transition itself is refused (verify the gate is wired, not just the
    # verdict computable).
    with pytest.raises(ModeloCrossPeriodCleanStateError):
        file_modelo_revision(
            revision_2t.calculation_revision_id,
            actor="operator-A",
            workflow_profile=profile,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )


def test_caller_binding_override_beats_auto_carried_previous_filing(repos: _Repos) -> None:
    """D2: a caller ``--binding`` of the carry binding overrides the auto-carried value.

    After filing 1T with a positive saldo-negativo carry, calculating 2T while supplying
    the carry binding id explicitly must (a) NOT be rejected as a source-owned collision
    and (b) drive casilla 15 to the caller's value, not the carried one. The carried
    value is read back from the no-override calculation so the override case is proven to
    actually differ.
    """
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    carried_seed = _file_1t_with_negative_result(repos)
    assert carried_seed > Decimal("0")

    override_value = carried_seed + Decimal("250")
    work_unit_2t = _seed_130(repos, period="2T", clock=_T4)
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_2t.work_unit_id,
        casilla_inputs=_2T_INPUTS_WITHOUT_15,
        binding_values={**_DEFAULT_130_BINDING_VALUES, _CARRY_BINDING_ID: override_value},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    casilla_15 = Decimal(result.revision.casilla_values["15"])
    assert casilla_15 == override_value, (
        f"caller --binding {override_value} must override the auto-carried {carried_seed}; got {casilla_15}"
    )


def test_carry_resolver_excludes_303_iva_compensation_binding(repos: _Repos) -> None:
    """D3: the previous_filing resolver does not emit the M303 IVA-compensation binding.

    A prior 303 filing whose observation carries the compensation casillas is persisted
    locally. The carry resolver's raw output DOES surface the
    ``modelo-303-compensacion-pendiente-anteriores`` binding (proven first), but the
    enrollment helper :func:`_previous_filing_resolution_excluding_iva_compensation`
    strips it so the iva-wallet decision remains the sole owner.
    """
    from ....core import Period
    from ...aggregation import CalculationSourceContext
    from ...calculations import PreviousFilingSourceResolver

    wu_repo = repos[0]
    work_unit_303 = create_work_unit(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="2T",
        revision_id="2023-y-siguientes",
        repository=wu_repo,
        clock=_T4,
    )
    _persist_prior_303(CalculationObservationRepository())

    from ....core.resources import resources

    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
    context = CalculationSourceContext(
        bucket_id=work_unit_303.bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision=snapshot.revision,
    )
    raw = PreviousFilingSourceResolver(registry_snapshot=snapshot).resolve(context)
    assert _MODELO_303_IVA_COMPENSATION_BINDING_ID in raw.binding_values, (
        "test precondition: the raw resolver must surface the 303 compensation binding "
        "so the exclusion has something to strip"
    )

    filtered = _previous_filing_resolution_excluding_iva_compensation(raw)
    assert _MODELO_303_IVA_COMPENSATION_BINDING_ID not in filtered.binding_values
    assert all(
        not item.source_ref.endswith(f":{_MODELO_303_IVA_COMPENSATION_BINDING_ID}") for item in filtered.provenance
    )
    # Every other binding the raw resolver carried survives the exclusion untouched.
    for binding_id, value in raw.binding_values.items():
        if binding_id == _MODELO_303_IVA_COMPENSATION_BINDING_ID:
            continue
        assert filtered.binding_values[binding_id] == value


def _persist_prior_303(repository: CalculationObservationRepository) -> None:
    """Persist a prior-period 303 observation carrying the compensation carry casilla.

    Stored under the prior period (1T) so the 2T snapshot's previous_filing
    compensation binding (``source_output = iva.compensacion-disponible-fin-periodo``,
    offset -1) discovers it and the raw resolver emits the
    ``modelo-303-compensacion-pendiente-anteriores`` binding the D3 exclusion strips.
    """
    repository.save_observation(
        RegistryModeloObservation(
            modelo="303",
            filing_year=2026,
            period="1T",
            observations=(
                CasillaObservation(casilla_id="iva.compensacion-disponible-fin-periodo", value=Decimal("1200.00")),
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T1,
    )
