"""Backend integration for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.outbound.aeat.sede import IVA_COMPENSATION_WALLET_URL, parse_iva_compensation_wallet_html
from ....core import Period
from ....core.config import AuthProviderKindSetting, Settings
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation, RegistrySnapshot
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva_compensation._reconciliation import (
    IvaCompensationOverride,
    IvaCompensationReconciliationDecision,
)
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._filing_record import ModeloRecordStatus
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    reconcile_modelo_303_iva_compensation,
)
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    ModeloIvaWalletOverrideFreshWalletError,
    ModeloIvaWalletOverrideSealedError,
    ModeloIvaWalletReconciliationBlocked,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    record_iva_compensation_override_for_bucket,
    verify_modelo_revision,
)
from .._actions import _require_persisted_iva_compensation_decision_matches_revision
from ._file_flow_support import _seed_clean_cross_period_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAXPAYER_NIF = "taxpayeralpha"
_TARGET_YEAR = 2026
_TARGET_PERIOD = "2T"
_DECIDED_AT = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)


def _period(filing_year: int, period: str) -> Period:
    return Period.from_year_and_code(filing_year, period)


_TARGET_PERIOD_VALUE = _period(_TARGET_YEAR, _TARGET_PERIOD)


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        yield


def _wallet_observation(
    *,
    pending: Decimal,
    taxpayer_nif: str = _TAXPAYER_NIF,
    target_year: int = _TARGET_YEAR,
    target_period: Period = _TARGET_PERIOD_VALUE,
    generation_year: int = 2026,
    generation_period: str = "1T",
    captured_at: datetime = _DECIDED_AT,
):
    pending_text = _spanish_amount(pending)
    return parse_iva_compensation_wallet_html(
        f"""
        <html><head><title>Cartera de cuotas de IVA a compensar</title></head>
          <body>
            <h1>Cartera de cuotas de IVA a compensar</h1>
            <li><strong>Cuotas a compensar pendientes de períodos anteriores:</strong>
              <span>{pending_text}</span></li>
            <table id="tablaResultados">
              <thead>
                <tr><th>Ejercicio</th><th>Período</th><th>Cuota Disponible</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td>{generation_year}</td><td>{generation_period}</td><td>{pending_text}</td>
                </tr>
              </tbody>
            </table>
          </body>
        </html>
        """,
        taxpayer_nif=taxpayer_nif,
        authenticated_identity=taxpayer_nif,
        target_year=target_year,
        target_period=target_period,
        source_url=IVA_COMPENSATION_WALLET_URL,
        captured_at=captured_at,
    )


def _spanish_amount(value: Decimal) -> str:
    whole, cents = f"{value:.2f}".split(".")
    chunks: list[str] = []
    while whole:
        chunks.append(whole[-3:])
        whole = whole[:-3]
    return f"{'.'.join(reversed(chunks))},{cents}"


def _store_prior_303_compensation(
    repo: CalculationObservationRepository,
    *,
    amount: Decimal,
    filing_year: int = _TARGET_YEAR,
    period: str = "1T",
) -> None:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
    casilla = next(item for item in snapshot.revision.casillas if item.id == "iva.compensacion-disponible-fin-periodo")
    formula = next(
        item for item in snapshot.revision.formulas if item.target == "iva.compensacion-disponible-fin-periodo"
    )
    repo.save_observation(
        RegistryModeloObservation(
            modelo="303",
            filing_year=filing_year,
            period=period,
            observations=(
                CasillaObservation(
                    casilla_id="iva.compensacion-disponible-fin-periodo",
                    value=amount,
                    formula_id=formula.id,
                    legal_refs=tuple(casilla.legal_refs),
                    source_refs=tuple(casilla.source_refs),
                ),
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=_DECIDED_AT,
    )


def _work_unit_repositories():
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _store_operator_profile() -> None:
    _store_operator_profile_with_tax_id(_TAXPAYER_NIF)


def _store_operator_profile_with_tax_id(tax_id: str) -> None:
    UserProfileLifecycleRepository(bucket_id="operator").save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value=tax_id),),
            created_at=_DECIDED_AT,
            updated_at=_DECIDED_AT,
        ),
    )


def _workflow_profile(tax_id: str = _TAXPAYER_NIF) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=tax_id,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _modelo_303_engine_inputs() -> dict[str, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        # State attribution: common-regime taxpayers receive the full
        # 100% State attribution. The engine consumes this through the
        # M303 C65 binding (bound to the derived profile fact
        # ``tax_residence.state_attribution_ratio``) after the dual-keying
        # profile-binding contract pivot.
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }


def _work_unit_and_revision_for_wallet_gate(
    *,
    compensation_amount: Decimal,
    state: CalculationRevisionState = CalculationRevisionState.BORRADOR,
) -> tuple[WorkUnit, CalculationRevision]:
    target_period = _period(_TARGET_YEAR, _TARGET_PERIOD)
    work_unit_id = derive_work_unit_id(
        bucket_id="operator",
        modelo="303",
        filing_year=_TARGET_YEAR,
        period=target_period,
        revision_id="m303-wallet-gate-test",
    )
    casilla_values = {"iva.compensacion-pendiente-periodos-anteriores": compensation_amount}
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id="operator",
        modelo=ModeloCode("303"),
        filing_year=_TARGET_YEAR,
        period=target_period,
        revision_id="m303-wallet-gate-test",
        name="303 wallet gate test",
        created_at=_DECIDED_AT,
        updated_at=_DECIDED_AT,
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values=casilla_values,
        created_at=_DECIDED_AT,
        updated_at=_DECIDED_AT,
    )
    return work_unit, revision


def _save_wallet_gate_decision(*, amount: Decimal, blocked: bool = False) -> None:
    IvaWalletDecisionRepository().save_decision(
        IvaCompensationReconciliationDecision(
            taxpayer_nif=_TAXPAYER_NIF,
            target_year=_TARGET_YEAR,
            target_period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            selected_authority="aeat_wallet" if not blocked else "missing",
            selected_amount=amount if not blocked else None,
            wallet_amount=amount,
            local_recurrence_amount=amount,
            override_amount=None,
            divergence="match" if not blocked else "filed_history_only",
            blocked=blocked,
            stale_wallet=False,
            reason="wallet gate decision fixture",
            wallet_captured_at=_DECIDED_AT,
            decided_at=_DECIDED_AT,
        ),
    )


def test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_filing_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        loaded_decision = IvaWalletDecisionRepository().load_decision(
            _TAXPAYER_NIF,
            _period(_TARGET_YEAR, _TARGET_PERIOD),
        )
        assert loaded_decision == report.decision
        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.local_recurrence_amount == Decimal("1200.00")
        assert {source.source_kind for source in report.decision.authority_sources} == {
            "aeat_wallet",
            "local_recurrence",
            "filed_history_observation",
        }
        filed_history_source = next(
            source for source in report.decision.authority_sources if source.source_kind == "filed_history_observation"
        )
        assert filed_history_source.source_modelo == "303"
        assert filed_history_source.source_filing_year == _TARGET_YEAR
        assert filed_history_source.source_periods == (Period.from_year_and_code(_TARGET_YEAR, "1T"),)

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=loaded_decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )

        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("1200.00")
        assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("1200.00")
        assert revision.casilla_values["iva.compensacion-aplicada-periodo"] == Decimal("1000.00")
        assert revision.casilla_values["iva.compensacion-pendiente-periodos-posteriores"] == Decimal("200.00")
        assert revision.casilla_values["iva.resultado"] == Decimal("0.00")
        assert revision.casilla_values["iva.compensacion-disponible-fin-periodo"] == Decimal("200.00")
        assert any(
            obs.casilla_id == "iva.compensacion-aplicada-periodo" and obs.legal_refs and obs.source_refs
            for obs in revision.observations
        )


def test_no_seed_no_override_303_calculate_lazily_reconciles_local_zero_and_surfaces_casilla_110(
    tmp_path: Path,
) -> None:
    """#50: a fresh-profile 303 calculate with NO seed and NO override proceeds.

    Before the calculate-side lazy reconcile, an operator who classified rows but
    never seeded the IVA wallet hit a circular dead-end (calculate demanded a
    decision; the seed verb wrote a different record). Now, with no persisted
    decision and no live wallet, calculate auto-derives the local-authority
    decision (zero, since there is no prior local recurrence) and proceeds. The
    carried prior-compensation is surfaced NON-SILENTLY as casilla 110
    (``iva.compensacion-pendiente-periodos-anteriores``) on the result, with its
    registry legal_refs (LIVA art. 99) present — never a silent omission.
    """
    with _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=None,  # no caller decision -> lazy reconcile fires
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )

        # A non-blocking first-period decision was persisted by the lazy reconcile.
        # Read it inside the active session block (the secure store needs it).
        decision = IvaWalletDecisionRepository().load_decision(_TAXPAYER_NIF, _period(_TARGET_YEAR, _TARGET_PERIOD))

    # Calculate proceeded (no ModeloIvaWalletReconciliationBlocked) and the prior
    # compensation is a computed zero, surfaced on the result.
    assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("0.00")
    # Non-silent: casilla 110 is present as an observation carrying its grounding.
    casilla_110_obs = next(
        obs for obs in revision.observations if obs.casilla_id == "iva.compensacion-pendiente-periodos-anteriores"
    )
    assert casilla_110_obs.legal_refs, "casilla 110 must surface its LIVA legal_refs, not a silent zero"
    assert decision is not None
    assert not decision.blocked
    assert decision.selected_amount is not None
    assert Decimal(decision.selected_amount) == Decimal("0.00")
    assert decision.divergence == "first_period_zero"


def test_first_period_zero_decision_feeds_real_modelo_303_engine_and_lifecycle_gate(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=None,
            repository=CalculationObservationRepository(),
            decided_at=_DECIDED_AT,
            treat_absent_recurrence_as_first_period=True,
        )

        assert report.decision.selected_authority == "local_recurrence"
        assert report.decision.selected_amount == Decimal("0")
        assert report.decision.divergence == "first_period_zero"
        assert report.decision.blocked is False
        assert {source.source_kind for source in report.decision.authority_sources} == {"local_recurrence"}

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )

        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("0")
        assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("0.00")
        assert revision.casilla_values["iva.compensacion-aplicada-periodo"] == Decimal("0.00")
        decision = _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert decision is not None
        assert decision.divergence == "first_period_zero"


def test_no_seed_303_calculate_with_prior_filed_history_stays_safely_blocked(
    tmp_path: Path,
) -> None:
    """#50 guardrail 3 + safety: a real prior filed-history balance is NOT auto-carried.

    With a prior 303 filing leaving a 1200.00 carry-forward in the local history
    (and no caller override, no live wallet), the lazy reconcile must NOT silently
    auto-carry that filed-history-derived balance into casilla 110 — the domain
    deliberately blocks filed-history-only evidence pending explicit operator
    confirmation (it may diverge from AEAT's authoritative cartera). Calculate
    therefore refuses, NON-circularly: the operator is directed to confirm/override
    the carried amount, never auto-zeroed and never silently carried. (The genuine
    first-period-zero path above is the case that lazy-reconcile unblocks; this is
    the case it must keep gated.)
    """
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )

    # Blocked on the filed-history-only divergence — never silently carried.
    assert "filed_history_only" in str(exc_info.value) or exc_info.value.translated_message is not None
    # The blocked error MUST carry the divergence/reason context so the localized
    # `iva_wallet_blocked` template renders them instead of leaking `%{divergence}`/`%{reason}`.
    assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_blocked"
    assert exc_info.value.context is not None
    assert exc_info.value.context["divergence"] == "filed_history_only"
    assert exc_info.value.context.get("reason")


def test_modelo_303_lifecycle_gate_requires_persisted_wallet_authority(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(compensation_amount=Decimal("1200.00"))

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)

        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_not_seeded"


def test_modelo_303_lifecycle_gate_rejects_wallet_authority_amount_drift(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("800.00"))
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(compensation_amount=Decimal("1200.00"))

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_blocked"
        assert exc_info.value.context is not None
        assert exc_info.value.context["divergence"] == "authority_amount_mismatch"


def test_modelo_303_lifecycle_gate_accepts_matching_wallet_authority(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("1200.00"))
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(compensation_amount=Decimal("1200.00"))

        decision = _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)

        assert decision is not None
        assert decision.selected_authority == "aeat_wallet"


def test_missing_wallet_filed_history_decision_blocks_real_modelo_303_engine(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=None,
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        assert report.decision.selected_authority == "filed_history"
        assert report.decision.divergence == "filed_history_only"
        assert report.decision.blocked is True
        assert {source.source_kind for source in report.decision.authority_sources} == {
            "local_recurrence",
            "filed_history_observation",
        }

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="filed_history_only"):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={},
                backend_binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )
        assert len(calc_repo.load()) == 0


def test_wallet_only_decision_feeds_real_modelo_303_engine_and_lifecycle_gate(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=CalculationObservationRepository(),
            decided_at=_DECIDED_AT,
        )

        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.divergence == "wallet_only"
        assert report.decision.blocked is False
        assert {source.source_kind for source in report.decision.authority_sources} == {"aeat_wallet"}

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )

        assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("1200.00")
        assert revision.casilla_values["iva.compensacion-aplicada-periodo"] == Decimal("1000.00")
        assert revision.casilla_values["iva.compensacion-pendiente-periodos-posteriores"] == Decimal("200.00")
        assert revision.casilla_values["iva.resultado"] == Decimal("0.00")
        decision = _require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert decision is not None
        assert decision.divergence == "wallet_only"


def test_wallet_only_modelo_303_can_be_locally_filed_with_real_clave_provider_preflight(tmp_path: Path) -> None:
    taxpayer_nif = "X1234567L"
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=taxpayer_nif,
            wallet=_wallet_observation(pending=Decimal("1200.00"), taxpayer_nif=taxpayer_nif),
            repository=CalculationObservationRepository(),
            decided_at=_DECIDED_AT,
        )
        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.divergence == "wallet_only"

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        filing_repo = ModeloRecordCatalogueRepository()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={
                "iva.prorrata-volumen-con-derecho": Decimal("100.00"),
                "iva.prorrata-volumen-total": Decimal("100.00"),
            },
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )
        _seed_clean_cross_period_sources(
            work_unit,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            bucket_event_repository=event_repo,
        )
        verification_report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(taxpayer_nif),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            bucket_event_repository=event_repo,
            clock=datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC),
        )
        assert verification_report.granted_verificado_completo is True

        filing = file_modelo_revision(
            revision.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(taxpayer_nif),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            bucket_event_repository=event_repo,
            settings=Settings(
                aeat_auth_provider=AuthProviderKindSetting.CLAVE_MOVIL,
                aeat_clave_movil_dni_nie=SecretStr(taxpayer_nif),
            ),
            clock=datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC),
        )

        assert filing.status is ModeloRecordStatus.VIGENTE
        assert filing.aeat_accepted is False
        assert filing.external_evidence is None
        stored_revision = calc_repo.load().get(revision.calculation_revision_id)
        assert stored_revision is not None
        assert stored_revision.state is CalculationRevisionState.PRESENTADO
        stored_work_unit = work_repo.load().get(work_unit.work_unit_id)
        assert stored_work_unit is not None
        assert stored_work_unit.filed_calculation_revision_id == revision.calculation_revision_id
        assert (
            filing_repo.load().current_for(
                bucket_id="operator",
                modelo="303",
                filing_year=_TARGET_YEAR,
                period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            )
            == filing
        )


def test_missing_wallet_requires_explicit_override_before_real_modelo_303_engine_prefill(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=None,
            repository=observation_repo,
            override=IvaCompensationOverride(
                amount=Decimal("1200.00"),
                reason="Operator reviewed filed-history evidence while direct wallet/cartera was unavailable.",
                evidence_locator="operator-review:modelo-303-2026-2T-filed-history",
                recorded_at=_DECIDED_AT,
            ),
            decided_at=_DECIDED_AT,
        )

        assert report.decision.selected_authority == "taxpayer_override"
        assert report.decision.divergence == "override"
        assert report.decision.blocked is False
        assert {source.source_kind for source in report.decision.authority_sources} == {
            "local_recurrence",
            "filed_history_observation",
            "taxpayer_override",
        }

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )

        assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("1200.00")


def test_recorded_override_unblocks_carry_and_reduces_final_result(tmp_path: Path) -> None:
    """Recording an override reduces the FINAL Modelo 303 result, with a negative control.

    A/B: with NO override the first-period reconciliation yields casilla 110 = 0 and the
    full devengada as the result; AFTER recording an override of 450 the carry applies
    and the FINAL result (iva.resultado) drops by 450. This asserts the carry's effect
    on the final figure, not just that the override value plumbs through to casilla 110.
    """
    with _secure_backend(tmp_path):
        _store_operator_profile()
        work_repo, calc_repo, event_repo = _work_unit_repositories()
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_TARGET_PERIOD_VALUE,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )

        def _calculate() -> CalculationRevision:
            return calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                backend_binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )

        # NEGATIVE CONTROL: no override recorded -> no prior compensation, full result.
        baseline = _calculate()
        assert baseline.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("0")
        assert baseline.casilla_values["iva.resultado"] == Decimal("1000.00")

        decision = record_iva_compensation_override_for_bucket(
            bucket_id="operator",
            period=_TARGET_PERIOD_VALUE,
            amount=Decimal("450.00"),
            reason="Operator asserts the prior-quarter cuota a compensar.",
            evidence_locator="operator-review:m303-prior-quarter",
        )
        assert decision.selected_authority == "taxpayer_override"
        assert decision.blocked is False

        # AFTER: the recorded override supersedes the first-period decision and the
        # FINAL result drops by the applied compensación.
        applied = _calculate()
        assert applied.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("450.00")
        assert applied.casilla_values["iva.compensacion-aplicada-periodo"] == Decimal("450.00")
        assert applied.casilla_values["iva.resultado"] == Decimal("550.00")


def test_override_refused_when_sealed_303_consumed_the_basis(tmp_path: Path) -> None:
    """Filed-immutability guard: an override is refused when a sealed Modelo 303 at or
    after the period has already consumed that period's compensación basis."""
    with _secure_backend(tmp_path):
        _store_operator_profile()
        work_unit, _ = _work_unit_and_revision_for_wallet_gate(compensation_amount=Decimal("450.00"))
        casilla_values = {"iva.compensacion-pendiente-periodos-anteriores": Decimal("450.00")}
        sealed_revision = CalculationRevision.model_validate(
            {
                "calculation_revision_id": derive_calculation_revision_id(
                    work_unit_id=work_unit.work_unit_id,
                    inputs_snapshot={},
                    binding_overrides={},
                    casilla_values=casilla_values,
                ),
                "work_unit_id": work_unit.work_unit_id,
                "state": CalculationRevisionState.VERIFICADO_COMPLETO,
                "inputs_snapshot": {},
                "binding_overrides": {},
                "casilla_values": casilla_values,
                "created_at": _DECIDED_AT,
                "updated_at": _DECIDED_AT,
                "verified_at": _DECIDED_AT,
                "verified_by": "tester",
            },
        )
        wu_repo = WorkUnitCatalogueRepository()
        wu_repo.save(upsert_work_unit(wu_repo.load(), work_unit))
        rev_repo = CalculationRevisionCatalogueRepository()
        rev_repo.save(upsert_calculation_revision(rev_repo.load(), sealed_revision))

        with pytest.raises(ModeloIvaWalletOverrideSealedError):
            record_iva_compensation_override_for_bucket(
                bucket_id="operator",
                period=_TARGET_PERIOD_VALUE,
                amount=Decimal("450.00"),
                reason="x",
                evidence_locator="y",
            )


def test_override_refused_when_fresh_wallet_decision_exists(tmp_path: Path) -> None:
    """No override of fresh AEAT evidence: an override is refused when a non-blocked
    aeat_wallet decision already resolves the period."""
    with _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("450.00"), blocked=False)

        with pytest.raises(ModeloIvaWalletOverrideFreshWalletError):
            record_iva_compensation_override_for_bucket(
                bucket_id="operator",
                period=_TARGET_PERIOD_VALUE,
                amount=Decimal("999.00"),
                reason="x",
                evidence_locator="y",
            )


