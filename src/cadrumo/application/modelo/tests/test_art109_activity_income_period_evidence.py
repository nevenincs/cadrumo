"""Art. 109 current-period activity-income coverage tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.period import Period
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .._art109_activity_income import (
    Art109ActivityIncomeCoverageStatus,
    derive_art109_activity_income_coverage,
)
from ..calculation_actions import calculate_modelo_revision
from ..verification_actions import verify_modelo_revision
from ..work_lifecycle import create_work_unit
from ._verification_substance_support import (
    _CASILLA_01,
    _CASILLA_02,
    _CASILLA_05,
    _CASILLA_06,
    _CASILLA_08,
    _CASILLA_10,
    _CASILLA_16,
    _CASILLA_18,
    _T0,
    _T1,
    _T2,
    _seed_ready_profile,
    _workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "13000000-0000-4000-8000-000000000408"
_Q1_2026 = Period.from_year_and_code(2026, "1T")


def _raw_transaction(provider_id: str, *, value_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=value_date,
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente SA",
        description=f"activity income {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _activity_invoice(
    provider_id: str,
    *,
    value_date: date = date(2026, 2, 15),
    base: Decimal,
    iva: Decimal,
    withholding: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                value_date=value_date,
                amount=base + iva - withholding,
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _gross_only_activity_receipt(provider_id: str, *, amount: Decimal) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, value_date=date(2026, 2, 20), amount=amount),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _positive_threshold_transactions() -> tuple[Transaction, ...]:
    return (
        _activity_invoice(
            "withheld-70",
            base=Decimal("700.00"),
            iva=Decimal("147.00"),
            withholding=Decimal("105.00"),
        ),
        _activity_invoice(
            "not-withheld-30",
            base=Decimal("300.00"),
            iva=Decimal("63.00"),
            withholding=Decimal("0.00"),
        ),
    )


def _below_threshold_transactions() -> tuple[Transaction, ...]:
    return (
        _activity_invoice(
            "withheld-60",
            base=Decimal("600.00"),
            iva=Decimal("126.00"),
            withholding=Decimal("90.00"),
        ),
        _activity_invoice(
            "not-withheld-40",
            base=Decimal("400.00"),
            iva=Decimal("84.00"),
            withholding=Decimal("0.00"),
        ),
    )


def _insufficient_transactions() -> tuple[Transaction, ...]:
    return (
        _activity_invoice(
            "withheld-70",
            base=Decimal("700.00"),
            iva=Decimal("147.00"),
            withholding=Decimal("105.00"),
        ),
        _gross_only_activity_receipt("gross-only-30", amount=Decimal("300.00")),
    )


def test_art109_period_evidence_derives_true_at_70_percent_from_current_period_rows() -> None:
    coverage = derive_art109_activity_income_coverage(
        TransactionCatalogue.from_transactions(_positive_threshold_transactions()),
        period=_Q1_2026,
    )

    assert coverage.status is Art109ActivityIncomeCoverageStatus.PROVEN
    assert coverage.meets_threshold is True
    assert coverage.numerator == Decimal("700.00")
    assert coverage.denominator == Decimal("1000.00")


def test_art109_period_evidence_derives_false_below_70_percent() -> None:
    coverage = derive_art109_activity_income_coverage(
        TransactionCatalogue.from_transactions(_below_threshold_transactions()),
        period=_Q1_2026,
    )

    assert coverage.status is Art109ActivityIncomeCoverageStatus.PROVEN
    assert coverage.meets_threshold is False
    assert coverage.numerator == Decimal("600.00")
    assert coverage.denominator == Decimal("1000.00")


def test_art109_period_evidence_fails_closed_when_gross_only_receipt_cannot_prove_denominator() -> None:
    coverage = derive_art109_activity_income_coverage(
        TransactionCatalogue.from_transactions(_insufficient_transactions()),
        period=_Q1_2026,
    )

    assert coverage.status is Art109ActivityIncomeCoverageStatus.INSUFFICIENT
    assert coverage.meets_threshold is None


@pytest.fixture
def objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_ready_profile(bucket_id=_BUCKET_ID)
        yield profile.repository


def _calculate_m130_draft(objects: SecureObjectRepository) -> CalculationRevision:
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=objects)
    bv_repo = BucketEventHistoryRepository(objects=objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=_Q1_2026,
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            _CASILLA_01: Decimal("1000.00"),
            _CASILLA_02: Decimal("0.00"),
            _CASILLA_05: Decimal("0.00"),
            _CASILLA_06: Decimal("0.00"),
            _CASILLA_08: Decimal("0.00"),
            _CASILLA_10: Decimal("0.00"),
            _CASILLA_16: Decimal("0.00"),
            _CASILLA_18: Decimal("0.00"),
        },
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("20000.00"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    return revision


def _verify_art109_findings(
    objects: SecureObjectRepository,
    *,
    transactions: tuple[Transaction, ...],
    profile_flag: bool,
) -> list[ModeloVerificationFinding]:
    revision = _calculate_m130_draft(objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile().model_copy(
            update={"art109_activity_income_withholding_ge_70pct": profile_flag},
        ),
        work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        verification_repository=VerificationReportCatalogueRepository(objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        transaction_repository=tx_repo,
        clock=_T2,
    )
    return [
        finding
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.ADVISORY and "rd-439-2007:art-109" in finding.legal_refs
    ]


def test_verify_art109_advisory_uses_proven_period_evidence_when_profile_flag_is_false(
    objects: SecureObjectRepository,
) -> None:
    findings = _verify_art109_findings(
        objects,
        transactions=_positive_threshold_transactions(),
        profile_flag=False,
    )

    assert len(findings) == 1


def test_verify_art109_advisory_proven_below_threshold_overrides_declared_profile_flag(
    objects: SecureObjectRepository,
) -> None:
    findings = _verify_art109_findings(
        objects,
        transactions=_below_threshold_transactions(),
        profile_flag=True,
    )

    assert findings == []


def test_verify_art109_advisory_keeps_declared_profile_fact_when_period_evidence_is_insufficient(
    objects: SecureObjectRepository,
) -> None:
    findings = _verify_art109_findings(
        objects,
        transactions=_insufficient_transactions(),
        profile_flag=True,
    )

    assert len(findings) == 1
