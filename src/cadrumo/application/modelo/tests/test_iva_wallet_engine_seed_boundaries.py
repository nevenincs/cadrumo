"""Seed and caller-binding boundary coverage for Modelo 303 IVA wallet decisions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.iva_compensation.reconciliation import IvaCompensationDecisionReason
from ....tests import general_m303_filing_evidence
from ...calculations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    reconcile_modelo_303_iva_compensation,
    seed_iva_compensation_period,
)
from .._calculation_actions import calculate_modelo_revision
from .._iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from ._iva_wallet_engine_support import (
    _DECIDED_AT,
    _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    _TARGET_PERIOD,
    _TARGET_YEAR,
    _TAXPAYER_NIF,
    _filing_instance_evidence,
    _modelo_303_engine_inputs,
    _period,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _store_operator_profile_with_tax_id,
    _work_unit_repositories_with_modelo_303_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_no_seed_no_override_303_calculate_blocks_missing_in_scope_prior_history(
    tmp_path: Path,
) -> None:
    """An in-scope prior 303 period must not become a first-period zero from blank local history."""
    with _secure_backend(tmp_path):
        _store_operator_profile()
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
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-seed-boundaries"
                ),
            )
        assert not hasattr(exc_info.value, "suggestion")
        assert exc_info.value.precondition_failure.scenario_id == "modelo.work.calculate.iva_wallet.no_usable_authority"


def test_in_scope_period_rejects_supplied_first_period_zero_decision(tmp_path: Path) -> None:
    taxpayer_nif = "12345678Z"
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = _snapshot_303()
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=taxpayer_nif,
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

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)

        for supplied_decision in (None, report.decision):
            with pytest.raises(ModeloIvaWalletReconciliationBlocked):
                calculate_modelo_revision(
                    work_unit.work_unit_id,
                    actor="operator",
                    casilla_inputs={},
                    binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                    backend_binding_values=_modelo_303_engine_inputs(),
                    iva_compensation_decision=supplied_decision,
                    filing_period_date=date(2026, 6, 30),
                    work_unit_repository=work_repo,
                    calculation_repository=calc_repo,
                    bucket_event_repository=event_repo,
                    clock=_DECIDED_AT,
                    filing_instance_evidence=general_m303_filing_evidence(
                        work_unit.period, reference="test:iva-wallet-engine-seed-boundaries"
                    ),
                )


def test_persisted_first_period_zero_refreshes_when_later_seeded_history_arrives(tmp_path: Path) -> None:
    """A later seed must replace a sticky first-period-zero wallet decision."""
    taxpayer_nif = "12345678Z"
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = _snapshot_303(period="1T")
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)

        first_revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
            backend_binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=None,
            filing_instance_evidence=_filing_instance_evidence(work_unit.period),
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )
        assert first_revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0")
        first_decision = IvaWalletDecisionRepository().load_decision(
            taxpayer_nif,
            _period(_TARGET_YEAR, "1T"),
        )
        assert first_decision is not None
        assert first_decision.divergence == "first_period_zero"
        assert first_decision.blocked is False
        assert (
            first_decision.reason_identity
            is IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED
        )

        seed_iva_compensation_period(
            taxpayer_nif=taxpayer_nif,
            period=_period(2025, "4T"),
            amount=Decimal("450.00"),
            seeded_at=_DECIDED_AT,
        )

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                backend_binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_instance_evidence=_filing_instance_evidence(work_unit.period),
                filing_period_date=date(2026, 3, 31),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
            )

        assert exc_info.value.context is not None
        assert exc_info.value.context["divergence"] == "filed_history_only"
        refreshed = IvaWalletDecisionRepository().load_decision(
            taxpayer_nif,
            _period(_TARGET_YEAR, "1T"),
        )
        assert refreshed is not None
        assert refreshed.divergence == "filed_history_only"
        assert refreshed.local_recurrence_amount == Decimal("450.00")
        assert refreshed.blocked is True
        assert any(source.source_periods == (_period(2025, "4T"),) for source in refreshed.authority_sources)


def test_explicit_zero_binding_matches_prior_zero_seed_and_feeds_real_modelo_303_engine(tmp_path: Path) -> None:
    """A caller explicit zero is allowed only after the local zero seed reconciles it."""
    with _secure_backend(tmp_path):
        _store_operator_profile()
        seed_iva_compensation_period(
            taxpayer_nif=_TAXPAYER_NIF,
            period=_period(_TARGET_YEAR, "1T"),
            amount=Decimal("0"),
            seeded_at=_DECIDED_AT,
        )
        snapshot = _snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)

        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values={
                **_modelo_303_engine_inputs(),
                "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
            },
            iva_compensation_decision=None,
            filing_period_date=date(2026, 6, 30),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-seed-boundaries"
            ),
        )

        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("0")
        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0.00")
        decision = IvaWalletDecisionRepository().load_decision(
            _TAXPAYER_NIF,
            _period(_TARGET_YEAR, _TARGET_PERIOD),
        )
        assert decision is not None
        assert decision.selected_amount == Decimal("0")
        assert decision.local_recurrence_amount == Decimal("0")
        assert decision.blocked is False
        assert decision.reason_identity is IvaCompensationDecisionReason.CALLER_ZERO_MATCHES_LOCAL_AUTHORITY
        assert any(
            source.amount == Decimal("0") and source.source_periods == (_period(_TARGET_YEAR, "1T"),)
            for source in decision.authority_sources
        )


def test_explicit_nonzero_binding_conflicts_with_prior_zero_seed(tmp_path: Path) -> None:
    """A caller value that differs from the reconciled zero seed is refused."""
    with _secure_backend(tmp_path):
        _store_operator_profile()
        seed_iva_compensation_period(
            taxpayer_nif=_TAXPAYER_NIF,
            period=_period(_TARGET_YEAR, "1T"),
            amount=Decimal("0"),
            seeded_at=_DECIDED_AT,
        )
        snapshot = _snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={
                    **_modelo_303_engine_inputs(),
                    "modelo-303-compensacion-pendiente-anteriores": Decimal("1.00"),
                },
                iva_compensation_decision=None,
                filing_period_date=date(2026, 6, 30),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-seed-boundaries"
                ),
            )

        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_caller_binding_conflict"
        assert len(calc_repo.load()) == 0
