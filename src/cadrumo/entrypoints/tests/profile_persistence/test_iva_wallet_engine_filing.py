"""Filing-flow coverage for AEAT IVA wallet decisions in Modelo 303."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.cross_period_seeding import seed_clean_cross_period_sources
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.calculations.binding_prefill import BindingPrefillReport
from cadrumo.application.calculations.iva_wallet_balance import query_iva_wallet_balance
from cadrumo.application.calculations.iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from cadrumo.application.modelo.verification_actions import verify_modelo_revision
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import Settings
from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import IvaSettlementRefundState, ModeloRecordStatus
from cadrumo.entrypoints.adapter_composition import build_filing_action_ports
from cadrumo.entrypoints.tests.profile_persistence._iva_wallet_engine_support import (
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
    workflow_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_wallet_only_modelo_303_can_be_locally_filed_with_real_clave_provider_preflight(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "X1234567L"
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = _snapshot_303()
        with bundled_indexed_authority().operation() as operation:
            report = reconcile_modelo_303_iva_compensation(
                snapshot,
                taxpayer_nif=taxpayer_nif,
                wallet=_wallet_observation(pending=Decimal("1200.00"), taxpayer_nif=taxpayer_nif),
                repository=CalculationObservationRepository(),
                decision_repository=IvaWalletDecisionRepository(),
                decided_at=_DECIDED_AT,
                local_recurrence=None,
                prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
                operation=operation,
            )
        assert report.decision.selected_authority == "aeat_wallet"
        assert report.decision.divergence == "wallet_only"

        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        filing_repo = ModeloRecordCatalogueRepository()
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_97:
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
                ports=_calculation_ports_97,
                clock=_DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:iva-wallet-engine-filing", operation=operation
                ),
            )
        seed_clean_cross_period_sources(
            work_unit,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            filing_repository=filing_repo,
            bucket_event_repository=event_repo,
            operation=operation,
        )
        with bundled_indexed_authority().operation() as operation:
            verification_report = verify_modelo_revision(
                revision.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=build_test_verification_repository_bundle(),
                actor="operator",
                workflow_profile=workflow_profile(taxpayer_nif),
                settings=Settings(
                    cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                    cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
                ),
                clock=datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
        assert verification_report.granted_verificado_completo is True

        with bundled_indexed_authority().operation() as operation:
            filing = file_modelo_revision(
                revision.calculation_revision_id,
                actor="operator",
                workflow_profile=workflow_profile(taxpayer_nif),
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                ports=build_filing_action_ports(bucket_id=_BUCKET_ID),
                settings=Settings(
                    cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                    cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
                ),
                clock=datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
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


def test_refiling_local_modelo_303_preserves_each_settlement_credit_snapshot_and_lifecycle(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A replacement local 303 keeps the retired filing's settlement evidence.

    Local filing is deliberately not an AEAT confirmation.  Each replacement
    retains the original 303's filing-time credit snapshot for audit, while
    only the current record exposes the replacement snapshot.
    """
    taxpayer_nif = "X1234567L"
    verification_times = (
        datetime(2026, 7, 15, 9, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 16, 9, 0, 0, tzinfo=UTC),
    )
    filing_times = (
        datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 16, 10, 0, 0, tzinfo=UTC),
    )
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot = _snapshot_303()
        work_unit, work_repo, calc_repo, event_repo = _work_unit_repositories_with_modelo_303_work_unit(
            snapshot, operation=operation
        )
        filing_repo = ModeloRecordCatalogueRepository()
        revisions = []
        filings = []

        for index, wallet_pending in enumerate((Decimal("1200.00"), Decimal("600.00"))):
            with bundled_indexed_authority().operation() as operation:
                report = reconcile_modelo_303_iva_compensation(
                    snapshot,
                    taxpayer_nif=taxpayer_nif,
                    wallet=_wallet_observation(pending=wallet_pending, taxpayer_nif=taxpayer_nif),
                    repository=CalculationObservationRepository(),
                    decision_repository=IvaWalletDecisionRepository(),
                    decided_at=_DECIDED_AT,
                    local_recurrence=None,
                    prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
                    operation=operation,
                )
            with calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as calculation_ports:
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
                    ports=calculation_ports,
                    clock=_DECIDED_AT,
                    filing_instance_evidence=general_m303_filing_evidence(
                        work_unit.period,
                        reference="test:iva-wallet-engine-filing-supersession",
                        operation=operation,
                    ),
                )
            if index == 0:
                seed_clean_cross_period_sources(
                    work_unit,
                    work_unit_repository=work_repo,
                    calculation_repository=calc_repo,
                    filing_repository=filing_repo,
                    bucket_event_repository=event_repo,
                    operation=operation,
                )
            with bundled_indexed_authority().operation() as operation:
                verification = verify_modelo_revision(
                    revision.calculation_revision_id,
                    certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                    verification_repositories=build_test_verification_repository_bundle(),
                    actor="operator",
                    workflow_profile=workflow_profile(taxpayer_nif),
                    settings=Settings(
                        cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                        cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
                    ),
                    clock=verification_times[index],
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                    operation=operation,
                )
            assert verification.granted_verificado_completo is True
            with bundled_indexed_authority().operation() as operation:
                filing = file_modelo_revision(
                    revision.calculation_revision_id,
                    actor="operator",
                    workflow_profile=workflow_profile(taxpayer_nif),
                    certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                    ports=build_filing_action_ports(bucket_id=_BUCKET_ID),
                    settings=Settings(
                        cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                        cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
                    ),
                    clock=filing_times[index],
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                    operation=operation,
                )
            revisions.append(revision)
            filings.append(filing)

        first_filing, second_filing = filings
        first_snapshot = first_filing.settlement
        second_snapshot = second_filing.settlement
        assert first_snapshot is not None
        assert second_snapshot is not None
        assert first_filing.aeat_accepted is False
        assert second_filing.aeat_accepted is False

        catalogue = filing_repo.load()
        retired = catalogue.get(first_filing.filing_record_id)
        current = catalogue.current_for(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_TARGET_YEAR,
            period=_period(_TARGET_YEAR, _TARGET_PERIOD),
        )
        assert retired is not None
        assert retired.status is ModeloRecordStatus.SUPERSEDIDO
        assert retired.superseded_at == filing_times[1]
        assert retired.superseded_by_filing_record_id == second_filing.filing_record_id
        assert retired.settlement == first_snapshot
        assert retired.settlement.calculation_revision_id == revisions[0].calculation_revision_id
        assert retired.settlement.credit_snapshot.opening_amount == Decimal("1200.00")
        assert retired.settlement.credit_snapshot.generated_amount == Decimal("0")
        assert retired.settlement.credit_snapshot.applied_amount == Decimal("1000.00")
        assert retired.settlement.credit_snapshot.remaining_amount == Decimal("200.00")

        assert current == second_filing
        assert current.settlement == second_snapshot
        assert current.settlement.calculation_revision_id == revisions[1].calculation_revision_id
        assert current.settlement.credit_snapshot.opening_amount == Decimal("600.00")
        assert current.settlement.credit_snapshot.generated_amount == Decimal("0")
        assert current.settlement.credit_snapshot.applied_amount == Decimal("600.00")
        assert current.settlement.credit_snapshot.remaining_amount == Decimal("0")
        assert current.settlement != retired.settlement
        calculations = calc_repo.load()
        superseded_revision = calculations.get(revisions[0].calculation_revision_id)
        presented_revision = calculations.get(revisions[1].calculation_revision_id)
        assert superseded_revision is not None
        assert superseded_revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO
        assert presented_revision is not None
        assert presented_revision.state is CalculationRevisionState.PRESENTADO


