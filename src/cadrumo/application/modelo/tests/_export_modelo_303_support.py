"""Shared Modelo 303 export builders for wallet and output-path tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.runtime import inspect_bucket_storage_runtime
from ....core import Period
from ....core.config import Settings
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva_compensation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_calculation_revision_id,
    derive_filing_record_id,
    upsert_calculation_revision,
    upsert_filing_record,
    upsert_work_unit,
)
from ....tests.env_scope import ready_clave_settings
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    cross_period_dependency_requirements,
)
from .._calculation_actions import calculate_modelo_revision
from .._calculation_helpers import external_filing_observations
from .._verification_actions import verify_modelo_revision
from .._work_lifecycle import create_work_unit
from ._export_test_support import _seed_profile, _synthetic_valid_nif
from .justificante_metadata import persist_justificante_metadata


def _blocked_wallet_decision(*, taxpayer_nif: str, period: str = "2T") -> IvaCompensationReconciliationDecision:
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
        selected_authority="missing",
        selected_amount=None,
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=Decimal("800.00"),
        override_amount=None,
        divergence="wallet_higher",
        blocked=True,
        stale_wallet=False,
        reason_identity="wallet_local_recurrence_divergence",
        wallet_captured_at=now,
        decided_at=now,
    )


def _filed_history_only_wallet_decision(
    *,
    taxpayer_nif: str,
    period: str = "2T",
) -> IvaCompensationReconciliationDecision:
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
        selected_authority="filed_history",
        selected_amount=Decimal("800.00"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("800.00"),
        override_amount=None,
        divergence="filed_history_only",
        blocked=True,
        stale_wallet=False,
        reason_identity="filed_history_requires_override",
        wallet_captured_at=None,
        decided_at=now,
    )


def _wallet_only_decision(*, taxpayer_nif: str, period: str = "2T") -> IvaCompensationReconciliationDecision:
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("1200.00"),
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=None,
        override_amount=None,
        divergence="wallet_only",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_uncrosschecked",
        wallet_captured_at=now,
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("1200.00"),
                source_locator="aeat-wallet:synthetic-modelo-303-export-wallet-only",
                captured_at=now,
            ),
        ),
        decided_at=now,
    )


def _modelo_303_engine_inputs() -> dict[BindingId, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }


#: Manual, formula-operand "resultado" casillas the fichero-BOE completeness
#: manifest requires but that the engine never auto-zero-fills (unlike a
#: ledger-bound or computed casilla, an unset manual input is simply absent
#: from ``casilla_values``, not defaulted). Each feeds the casilla-71
#: ``modelo-303-iva-resultado-final`` formula (or a sibling "resultado"
#: identity) as an optional operand; the standard first-filing case is
#: "[70]=0 and [109]=0" per the registry formula comment, so a synthetic
#: fixture supplies explicit zeros to keep the draft representable-and-
#: rendered per the fichero-BOE parity gate
#: (``modelo-export-mirrors-official-structure``) rather than silently
#: omitting them.
_MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS: dict[str, Decimal] = {
    "18": Decimal("0.00"),
    "58": Decimal("0.00"),
    "68": Decimal("0.00"),
    "70": Decimal("0.00"),
    "76": Decimal("0.00"),
    "77": Decimal("0.00"),
    "109": Decimal("0.00"),
}


def _seed_modelo_303_1t_clean_state(
    *,
    bucket_id: str,
    taxpayer_tax_id: str = "taxpayerdefault",
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
) -> None:
    # The verb this fixture replaced defaulted its own repositories; the direct
    # writes below need concrete ones, so resolve the same bucket-local defaults.
    work_unit_repository = work_unit_repository or WorkUnitCatalogueRepository()
    calculation_repository = calculation_repository or CalculationRevisionCatalogueRepository()
    snapshot = bundled_authority().snapshot("303", filing_year=2026, period="2T")
    source_casilla_ids = sorted(
        {
            casilla_id
            for requirement in cross_period_dependency_requirements(snapshot)
            if requirement.source_modelo == "303"
            and requirement.filing_year == 2026
            and requirement.period == Period.from_year_and_code(2026, "1T")
            for casilla_id in requirement.source_casilla_ids
        },
    )
    assert source_casilla_ids, "Modelo 303 2T fixture must declare a 1T filed-history dependency"
    values = {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casilla_ids)}
    source_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")
    persist_justificante_metadata(
        "JUST30320261T",
        modelo="303",
        filing_year=2026,
        period="1T",
        captured_at=datetime(2026, 5, 21, 11, 0, tzinfo=UTC),
        tax_id=taxpayer_tax_id,
    )
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=source_snapshot.revision.id,
        repository=work_unit_repository,
        bucket_event_repository=bucket_event_repository,
        clock=datetime(2026, 5, 21, 11, 0, tzinfo=UTC),
    )
    # Prior-1T filed history is a PRECONDITION of these wallet-gate tests, not
    # their subject, so the fixture authors the end state directly. Modelo 303
    # external import is refused outright (it cannot infer the typed
    # filing-instance evidence a 303 filing requires), so routing through
    # ``import_external_filing_evidence`` is no longer available here. The
    # persisted shape below mirrors exactly what that verb used to leave behind:
    # a PRESENTADO revision, a VIGENTE ModeloRecord carrying the justificante
    # reference, and the advanced work-unit pointers.
    filed_at = datetime(2026, 5, 21, 11, 1, tzinfo=UTC)
    filed_by = "aeat-import-test"
    # Deliberately None, exactly as the import verb persisted it: absent
    # filing-instance evidence is what marks this revision as EXTERNALLY
    # imported AEAT evidence rather than an app-produced local filing. Supplying
    # real evidence here reclassifies the period as a local recurrence and
    # changes the wallet reconciliation outcome these tests assert.
    prior_filing_instance_evidence = None
    prior_observations = external_filing_observations(
        casilla_values=values,
        snapshot=source_snapshot,
    )
    prior_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=prior_filing_instance_evidence,
        source_provenance=(),
    )
    prior_revision = CalculationRevision(
        calculation_revision_id=prior_revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=values,
        observations=prior_observations,
        created_at=filed_at,
        updated_at=filed_at,
        verified_at=filed_at,
        verified_by=filed_by,
        filed_at=filed_at,
        filed_by=filed_by,
        filing_instance_evidence=prior_filing_instance_evidence,
        source_provenance=(),
    )
    calculation_repository.save(
        upsert_calculation_revision(calculation_repository.load(), prior_revision),
    )
    prior_filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=prior_revision_id,
        filed_by=filed_by,
    )
    filing_repository = ModeloRecordCatalogueRepository()
    filing_repository.save(
        upsert_filing_record(
            filing_repository.load(),
            ModeloRecord(
                filing_record_id=prior_filing_record_id,
                work_unit_id=work_unit.work_unit_id,
                calculation_revision_id=prior_revision_id,
                bucket_id=work_unit.bucket_id,
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period,
                filed_at=filed_at,
                filed_by=filed_by,
                notes=None,
                aeat_accepted=True,
                status=ModeloRecordStatus.VIGENTE,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    reference_id="JUST30320261T",
                    imported_at=filed_at,
                ),
            ),
        ),
    )
    work_unit_repository.save(
        upsert_work_unit(
            work_unit_repository.load(),
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": prior_revision_id,
                    "filed_calculation_revision_id": prior_revision_id,
                    "current_filing_record_id": prior_filing_record_id,
                    "updated_at": filed_at,
                },
            ),
        ),
    )
    CalculationObservationRepository().save(
        CalculationObservationRepository().prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="303",
                filing_year=2026,
                period="1T",
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=2026,
                    period="1T",
                    casilla_values=values,
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=datetime(2026, 5, 21, 11, 2, tzinfo=UTC),
            stamped_revision_id=source_snapshot.revision.id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "EXP-303-2026-1T",
                "aeat_justificante_csv": "JUST30320261T",
                "authenticated_identity": taxpayer_tax_id,
            },
        )
    )


def _wallet_decision_repository_at(sidecar_root: Path) -> tuple[IvaWalletDecisionRepository, Settings]:
    settings = Settings(cadrumo_local_storage_root=sidecar_root, cadrumo_active_profile="operator")
    objects = inspect_bucket_storage_runtime("operator", settings).secure_object_repository()
    return IvaWalletDecisionRepository(objects=objects), settings


def _build_verified_modelo_303_revision(
    *,
    positive_result: bool = False,
    negative_result: bool = False,
    casilla_111: Decimal | None = None,
) -> tuple[
    str,
    str,
    CalculationRevision,
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
]:
    taxpayer_nif = _synthetic_valid_nif(12_345_678)
    bucket_id = _seed_profile(
        tax_id=taxpayer_nif,
        profile_overrides={"identity.surnames": "Test Surnames"},
    )
    snapshot = bundled_authority().snapshot("303", filing_year=2026, period="2T")
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    event_repo = BucketEventHistoryRepository()
    decision = _wallet_only_decision(taxpayer_nif=taxpayer_nif)
    IvaWalletDecisionRepository().save_decision(decision)

    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
    )
    binding_values = _modelo_303_engine_inputs()
    if positive_result:
        # The wallet-only decision applies EUR 1,200 of prior compensation.
        # This deliberately exceeds that carry so public payment-election
        # paths exercise a genuinely positive M303 result.
        binding_values["modelo-303-iva-repercutido-general-cuota"] = Decimal("2400.00")
    if negative_result:
        binding_values["modelo-303-iva-soportado-interiores-cuota"] = Decimal("2000.00")

    casilla_inputs = {
        "iva.prorrata-volumen-con-derecho": Decimal("100.00"),
        "iva.prorrata-volumen-total": Decimal("100.00"),
        **_MODELO_303_MANUAL_RESULTADO_CASILLA_ZEROS,
    }
    if casilla_111 is not None:
        casilla_inputs["111"] = casilla_111

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator",
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        iva_compensation_decision=decision,
        filing_instance_evidence=general_m303_filing_evidence(
            work_unit.period,
            reference="test:export-modelo-303-support",
        ),
        filing_period_date=date(2026, 6, 30),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 1, tzinfo=UTC),
    )
    _seed_modelo_303_1t_clean_state(
        bucket_id=bucket_id,
        taxpayer_tax_id=taxpayer_nif,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
    )
    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=TaxpayerProfile(tax_id=taxpayer_nif, iva_regime=IVARegime.GENERAL),
        settings=ready_clave_settings(taxpayer_nif),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        verification_repository=VerificationReportCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 2, tzinfo=UTC),
    )
    assert report.granted_verificado_completo is True
    verified = calc_repo.load().revisions[revision.calculation_revision_id]
    return taxpayer_nif, bucket_id, verified, work_repo, calc_repo, event_repo
