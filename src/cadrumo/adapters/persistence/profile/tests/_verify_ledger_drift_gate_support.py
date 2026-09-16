"""Destination-local fixtures for the Modelo 303 ledger-drift tests.

The drift tests exercise the adapter-backed ledger and calculation repositories.
Their profile, transaction, and revision seed belong beside those tests so the
adapter test package does not reach back into an application test module.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.tests.profile_schema_support import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports

BUCKET_ID = "30300000-0000-4000-8000-000000000303"
TAX_ID = "12345678Z"
_YEAR = 2026
_PERIOD = "1T"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CALCULATED_AT = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)
_IVA_RATE = Decimal("0.21")


def workflow_profile() -> TaxpayerProfile:
    """Return the profile facts used by the live verify workflow."""
    return TaxpayerProfile(
        tax_id=TAX_ID,
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        activity_start_date=date(_YEAR, 1, 1),
    )


def _store_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=TAX_ID),
                UserProfileFact(path="identity.name", value="Irene"),
                UserProfileFact(path="identity.surnames", value="Evidence"),
                UserProfileFact(path="activities.description", value="consulting"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(_YEAR, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
    )


def _wallet_decision() -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=TAX_ID,
        target_year=_YEAR,
        target_period=Period.from_year_and_code(_YEAR, _PERIOD),
        target_registry_snapshot_ref=compiled_bundled_authority()
        .snapshot("303", filing_year=_YEAR, period=_PERIOD)
        .snapshot_ref,
        source_registry_snapshot_refs=(),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=None,
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="first_period_zero_aeat_wallet",
        wallet_captured_at=_CALCULATED_AT,
        decided_at=_CALCULATED_AT,
    )


def _raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
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
            "raw": _raw_transaction(provider_id, booked_date=booked_date, amount=taxable_base + iva_amount),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "material_oficina",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "deduction_fact_kind": (
                IvaDeductionFactKind.from_registry("domestic_current")
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _repositories(
    objects: SecureObjectRepository,
) -> tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
    TransactionCatalogueRepository,
]:
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        ModeloRecordCatalogueRepository(objects=objects),
        VerificationReportCatalogueRepository(objects=objects),
        BucketEventHistoryRepository(objects=objects),
        TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects),
    )


def calculate_irene_revision(
    objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
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
    """Seed Irene's deductible-evidence draft and return its repositories."""
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
    snapshot = compiled_bundled_authority().snapshot("303", filing_year=_YEAR, period=_PERIOD)
    work_unit = create_work_unit(
        bucket_id=BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=event_repo),
        clock=_T0,
        operation=operation,
    )
    decision = _wallet_decision()
    from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository

    IvaWalletDecisionRepository(objects=objects).save_decision(decision)
    with bundled_indexed_authority().operation() as operation:
        calculation_ports = build_calculation_action_ports(bucket_id=BUCKET_ID, operation=operation)
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=calculation_ports,
            actor="operator",
            binding_values={
                "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
                "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
            },
            iva_compensation_decision=decision,
            clock=_CALCULATED_AT,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:m303-deductible-evidence-gate", operation=operation
            ),
        ).revision
    return revision, sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo


__all__ = ["BUCKET_ID", "TAX_ID", "calculate_irene_revision", "workflow_profile"]
