"""Modelo 303 IVA wallet export readiness tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports

__all__ = ["isolated_backend"]

from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import (
    _blocked_wallet_decision,
    _filed_history_only_wallet_decision,
    _seed_modelo_303_1t_clean_state,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import (
    export_m303_filing_evidence as _general_m303_filing_evidence,
    export_taxpayer_profile as _profile,
    seed_profile as _seed_profile,
    seed_revision as _seed_revision,
)
from cadrumo.adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.export import ModeloExportCommand, export_modelo_revision
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from cadrumo.application.modelo.verification_actions import verify_modelo_revision
from cadrumo.core.config import Settings
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.entrypoints.adapter_composition import build_filing_action_ports

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _wallet_decision_repository_at(sidecar_db: Path) -> tuple[IvaWalletDecisionRepository, Settings]:
    settings = Settings(cadrumo_database_url=f"sqlite:///{sidecar_db.as_posix()}")
    objects = SecureObjectRepository(
        engine=get_engine(settings),
        namespace_registry=STORAGE_NAMESPACE_REGISTRY,
    )
    return IvaWalletDecisionRepository(objects=objects), settings


def test_export_refuses_modelo_303_when_persisted_wallet_decision_is_blocked(
    isolated_backend: None, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(
            Period.from_year_and_code(2026, "2T"), operation=operation
        ),
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id, taxpayer_tax_id=taxpayer_nif, operation=operation)
    IvaWalletDecisionRepository().save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))

    with (
        pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_local_recurrence_divergence"),
        bundled_indexed_authority().operation() as operation,
    ):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
            export_ports=modelo_export_ports_for_test(bucket_id=bucket_id, taxpayer_tax_id=taxpayer_nif),
            operation=operation,
        )
    assert not (tmp_path / "out.txt").exists()


def test_export_refuses_modelo_303_when_persisted_wallet_decision_is_filed_history_only(
    isolated_backend: None, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "87654321X"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(
            Period.from_year_and_code(2026, "2T"), operation=operation
        ),
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id, taxpayer_tax_id=taxpayer_nif, operation=operation)
    IvaWalletDecisionRepository().save_decision(_filed_history_only_wallet_decision(taxpayer_nif=taxpayer_nif))

    with (
        pytest.raises(ModeloIvaWalletReconciliationBlocked, match="filed_history_requires_override"),
        bundled_indexed_authority().operation() as operation,
    ):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
            export_ports=modelo_export_ports_for_test(bucket_id=bucket_id, taxpayer_tax_id=taxpayer_nif),
            operation=operation,
        )
    assert not (tmp_path / "out.txt").exists()


def test_export_modelo_303_uses_injected_wallet_decision_repository(
    isolated_backend: None, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(
            Period.from_year_and_code(2026, "2T"), operation=operation
        ),
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id, taxpayer_tax_id=taxpayer_nif, operation=operation)
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions-export.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

    try:
        with (
            pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_local_recurrence_divergence"),
            bundled_indexed_authority().operation() as operation,
        ):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=calc_rev_id,
                    output_path=tmp_path / "out.txt",
                    actor="operator",
                ),
                workflow_profile=_profile(),
                export_ports=modelo_export_ports_for_test(
                    bucket_id=bucket_id,
                    taxpayer_tax_id=taxpayer_nif,
                    iva_compensation_decision=decision_repo,
                ),
                operation=operation,
            )
    finally:
        dispose_engine(decision_settings)
    assert not (tmp_path / "out.txt").exists()


def test_verify_modelo_303_surfaces_filed_history_only_wallet_decision_as_blocking_readiness(
    isolated_backend: None, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "87654321X"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.BORRADOR,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(
            Period.from_year_and_code(2026, "2T"), operation=operation
        ),
    )
    IvaWalletDecisionRepository().save_decision(_filed_history_only_wallet_decision(taxpayer_nif=taxpayer_nif))

    with bundled_indexed_authority().operation() as operation:
        report = verify_modelo_revision(
            calc_rev_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            actor="operator",
            workflow_profile=_profile(),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert report.granted_verificado_completo is False
    assert any(
        finding.message_locale_key == "application.modelo.findings.iva_wallet_precondition_failed"
        and str(finding.message_facts.get("scenario_id", "")).endswith("filed_history_requires_override")
        for finding in report.findings
    )
    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR


def test_verify_modelo_303_uses_injected_wallet_decision_repository(
    isolated_backend: None, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.BORRADOR,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(
            Period.from_year_and_code(2026, "2T"), operation=operation
        ),
    )
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

    try:
        with bundled_indexed_authority().operation() as operation:
            report = verify_modelo_revision(
                calc_rev_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                verification_repositories=replace(
                    build_test_verification_repository_bundle(),
                    iva_compensation_decision=decision_repo,
                ),
                actor="operator",
                workflow_profile=_profile(),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )
    finally:
        dispose_engine(decision_settings)

    assert report.granted_verificado_completo is False
    assert any(
        finding.message_locale_key == "application.modelo.findings.iva_wallet_precondition_failed"
        and str(finding.message_facts.get("scenario_id", "")).endswith("wallet_local_recurrence_divergence")
        for finding in report.findings
    )
    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR


def test_file_modelo_303_uses_injected_wallet_decision_repository_before_mutation(
    isolated_backend: None, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    work_unit_id, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
        filing_instance_evidence=_general_m303_filing_evidence(
            Period.from_year_and_code(2026, "2T"), operation=operation
        ),
    )
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions-file.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

    try:
        with (
            pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_local_recurrence_divergence"),
            bundled_indexed_authority().operation() as operation,
        ):
            file_modelo_revision(
                calc_rev_id,
                actor="operator",
                workflow_profile=_profile(),
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                ports=replace(
                    build_filing_action_ports(bucket_id=bucket_id),
                    work_unit_repository=WorkUnitCatalogueRepository(),
                    calculation_repository=CalculationRevisionCatalogueRepository(),
                    filing_repository=ModeloRecordCatalogueRepository(),
                    iva_compensation_decision_repository=decision_repo,
                ),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
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