def test_local_filed_303_compensation_updates_wallet_balance_but_next_period_still_requires_authority(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "X1234567L"
    filed_period = _period(_TARGET_YEAR, "1T")
    decided_1t_at = datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC)
    filing_profile = workflow_profile(taxpayer_nif).model_copy(
        update={"activity_start_date": date(2026, 1, 1)},
    )
    with _secure_backend(tmp_path):
        _store_operator_profile_with_tax_id(taxpayer_nif)
        snapshot_1t = _snapshot_303(period="1T")
        with bundled_indexed_authority().operation() as operation:
            report_1t = reconcile_modelo_303_iva_compensation(
                snapshot_1t,
                taxpayer_nif=taxpayer_nif,
                wallet=None,
                repository=CalculationObservationRepository(),
                decision_repository=IvaWalletDecisionRepository(),
                decided_at=decided_1t_at,
                treat_absent_recurrence_as_first_period=True,
                local_recurrence=None,
                prefill_report=BindingPrefillReport(prefilled=(), binding_values={}),
                operation=operation,
            )
        assert report_1t.decision.divergence == "first_period_zero"

        work_repo, calc_repo, event_repo = _work_unit_repositories()
        ModeloRecordCatalogueRepository()
        work_unit_1t = _create_modelo_303_work_unit(
            snapshot_1t,
            work_unit_repository=work_repo,
            clock=decided_1t_at,
            operation=operation,
        )
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_210:
            revision_1t = calculate_modelo_revision(
                work_unit_1t.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values={"modelo-303-profile-state-attribution-ratio": Decimal("100")},
                backend_binding_values=_negative_modelo_303_engine_inputs(),
                iva_compensation_decision=report_1t.decision,
                filing_period_date=date(2026, 3, 31),
                ports=_calculation_ports_210,
                clock=decided_1t_at,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit_1t.period, reference="test:iva-wallet-engine-filing", operation=operation
                ),
            )
        assert revision_1t.casilla_values[_M303_RESULTADO_CASILLA] < Decimal("0")
        generated_carry = revision_1t.casilla_values[_M303_DISPONIBLE_CASILLA]
        assert generated_carry > Decimal("0")

        with bundled_indexed_authority().operation() as operation:
            verification = verify_modelo_revision(
                revision_1t.calculation_revision_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=build_test_verification_repository_bundle(),
                actor="operator",
                workflow_profile=filing_profile,
                settings=Settings(
                    cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                    cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
                ),
                clock=datetime(2026, 4, 15, 9, 0, 0, tzinfo=UTC),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
        assert verification.granted_verificado_completo is True

        with bundled_indexed_authority().operation() as operation:
            filing = file_modelo_revision(
                revision_1t.calculation_revision_id,
                actor="operator",
                workflow_profile=filing_profile,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                ports=build_filing_action_ports(bucket_id=_BUCKET_ID),
                settings=Settings(
                    cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
                    cadrumo_clave_movil_dni_nie=SecretStr(taxpayer_nif),
                ),
                clock=datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
        assert filing.status is ModeloRecordStatus.VIGENTE

        history = IvaCompensationHistoryRepository().load_period(filed_period)
        assert history is not None
        assert history.taxpayer_nif == taxpayer_nif
        assert history.provenance is IvaCompensationStateProvenance.APP_FILING
        assert history.generated_amount == generated_carry
        assert history.available_end_amount == generated_carry
        assert filing.settlement is not None
        assert filing.settlement.declared_liability == Decimal("0")
        assert filing.settlement.credit_snapshot.opening_amount == history.prior_pending_amount
        assert filing.settlement.credit_snapshot.generated_amount == history.generated_amount
        assert filing.settlement.credit_snapshot.applied_amount == history.applied_amount
        assert filing.settlement.credit_snapshot.remaining_amount == history.available_end_amount
        assert filing.settlement.refund_election_intent is False
        assert filing.settlement.refund_state is IvaSettlementRefundState.NOT_REQUESTED
        balance = query_iva_wallet_balance(as_of_year=2026, repository=IvaCompensationHistoryRepository())
        assert balance.total_balance == generated_carry
        assert balance.lot_count == 1

        snapshot_2t = _snapshot_303()
        work_unit_2t = _create_modelo_303_work_unit(snapshot_2t, work_unit_repository=work_repo, operation=operation)
        with (
            pytest.raises(ModeloIvaWalletReconciliationBlocked) as exc_info,
            calculation_ports_for_test(
                bucket_id=_BUCKET_ID,
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
            ) as _calculation_ports_279,
        ):
            calculate_modelo_revision(
                work_unit_2t.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_modelo_303_engine_inputs(),
                iva_compensation_decision=None,
                filing_period_date=date(2026, 6, 30),
                ports=_calculation_ports_279,
                clock=_DECIDED_AT,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit_2t.period, reference="test:iva-wallet-engine-filing", operation=operation
                ),
            )

        assert (
            exc_info.value.translated_message
            == "application.iva_wallet.decision_reason.local_recurrence_requires_override"
        )
        assert exc_info.value.context is not None
        assert exc_info.value.context["divergence"] == "wallet_missing"
