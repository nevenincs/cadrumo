"""Lifecycle-gate coverage for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....tests import general_m303_filing_evidence
from ....tests.env_scope import ready_clave_settings
from ...calculations import (
    CalculationObservationRepository,
    reconcile_modelo_303_iva_compensation,
)
from .._calculation_actions import calculate_modelo_revision
from .._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
    require_persisted_iva_compensation_decision_matches_revision,
)
from .._verification_actions import verify_modelo_revision
from ._iva_wallet_engine_support import (
    _DECIDED_AT,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _M303_RESULTADO_CASILLA,
    _TAXPAYER_NIF,
    _modelo_303_engine_inputs,
    _save_wallet_gate_decision,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile,
    _store_operator_profile_with_tax_id,
    _wallet_observation,
    _work_unit_and_revision_for_wallet_gate,
    _work_unit_repositories_with_modelo_303_work_unit,
    _workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_grounded_first_period_zero_decision_feeds_real_modelo_303_engine_and_lifecycle_gate(tmp_path: Path) -> None:
    taxpayer_nif = "12345678Z"
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = _snapshot_303(period="1T")
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
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-lifecycle-gate"
            ),
        )
        assert Decimal(revision.binding_overrides["modelo-303-compensacion-pendiente-anteriores"]) == Decimal("0")
        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("0.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("0.00")
        decision = require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert decision is not None
        assert decision.divergence == "first_period_zero"
        verification = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(taxpayer_nif).model_copy(
                update={"activity_start_date": date(2026, 1, 1)},
            ),
            settings=ready_clave_settings(taxpayer_nif),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=ModeloRecordCatalogueRepository(),
            bucket_event_repository=event_repo,
            clock=_DECIDED_AT,
        )
        assert verification.granted_verificado_completo is True
        assert not any(finding.kind.value == "cross_period_dependency_unclean" for finding in verification.findings)


def test_modelo_303_lifecycle_gate_requires_persisted_wallet_authority(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(compensation_amount=Decimal("1200.00"))

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)

        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_not_seeded"


def test_modelo_303_lifecycle_gate_rejects_wallet_authority_amount_drift(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("800.00"))
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(compensation_amount=Decimal("1200.00"))

        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_blocked"
        assert exc_info.value.context is not None
        assert exc_info.value.context["divergence"] == "authority_amount_mismatch"


def test_modelo_303_lifecycle_gate_accepts_matching_wallet_authority(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        _save_wallet_gate_decision(amount=Decimal("1200.00"))
        work_unit, revision = _work_unit_and_revision_for_wallet_gate(compensation_amount=Decimal("1200.00"))

        decision = require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)

        assert decision is not None
        assert decision.selected_authority == "aeat_wallet"


def test_wallet_only_decision_feeds_real_modelo_303_engine_and_lifecycle_gate(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        _store_operator_profile()
        snapshot = _snapshot_303()
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

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
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
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-lifecycle-gate"
            ),
        )

        assert revision.casilla_values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA] == Decimal("1200.00")
        assert revision.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] == Decimal("1000.00")
        assert revision.casilla_values[_M303_POSTERIOR_CASILLA] == Decimal("200.00")
        assert revision.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("0.00")
        decision = require_persisted_iva_compensation_decision_matches_revision(work_unit, revision)
        assert decision is not None
        assert decision.divergence == "wallet_only"
