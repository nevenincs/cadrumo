"""Backend integration for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ...calculations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    reconcile_modelo_303_iva_compensation,
)
from .. import (
    ModeloIvaWalletReconciliationBlocked,
    calculate_modelo_revision,
)
from ._iva_wallet_engine_support import (
    _DECIDED_AT,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    _M303_DISPONIBLE_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _M303_RESULTADO_CASILLA,
    _TARGET_PERIOD,
    _TARGET_YEAR,
    _TAXPAYER_NIF,
    _create_modelo_303_work_unit,
    _modelo_303_engine_inputs,
    _period,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _store_operator_profile_with_tax_id,
    _store_prior_303_compensation,
    _wallet_observation,
    _work_unit_repositories,
    _work_unit_repositories_with_modelo_303_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_wallet_capture_decision_feeds_real_modelo_303_engine_from_prior_filing_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = _snapshot_303()
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

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
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
        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("1200.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("1000.00")
        assert revision.casilla_values[_M303_POSTERIOR_CASILLA] == Decimal("200.00")
        assert revision.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("0.00")
        assert revision.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("200.00")
        assert any(
            obs.casilla_id == _M303_COMPENSACION_APLICADA_CASILLA and obs.legal_refs and obs.source_refs
            for obs in revision.observations
        )


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
        snapshot = _snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
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


def test_missing_wallet_filed_history_decision_blocks_real_modelo_303_engine(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        observation_repo = CalculationObservationRepository()
        _store_prior_303_compensation(observation_repo, amount=Decimal("1200.00"))
        snapshot = _snapshot_303()
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

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="filed_history_only") as exc_info:
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
        assert exc_info.value.suggestion is not None
        assert "iva-wallet override" in exc_info.value.suggestion
        assert "--amount AMOUNT" in exc_info.value.suggestion
        assert "iva-wallet seed" not in exc_info.value.suggestion
        assert len(calc_repo.load()) == 0


def test_prior_positive_payable_calculated_303_unblocks_next_period_zero_without_override(tmp_path: Path) -> None:
    taxpayer_nif = "X1234567L"
    decided_1t_at = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        work_repo, calc_repo, event_repo = _work_unit_repositories()
        snapshot_1t = _snapshot_303(period="1T")
        work_unit_1t = _create_modelo_303_work_unit(
            snapshot_1t,
            work_unit_repository=work_repo,
            clock=decided_1t_at,
        )
        revision_1t = calculate_modelo_revision(
            work_unit_1t.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values={
                **_modelo_303_engine_inputs(),
                "modelo-303-iva-repercutido-general-cuota": Decimal("84.00"),
            },
            iva_compensation_decision=None,
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=decided_1t_at,
        )
        assert revision_1t.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("84.00")
        assert revision_1t.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("0.00")

        snapshot_2t = _snapshot_303(period="2T")
        work_unit_2t = _create_modelo_303_work_unit(snapshot_2t, work_unit_repository=work_repo)
        revision_2t = calculate_modelo_revision(
            work_unit_2t.work_unit_id,
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

        assert revision_2t.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")
        decision = IvaWalletDecisionRepository().load_decision(
            taxpayer_nif,
            _period(_TARGET_YEAR, "2T"),
        )
        assert decision is not None
        assert decision.divergence == "local_recurrence_zero"
        assert decision.selected_amount == Decimal("0")
        assert decision.local_recurrence_amount == Decimal("0")
        assert any(
            source.source_locator == f"calculation_revision:{revision_1t.calculation_revision_id}"
            and source.source_periods == (_period(_TARGET_YEAR, "1T"),)
            for source in decision.authority_sources
        )


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
        snapshot = _snapshot_303(filing_year=target_year, period=target_period)
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

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
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

        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("450.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("450.00")
        assert revision.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("550.00")
        assert revision.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("0.00")
