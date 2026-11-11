"""Destination-local fixtures for the Modelo 303 ledger-drift tests.

The drift tests exercise the adapter-backed ledger and calculation repositories.
Their profile, transaction, and revision seed belong beside those tests so the
adapter test package does not reach back into an application test module.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_persona_profile
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.deadlines.models import TaxpayerProfile
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.work_unit import WorkUnit
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...adapter_composition_work_ports import build_calculation_action_ports
from .ready_profile_taxpayer import persona_tax_id
from .verification_substance_support import workflow_profile as plain_workflow_profile

BUCKET_ID = "30300000-0000-4000-8000-000000000303"
_PERSONA_ID = "autonomo-alta-reciente"
TAX_ID = persona_tax_id("alta.titular")
_YEAR = 2026
_PERIOD = "1T"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CALCULATED_AT = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)
_IVA_RATE = Decimal("0.21")


def workflow_profile() -> TaxpayerProfile:
    """Return the profile facts used by the live verify workflow."""
    return plain_workflow_profile(tax_id=TAX_ID, activity_start_date=date(_YEAR, 1, 1))


def _wallet_decision(period: str = _PERIOD) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=TAX_ID,
        target_year=_YEAR,
        target_period=Period.from_year_and_code(_YEAR, period),
        target_registry_snapshot_ref=published_authority_operation()
        .snapshot("303", filing_year=_YEAR, period=period)
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


def raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
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


def iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
    booked_date: date = date(_YEAR, 2, 15),
    operation_date: date | None = None,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": raw_transaction(provider_id, booked_date=booked_date, amount=taxable_base + iva_amount),
            "direction": direction,
            "operation_date": operation_date,
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


def calculate_irene(
    work_unit: WorkUnit, *, decision: IvaCompensationReconciliationDecision | None = None
) -> BucketAggregationCalculationResult:
    """Run the real bucket calculation, diagnostics included; a later run reads the persisted decision."""
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=BUCKET_ID, operation=operation),
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
        )


def calculate_irene_revision(
    objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
    empty: bool = False,
    held_back_purchase: bool = False,
    rows: tuple[Transaction, ...] | None = None,
    period: str = _PERIOD,
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
    seed_persona_profile(_PERSONA_ID, bucket_id=BUCKET_ID, at=_T0)
    wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo = _repositories(objects)
    sale = iva_transaction(
        "irene-sale-no-evidence",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
    )
    purchase = iva_transaction(
        "irene-purchase-no-evidence",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
    )
    if held_back_purchase:
        purchase = purchase.model_copy(update={"deduction_fact_kind": None, "deduction_provenance": None})
    seeded = rows if rows is not None else (() if empty else (sale, purchase))
    tx_repo.save(TransactionCatalogue.from_transactions(seeded))
    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period=period)
    work_unit = create_work_unit(
        bucket_id=BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=event_repo),
        clock=_T0,
        operation=operation,
    )
    decision = _wallet_decision(period)
    from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository

    IvaWalletDecisionRepository(objects=objects).save_decision(decision)
    revision = calculate_irene(work_unit, decision=decision).revision
    return revision, sale, purchase, wu_repo, cr_repo, filing_repo, vr_repo, event_repo, tx_repo


__all__ = [
    "BUCKET_ID",
    "TAX_ID",
    "calculate_irene",
    "calculate_irene_revision",
    "iva_transaction",
    "raw_transaction",
    "workflow_profile",
]
