"""Modelo 303 filing-grade gate for deductible IVA evidence gaps."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation._ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
)
from ...calculations import IvaWalletDecisionRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    file_modelo_revision,
    verify_modelo_revision,
)
from .._export import ModeloExportCommand, ModeloExportEvidenceMissingError, export_modelo_revision
from .._filing_actions import ModeloFilingEvidenceMissingError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "30300000-0000-4000-8000-000000000303"
_TAX_ID = "12345678Z"
_YEAR = 2026
_PERIOD = "1T"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CALCULATED_AT = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)
_VERIFIED_AT = datetime(2026, 4, 6, 10, 0, tzinfo=UTC)
_IVA_RATE = Decimal("0.21")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M303 evidence-gate fixture casilla key {value!r} is not a CasillaId") from exc


_DEVENGADA_TOTAL: CasillaId = _casilla_id("iva.cuota-devengada-total")
_DEDUCIBLE_TOTAL: CasillaId = _casilla_id("iva.cuota-deducible-total")
_RESULTADO: CasillaId = _casilla_id("iva.resultado-regimen-general")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _store_profile(objects: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="M303 evidence gate profile",
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Irene"),
                UserProfileFact(path="identity.surnames", value="Evidence"),
                UserProfileFact(path="activities.description", value="consulting"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(_YEAR, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_YEAR, 1, 1),
    )


def _wallet_decision() -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAX_ID,
        target_year=_YEAR,
        target_period=Period.from_year_and_code(_YEAR, _PERIOD),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="M303 evidence gate first-period neutral balance",
        wallet_captured_at=_CALCULATED_AT,
        decided_at=_CALCULATED_AT,
    )


def _raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"M303 evidence gate {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    booked_date = date(_YEAR, 2, 15)
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=booked_date,
                amount=taxable_base + iva_amount,
            ),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _repositories(objects: SecureObjectRepository):
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        ModeloRecordCatalogueRepository(objects=objects),
        VerificationReportCatalogueRepository(objects=objects),
        BucketEventHistoryRepository(objects=objects),
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
    )


def _calculate_irene_revision(
    objects: SecureObjectRepository,
) -> tuple[
    CalculationRevision,
    Transaction,
    Transaction,
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
    TransactionCatalogueRepository,
]:
    _store_profile(objects)
    wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = _repositories(objects)
    sale = _iva_transaction(
        "irene-sale-no-evidence",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
    )
    purchase = _iva_transaction(
        "irene-purchase-no-evidence",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((sale, purchase)))
    snapshot = resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        bucket_event_repository=event_repo,
        clock=_T0,
    )
    decision = _wallet_decision()
    IvaWalletDecisionRepository(objects=objects).save_decision(decision)
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="operator",
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_CALCULATED_AT,
    )
    return revision, sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo


def _persist_legacy_verified_revision(
    revision: CalculationRevision,
    *,
    cr_repo: CalculationRevisionCatalogueRepository,
    tx_repo: TransactionCatalogueRepository,
) -> CalculationRevision:
    catalogue = tx_repo.load()
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=revision.source_transaction_ids,
        catalogue=catalogue,
        captured_at=_VERIFIED_AT,
    )
    evidence = compute_ledger_filing_evidence(
        source_transaction_ids=revision.source_transaction_ids,
        catalogue=catalogue,
        snapshot_fingerprint=snapshot.snapshot_fingerprint,
        captured_at=_VERIFIED_AT,
    )
    legacy = revision.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": _VERIFIED_AT,
            "verified_by": "legacy-operator",
            "ledger_filing_snapshot": snapshot,
            "ledger_filing_evidence": evidence,
            "updated_at": _VERIFIED_AT,
        },
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), legacy))
    return legacy


def test_modelo_303_verify_blocks_deductible_vat_missing_evidence_but_warns_output_gap(
    secure_objects: SecureObjectRepository,
) -> None:
    revision, sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )

    assert revision.casilla_values[_DEVENGADA_TOTAL] == sale.iva_amount
    assert revision.casilla_values[_DEDUCIBLE_TOTAL] == purchase.iva_amount
    assert revision.casilla_values[_RESULTADO] == sale.iva_amount - purchase.iva_amount

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        verification_repository=vr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_VERIFIED_AT,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.BLOCKED
    blocking = [
        finding for finding in report.findings if finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    ]
    warning = [finding for finding in report.findings if finding.severity is ModeloVerificationFindingSeverity.WARNING]
    assert any(
        finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
        and purchase.transaction_id in finding.message
        and "deductible VAT" in finding.message
        for finding in blocking
    )
    assert any(
        finding.kind is ModeloVerificationFindingKind.ADVISORY
        and sale.transaction_id in finding.message
        and "output VAT" in finding.message
        for finding in warning
    )
    stored = cr_repo.load().get(revision.calculation_revision_id)
    assert stored is not None
    assert stored.state is CalculationRevisionState.BORRADOR
    assert stored.ledger_filing_evidence is None


def test_modelo_303_export_refuses_legacy_verified_deductible_vat_missing_evidence(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    revision, _sale, _purchase, _wu_repo, cr_repo, _filing_repo, _vr_repo, _event_repo, tx_repo = (
        _calculate_irene_revision(secure_objects)
    )
    legacy = _persist_legacy_verified_revision(revision, cr_repo=cr_repo, tx_repo=tx_repo)
    output_path = tmp_path / "modelo-303.txt"

    with pytest.raises(ModeloExportEvidenceMissingError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=legacy.calculation_revision_id,
                output_path=output_path,
                actor="operator",
            ),
            workflow_profile=_workflow_profile(),
            calculation_repository=cr_repo,
        )

    assert exc_info.value.context["reason"] == "deductible_vat_evidence_missing"
    assert not output_path.exists()
    assert not output_path.with_name(output_path.name + ".tmp").exists()


def test_modelo_303_internal_file_refuses_legacy_verified_deductible_vat_missing_evidence(
    secure_objects: SecureObjectRepository,
) -> None:
    revision, _sale, _purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )
    legacy = _persist_legacy_verified_revision(revision, cr_repo=cr_repo, tx_repo=tx_repo)

    with pytest.raises(ModeloFilingEvidenceMissingError) as exc_info:
        file_modelo_revision(
            legacy.calculation_revision_id,
            actor="operator",
            workflow_profile=_workflow_profile(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=filing_repo,
            verification_repository=vr_repo,
            bucket_event_repository=event_repo,
            clock=_VERIFIED_AT,
        )

    assert exc_info.value.context["reason"] == "deductible_vat_evidence_missing"
    assert tuple(filing_repo.load().values()) == ()
