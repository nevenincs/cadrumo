"""Seeded Modelo 193 bucket, capital-income capture and calculation shared by the settled-row gate tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    CAPITAL_YEAR,
    MANUAL_HOLDER_NIF,
    capital_payment,
    capital_pending_payment,
    capital_request,
    manual_capital_row,
    seed_manual_percepcion_window,
    withholding_producer,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import build_ledger_payment_withholding_capture
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
)
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import (
    AggregationCaptureKind,
    BindingSourceKind,
    RetencionScheme,
)
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
)
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

from ...adapters.persistence.profile.tests.retencion_observation_authoring import replace_retencion_observations

BUCKET_ID = "00000000-0000-4000-8000-000000000193"
T0 = datetime(CAPITAL_YEAR + 1, 2, 1, 9, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class M193Bucket:
    objects: SecureObjectRepository
    filing_year: int
    work_unit_id: str


def seed_ready_m193_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="capital income payer"),
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
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
            ),
            created_at=T0,
            updated_at=T0,
            context=profile_creation_context_for_test(),
        ),
    )


@contextmanager
def m193_bucket(tmp_path: Path, *, filing_year: int, operation: PinnedAuthorityOperation) -> Generator[M193Bucket]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID, label="M193 settled row") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_ready_m193_profile(objects)
        snapshot = operation.snapshot("193", filing_year=filing_year, period="0A")
        work_unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo="193",
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=T0,
            operation=operation,
        )
        yield M193Bucket(objects=objects, filing_year=filing_year, work_unit_id=work_unit.work_unit_id)


def capture_coupon_collected_next_year(objects: SecureObjectRepository) -> None:
    """Capture a key B coupon exigible on 15 December of CAPITAL_YEAR and collected on 20 January of the next year."""
    paid_on = date(CAPITAL_YEAR + 1, 1, 20)
    transaction = capital_payment(provider_id=f"coupon-{CAPITAL_YEAR}-12", booked_date=paid_on)
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="c" * 64,
        request=capital_request(
            transaction,
            payment_event_id=f"coupon-payment-{CAPITAL_YEAR + 1}-01",
            exigibility_occurred_on=date(CAPITAL_YEAR, 12, 15),
            modelo_193_pending_payment=capital_pending_payment(transaction, transaction_date=paid_on),
        ),
        applicable_year=CAPITAL_YEAR,
        cadence=quarterly_filer_cadence(CAPITAL_YEAR),
    )
    assert (
        withholding_producer(objects).capture(capture.command, cadence=quarterly_filer_cadence_for(capture.command))
        is not None
    )


def persist_manual_row(objects: SecureObjectRepository, *, filing_year: int) -> None:
    """Declare one ordinary key B row by hand for a second, synthetic holder."""
    seed_manual_percepcion_window(
        objects,
        filing_year=filing_year,
        observations=[manual_capital_row(filing_year=filing_year)],
    )


def seed_declarant_retenciones(objects: SecureObjectRepository, *, filing_year: int) -> None:
    """Store the retenciones the 193 declarant totals read from its own annual window."""
    replace_retencion_observations(
        RetencionObservationRepositoryAdapter(objects=objects),
        modelo="193",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id=f"declarant-{filing_year}",
                perceptor_nif=MANUAL_HOLDER_NIF,
                perceptor_name="Perceptor Manual Sintetico",
                scheme=RetencionScheme("intereses"),
                taxable_base=Decimal("1000.00"),
                retencion_amount=Decimal("190.00"),
                accrued_on=f"{filing_year}-05-05",
            )
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


def calculate_m193_revision(bucket: M193Bucket) -> CalculationRevision:
    seed_declarant_retenciones(bucket.objects, filing_year=bucket.filing_year)
    with calculation_ports_for_test(
        bucket_id=BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=bucket.objects),
        invoice_repository=InvoiceCatalogueRepository(objects=bucket.objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=bucket.objects),
        work_unit_repository=WorkUnitCatalogueRepository(objects=bucket.objects),
    ) as ports:
        result = calculate_modelo_work_revision(
            work_unit_id=bucket.work_unit_id,
            actor="test",
            inputs=WorkCalculateInputBundle.build(
                casilla_inputs={},
                binding_values={},
                enum_binding_values={},
                relation_values={},
                detail_rows=(),
                borrador_snapshot_id=None,
            ),
            ports=ports,
        )
    return stored_revision(bucket, result.revision.calculation_revision_id)


def stored_revision(bucket: M193Bucket, revision_id: CalculationRevisionId) -> CalculationRevision:
    revision = (
        CalculationRevisionCatalogueRepository(bucket_id=BUCKET_ID, objects=bucket.objects).load().get(revision_id)
    )
    assert revision is not None
    return revision


def workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime("GENERAL"),
        activity_start_date=date(2020, 1, 1),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
