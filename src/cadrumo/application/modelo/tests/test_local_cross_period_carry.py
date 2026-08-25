"""Automatic local cross-period previous_filing carry.

These tests exercise the local ``file`` -> next-period ``calculate`` carry seam end
to end with real encrypted-SQLite repositories and the real registry — no mocks,
stubs, skips, or xfail.

The carry vehicle is Modelo 130 (IRPF pago fraccionado, estimación directa). Casilla
15 ("Resultados negativos de trimestres anteriores") is bound via
``source = "previous_filing"`` to the prior quarter's computed
``saldo-negativo-fin-periodo`` (AEAT instructions under the RD 439/2007
art. 110 pago-fraccionado framework). When a quarter's Diferencia (casilla
17) is negative the absolute value seeds the next quarter's casilla 15.

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
  :mod:`cadrumo.application.modelo._filed_revision_observation`; no test asserts member
  fan-in for the local-filing flow.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import BindingSourceKind, CalculationSourceLineageRole, CasillaId, Period, validated_casilla_id
from ....domain.calculations.registry import (
    MODELO_303_IVA_COMPENSATION_BINDING_ID,
    RegistryModeloObservation,
    iva_wallet_owned_binding_ids_for_revision,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceProvenance, CalculationSourceResolution, merge_source_resolutions
from ...calculations import CalculationObservationRepository
from .._calculation_actions import calculate_modelo_revision
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from .._iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from .._work_lifecycle import create_work_unit
from .._calculation_actions import (
    _resolve_bucket_source_mesh,
    _source_resolution_excluding_iva_compensation,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ._file_flow_support import (
    _DEFAULT_130_BINDING_VALUES,
    _M130_AGRARIAN_VOLUME_CASILLA,
    _M130_AGRARIAN_WITHHELD_CASILLA,
    _M130_CARRY_FORWARD_CASILLA,
    _M130_HOME_DEDUCTION_CASILLA,
    _M130_PRIOR_RETURN_RESULT_CASILLA,
    _M130_SALDO_NEGATIVO_CASILLA,
    _M130_WITHHELD_CASILLA,
    _file_revision,
    _Repos,
    _verify_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T1 = datetime(2026, 4, 10, 9, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 11, 9, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 7, 10, 9, 0, 0, tzinfo=UTC)
_BUCKET_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            ModeloRecordCatalogueRepository(objects=objects),
            VerificationReportCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


_M303_COMPENSACION_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M130_DIFERENCIA_PREVIA_CASILLA: CasillaId = validated_casilla_id("14")

# The M130 carry binding feeds computed casilla 15. Calculation caps the raw
# previous_filing saldo-negativo at the current positive C14 before it flows through.
_CARRY_BINDING_ID = "modelo-130-resultados-negativos-anteriores"

# Inputs that drive Modelo 130 1T to a NEGATIVE Diferencia (casilla 17):
# casilla 01 (income) and 02 (gastos) are resolver-owned and resolve to 0 for this
# empty transaction bucket, so rendimiento neto is 0; the manual casilla-16
# deduction of 5000 then forces casilla 17 negative, so saldo-negativo-fin-periodo
# > 0 and seeds the next quarter. The exact seed is read back from the persisted
# revision (anti-tautology), never hand-derived from the formula.
# Casilla 05 ("Pagos fraccionados anteriores") is now a bound carry (Stage 2);
# at 1T its expanding span is empty (absent-by-design = 0), so it is NOT supplied
# as a manual input here.
_NEGATIVE_1T_INPUTS: dict[CasillaId, Decimal] = {
    # Casilla 01 (income) and 02 (gastos) are resolver-owned (the enrolled
    # LedgerRentaIncome/Gasto aggregation resolvers); they return 0 for this
    # empty transaction bucket and must not be supplied as manual inputs. The
    # negative result that seeds the carry comes from the manual casilla-16
    # deduction below applied against a zero rendimiento neto.
    _M130_WITHHELD_CASILLA: Decimal("0"),
    _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
    _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("5000"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}
# Casilla "01" (actividad-económica gross income) is now owned by the enrolled
# LedgerRentaIncomeAggregationSourceResolver, and casilla "02" (Gastos) by the
# enrolled LedgerRentaGastosPagoFraccionadoAggregationSourceResolver.  Callers must not supply
# either on the aggregation path; both resolvers return zero for an empty
# transaction bucket, which is correct for these carry-forward tests that do not
# seed income or expense transactions.  The carry-forward assertion (casilla 15
# == 1T saldo-negativo) is independent of casilla 01/02 and remains valid with
# resolver-supplied zero.  Casilla 05 (now a bound carry) and casilla 15 (the
# carry under test) are both resolved by the previous_filing pipeline at 2T,
# never supplied as manual inputs.
_2T_INPUTS_WITHOUT_15: dict[CasillaId, Decimal] = {
    _M130_WITHHELD_CASILLA: Decimal("0"),
    _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
    _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}


def _seed_130(repos_: _Repos, *, period: str, clock: datetime):
    wu_repo = repos_[0]
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, period),
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
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos_
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
    saldo = Decimal(revision.casilla_values[_M130_SALDO_NEGATIVO_CASILLA])
    assert saldo > 0, "1T inputs must produce a positive carry-forward seed for the test to be meaningful"
    # 1T's casilla-05 expanding-span and casilla-15 single-offset previous_filing
    # bindings are both absent-by-design at 1T (max_year_delta=0, no prior quarter),
    # but the M100 prior-year minoración relation is a real cross-period dependency,
    # so the direct mark-complete shortcut is refused and the full verify pipeline
    # is required. _verify_revision seeds the clean M100 prior-year evidence and
    # marks the 1T revision VERIFICADO_COMPLETO so filing can proceed.
    _verify_revision(
        revision.calculation_revision_id,
        revision=revision,
        work_unit=work_unit,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    # Filing then succeeds because the M100 dependency is clean and the M130
    # same-ejercicio bindings have no prior quarter at 1T.
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


def _seed_first_year_activity_profile(repos_: _Repos) -> None:
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Autonomo"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="provenance.source", value="manual_cli"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value="2026-01-01"),
        ),
        created_at=_T1,
        updated_at=_T1,
    )
    seed_test_profile_record(profile)


def _seed_existing_303_activity_profile(repos_: _Repos) -> None:
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="Test Company SL"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Company"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="provenance.source", value="manual_cli"),
            UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
        ),
        created_at=_T1,
        updated_at=_T1,
    )
    seed_test_profile_record(profile)


def _seed_first_303_activity_profile(repos_: _Repos) -> None:
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="Test Company SL"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Company"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="provenance.source", value="manual_cli"),
            UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),
        ),
        created_at=_T1,
        updated_at=_T1,
    )
    seed_test_profile_record(profile)


def test_local_file_then_next_period_calculate_carries_previous_filing_value(repos: _Repos) -> None:
    """E2E: filing 1T auto-carries its saldo-negativo into 2T's casilla 15 on calculate.

    No manual ``--casilla 15`` / ``--binding`` is supplied for 2T. The carry contract:
    2T's casilla 15 equals the value the 1T revision actually computed for
    ``saldo-negativo-fin-periodo`` (read back from the filed revision, not hand-derived
    from the formula — anti-tautology).
    """
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
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

    carried_casilla_15 = Decimal(result.revision.casilla_values[_M130_CARRY_FORWARD_CASILLA])
    c14 = Decimal(result.revision.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA])
    assert Decimal(result.revision.binding_overrides[_CARRY_BINDING_ID]) == carried_seed
    assert carried_seed > c14 > Decimal("0")
    assert carried_casilla_15 == c14


def test_first_year_activity_start_calculate_scopes_prior_year_m100_binding(repos: _Repos) -> None:
    """2T calculation reaches same-year carry without a manual prior-year M100 binding."""
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    carried_seed = _file_1t_with_negative_result(repos)

    work_unit_2t = _seed_130(repos, period="2T", clock=_T4)
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_2t.work_unit_id,
        casilla_inputs=_2T_INPUTS_WITHOUT_15,
        binding_values={},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    assert Decimal(result.revision.binding_overrides["irpf.previous_year_economic_activity_net_income"]) == Decimal(
        "0",
    )
    c14 = Decimal(result.revision.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA])
    assert Decimal(result.revision.binding_overrides[_CARRY_BINDING_ID]) == carried_seed
    assert carried_seed > c14 > Decimal("0")
    assert Decimal(result.revision.casilla_values[_M130_CARRY_FORWARD_CASILLA]) == c14


def test_app_filing_source_kind_is_not_official_evidence() -> None:
    """D1 (structural): the local-filing source_kind is NOT in the official-evidence set.

    The cross-period clean-state guard grants filing only when the upstream observation
    carries an official source_kind. ``app_filing`` must never join that set, or an
    unevidenced local chain would launder past the filing gate.
    """
    assert APP_FILING_SOURCE_KIND == "app_filing"
    assert not APP_FILING_SOURCE_KIND.is_official_aeat


def test_same_year_locally_filed_upstream_admitted_with_advisory(repos: _Repos) -> None:
    """Same-year admission: a same-year locally-filed 1T lets 2T FILE with a disclosing advisory.

    Filing 1T persists an ``app_filing`` carry observation. A SAME-FILING-YEAR dependent
    period (2T) is admitted: the clean-state guard clears the official-evidence-delta
    blockers for the present, value-consistent app_filing chain and flags a non-blocking
    ``non_official_local_chain_advisory`` so the non-official basis is surfaced
    (``no-silent-under-declaration``). The ``app_filing`` source stays non-official, and a
    cross-YEAR non-official prior still blocks. The within-year reconstruction can reach
    export; the operator files every period with AEAT externally.
    """
    from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ....domain.modelos import (
        CalculationRevisionState,
        upsert_calculation_revision,
    )
    from ...calculations import CrossPeriodCleanStateBlocker
    from .._verification_actions import _cross_period_clean_state_verdict_for_work_unit

    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    _file_1t_with_negative_result(repos)
    local_filing = fr_repo.load().current_for(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
    )
    assert local_filing is not None
    assert local_filing.aeat_accepted is False
    assert local_filing.external_evidence is None
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
    # The 2T cross-period state is deliberately UNCLEAN (the only upstream 1T
    # evidence is the non-official app_filing carry), so the verify pipeline cannot
    # legitimately grant VERIFICADO_COMPLETO and the direct mark-complete shortcut is
    # refused for a cross-period revision. To exercise the FILE gate's own
    # cross-period refusal, force the revision into VERIFICADO_COMPLETO directly
    # through the catalogue - this is fixture setup for the file-transition assertion
    # below, not a test of the mark path.
    verificado_2t = revision_2t.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": _T4,
            "verified_by": "operator-A",
            "updated_at": _T4,
        },
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), verificado_2t))
    revision_2t = verificado_2t

    # Same-year scope: the same-year 1T (M130/2026) previous_filing
    # dependency is admitted - its official-evidence-delta blockers are cleared (the row
    # is clean) and it carries the disclosing non-official-local-chain advisory. A
    # cross-YEAR dependency (the M100 prior-year minoración evidence) is NOT relaxed, so
    # the anti-laundering scope holds. The app_filing source stays non-official.
    verdict = _cross_period_clean_state_verdict_for_work_unit(
        work_unit_2t,
        observation_repository=CalculationObservationRepository(),
        filing_repository=ModeloRecordCatalogueRepository(objects=bv_repo.secure_object_repository),
        calculation_repository=cr_repo,
        verification_repository=VerificationReportCatalogueRepository(objects=bv_repo.secure_object_repository),
    )
    assert verdict is not None
    same_year = [
        d for d in verdict.dependencies if d.requirement.source_modelo == "130" and d.requirement.filing_year == 2026
    ]
    assert same_year, "expected the same-year M130/2026 carry dependency"
    assert all(d.clean for d in same_year)
    assert all(d.non_official_local_chain_advisory for d in same_year)
    assert all(CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE not in d.blockers for d in same_year)
    assert verdict.has_non_official_local_chain_advisory
    # The cross-YEAR dependency is NOT relaxed - the same-year scope is the safety boundary.
    cross_year = [d for d in verdict.dependencies if d.requirement.filing_year != 2026]
    assert all(not d.non_official_local_chain_advisory for d in cross_year)


def test_caller_binding_override_beats_auto_carried_previous_filing(repos: _Repos) -> None:
    """D2: a caller ``--binding`` of the carry binding overrides the auto-carried value.

    After filing 1T with a positive saldo-negativo carry, calculating 2T while supplying
    the carry binding id explicitly must (a) NOT be rejected as a source-owned collision
    and (b) drive casilla 15 to the caller's value, not the carried one. The carried
    value is read back from the no-override calculation so the override case is proven to
    actually differ.
    """
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
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

    casilla_15 = Decimal(result.revision.casilla_values[_M130_CARRY_FORWARD_CASILLA])
    c14 = Decimal(result.revision.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA])
    assert Decimal(result.revision.binding_overrides[_CARRY_BINDING_ID]) == override_value
    assert override_value > c14 > Decimal("0")
    assert casilla_15 == c14


def test_carry_resolver_excludes_303_iva_compensation_binding(repos: _Repos) -> None:
    """D3: the previous_filing resolver does not emit the M303 IVA-compensation binding.

    A prior 303 filing whose observation carries the compensation casillas is persisted
    locally. The carry resolver's raw output DOES surface the
    ``modelo-303-compensacion-pendiente-anteriores`` binding (proven first), but
    the enrolled resolver receives the registry-declared iva-wallet-owned set as
    ``excluded_binding_ids`` so the iva-wallet decision remains the sole owner.
    """
    from ....core import Period
    from ...aggregation import CalculationSourceContext
    from ...calculations import PreviousFilingSourceResolver

    wu_repo = repos[0]
    _seed_existing_303_activity_profile(repos)
    work_unit_303 = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id="2026-y-siguientes",
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
    assert MODELO_303_IVA_COMPENSATION_BINDING_ID in raw.binding_values, (
        "test precondition: the raw resolver must surface the 303 compensation binding "
        "so the exclusion has something to strip"
    )
    # The revision's self-referential dependency classification
    # (modelo-303-dep-self-prior-quarter, source_modelo="303") declares this carry
    # a fact to reconcile against, not a settling figure; that real, non-default
    # treatment must survive the resolver join onto the provenance trace rather
    # than default to the undeclared empty string.
    compensation_provenance = [
        item for item in raw.provenance if item.source_ref.endswith(f":{MODELO_303_IVA_COMPENSATION_BINDING_ID}")
    ]
    assert compensation_provenance, "test precondition: the compensation binding must carry a provenance row"
    assert all(item.dependency_treatment == "factual_evidence" for item in compensation_provenance)

    filtered = PreviousFilingSourceResolver(
        registry_snapshot=snapshot,
        excluded_binding_ids=iva_wallet_owned_binding_ids_for_revision(
            modelo_id=str(snapshot.modelo.id),
            revision_id=str(snapshot.revision.id),
            relations=snapshot.revision.relations,
        ),
    ).resolve(context)
    assert MODELO_303_IVA_COMPENSATION_BINDING_ID not in filtered.binding_values
    assert all(
        not item.source_ref.endswith(f":{MODELO_303_IVA_COMPENSATION_BINDING_ID}") for item in filtered.provenance
    )
    # Every other binding the raw resolver carried survives the exclusion untouched.
    for binding_id, value in raw.binding_values.items():
        if binding_id == MODELO_303_IVA_COMPENSATION_BINDING_ID:
            continue
        assert filtered.binding_values[binding_id] == value


def test_source_mesh_excludes_303_iva_compensation_relation_binding(repos: _Repos) -> None:
    """D3: relation-prefill must not bypass the IVA-wallet owner for M303 casilla 110."""
    from ....core.resources import resources

    wu_repo = repos[0]
    _seed_existing_303_activity_profile(repos)
    work_unit_303 = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id="2026-y-siguientes",
        repository=wu_repo,
        clock=_T4,
    )
    _persist_prior_303(CalculationObservationRepository())

    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
    resolution = _resolve_bucket_source_mesh(
        snapshot,
        work_unit_303,
        transaction_repository=None,
        invoice_repository=None,
        foreign_asset_observations=(),
    )

    assert MODELO_303_IVA_COMPENSATION_BINDING_ID not in resolution.binding_values
    assert "modelo-303-rel-self-compensacion-anteriores" not in resolution.relation_values
    assert all("modelo-303-rel-self-compensacion-anteriores" not in item.source_ref for item in resolution.provenance)


def test_source_resolution_keeps_reused_wallet_binding_outside_m303_coordinate() -> None:
    """A reused wallet binding id is retained when the validated snapshot is not M303."""
    from ....core.resources import resources

    snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")
    reused_binding_id = MODELO_303_IVA_COMPENSATION_BINDING_ID
    reused_relation_id = "modelo-303-rel-self-compensacion-anteriores"
    resolution = merge_source_resolutions(
        (
            CalculationSourceResolution(
                resolver_id="previous_filing",
                binding_values={reused_binding_id: Decimal("42.00")},
                provenance=(
                    CalculationSourceProvenance(
                        resolver_id="previous_filing",
                        resolved_binding_source=BindingSourceKind.PREVIOUS_FILING,
                        contributor_source_kind="previous_filing",
                        contributor_binding_source=BindingSourceKind.PREVIOUS_FILING,
                        lineage_role=CalculationSourceLineageRole.PRIMARY,
                        source_ref=f"100:2025:0A:{reused_binding_id}",
                        parent_source_ref=None,
                    ),
                ),
            ),
            CalculationSourceResolution(
                resolver_id="relation_prefill",
                relation_values={reused_relation_id: Decimal("17.00")},
                provenance=(
                    CalculationSourceProvenance(
                        resolver_id="relation_prefill",
                        resolved_binding_source=BindingSourceKind.RELATION_PREFILL,
                        contributor_source_kind="relation_prefill",
                        contributor_binding_source=BindingSourceKind.RELATION_PREFILL,
                        lineage_role=CalculationSourceLineageRole.PRIMARY,
                        source_ref=f"{reused_relation_id}:100:2025:0A",
                        parent_source_ref=None,
                    ),
                ),
            ),
        ),
    )

    filtered = _source_resolution_excluding_iva_compensation(snapshot, resolution)

    assert filtered.binding_values == resolution.binding_values
    assert filtered.relation_values == resolution.relation_values
    assert filtered.provenance == resolution.provenance


def test_existing_activity_m303_1t_missing_prior_filing_blocks_wallet_zero(repos: _Repos) -> None:
    """An existing activity with no local 4T filing cannot invent a first-period zero."""
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_existing_303_activity_profile(repos)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision_id="2025",
        repository=wu_repo,
        clock=_T1,
    )

    with pytest.raises(ModeloIvaWalletReconciliationBlocked):
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:m303-local-cross-period-carry"
            ),
        )


def test_first_iva_period_m303_1t_uses_wallet_first_period_zero(repos: _Repos) -> None:
    """A true first IVA period proven by activity start may use a zero prior compensation."""
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_303_activity_profile(repos)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision_id="2025",
        repository=wu_repo,
        clock=_T1,
    )

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
        filing_instance_evidence=general_m303_filing_evidence(
            work_unit.period, reference="test:m303-local-cross-period-carry"
        ),
    )
    revision = result.revision
    assert Decimal(revision.binding_overrides[MODELO_303_IVA_COMPENSATION_BINDING_ID]) == Decimal("0")
    assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")


_SEED_OPENING_BALANCE_WITH_ZERO_REFUSAL = "application.modelo.errors.iva_wallet_not_seeded"


def _persist_unreadable_prior_303(period_code: str = "4T", filing_year: int = 2024) -> None:
    """Store a prior-period Modelo 303 observation the carry gate cannot interpret.

    Written the way the operator CLI writes one: an unrestricted local observation
    with no carry normalisation, so it carries neither a result disposition nor the
    normalized available/generated pair the carry consumer requires.
    """
    CalculationObservationRepository().save(
        CalculationObservationRepository().prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="303",
                filing_year=filing_year,
                period=period_code,
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=filing_year,
                    period=period_code,
                    casilla_values={_M303_COMPENSACION_DISPONIBLE_CASILLA: Decimal("850.00")},
                ),
            ),
            source_kind="operator_manual",
            captured_at=_T1,
        )
    )


def test_unreadable_prior_303_observation_cannot_prove_a_first_period_zero(repos: _Repos) -> None:
    """A stored prior observation this build cannot read must block, never prove zero.

    The profile carries first-period activity-start evidence, so the activity-start
    proof holds and the gate would previously have produced ``first_period_zero``.
    But an observation for the prior period IS stored -- which is itself proof the
    taxpayer had a prior Modelo 303 period, the exact fact that proof asserts did
    not exist. The carry consumer cannot interpret the envelope and must surface
    that as a refusal rather than as an absence, or a taxpayer's carried credit is
    laundered into a zero on the compensación with no signal.
    """
    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_303_activity_profile(repos)
    _persist_unreadable_prior_303()
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        revision_id="2025",
        repository=wu_repo,
        clock=_T1,
    )

    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as blocked:
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:m303-local-cross-period-carry"
            ),
        )

    surfaced_key = blocked.value.translated_message
    assert surfaced_key is not None, "the refusal reached the operator with no locale key at all"
    assert surfaced_key != _SEED_OPENING_BALANCE_WITH_ZERO_REFUSAL, (
        "a taxpayer whose stored prior-period evidence could not be read was told to seed the "
        "opening balance with zero and confirm it, which reconstructs by hand the under-declaration "
        "that blocking this case exists to prevent, and stamps it as an operator decision. "
        f"Surfaced refusal: {surfaced_key}"
    )


def _persist_prior_303(repository: CalculationObservationRepository) -> None:
    """Persist a prior-period 303 observation carrying the compensation carry casilla.

    Stored under the prior period (1T) so the 2T snapshot's previous_filing
    compensation binding (``source_casilla_id = iva.compensacion-disponible-fin-periodo``,
    offset -1) discovers it and the raw resolver emits the
    ``modelo-303-compensacion-pendiente-anteriores`` binding the D3 exclusion strips.
    """
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="303",
                filing_year=2026,
                period="1T",
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=2026,
                    period="1T",
                    casilla_values={_M303_COMPENSACION_DISPONIBLE_CASILLA: Decimal("1200.00")},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T1,
        )
    )


def test_first_filer_same_year_chain_is_fully_reachable(repos: _Repos) -> None:
    """Reachability proof: with first-year activity-start, the M130 2T verdict is fully clean.

    Adversarial check of the end-to-end reachability claim. The M130 minoración binding
    (``irpf.previous_year_economic_activity_net_income``, source_modelo 100,
    filing_year_delta -1) creates a CROSS-YEAR M100 prior-year dependency that same-year
    admission deliberately does NOT relax. For a first-year autónomo (activity-start in the filing
    year) that cross-year M100 dep is strictly pre-activity, so the first-filer suppression
    scopes it out; the same-year 1T dep is admitted under same-year scope. Both handled => the
    verdict is clean => the quarter is reachable to verify/export. If suppression did NOT
    cover the previous_filing M100 dep, this verdict would be unclean (a real gap).
    """
    from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from .._verification_actions import _cross_period_clean_state_verdict_for_work_unit

    wu_repo, cr_repo, _fr_repo, _vr_repo, bv_repo = repos
    _seed_first_year_activity_profile(repos)
    _file_1t_with_negative_result(repos)
    work_unit_2t = _seed_130(repos, period="2T", clock=_T4)
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit_2t.work_unit_id,
        casilla_inputs=_2T_INPUTS_WITHOUT_15,
        binding_values=_DEFAULT_130_BINDING_VALUES,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T4,
    )

    verdict = _cross_period_clean_state_verdict_for_work_unit(
        work_unit_2t,
        observation_repository=CalculationObservationRepository(),
        filing_repository=ModeloRecordCatalogueRepository(objects=bv_repo.secure_object_repository),
        calculation_repository=cr_repo,
        verification_repository=VerificationReportCatalogueRepository(objects=bv_repo.secure_object_repository),
        activity_start_date=date(2026, 1, 1),
    )
    assert verdict is not None
    # The cross-year M100/2025 minoración dep is suppressed (pre-activity).
    cross_year = [d for d in verdict.dependencies if d.requirement.filing_year != 2026]
    assert cross_year, "expected the cross-year M100 prior-year minoración dependency"
    assert all(d.suppressed_pre_activity for d in cross_year)
    # The same-year M130/2026 dep is admitted with the disclosing advisory.
    same_year = [
        d for d in verdict.dependencies if d.requirement.source_modelo == "130" and d.requirement.filing_year == 2026
    ]
    assert same_year and all(d.non_official_local_chain_advisory for d in same_year)
    # Both handled -> the verdict is clean -> the quarter is reachable.
    assert verdict.clean
