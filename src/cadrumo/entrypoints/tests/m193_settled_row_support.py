"""Seeded Modelo 193 bucket, capital-income capture and calculation shared by the settled-row gate tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
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
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import build_ledger_payment_withholding_capture
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
)
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
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
)

from ...adapters.persistence.profile.tests.retencion_observation_authoring import replace_retencion_observations
from .modelo_gate_bucket_support import calculate_without_inputs, seed_ready_capital_payer_profile

BUCKET_ID = "00000000-0000-4000-8000-000000000193"
T0 = datetime(CAPITAL_YEAR + 1, 2, 1, 9, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class M193Bucket:
    objects: SecureObjectRepository
    filing_year: int
    work_unit_id: str


@contextmanager
def m193_bucket(tmp_path: Path, *, filing_year: int, operation: PinnedAuthorityOperation) -> Generator[M193Bucket]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID, label="M193 settled row") as profile:
        objects: SecureObjectRepository = profile.repository
        seed_ready_capital_payer_profile(bucket_id=BUCKET_ID, at=T0)
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
    revision_id = calculate_without_inputs(
        bucket_id=BUCKET_ID, objects=bucket.objects, work_unit_id=bucket.work_unit_id
    )
    return stored_revision(bucket, revision_id)


def stored_revision(bucket: M193Bucket, revision_id: CalculationRevisionId) -> CalculationRevision:
    revision = (
        CalculationRevisionCatalogueRepository(bucket_id=BUCKET_ID, objects=bucket.objects).load().get(revision_id)
    )
    assert revision is not None
    return revision