def test_unpersisted_wallet_decision_cannot_feed_modelo_303_engine(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
            persist=False,
        )
        assert (
            IvaWalletDecisionRepository().load_decision(
                _TAXPAYER_NIF,
                _period(_TARGET_YEAR, _TARGET_PERIOD),
            )
            is None
        )

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )
        # The error must route through the seed-verb locale key and name the
        # iva-wallet seed command so the operator knows the unblock path.
        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_not_seeded"
        assert exc_info.value.suggestion is not None
        assert "iva-wallet seed" in exc_info.value.suggestion
        assert len(calc_repo.load()) == 0


def test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_year_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(
            observation_repo,
            amount=Decimal("450.00"),
            filing_year=2025,
            period="4T",
        )
        target_year = 2026
        target_period = "1T"
        snapshot = resources().modelos.authority.snapshot("303", filing_year=target_year, period=target_period)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(
                pending=Decimal("450.00"),
                target_year=target_year,
                target_period=_period(target_year, target_period),
                generation_year=2025,
                generation_period="4T",
            ),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.local_recurrence_amount == Decimal("450.00")
        assert report.prefill_report.prefilled[0].source_filing_year == 2025
        assert report.prefill_report.prefilled[0].source_periods == ("4T",)

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=target_year,
            period=_period(target_year, target_period),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=report.decision,
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )

        assert revision.casilla_values["iva.compensacion-pendiente-periodos-anteriores"] == Decimal("450.00")
        assert revision.casilla_values["iva.compensacion-aplicada-periodo"] == Decimal("450.00")
        assert revision.casilla_values["iva.resultado"] == Decimal("550.00")
        assert revision.casilla_values["iva.compensacion-disponible-fin-periodo"] == Decimal("0.00")


