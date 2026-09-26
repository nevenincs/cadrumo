"""A settled prior-accrual Modelo 193 row's unresolved amount authority reaches the calculate result.

A key B coupon exigible in 2025 and collected in January 2026 is captured from
its ledger payment into the Modelo 123 window. The live Modelo 193 2026
calculate reads it through the withholding source as a settled prior-accrual
row, and the advisory that its base and withholding amounts rest on no settled
authority must arrive in the result's source diagnostics beside the values.
Real encrypted store, real producer, real source mesh and the published
authority; the seeded profile is an ordinary filer whose Modelo 123 schedule is
quarterly.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    capital_payment,
    capital_pending_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_modelo_ready_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import build_ledger_payment_withholding_capture
from cadrumo.application.aggregation.source_mesh import CallerOverrideDisposition, precedence_ladder_sources
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
)
from cadrumo.application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "19319319-3193-4193-8193-193193193193"
_T0 = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 9, 24, 11, 0, tzinfo=UTC)
_FILING_YEAR = 2026
_UNRESOLVED_AMOUNTS = "m193_settled_row_amounts_unresolved_authority"


def _caller_zero_bindings(operation: PinnedAuthorityOperation) -> dict[BindingId, Decimal]:
    """Zero the bindings neither the mesh resolves nor the aggregation locks."""
    snapshot = operation.snapshot("193", filing_year=_FILING_YEAR, period="0A")
    resolved = {kind.value for kind in precedence_ladder_sources(CallerOverrideDisposition.LOCK)} | {
        BindingSourceKind.WITHHOLDING.value,
        "profile",
        "relation_prefill",
    }
    return {binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source not in resolved}


def test_the_settled_row_advisory_reaches_the_modelo_193_2026_calculate_result(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The calculate result carries exactly one unresolved-amount advisory, naming the row's years and fields."""
    paid_on = date(2026, 1, 20)
    transaction = capital_payment(provider_id="coupon-2025-12", booked_date=paid_on)
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="c" * 64,
        request=capital_request(
            transaction,
            payment_event_id="coupon-payment-2026-01",
            exigibility_occurred_on=date(2025, 12, 15),
            modelo_193_pending_payment=capital_pending_payment(transaction, transaction_date=paid_on),
        ),
        applicable_year=2025,
        cadence=quarterly_filer_cadence(2025),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=datetime.now(UTC))
        assert (
            withholding_producer(objects).capture(capture.command, cadence=quarterly_filer_cadence_for(capture.command))
            is not None
        )
        work_unit_repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        snapshot = authority_operation.snapshot("193", filing_year=_FILING_YEAR, period="0A")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="193",
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=work_unit_repository,
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=_T0,
            operation=authority_operation,
        )
        with calculation_ports_for_test(
            bucket_id=_BUCKET_ID,
            calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
            invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            work_unit_repository=work_unit_repository,
        ) as ports:
            result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                binding_values=_caller_zero_bindings(authority_operation),
                ports=ports,
                clock=_T1,
            )

    advisories = [diagnostic for diagnostic in result.source_diagnostics if diagnostic.reason == _UNRESOLVED_AMOUNTS]
    assert len(advisories) == 1
    (advisory,) = advisories
    assert advisory.binding_source is BindingSourceKind.WITHHOLDING
    assert "Modelo 193 2026" in advisory.message
    assert "accrued in 2025" in advisory.message
    assert "(base_retenciones)" in advisory.message
    assert "(retencion_practicada)" in advisory.message
    assert advisory.source_ref is not None
    assert advisory.source_ref in {ref.source_ref for ref in result.revision.source_provenance}
