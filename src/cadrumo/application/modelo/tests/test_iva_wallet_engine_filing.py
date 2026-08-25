"""Filing-flow coverage for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....core import AuthProviderKind
from ....core.config import Settings
from ....domain.modelos import CalculationRevisionState, ModeloRecordStatus
from ....tests import general_m303_filing_evidence
from ...calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    query_iva_wallet_balance,
    reconcile_modelo_303_iva_compensation,
)
from .._calculation_actions import calculate_modelo_revision
from .._filing_actions import file_modelo_revision
from .._iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from .._verification_actions import verify_modelo_revision
from ._file_flow_support import seed_clean_cross_period_sources
from ._iva_wallet_engine_support import (
    _BUCKET_ID,
    _DECIDED_AT,
    _M303_DISPONIBLE_CASILLA,
    _M303_RESULTADO_CASILLA,
    _TARGET_PERIOD,
    _TARGET_YEAR,
    _create_modelo_303_work_unit,
    _modelo_303_engine_inputs,
    _negative_modelo_303_engine_inputs,
    _period,
    _secure_backend,
    _snapshot_303,
    _store_operator_profile_with_tax_id,
    _wallet_observation,
    _work_unit_repositories,
    _work_unit_repositories_with_modelo_303_work_unit,
    _workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_wallet_only_modelo_303_can_be_locally_filed_with_real_clave_provider_preflight(tmp_path: Path) -> None:
    taxpayer_nif = "X1234567L"
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = _snapshot_303()
        report = reconcile_modelo_303_iva_compensation(
            snapshot,
            taxpayer_nif=taxpayer_nif,
            wallet=_wallet_observation(pending=Decimal("1200.00"), taxpayer_nif=taxpayer_nif),
            repository=CalculationObservationRepository(),
            decided_at=_DECIDED_AT,
        )
        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.divergence == "wallet_only"

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(snapshot)
        filing_repo = ModeloRecordCatalogueRepository()
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
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:iva-wallet-engine-filing"
            ),
        )
        seed_clean_cross_period_sources(
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
            settings=Settings(
                cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
            ),
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
                cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
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
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=_TARGET_YEAR,
                period=_period(_TARGET_YEAR, _TARGET_PERIOD),
            )
            == filing
        )


def test_local_filed_303_compensation_updates_wallet_balance_but_next_period_still_requires_authority(
    tmp_path: Path,
) -> None:
    taxpayer_nif = "X1234567L"
    filed_period = _period(_TARGET_YEAR, "1T")
    decided_1t_at = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)
    workflow_profile = _workflow_profile(taxpayer_nif).model_copy(
        update={"activity_start_date": date(2026, 1, 1)},
    )
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot_1t = _snapshot_303(period="1T")
        report_1t = reconcile_modelo_303_iva_compensation(
            snapshot_1t,
            taxpayer_nif=taxpayer_nif,
            wallet=None,
            repository=CalculationObservationRepository(),
            decided_at=decided_1t_at,
            treat_absent_recurrence_as_first_period=True,
        )
        assert report_1t.decision.divergence == "first_period_zero"

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        filing_repo = ModeloRecordCatalogueRepository()
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
            backend_binding_values=_negative_modelo_303_engine_inputs(),
            iva_compensation_decision=report_1t.decision,
            filing_period_date=date(2026, 3, 31),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=decided_1t_at,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit_1t.period, reference="test:iva-wallet-engine-filing"
            ),
        )
        assert revision_1t.casilla_values[_M303_RESULTADO_CASILLA] < Decimal("0")
        generated_carry = revision_1t.casilla_values[_M303_DISPONIBLE_CASILLA]
        assert generated_carry > Decimal("0")

        verification = verify_modelo_revision(
            revision_1t.calculation_revision_id,
            actor="operator",
            workflow_profile=workflow_profile,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            bucket_event_repository=event_repo,
            settings=Settings(
                cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
            ),
            clock=datetime(2026, 4, 15, 9, 0, 0, tzinfo=UTC),
        )
        assert verification.granted_verificado_completo is True

        filing = file_modelo_revision(
            revision_1t.calculation_revision_id,
            actor="operator",
            workflow_profile=workflow_profile,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            bucket_event_repository=event_repo,
            settings=Settings(
                cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
            ),
            clock=datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC),
        )
        assert filing.status is ModeloRecordStatus.VIGENTE

        history = IvaCompensationHistoryRepository().load_period(filed_period)
        assert history is not None
        assert history.taxpayer_nif == taxpayer_nif
        assert history.status == "app_filing"
        assert history.generated_amount == generated_carry
        assert history.available_end_amount == generated_carry
        balance = query_iva_wallet_balance(as_of_year=2026)
        assert balance.total_balance == generated_carry
        assert balance.lot_count == 1

        snapshot_2t = _snapshot_303()
        work_unit_2t = _create_modelo_303_work_unit(snapshot_2t, work_unit_repository=work_repo)
        with pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info:
            calculate_modelo_revision(
                work_unit_2t.work_unit_id,
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
                    work_unit_2t.period, reference="test:iva-wallet-engine-filing"
                ),
            )

        assert exc_info.value.translated_message == "application.modelo.errors.iva_wallet_blocked"
        assert exc_info.value.context is not None
        assert exc_info.value.context["divergence"] == "filed_history_only"