def test_wallet_divergence_blocks_real_modelo_303_engine_before_persisting_revision(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("800.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )
        assert report.decision.blocked is True
        assert report.decision.divergence == "wallet_higher"

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=report.decision,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )
        assert len(calc_repo.load()) == 0


def _assert_blocked_wallet_decision_refuses_real_modelo_303_calculation(
    *,
    snapshot: RegistrySnapshot,
    decision: IvaCompensationReconciliationDecision,
    expected_divergence: str,
) -> None:
    work_repo, calc_repo, event_repo = _work_unit_repositories()
    work_unit = create_work_unit(
        bucket_id="operator",
        modelo="303",
        filing_year=snapshot.filing_year,
        period=_period(snapshot.filing_year, snapshot.period),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        clock=_DECIDED_AT,
    )
    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match=expected_divergence):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=decision,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )
    assert len(calc_repo.load()) == 0


def test_wallet_lower_divergence_blocks_real_modelo_303_engine_before_persisting_revision(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("800.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )

        assert report.decision.divergence == "wallet_lower"
        assert report.decision.blocked is True
        _assert_blocked_wallet_decision_refuses_real_modelo_303_calculation(
            snapshot=snapshot,
            decision=report.decision,
            expected_divergence="wallet_lower",
        )


def test_stale_wallet_divergence_blocks_real_modelo_303_engine_before_persisting_revision(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("800.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(
                pending=Decimal("1200.00"),
                captured_at=_DECIDED_AT - timedelta(days=40),
            ),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
            max_wallet_age_days=31,
        )

        assert report.decision.divergence == "wallet_stale"
        assert report.decision.stale_wallet is True
        assert report.decision.blocked is True
        _assert_blocked_wallet_decision_refuses_real_modelo_303_calculation(
            snapshot=snapshot,
            decision=report.decision,
            expected_divergence="wallet_stale",
        )


def test_missing_remote_and_local_compensation_blocks_real_modelo_303_engine(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=None,
            repository=CalculationObservationRepository(),
            decided_at=_DECIDED_AT,
        )

        assert report.decision.divergence == "missing"
        assert report.decision.selected_authority == "missing"
        assert report.decision.blocked is True
        _assert_blocked_wallet_decision_refuses_real_modelo_303_calculation(
            snapshot=snapshot,
            decision=report.decision,
            expected_divergence="missing",
        )


def test_persisted_blocked_wallet_decision_is_replayed_by_modelo_303_calculation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("800.00"))
        snapshot = resources().modelos.authority.snapshot("303", filing_year=_TARGET_YEAR, period=_TARGET_PERIOD)
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=_TAXPAYER_NIF,
            wallet=_wallet_observation(pending=Decimal("1200.00")),
            repository=observation_repo,
            decided_at=_DECIDED_AT,
        )
        assert report.decision.blocked is True

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_DECIDED_AT,
        )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )
        assert len(calc_repo.load()) == 0
