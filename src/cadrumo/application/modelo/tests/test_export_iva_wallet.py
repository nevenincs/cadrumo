"""Modelo 303 IVA wallet export readiness tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._export_test_support import isolated_backend

__all__ = ["isolated_backend"]

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage import (
    STORAGE_NAMESPACE_REGISTRY,
    SecureObjectRepository,
    dispose_engine,
    get_engine,
)
from ....core import Period
from ....core.config import Settings
from ....domain.modelos import CalculationRevisionState
from ...calculations import IvaWalletDecisionRepository
from .._export import ModeloExportCommand, export_modelo_revision
from .._filing_actions import file_modelo_revision
from .._iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from .._verification_actions import verify_modelo_revision
from ._export_modelo_303_support import (
    _blocked_wallet_decision,
    _filed_history_only_wallet_decision,
    _seed_modelo_303_1t_clean_state,
)
from ._export_test_support import (
    _general_m303_filing_evidence,
    _profile,
    _seed_profile,
    _seed_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _wallet_decision_repository_at(sidecar_db: Path) -> tuple[IvaWalletDecisionRepository, Settings]:
    settings = Settings(cadrumo_database_url=f"sqlite:///{sidecar_db.as_posix()}")
    objects = SecureObjectRepository(
        engine=get_engine(settings),
        namespace_registry=STORAGE_NAMESPACE_REGISTRY,
    )
    return IvaWalletDecisionRepository(objects=objects), settings


def test_export_refuses_modelo_303_when_persisted_wallet_decision_is_blocked(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(Period.from_year_and_code(2026, "2T")),
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id)
    IvaWalletDecisionRepository().save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))

    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert not (tmp_path / "out.txt").exists()


def test_export_refuses_modelo_303_when_persisted_wallet_decision_is_filed_history_only(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "87654321X"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(Period.from_year_and_code(2026, "2T")),
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id)
    IvaWalletDecisionRepository().save_decision(_filed_history_only_wallet_decision(taxpayer_nif=taxpayer_nif))

    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="filed_history_only"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert not (tmp_path / "out.txt").exists()


def test_export_modelo_303_uses_injected_wallet_decision_repository(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(Period.from_year_and_code(2026, "2T")),
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id)
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions-export.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

    try:
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=calc_rev_id,
                    output_path=tmp_path / "out.txt",
                    actor="operator",
                ),
                workflow_profile=_profile(),
                iva_compensation_decision_repository=decision_repo,
            )
    finally:
        dispose_engine(decision_settings)
    assert not (tmp_path / "out.txt").exists()


def test_verify_modelo_303_surfaces_filed_history_only_wallet_decision_as_blocking_readiness(
    isolated_backend: None,
) -> None:
    taxpayer_nif = "87654321X"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.BORRADOR,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(Period.from_year_and_code(2026, "2T")),
    )
    IvaWalletDecisionRepository().save_decision(_filed_history_only_wallet_decision(taxpayer_nif=taxpayer_nif))

    report = verify_modelo_revision(
        calc_rev_id,
        actor="operator",
        workflow_profile=_profile(),
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        verification_repository=VerificationReportCatalogueRepository(),
    )

    assert report.granted_verificado_completo is False
    assert any(
        finding.message_locale_key == "application.modelo.findings.iva_wallet_reconciliation_blocked"
        and finding.message_facts.get("divergence_code") == "filed_history_only"
        for finding in report.findings
    )
    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR


def test_verify_modelo_303_uses_injected_wallet_decision_repository(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.BORRADOR,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(Period.from_year_and_code(2026, "2T")),
    )
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

    try:
        report = verify_modelo_revision(
            calc_rev_id,
            actor="operator",
            workflow_profile=_profile(),
            work_unit_repository=WorkUnitCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            iva_compensation_decision_repository=decision_repo,
        )
    finally:
        dispose_engine(decision_settings)

    assert report.granted_verificado_completo is False
    assert any(
        finding.message_locale_key == "application.modelo.findings.iva_wallet_reconciliation_blocked"
        and finding.message_facts.get("divergence_code") == "wallet_higher"
        for finding in report.findings
    )
    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR


def test_file_modelo_303_uses_injected_wallet_decision_repository_before_mutation(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    work_unit_id, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(Period.from_year_and_code(2026, "2T")),
    )
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions-file.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

    try:
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            file_modelo_revision(
                calc_rev_id,
                actor="operator",
                workflow_profile=_profile(),
                work_unit_repository=WorkUnitCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                filing_repository=ModeloRecordCatalogueRepository(),
                iva_compensation_decision_repository=decision_repo,
            )
    finally:
        dispose_engine(decision_settings)

    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(bucket_id=bucket_id, modelo="303", filing_year=2026, period=Period.from_year_and_code(2026, "2T"))
        is None
    )
    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    assert work_unit is not None
    assert work_unit.filed_calculation_revision_id is None
